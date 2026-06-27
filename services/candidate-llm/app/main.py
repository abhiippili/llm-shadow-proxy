import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.complete import router as complete_router

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()

app = FastAPI(title="Candidate LLM Mock", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(complete_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "candidate-llm"}


@app.get("/ready")
async def ready():
    return {"status": "ready", "service": "candidate-llm"}
