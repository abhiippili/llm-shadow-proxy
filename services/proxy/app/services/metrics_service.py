from app.clients.redis_client import RedisClient
from app.models.schemas.metrics import MetricsResponse


class MetricsService:
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client

    async def get_metrics(self) -> MetricsResponse:
        raw = await self.redis.get_metrics()
        total = raw["total_compared"]
        matches = raw["matches"]

        match_rate = round((matches / total * 100), 2) if total > 0 else 0.0

        return MetricsResponse(
            total_requests=raw["total_requests"],
            total_compared=total,
            matches=matches,
            mismatches=raw["mismatches"],
            shadow_errors=raw["shadow_errors"],
            match_rate_percent=match_rate,
        )
