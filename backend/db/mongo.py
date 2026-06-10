from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING # <-- Add this import
from config import settings

class Database:
    client: AsyncIOMotorClient = None
    db = None

# Create a global instance
mongodb = Database()

async def init_indexes(db):
    """Creates required MongoDB indexes for performance and data integrity."""
    try:
        # 1. Users Collection Indexes
        user_indexes = [
            IndexModel([("username", ASCENDING)], unique=True),
            IndexModel([("email", ASCENDING)], unique=True),
            IndexModel([("full_name", ASCENDING)]),
        ]
        await db.users.create_indexes(user_indexes)
        print(" Users collection indexes verified.")

        # 2. Follows Collection Indexes (The Social Graph)
        follow_indexes = [
            IndexModel([("follower_id", ASCENDING), ("following_id", ASCENDING)], unique=True),
            IndexModel([("following_id", ASCENDING)]),
            IndexModel([("follower_id", ASCENDING)]),
        ]
        await db.follows.create_indexes(follow_indexes)
        print(" Follows collection indexes verified.")

        # 3. Blocks Collection Indexes
        block_indexes = [
            # Compound unique index prevents double-blocking the same person
            IndexModel([("blocker_id", ASCENDING), ("blocked_id", ASCENDING)], unique=True),
        ]
        await db.blocks.create_indexes(block_indexes)
        print(" Blocks collection indexes verified.")


    except Exception as e:
        print(f" Failed to initialize MongoDB indexes: {e}")

async def connect_to_mongo():
    print("Connecting to MongoDB...")
    # We use settings from config.py so no secrets are hardcoded!
    mongodb.client = AsyncIOMotorClient(settings.MONGO_URI)
    mongodb.db = mongodb.client[settings.MONGO_DB_NAME]
    print("Successfully connected to WabiSabiFlo Database!")
    
    # <-- Trigger index creation right after connecting -->
    await init_indexes(mongodb.db)

async def close_mongo_connection():
    print("Closing MongoDB connection...")
    if mongodb.client:
        mongodb.client.close()
        print("MongoDB connection closed.")

# A dependency function we will use later in our routers
async def get_database():
    return mongodb.db