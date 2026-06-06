from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

class Database:
    client: AsyncIOMotorClient = None
    db = None

# Create a global instance
mongodb = Database()

async def connect_to_mongo():
    print("Connecting to MongoDB...")
    # We use settings from config.py so no secrets are hardcoded!
    mongodb.client = AsyncIOMotorClient(settings.MONGO_URI)
    mongodb.db = mongodb.client[settings.MONGO_DB_NAME]
    print("Successfully connected to WabiSabiFlo Database!")

async def close_mongo_connection():
    print("Closing MongoDB connection...")
    if mongodb.client:
        mongodb.client.close()
        print("MongoDB connection closed.")

# A dependency function we will use later in our routers
async def get_database():
    return mongodb.db