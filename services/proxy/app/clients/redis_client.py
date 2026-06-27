import redis.asyncio as aioredis


class RedisClient:
    def __init__(self, url: str):
        self.client = aioredis.from_url(url, decode_responses=True)

    async def ping(self) -> bool:
        return await self.client.ping()

    async def incr(self, key: str) -> int:
        return await self.client.incr(key)

    async def get_int(self, key: str) -> int:
        val = await self.client.get(key)
        return int(val) if val else 0

    async def get_metrics(self) -> dict:
        pipe = self.client.pipeline()
        pipe.get("metrics:total_requests")
        pipe.get("metrics:total_compared")
        pipe.get("metrics:matches")
        pipe.get("metrics:mismatches")
        pipe.get("metrics:shadow_errors")
        results = await pipe.execute()
        return {
            "total_requests": int(results[0] or 0),
            "total_compared": int(results[1] or 0),
            "matches": int(results[2] or 0),
            "mismatches": int(results[3] or 0),
            "shadow_errors": int(results[4] or 0),
        }

    async def close(self):
        await self.client.aclose()
