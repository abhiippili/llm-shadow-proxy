import pytest
from unittest.mock import AsyncMock
from app.services.metrics_service import MetricsService


@pytest.fixture
def redis_mock():
    return AsyncMock()


@pytest.mark.asyncio
async def test_metrics_returns_expected_fields(redis_mock):
    redis_mock.get_metrics.return_value = {
        "total_requests": 100,
        "total_compared": 80,
        "matches": 60,
        "mismatches": 20,
        "shadow_errors": 5,
    }

    service = MetricsService(redis_client=redis_mock)
    result = await service.get_metrics()

    assert result.total_requests == 100
    assert result.total_compared == 80
    assert result.matches == 60
    assert result.mismatches == 20
    assert result.shadow_errors == 5


@pytest.mark.asyncio
async def test_metrics_calculates_match_rate(redis_mock):
    redis_mock.get_metrics.return_value = {
        "total_requests": 100,
        "total_compared": 80,
        "matches": 60,
        "mismatches": 20,
        "shadow_errors": 0,
    }

    service = MetricsService(redis_client=redis_mock)
    result = await service.get_metrics()

    assert result.match_rate_percent == 75.0


@pytest.mark.asyncio
async def test_metrics_returns_zero_match_rate_when_no_comparisons(redis_mock):
    redis_mock.get_metrics.return_value = {
        "total_requests": 0,
        "total_compared": 0,
        "matches": 0,
        "mismatches": 0,
        "shadow_errors": 0,
    }

    service = MetricsService(redis_client=redis_mock)
    result = await service.get_metrics()

    assert result.match_rate_percent == 0.0
