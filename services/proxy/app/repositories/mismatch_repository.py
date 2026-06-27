from motor.motor_asyncio import AsyncIOMotorDatabase
from app.repositories.interfaces import IMismatchRepository
from app.models.domain.mismatch import Mismatch


class MongoMismatchRepository(IMismatchRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db["mismatches"]

    async def create(self, mismatch: Mismatch) -> Mismatch:
        await self.col.insert_one(mismatch.model_dump())
        return mismatch

    async def get_recent(self, limit: int = 20) -> list[Mismatch]:
        cursor = self.col.find().sort("timestamp", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [Mismatch(**d) for d in docs]

    async def count(self) -> int:
        return await self.col.count_documents({})
