from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING
import os

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/feedback_system")
client = AsyncIOMotorClient(MONGO_URL)
db = client["feedback_system"]

async def ensure_indexes():
    await db.users.create_index([("username", ASCENDING)], unique=True)
    await db.feedbacks.create_index([("employee_id", ASCENDING)])
    await db.feedbacks.create_index([("manager_id", ASCENDING)]) 