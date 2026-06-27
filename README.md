# llm-shadow-proxy

A proxy API that serves customer traffic synchronously using a stable Primary LLM, while safely firing an asynchronous shadow request to a Candidate LLM, comparing both responses via a Judge service, and logging mismatches to MongoDB.

---

## Architecture

```
Client
  │
  ▼
┌─────────────────────────────────────────────────┐
│  proxy  :8000                                   │
│                                                 │
│  1. POST /api/v1/chat                           │
│  2. await primary-llm ──► returns in ~10ms      │
│  3. asyncio.create_task(shadow) ──► fire+forget │
│  4. return primary response to client           │
│                                                 │
│  Shadow task (runs after response sent):        │
│  5. await candidate-llm                         │
│  6. await judge (compare primary vs candidate)  │
│  7. incr Redis counters                         │
│  8. if mismatch: write to MongoDB               │
└─────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
  primary-llm:8001    candidate-llm:8002
  (stable mock)       (~30% divergence)
                             │
                             ▼
                       judge:8003
                       (normalised comparison)
```

### Services

| Service | Port | Purpose |
|---|---|---|
| proxy | 8000 | Entry point — calls primary, fires shadow, exposes metrics |
| primary-llm | 8001 | Mock stable LLM — always returns consistent responses |
| candidate-llm | 8002 | Mock candidate LLM — ~30% divergence, configurable delay |
| judge | 8003 | Normalised comparison — returns match verdict and reason |

### Infrastructure

| Component | Local | Production |
|---|---|---|
| Redis | Docker (redis:7-alpine) | DO Managed Redis |
| MongoDB | Docker (mongo:6-jammy) | DO Managed MongoDB |

---

## How the Background Task is Decoupled

The shadow call uses `asyncio.create_task()` rather than FastAPI's `BackgroundTasks`:

```python
# api/v1/chat.py
asyncio.create_task(
    shadow_service.execute(
        prompt=body.prompt,
        primary_response=primary_response,
        request_id=request_id,
        user_id=body.user_id,
    )
)
# returns immediately — shadow hasn't started yet
return ChatResponse(...)
```

**Why `create_task()` over `BackgroundTasks`:**

- `BackgroundTasks` is tied to the request lifecycle. If the client closes the connection, the framework can cancel it.
- `asyncio.create_task()` transfers ownership to the event loop. The task runs independently of the request context and is never cancelled by a connection close.
- This means candidate latency of 30 seconds does not add one millisecond to the primary response time.

---

## Proof: Candidate Failure Does Not Affect Primary

The integration test `test_primary_returns_under_500ms` sets `RESPONSE_DELAY_SECONDS=2` on the candidate service and asserts the proxy returns in under 500ms:

```python
# tests/integration/test_chat_routes.py
@pytest.mark.asyncio
async def test_primary_returns_under_500ms():
    # candidate has RESPONSE_DELAY_SECONDS=2 in test env
    async with httpx.AsyncClient() as client:
        start = time.time()
        response = await client.post(
            f"{BASE_URL}/api/v1/chat",
            json={"prompt": "What is the capital of France?"},
        )
        elapsed = time.time() - start

    assert response.status_code == 200
    assert elapsed < 0.5  # primary returns before candidate even starts
```

The shadow service also swallows all exceptions silently and increments `metrics:shadow_errors` — a candidate crash never propagates to the primary path.

---

## Running Locally

### Prerequisites

- Docker + Docker Compose
- Make

### Start all services

```bash
make dev
```

This builds all four service images and starts MongoDB, Redis, primary-llm, candidate-llm, judge, and proxy.

### Verify

```bash
# health
curl http://localhost:8000/health

# readiness (checks Redis + MongoDB)
curl http://localhost:8000/ready

# send a chat request
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the capital of France?"}'

# check metrics
curl http://localhost:8000/api/v1/metrics

# browse mismatches
curl http://localhost:8000/api/v1/mismatches
```

### Stop

```bash
make down       # stop containers
make clean      # stop and remove volumes
```

### Logs

```bash
make logs s=proxy
make logs s=candidate-llm
```

---

## Running Tests

### Unit tests for a service

```bash
make test s=proxy
make test s=judge
```

### Unit tests only

```bash
make test-unit s=proxy
make test-unit s=judge
```

### Integration tests (requires running stack)

```bash
make dev          # start services first
make test-integration s=proxy
```

### All tests

```bash
make test-all
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ENV` | `development` | Environment name |
| `LOG_LEVEL` | `INFO` | Structured log level |
| `PRIMARY_LLM_URL` | `http://primary-llm:8001` | Primary LLM service URL |
| `CANDIDATE_LLM_URL` | `http://candidate-llm:8002` | Candidate LLM service URL |
| `JUDGE_URL` | `http://judge:8003` | Judge service URL |
| `MONGODB_URL` | `mongodb://...` | MongoDB connection string |
| `MONGODB_DB_NAME` | `shadowproxy` | MongoDB database name |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `RESPONSE_DELAY_SECONDS` | `0` | Artificial candidate delay (testing) |
| `DIVERGENCE_RATE` | `0.3` | Probability of candidate diverging (0.0–1.0) |
| `PRIMARY_TIMEOUT` | `10` | Primary LLM HTTP timeout (seconds) |
| `CANDIDATE_TIMEOUT` | `30` | Candidate LLM HTTP timeout (seconds) |
| `JUDGE_TIMEOUT` | `10` | Judge HTTP timeout (seconds) |
| `RATE_LIMIT_PER_MINUTE` | `60` | Max requests per minute per client |

Copy `.env.example` to `.env` to get started:

```bash
cp .env.example .env
```

---

## API Reference

### `POST /api/v1/chat`

Send a prompt and receive the primary LLM response synchronously. Shadow comparison runs asynchronously after the response is returned.

**Request:**
```json
{ "prompt": "What is the capital of France?", "user_id": "user-123" }
```

**Response:**
```json
{ "response": "Primary response to: What is...", "model": "primary-llm-v1", "request_id": "uuid" }
```

### `GET /api/v1/metrics`

Returns aggregate counters from Redis.

```json
{
  "total_requests": 100,
  "total_compared": 98,
  "matches": 68,
  "mismatches": 30,
  "shadow_errors": 2,
  "match_rate_percent": 69.39
}
```

### `GET /api/v1/mismatches?limit=20`

Returns recent mismatch records from MongoDB, sorted by timestamp descending.

### `GET /health`

Liveness probe — returns `{"status": "ok"}`.

### `GET /ready`

Readiness probe — pings Redis and MongoDB. Returns 503 if either is unreachable.

---

## Production Deployment

Deploys to DigitalOcean App Platform via `git push` to `main`:

```bash
# manual deploy
doctl apps create --spec infra/app-platform/app.yaml
```

GitHub Actions handle CI (unit + integration tests) and CD (App Platform deploy) automatically.

---

## Key Design Decisions

**`asyncio.create_task()` over `BackgroundTasks`**
BackgroundTasks is bound to the request lifecycle and can be cancelled on connection close. `create_task()` is owned by the event loop — it survives connection close because it is not bound to the request context. Candidate latency never affects primary response latency.

**Judge as a separate service**
The proxy never knows how comparison works. Swapping normalised string comparison for semantic or LLM-based comparison is a judge-only change. The proxy interface never changes.

**Normalised comparison over exact match**
Exact string comparison produces false positives for semantically equivalent responses with minor formatting differences. Normalisation handles case, punctuation, and whitespace differences.

**Redis for metrics counters**
Atomic `INCR` prevents race conditions under concurrent requests. Pipeline reads all five counters in a single round trip.

**MongoDB for mismatch logs**
Document store suits the mismatch payload — flexible schema, indexed by `timestamp` and `user_id`, queryable without migrations.

**App Platform over DOKS**
No independent scaling requirement justifies Kubernetes complexity. App Platform provides deployment, HTTPS, health checks, and automatic restarts for free.

**Production evolution: RabbitMQ**
The current `asyncio.create_task()` approach loses shadow tasks on proxy restart — acceptable for observational data with low durability requirements. Adding RabbitMQ would provide process-level durability and independent worker scaling at the cost of operational complexity. That migration would be: proxy enqueues to RabbitMQ instead of `create_task()`, a separate worker service consumes and runs the shadow + judge + log pipeline.
