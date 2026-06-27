import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.logging import LoggingMiddleware
from app.db.mongo import connect_db, close_db, get_db
from app.dependencies import get_redis_client_instance
from app.config import settings

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("proxy_starting", env=settings.env)
    await connect_db()
    logger.info("mongodb_connected")
    yield
    await close_db()
    redis = get_redis_client_instance()
    await redis.close()
    logger.info("proxy_shutdown")


app = FastAPI(title="LLM Shadow Proxy", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "proxy"}


@app.get("/ready")
async def ready():
    try:
        redis = get_redis_client_instance()
        await redis.ping()
        db = await get_db()
        await db.command("ping")
        return {"status": "ready", "service": "proxy"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
