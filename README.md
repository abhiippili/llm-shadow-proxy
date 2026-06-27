# llm-shadow-proxy

A proxy API that serves customer traffic synchronously using a stable Primary LLM, while safely firing an asynchronous shadow request to a Candidate LLM, passing both responses to a Judge service for comparison, and logging any mismatches.

The core engineering challenge: the shadow task must be fully decoupled from the primary response path — candidate latency or failure must **never** affect what the client sees.

---

## Table of Contents

1. [Architecture](#architecture)
2. [How the Background Task is Decoupled](#how-the-background-task-is-decoupled)
3. [Cloud Architecture (DigitalOcean)](#cloud-architecture-digitalocean)
4. [Local Setup](#local-setup)
5. [Running the Services](#running-the-services)
6. [API Reference & Testing](#api-reference--testing)
7. [Running Tests](#running-tests)
8. [Environment Variables](#environment-variables)
9. [CI/CD](#cicd)
10. [Key Design Decisions](#key-design-decisions)

---

## Architecture

```
                        ┌─────────────────────────────────────────────┐
                        │                  proxy :8000                 │
                        │                                              │
  Client                │  1. POST /api/v1/chat                        │
  ──────  ─────────────►│  2. await primary-llm  ──────────────────►   │
                        │  3. return response to client  ◄──────────   │
  ◄──────  response     │  4. asyncio.create_task(shadow)  ← detached  │
                        │                                              │
                        └──────────────────────────────────────────────┘
                                │ (sync)              │ (async, after response sent)
                                ▼                     ▼
                         primary-llm:8001      candidate-llm:8002
                         (stable mock)         (~30% divergence)
                                                      │
                                                      ▼
                                               judge:8003
                                         (normalised comparison)
                                                      │
                                    ┌─────────────────┴──────────────────┐
                                    ▼                                    ▼
                             Redis                                  MongoDB
                          (atomic counters)                     (mismatch log)
```

### Services

| Service | Port | Purpose |
|---|---|---|
| `proxy` | 8000 | Entry point — calls primary, fires shadow, exposes metrics |
| `primary-llm` | 8001 | Mock stable LLM — always returns consistent responses |
| `candidate-llm` | 8002 | Mock candidate LLM — ~30% divergence, configurable delay |
| `judge` | 8003 | Normalised text comparison — returns match verdict |

### Data stores

| Store | Purpose |
|---|---|
| Redis | Atomic counters: `total_requests`, `total_compared`, `matches`, `mismatches`, `shadow_errors` |
| MongoDB | Full mismatch document log — queryable by `timestamp` and `user_id` |

---

## How the Background Task is Decoupled

The shadow call uses `asyncio.create_task()`, **not** `await` and **not** FastAPI's `BackgroundTasks`:

```python
# api/v1/chat.py

# Step 1 — await primary (client waits for this)
primary_json = await primary_client.complete(body.prompt)
primary_response = extract_response(primary_json)

# Step 2 — fire shadow, do NOT await
# create_task() hands ownership to the event loop
# the task lives on even if the client disconnects
asyncio.create_task(
    shadow_service.execute(
        prompt=body.prompt,
        primary_response=primary_response,
        request_id=request_id,
        user_id=body.user_id,
    )
)

# Step 3 — return immediately, shadow hasn't even started yet
return ChatResponse(response=primary_response, ...)
```

**Why `create_task()` over `BackgroundTasks`:**

`BackgroundTasks` is tied to the request lifecycle. If the client closes the connection, the framework can cancel it. `asyncio.create_task()` transfers ownership to the event loop — the task is not bound to the request context and survives a connection close.

**Why this matters in practice:**

If `candidate-llm` has a 30-second delay, the proxy still returns the primary response in ~10ms. The candidate call happens invisibly in the background. The client never waits for it. If the shadow task fails for any reason — candidate down, judge down, Redis down — the exception is caught silently inside `shadow_service.execute()` and counted as a `shadow_error`. Nothing propagates to the client.

```
Timeline:

t=0ms    Client sends POST /api/v1/chat
t=10ms   Primary LLM responds
t=10ms   Proxy returns response to client  ◄── client done
t=10ms   Shadow task starts (detached)
t=30ms   Candidate LLM responds (2000ms if delayed)
t=35ms   Judge compares responses
t=36ms   Redis counters incremented
t=36ms   If mismatch: MongoDB document written
         (client left at t=10ms, none of this affects them)
```

---

## Cloud Architecture (DigitalOcean)

```
                         Internet
                             │
                             ▼
                    ┌─────────────────┐
                    │  DO App Platform │
                    │   Load Balancer  │
                    │   + Auto HTTPS   │
                    └────────┬────────┘
                             │ HTTPS
                             ▼
              ┌──────────────────────────────┐
              │        proxy (public)         │
              │   your-app.ondigitalocean.com │
              └──────────────┬───────────────┘
                             │
              ┌──────────────┼──────────────────┐
              │    DO App Platform Private LAN   │
              │                                  │
              │  ┌─────────────┐  ┌───────────┐  │
              │  │ primary-llm │  │  judge    │  │
              │  │ (internal)  │  │ (internal)│  │
              │  └─────────────┘  └───────────┘  │
              │                                  │
              │  ┌───────────────┐               │
              │  │ candidate-llm │               │
              │  │  (internal)   │               │
              │  └───────────────┘               │
              └──────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
   ┌─────────────────────┐    ┌─────────────────────┐
   │   DO Managed Redis   │    │  DO Managed MongoDB  │
   │   (private network)  │    │  (private network)   │
   └─────────────────────┘    └─────────────────────┘
```

**Key points:**

- Only `proxy` has a public HTTPS URL. `primary-llm`, `candidate-llm`, and `judge` are **internal services** — no public ports, not reachable from the internet
- Services communicate over DO's private LAN using component names as DNS: `http://primary-llm:8001`
- MongoDB and Redis are DO Managed Databases — provisioned separately, connected via private network, not exposed publicly
- DO App Platform handles TLS termination, health checks, and restarts automatically

---

## Local Setup

### Prerequisites

- Python 3.11+
- MongoDB (`mongod`)
- Redis (`redis-server`)

### 1. Clone and configure

```bash
git clone https://github.com/abhiippili/llm-shadow-proxy.git
cd llm-shadow-proxy

cp .env.example .env
# .env is already configured for localhost — no changes needed for local dev
```

### 2. Start MongoDB and Redis

```bash
make infra
```

This runs:
```
mongod --dbpath /tmp/mongodata --port 27017 --fork --logpath /tmp/mongod.log
redis-server --daemonize yes --logfile /tmp/redis.log
```

To stop:
```bash
make stop-infra
```

### 3. Start all four services (four separate terminals)

```bash
# Terminal 1
make run-primary

# Terminal 2
make run-candidate

# Terminal 3
make run-judge

# Terminal 4
make run-proxy
```

Each command installs dependencies and starts the service with `--reload` (auto-restarts on file changes).

### 4. Verify everything is up

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

Each should return `{"status": "ok", "service": "<name>"}`.

```bash
curl http://localhost:8000/ready
```

The `/ready` endpoint on the proxy pings both Redis and MongoDB. Returns `{"status": "ready"}` if both are reachable, or `503` if either is down.

---

## API Reference & Testing

### POST /api/v1/chat

Send a prompt. Returns the primary LLM response immediately. Shadow comparison runs in the background.

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the capital of France?"}'
```

**Response:**
```json
{
  "response": "Primary response to: What is the capital of France?. The answer is well established.",
  "model": "primary-llm-v1",
  "request_id": "3f8a2b1c-..."
}
```

**With a user ID (for mismatch tracking):**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2+2?", "user_id": "user-123"}'
```

**With a custom request ID (for tracing):**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: my-trace-id-001" \
  -d '{"prompt": "Hello"}'
```

The same ID will appear in the response headers and in the response body `request_id` field.

---

### GET /api/v1/metrics

Returns aggregate counters from Redis.

```bash
curl http://localhost:8000/api/v1/metrics
```

```json
{
  "total_requests": 42,
  "total_compared": 41,
  "matches": 28,
  "mismatches": 13,
  "shadow_errors": 0,
  "match_rate_percent": 68.29
}
```

| Field | Meaning |
|---|---|
| `total_requests` | Total POST /chat calls |
| `total_compared` | Shadow tasks that completed a judge comparison |
| `matches` | Judge returned `match: true` |
| `mismatches` | Judge returned `match: false` — stored in MongoDB |
| `shadow_errors` | Shadow tasks that failed (candidate/judge/Redis error) |
| `match_rate_percent` | `matches / total_compared * 100` |

---

### GET /api/v1/mismatches

Returns the most recent mismatch records from MongoDB.

```bash
curl http://localhost:8000/api/v1/mismatches
```

```bash
# limit the results
curl "http://localhost:8000/api/v1/mismatches?limit=5"
```

```json
{
  "mismatches": [
    {
      "id": "uuid",
      "request_id": "3f8a2b1c-...",
      "user_id": "user-123",
      "prompt": "What is the capital of France?",
      "primary_response": "Primary response to: What is...",
      "candidate_response": "Candidate response to: What is...",
      "judge_score": 0.0,
      "judge_reason": "responses differ after normalisation",
      "timestamp": "2026-06-27T10:00:00+00:00"
    }
  ],
  "count": 1
}
```

---

### GET /health and GET /ready

```bash
curl http://localhost:8000/health   # liveness — always returns 200 if process is up
curl http://localhost:8000/ready    # readiness — checks Redis + MongoDB connectivity
```

---

### Prove the decoupling works

Set `RESPONSE_DELAY_SECONDS=2` in `.env`, restart candidate-llm (`make run-candidate`), then time a chat request:

```bash
time curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test"}'
```

Expected output — response in under 100ms even though candidate takes 2 seconds:
```
real    0m0.08s
```

---

## Running Tests

### Unit tests (no services needed)

```bash
make test-unit s=proxy   # 18 tests — extraction, shadow service, metrics service
make test-unit s=judge   # 11 tests — normalise, compare
```

Or run all unit tests at once:
```bash
make test-all
```

### Full test suite with coverage

```bash
make test s=proxy
make test s=judge
```

### Integration tests (all services must be running)

Start infra and all four services first, then:

```bash
make test-integration s=proxy
```

Integration tests verify:
- Primary returns in under 500ms even with a 2-second candidate delay
- Proxy returns 200 even when candidate is configured to fail
- Metrics endpoint returns all expected fields
- Mismatch endpoint returns a list
- `X-Request-ID` header is preserved end-to-end

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ENV` | `development` | Environment name |
| `LOG_LEVEL` | `INFO` | Structured log level |
| `PRIMARY_LLM_URL` | `http://localhost:8001` | Primary LLM service URL |
| `CANDIDATE_LLM_URL` | `http://localhost:8002` | Candidate LLM service URL |
| `JUDGE_URL` | `http://localhost:8003` | Judge service URL |
| `MONGODB_URL` | `mongodb://localhost:27017/shadowproxy` | MongoDB connection string |
| `MONGODB_DB_NAME` | `shadowproxy` | MongoDB database name |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `RESPONSE_DELAY_SECONDS` | `0` | Artificial candidate delay in seconds (use `2` for decoupling tests) |
| `DIVERGENCE_RATE` | `0.3` | Probability of candidate diverging (0.0–1.0) |
| `PRIMARY_TIMEOUT` | `10` | Primary LLM HTTP timeout (seconds) — client waits for this |
| `CANDIDATE_TIMEOUT` | `30` | Candidate LLM HTTP timeout (seconds) — shadow only, client never sees it |
| `JUDGE_TIMEOUT` | `10` | Judge HTTP timeout (seconds) |
| `RATE_LIMIT_PER_MINUTE` | `60` | Max requests per minute |

---

## CI/CD

### CI — GitHub Actions (`.github/workflows/ci.yml`)

Triggers on push to `main` or `develop`, and on pull requests to `main`.

```
CI
├── test job
│   ├── Run judge unit tests (11 tests)
│   └── Run proxy unit tests (18 tests)
│
└── integration job  (runs after test passes)
    ├── Start MongoDB 7.0 (via supercharge/mongodb-github-action)
    ├── Start Redis 7 (via supercharge/redis-github-action)
    ├── Install all service dependencies
    ├── Start primary-llm, candidate-llm (with 2s delay), judge
    ├── Start proxy
    └── Run integration tests
```

### CD — GitHub Actions (`.github/workflows/deploy.yml`)

Triggers on push to `main` only.

**First deploy:**
- Add `DIGITALOCEAN_ACCESS_TOKEN` secret to GitHub repo settings
- Push to `main` — `doctl apps create` creates the app on DO App Platform
- Get the app ID: `doctl apps list`
- Add `DO_APP_ID` secret to GitHub repo settings

**Subsequent deploys:**
- Every push to `main` automatically runs `doctl apps update $DO_APP_ID`

### Required GitHub Secrets

| Secret | How to get it |
|---|---|
| `DIGITALOCEAN_ACCESS_TOKEN` | DO Dashboard → API → Generate New Token (read + write) |
| `DO_APP_ID` | `doctl apps list` after first deploy |

---

## Production Setup (DigitalOcean)

### 1. Provision databases

**MongoDB** — DO Dashboard → Databases → Create → MongoDB 7 → Bangalore (blr) → Basic 1GB
**Redis** — DO Dashboard → Databases → Create → Redis 7 → Bangalore (blr) → Basic 1GB

### 2. Add database secrets to the app

After the first deploy, go to DO Dashboard → Apps → llm-shadow-proxy → Settings → Environment Variables and add:

| Key | Value |
|---|---|
| `MONGODB_URL` | MongoDB connection string from DO database dashboard |
| `REDIS_URL` | Redis connection string from DO database dashboard |

### 3. Restrict database access

In each database → Trusted Sources → add your App Platform app. This ensures only your app can connect — the databases are not exposed to the public internet.

### 4. Trigger a redeploy

```bash
git commit --allow-empty -m "trigger redeploy with db secrets"
git push
```

---

## Key Design Decisions

**`asyncio.create_task()` over `BackgroundTasks`**
`BackgroundTasks` is tied to the request lifecycle — a connection close can cancel it. `create_task()` is owned by the event loop and survives connection close. Candidate latency never becomes client latency.

**Judge as a separate service**
The proxy has no knowledge of how comparison works. Swapping normalised string matching for semantic/LLM-based comparison is a judge-only change. The proxy interface never changes.

**Normalised comparison over exact match**
Exact string comparison produces false positives on semantically identical responses with minor formatting differences. Normalisation handles case, punctuation, and whitespace.

**Redis for metrics counters**
Atomic `INCR` is safe under concurrent requests — no race conditions. Pipeline reads all five counters in one round trip.

**MongoDB for mismatch logs**
Document store suits the mismatch payload. Flexible schema, indexed by `timestamp` and `user_id`, queryable without migrations.

**DO App Platform over Kubernetes**
No independent scaling requirement justifies Kubernetes complexity. App Platform provides deployment, HTTPS, health checks, and automatic restarts for free.

**Production evolution: RabbitMQ**
The current `asyncio.create_task()` approach loses shadow tasks on proxy restart — acceptable for observational data. The next durability step is RabbitMQ: proxy enqueues to a queue instead of calling `create_task()`, a separate worker consumes the queue and runs the shadow pipeline. This adds process-level durability and independent worker scaling at the cost of operational complexity.
