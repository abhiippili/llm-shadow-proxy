import httpx
from app.config import settings


class PrimaryLLMClient:
    async def complete(self, prompt: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.primary_llm_url}/api/v1/complete",
                json={"prompt": prompt},
                timeout=settings.primary_timeout,
            )
            response.raise_for_status()
            return response.json()
