import httpx
from app.config import settings


class JudgeClient:
    async def judge(self, primary_response: str, candidate_response: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.judge_url}/api/v1/judge",
                json={
                    "primary_response": primary_response,
                    "candidate_response": candidate_response,
                },
                timeout=settings.judge_timeout,
            )
            response.raise_for_status()
            return response.json()
