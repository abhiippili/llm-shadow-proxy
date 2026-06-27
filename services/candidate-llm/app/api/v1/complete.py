import asyncio
import random
from fastapi import APIRouter
from pydantic import BaseModel
from app.config import settings

router = APIRouter()


class CompletionRequest(BaseModel):
    prompt: str


@router.post("/complete")
async def complete(request: CompletionRequest):
    if settings.response_delay_seconds > 0:
        await asyncio.sleep(settings.response_delay_seconds)

    if random.random() < settings.divergence_rate:
        return {
            "model": "candidate-llm-v1",
            "response": f"Candidate response to: {request.prompt[:50]}. This is a different perspective.",
            "tokens": 38,
        }

    return {
        "model": "candidate-llm-v1",
        "response": f"Primary response to: {request.prompt[:50]}. The answer is well established.",
        "tokens": 42,
    }
