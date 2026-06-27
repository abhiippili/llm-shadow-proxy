import structlog
from app.clients.candidate_llm_client import CandidateLLMClient
from app.clients.judge_client import JudgeClient
from app.clients.redis_client import RedisClient
from app.repositories.interfaces import IMismatchRepository
from app.models.domain.mismatch import Mismatch
from app.core.extraction import extract_response

logger = structlog.get_logger()


class ShadowService:
    def __init__(
        self,
        candidate_client: CandidateLLMClient,
        judge_client: JudgeClient,
        redis_client: RedisClient,
        mismatch_repo: IMismatchRepository,
    ):
        self.candidate = candidate_client
        self.judge = judge_client
        self.redis = redis_client
        self.mismatch_repo = mismatch_repo

    async def execute(
        self,
        prompt: str,
        primary_response: str,
        request_id: str,
        user_id: str | None = None,
    ) -> None:
        try:
            candidate_json = await self.candidate.complete(prompt)
            candidate_response = extract_response(candidate_json)

            verdict = await self.judge.judge(primary_response, candidate_response)

            await self.redis.incr("metrics:total_compared")

            if verdict["match"]:
                await self.redis.incr("metrics:matches")
                logger.info(
                    "shadow_match",
                    request_id=request_id,
                    score=verdict["score"],
                )
            else:
                await self.redis.incr("metrics:mismatches")
                await self.mismatch_repo.create(
                    Mismatch(
                        request_id=request_id,
                        user_id=user_id,
                        prompt=prompt,
                        primary_response=primary_response,
                        candidate_response=candidate_response,
                        judge_score=verdict["score"],
                        judge_reason=verdict["reason"],
                    )
                )
                logger.info(
                    "shadow_mismatch",
                    request_id=request_id,
                    score=verdict["score"],
                    reason=verdict["reason"],
                )

        except Exception as e:
            logger.error(
                "shadow_task_failed",
                request_id=request_id,
                error=str(e),
            )
            try:
                await self.redis.incr("metrics:shadow_errors")
            except Exception:
                pass
