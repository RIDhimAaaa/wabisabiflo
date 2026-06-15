from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

from shared.s3 import S3Service  # <-- Clean import

logger = logging.getLogger(__name__)

class PostCleanupService:
    @staticmethod
    async def purge_expired_deleted_posts(db: AsyncIOMotorDatabase, days_to_keep: int = 30):
        expiration_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        query = {
            "is_deleted": True,
            "deleted_at": {"$lt": expiration_date}
        }

        expired_posts = await db.posts.find(query).to_list(length=None)

        if not expired_posts:
            logger.info("No expired posts found for cleanup.")
            return {"deleted_count": 0}

        urls_to_delete = []
        post_ids_to_delete = []

        for post in expired_posts:
            post_ids_to_delete.append(post["_id"])
            for media_item in post.get("media", []):
                urls_to_delete.append(media_item["url"])

        # Wipe the files using your centralized S3Service class
        try:
            S3Service.delete_s3_objects(urls_to_delete)
        except Exception as e:
            logger.error(f"Database purge aborted because S3 cleanup failed: {e}")
            return {"error": str(e)}

        result = await db.posts.delete_many({"_id": {"$in": post_ids_to_delete}})
        await db.likes.delete_many({"post_id": {"$in": post_ids_to_delete}})
        await db.comments.delete_many({"post_id": {"$in": post_ids_to_delete}})

        logger.info(f"Successfully purged {result.deleted_count} posts from database.")
        return {"deleted_count": result.deleted_count, "freed_files": len(urls_to_delete)}