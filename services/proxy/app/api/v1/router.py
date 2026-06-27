from fastapi import APIRouter
from app.api.v1.chat import router as chat_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.mismatches import router as mismatches_router

router = APIRouter()

router.include_router(chat_router)
router.include_router(metrics_router)
router.include_router(mismatches_router)
