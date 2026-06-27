import pytest
import time
import httpx

BASE_URL = "http://localhost:8000"


@pytest.mark.asyncio
async def test_primary_returns_under_500ms():
    """Candidate has RESPONSE_DELAY_SECONDS=2 in test env.
    Proxy returns in under 500ms because shadow is fire-and-forget."""
    async with httpx.AsyncClient() as client:
        start = time.time()
        response = await client.post(
            f"{BASE_URL}/api/v1/chat",
            json={"prompt": "What is the capital of France?"},
        )
        elapsed = time.time() - start

    assert response.status_code == 200
    assert elapsed < 0.5


@pytest.mark.asyncio
async def test_primary_returns_even_when_candidate_would_fail():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/chat",
            json={"prompt": "test prompt"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "request_id" in data


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_expected_fields():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/metrics")

    assert response.status_code == 200
    data = response.json()
    assert "total_requests" in data
    assert "match_rate_percent" in data
    assert "mismatches" in data


@pytest.mark.asyncio
async def test_mismatches_endpoint_returns_list():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/v1/mismatches")

    assert response.status_code == 200
    data = response.json()
    assert "mismatches" in data
    assert "count" in data
    assert isinstance(data["mismatches"], list)


@pytest.mark.asyncio
async def test_health_endpoint():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "proxy"


@pytest.mark.asyncio
async def test_request_id_returned_in_response_headers():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/chat",
            json={"prompt": "test"},
        )

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_custom_request_id_echoed_back():
    custom_id = "my-custom-request-id-123"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/chat",
            json={"prompt": "test"},
            headers={"X-Request-ID": custom_id},
        )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id
    assert response.json()["request_id"] == custom_id
