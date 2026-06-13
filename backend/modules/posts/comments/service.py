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
        if not ObjectId.is_valid(post_id):
            raise HTTPException(status_code=400, detail="Invalid Post ID")

        post = await db.posts.find_one({"_id": ObjectId(post_id), "is_deleted": False})
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        if not post.get("allow_comments", True):
            raise HTTPException(status_code=403, detail="Comments are disabled for this post")

        # --- THE INSTAGRAM FLATTENING LOGIC ---
        final_parent_id = None
        if payload.parent_comment_id:
            if not ObjectId.is_valid(payload.parent_comment_id):
                raise HTTPException(status_code=400, detail="Invalid Parent Comment ID")
            
            target_comment = await db.comments.find_one({"_id": ObjectId(payload.parent_comment_id)})
            if not target_comment:
                raise HTTPException(status_code=404, detail="Target comment not found")
            
            # If the target comment ALREADY has a parent, it means it's a reply.
            # We bypass it and point our new comment to the top-level parent instead.
            if target_comment.get("parent_comment_id"):
                final_parent_id = target_comment["parent_comment_id"]
            else:
                # Otherwise, the target is a top-level comment, so we point to it.
                final_parent_id = target_comment["_id"]
        # ----------------------------------------

        comment_doc = {
            "post_id": ObjectId(post_id),
            "parent_comment_id": final_parent_id,
            "author_id": current_user["_id"],
            "content": payload.content,
            "created_at": datetime.now(timezone.utc)
        }

        result = await db.comments.insert_one(comment_doc)
        comment_doc["_id"] = result.inserted_id

        await db.posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$inc": {"comment_count": 1}}
        )

        comment_doc["author"] = {
            "_id": current_user["_id"],
            "username": current_user["username"],
            "profile_picture": current_user.get("profile_picture")
        }

        return comment_doc

    @staticmethod
    async def get_comments_for_post(post_id: str, db: AsyncIOMotorDatabase) -> list[dict]:
        """Fetches ONLY top-level comments for the initial feed load."""
        if not ObjectId.is_valid(post_id):
            raise HTTPException(status_code=400, detail="Invalid Post ID")

        pipeline = [
            # MATCH: Only this post, and ONLY comments where parent_comment_id is null
            {"$match": {
                "post_id": ObjectId(post_id), 
                "parent_comment_id": None
            }},
            {"$sort": {"created_at": -1}}, 
            {"$limit": 50}, 
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

        for comment in comments:
            comment["author"] = {
                "_id": comment["author_data"]["_id"],
                "username": comment["author_data"]["username"],
                "profile_picture": comment["author_data"].get("profile_picture")
            }
        return comments

    @staticmethod
    async def get_replies_for_comment(parent_comment_id: str, db: AsyncIOMotorDatabase) -> list[dict]:
        """Fetches replies specifically linked to a top-level comment."""
        if not ObjectId.is_valid(parent_comment_id):
            raise HTTPException(status_code=400, detail="Invalid Parent Comment ID")

        pipeline = [
            {"$match": {"parent_comment_id": ObjectId(parent_comment_id)}},
            {"$sort": {"created_at": 1}}, # Oldest first for replies makes more chronological sense
            {"$limit": 50},
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
        replies = await cursor.to_list(length=50)

        for reply in replies:
            reply["author"] = {
                "_id": reply["author_data"]["_id"],
                "username": reply["author_data"]["username"],
                "profile_picture": reply["author_data"].get("profile_picture")
            }
        return replies