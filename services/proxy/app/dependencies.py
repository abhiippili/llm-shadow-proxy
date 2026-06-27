from fastapi import Depends
from app.clients.primary_llm_client import PrimaryLLMClient
from app.clients.candidate_llm_client import CandidateLLMClient
from app.clients.judge_client import JudgeClient
from app.clients.redis_client import RedisClient
from app.repositories.mismatch_repository import MongoMismatchRepository
from app.repositories.interfaces import IMismatchRepository
from app.services.shadow_service import ShadowService
from app.services.metrics_service import MetricsService
from app.db.mongo import get_db
from app.config import settings

_redis_client: RedisClient = None


def get_redis_client_instance() -> RedisClient:
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient(url=settings.redis_url)
    return _redis_client


def get_primary_client() -> PrimaryLLMClient:
    return PrimaryLLMClient()


def get_candidate_client() -> CandidateLLMClient:
    return CandidateLLMClient()


def get_judge_client() -> JudgeClient:
    return JudgeClient()


def get_redis_client() -> RedisClient:
    return get_redis_client_instance()


async def get_mismatch_repo() -> IMismatchRepository:
    db = await get_db()
    return MongoMismatchRepository(db=db)


def get_shadow_service(
    candidate_client: CandidateLLMClient = Depends(get_candidate_client),
    judge_client: JudgeClient = Depends(get_judge_client),
    redis_client: RedisClient = Depends(get_redis_client),
    mismatch_repo: IMismatchRepository = Depends(get_mismatch_repo),
) -> ShadowService:
    return ShadowService(
        candidate_client=candidate_client,
        judge_client=judge_client,
        redis_client=redis_client,
        mismatch_repo=mismatch_repo,
    )


def get_metrics_service(
    redis_client: RedisClient = Depends(get_redis_client),
) -> MetricsService:
    return MetricsService(redis_client=redis_client)
