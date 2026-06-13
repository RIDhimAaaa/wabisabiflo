from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ReturnDocument
from modules.feed.service import FeedService

class LikeService:
    @staticmethod
    async def toggle_like(post_id: str, current_user_id: ObjectId, db: AsyncIOMotorDatabase) -> dict:
        """
        Idempotent toggle: If the like exists, remove it. If it doesn't, add it.
        Uses $inc for atomic operations to prevent race conditions.
        """
        if not ObjectId.is_valid(post_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Post ID")

        # 1. Verify the post actually exists and isn't soft-deleted
        post = await db.posts.find_one({"_id": ObjectId(post_id), "is_deleted": False})
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

        # 2. Check for an existing like
        existing_like = await db.likes.find_one({
            "post_id": ObjectId(post_id),
            "user_id": current_user_id
        })

        if existing_like:
            # UNLIKE: Delete the record and decrement the post's counter
            await db.likes.delete_one({"_id": existing_like["_id"]})
            updated_post = await db.posts.find_one_and_update(
                {"_id": ObjectId(post_id)},
                {"$inc": {"like_count": -1}},
                return_document=ReturnDocument.AFTER
            )
            has_liked = False
        else:
            # LIKE: Create the record and increment the post's counter
            await db.likes.insert_one({
                "post_id": ObjectId(post_id),
                "user_id": current_user_id
            })
            updated_post = await db.posts.find_one_and_update(
                {"_id": ObjectId(post_id)},
                {"$inc": {"like_count": 1}},
                return_document=ReturnDocument.AFTER
            )
            has_liked = True

            # Only increase their affinity score if they actually LIKED the post
            await FeedService.track_user_affinity(current_user_id, post.get("hashtags", []), db)

        # 3. Return the exact UI state the frontend needs
        return {
            "post_id": post_id,
            "has_liked": has_liked,
            "new_like_count": updated_post["like_count"]
        }
    
    @staticmethod
    async def get_users_who_liked(post_id: str, db: AsyncIOMotorDatabase) -> list[dict]:
        """Fetches the profiles of users who liked a specific post."""
        if not ObjectId.is_valid(post_id):
            raise HTTPException(status_code=400, detail="Invalid Post ID")

        pipeline = [
            {"$match": {"post_id": ObjectId(post_id)}},
            {"$sort": {"_id": -1}}, # Show newest likes at the top
            {"$limit": 100}, # Standard production limit for the "Likes" modal
            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_id",
                    "foreignField": "_id",
                    "as": "user_data"
                }
            },
            {"$unwind": "$user_data"}
        ]

        cursor = db.likes.aggregate(pipeline)
        likes = await cursor.to_list(length=100)

        # Format to match our existing AuthorInfo schema
        users = []
        for like in likes:
            users.append({
                "_id": like["user_data"]["_id"],
                "username": like["user_data"]["username"],
                "profile_picture": like["user_data"].get("profile_picture")
            })
            
        return users