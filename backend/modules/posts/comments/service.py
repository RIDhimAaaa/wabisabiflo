from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from fastapi import HTTPException, status

from ..schemas import CommentCreate

class CommentService:
    @staticmethod
    async def create_comment(
        post_id: str, 
        payload: CommentCreate, 
        current_user: dict, 
        db: AsyncIOMotorDatabase
    ) -> dict:
        """Saves a comment and atomically increments the parent post's counter."""
        if not ObjectId.is_valid(post_id):
            raise HTTPException(status_code=400, detail="Invalid Post ID")

        # 1. Verify post exists, is not deleted, and ALLOWS comments
        post = await db.posts.find_one({"_id": ObjectId(post_id), "is_deleted": False})
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        if not post.get("allow_comments", True):
            raise HTTPException(status_code=403, detail="Comments are disabled for this post")

        # 2. Build the comment document
        comment_doc = {
            "post_id": ObjectId(post_id),
            "author_id": current_user["_id"],
            "content": payload.content,
            "created_at": datetime.now(timezone.utc)
        }

        # 3. Save comment to DB
        result = await db.comments.insert_one(comment_doc)
        comment_doc["_id"] = result.inserted_id

        # 4. Atomically increment the parent post's comment count
        await db.posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"comment_count": 1}}
        )

        # 5. Hydrate author info for the frontend response
        comment_doc["author"] = {
            "_id": current_user["_id"],
            "username": current_user["username"],
            "profile_picture": current_user.get("profile_picture")
        }

        return comment_doc

    @staticmethod
    async def get_comments_for_post(post_id: str, db: AsyncIOMotorDatabase) -> list[dict]:
        """Fetches comments for a post, embedding the author data via aggregation."""
        if not ObjectId.is_valid(post_id):
            raise HTTPException(status_code=400, detail="Invalid Post ID")

        pipeline = [
            {"$match": {"post_id": ObjectId(post_id)}},
            {"$sort": {"created_at": -1}}, # Newest first
            {"$limit": 50}, # Pagination limit for V1
            {
                "$lookup": {
                    "from": "users",
                    "localField": "author_id",
                    "foreignField": "_id",
                    "as": "author_data"
                }
            },
            {"$unwind": "$author_data"}
        ]

        cursor = db.comments.aggregate(pipeline)
        comments = await cursor.to_list(length=50)

        # Format author data to match the AuthorInfo schema
        for comment in comments:
            comment["author"] = {
                "_id": comment["author_data"]["_id"],
                "username": comment["author_data"]["username"],
                "profile_picture": comment["author_data"].get("profile_picture")
            }

        return comments