from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
import logging

from .schemas import StoryCreate, StoryResponse
from db.redis import redis_client # Bringing in our lightning-fast scratchpad
# from shared.s3 import delete_s3_file # You'll use your existing S3 delete function here

logger = logging.getLogger(__name__)

class StoryService:
    @staticmethod
    async def create_story(
        user_id: str,
        story_in: StoryCreate,
        db: AsyncIOMotorDatabase
    ) -> StoryResponse:
        """
        Pillar 1 & 2: MongoDB as Truth, S3 as Storage (via frontend presigned URL).
        We stamp it with an exact 24-hour expiration clock.
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=24)

        story_doc = {
            "author_id": ObjectId(user_id),
            "media_url": story_in.media_url,
            "media_type": story_in.media_type,
            "caption": story_in.caption,
            "created_at": now,
            "expires_at": expires,
            "views_count": 0,
            "is_deleted": False # Safety flag
        }

        result = await db.stories.insert_one(story_doc)

        return StoryResponse(
            id=str(result.inserted_id),
            author_id=user_id,
            media_url=story_doc["media_url"],
            media_type=story_doc["media_type"],
            caption=story_doc["caption"],
            created_at=story_doc["created_at"],
            expires_at=story_doc["expires_at"],
            views_count=0
        )

    @staticmethod
    async def view_story(
        story_id: str,
        viewer_id: str,
        db: AsyncIOMotorDatabase
    ) -> bool:
        """
        Pillar 3: Redis for Views.
        We use Redis to guarantee we never count the same viewer twice within 24 hours,
        protecting MongoDB from heavy, useless write operations.
        """
        # Create a highly specific lock key: e.g., "story_view:abc123:user_xyz789"
        cache_key = f"story_view:{story_id}:{viewer_id}"
        
        # Check Redis first. If the key exists, they already watched it. Skip the DB entirely.
        has_viewed = await redis_client.get(cache_key)
        if has_viewed:
            return False 

        # If we get here, it's a completely new view!
        # 1. Save the lock to Redis for exactly 24 hours (86400 seconds)
        await redis_client.set(cache_key, "1", ex=86400)
        
        # 2. Safely increment the permanent count in MongoDB
        await db.stories.update_one(
            {"_id": ObjectId(story_id)},
            {"$inc": {"views_count": 1}}
        )
        return True

    @staticmethod
    async def cleanup_expired_stories(db: AsyncIOMotorDatabase):
        """
        Pillar 4: The Janitor (Cron Worker).
        Finds all expired stories, deletes the S3 files, and wipes the DB rows.
        """
        now = datetime.now(timezone.utc)
        
        # Find all stories where the expires_at clock has passed
        cursor = db.stories.find({"expires_at": {"$lt": now}, "is_deleted": False})
        expired_stories = await cursor.to_list(length=100) # Process in batches of 100
        
        deleted_count = 0
        for story in expired_stories:
            try:
                # 1. Delete from S3 FIRST (Preventing the Orphan Trap)
                # await delete_s3_file(story["media_url"])
                
                # 2. Hard delete from MongoDB (or soft delete if compliance requires it)
                await db.stories.delete_one({"_id": story["_id"]})
                deleted_count += 1
                
            except Exception as e:
                logger.error(f"Failed to clean up story {story['_id']}: {e}")
                # We skip to the next one. The beauty of the cron worker is it will 
                # simply try to delete this failed story again in 5 minutes!

        if deleted_count > 0:
            logger.info(f"Janitor wiped {deleted_count} expired stories from S3 and MongoDB.")