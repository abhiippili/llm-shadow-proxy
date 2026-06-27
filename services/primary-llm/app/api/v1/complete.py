from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class CompletionRequest(BaseModel):
    prompt: str


@router.post("/complete")
async def complete(request: CompletionRequest):
    return {
        "model": "primary-llm-v1",
        "response": f"Primary response to: {request.prompt[:50]}. The answer is well established.",
        "tokens": 42,
    }
