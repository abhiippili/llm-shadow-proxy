import pytest
from unittest.mock import AsyncMock
from app.services.shadow_service import ShadowService


@pytest.fixture
def mock_deps():
    return {
        "candidate_client": AsyncMock(),
        "judge_client": AsyncMock(),
        "redis_client": AsyncMock(),
        "mismatch_repo": AsyncMock(),
    }


@pytest.mark.asyncio
async def test_shadow_increments_match_counter_on_match(mock_deps):
    mock_deps["candidate_client"].complete.return_value = {
        "response": "same",
        "model": "c",
        "tokens": 1,
    }
    mock_deps["judge_client"].judge.return_value = {
        "match": True,
        "score": 1.0,
        "reason": "match",
    }

    service = ShadowService(**mock_deps)
    await service.execute("prompt", "same", "req-1")

    mock_deps["redis_client"].incr.assert_any_call("metrics:matches")
    mock_deps["mismatch_repo"].create.assert_not_called()


@pytest.mark.asyncio
async def test_shadow_increments_compared_counter(mock_deps):
    mock_deps["candidate_client"].complete.return_value = {
        "response": "same",
        "model": "c",
        "tokens": 1,
    }
    mock_deps["judge_client"].judge.return_value = {
        "match": True,
        "score": 1.0,
        "reason": "match",
    }

    service = ShadowService(**mock_deps)
    await service.execute("prompt", "same", "req-1")

    mock_deps["redis_client"].incr.assert_any_call("metrics:total_compared")


@pytest.mark.asyncio
async def test_shadow_logs_mismatch_to_mongo_on_mismatch(mock_deps):
    mock_deps["candidate_client"].complete.return_value = {
        "response": "different",
        "model": "c",
        "tokens": 1,
    }
    mock_deps["judge_client"].judge.return_value = {
        "match": False,
        "score": 0.0,
        "reason": "differ",
    }

    service = ShadowService(**mock_deps)
    await service.execute("prompt", "original", "req-1")

    mock_deps["redis_client"].incr.assert_any_call("metrics:mismatches")
    mock_deps["mismatch_repo"].create.assert_called_once()


@pytest.mark.asyncio
async def test_shadow_mismatch_stores_correct_data(mock_deps):
    mock_deps["candidate_client"].complete.return_value = {
        "response": "different answer",
        "model": "c",
        "tokens": 1,
    }
    mock_deps["judge_client"].judge.return_value = {
        "match": False,
        "score": 0.0,
        "reason": "differ",
    }

    service = ShadowService(**mock_deps)
    await service.execute("my prompt", "original answer", "req-42", user_id="user-1")

    call_args = mock_deps["mismatch_repo"].create.call_args[0][0]
    assert call_args.request_id == "req-42"
    assert call_args.user_id == "user-1"
    assert call_args.prompt == "my prompt"
    assert call_args.primary_response == "original answer"
    assert call_args.candidate_response == "different answer"


@pytest.mark.asyncio
async def test_shadow_handles_candidate_failure_gracefully(mock_deps):
    mock_deps["candidate_client"].complete.side_effect = Exception("candidate down")

    service = ShadowService(**mock_deps)
    await service.execute("prompt", "response", "req-1")

    mock_deps["redis_client"].incr.assert_any_call("metrics:shadow_errors")


@pytest.mark.asyncio
async def test_shadow_handles_judge_failure_gracefully(mock_deps):
    mock_deps["candidate_client"].complete.return_value = {
        "response": "answer",
        "model": "c",
        "tokens": 1,
    }
    mock_deps["judge_client"].judge.side_effect = Exception("judge down")

    service = ShadowService(**mock_deps)
    await service.execute("prompt", "response", "req-1")

    mock_deps["redis_client"].incr.assert_any_call("metrics:shadow_errors")
    mock_deps["mismatch_repo"].create.assert_not_called()


@pytest.mark.asyncio
async def test_shadow_handles_redis_failure_gracefully(mock_deps):
    mock_deps["candidate_client"].complete.return_value = {
        "response": "same",
        "model": "c",
        "tokens": 1,
    }
    mock_deps["judge_client"].judge.return_value = {
        "match": True,
        "score": 1.0,
        "reason": "match",
    }
    mock_deps["redis_client"].incr.side_effect = Exception("redis down")

    service = ShadowService(**mock_deps)
    # must not raise
    await service.execute("prompt", "same", "req-1")
