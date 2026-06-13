from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ReturnDocument

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

        # 3. Return the exact UI state the frontend needs
        return {
            "post_id": post_id,
            "has_liked": has_liked,
            "new_like_count": updated_post["like_count"]
        }