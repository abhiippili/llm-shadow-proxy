import asyncio
import structlog
from fastapi import APIRouter, Depends, Request
from app.models.schemas.chat import ChatRequest, ChatResponse
from app.clients.primary_llm_client import PrimaryLLMClient
from app.clients.redis_client import RedisClient
from app.services.shadow_service import ShadowService
from app.core.extraction import extract_response, extract_model
from app.dependencies import get_primary_client, get_shadow_service, get_redis_client

router = APIRouter()
logger = structlog.get_logger()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    primary_client: PrimaryLLMClient = Depends(get_primary_client),
    shadow_service: ShadowService = Depends(get_shadow_service),
    redis_client: RedisClient = Depends(get_redis_client),
):
    request_id = request.state.request_id

    primary_json = await primary_client.complete(body.prompt)
    primary_response = extract_response(primary_json)

    await redis_client.incr("metrics:total_requests")

    # fire shadow task — NOT awaited
    # asyncio.create_task() is owned by the event loop, survives connection close
    # candidate latency or failure never affects the primary response path
    asyncio.create_task(
        shadow_service.execute(
            prompt=body.prompt,
            primary_response=primary_response,
            request_id=request_id,
            user_id=body.user_id,
        )
    )

    logger.info(
        "primary_response_returned",
        request_id=request_id,
        model=extract_model(primary_json),
    )

    return ChatResponse(
        response=primary_response,
        model=extract_model(primary_json),
        request_id=request_id,
    )
