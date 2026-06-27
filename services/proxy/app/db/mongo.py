from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

client: AsyncIOMotorClient = None
db: AsyncIOMotorDatabase = None


async def connect_db():
    global client, db
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.mongodb_db_name]
    await create_indexes(db)


async def close_db():
    if client:
        client.close()


async def get_db() -> AsyncIOMotorDatabase:
    return db


async def create_indexes(database: AsyncIOMotorDatabase):
    await database["mismatches"].create_index("timestamp")
    await database["mismatches"].create_index("user_id")
    await database["mismatches"].create_index([("timestamp", -1)])
