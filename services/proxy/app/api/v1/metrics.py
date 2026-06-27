from fastapi import APIRouter, Depends
from app.services.metrics_service import MetricsService
from app.models.schemas.metrics import MetricsResponse
from app.dependencies import get_metrics_service

router = APIRouter()


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(service: MetricsService = Depends(get_metrics_service)):
    return await service.get_metrics()
