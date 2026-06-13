import re
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from fastapi import HTTPException, status

from .schemas import PostCreate, PostUpdate

class PostService:
    @staticmethod
    def _extract_entities(text: str) -> tuple[list[str], list[str]]:
        """
        Extracts unique hashtags and mentions from text using regex.
        Ensures lowercase consistency for better indexing and searchability.
        """
        hashtags = list(set(re.findall(r"#(\w+)", text.lower())))
        mentions = list(set(re.findall(r"@(\w+)", text.lower())))
        return hashtags, mentions

    @staticmethod
    async def create_post(
        payload: PostCreate, 
        current_user: dict, 
        db: AsyncIOMotorDatabase
    ) -> dict:
        """
        Validates, parses entities, and saves a new post document to the database.
        """
        post_doc = payload.model_dump()

        # Parse text entities
        hashtags, mentions = PostService._extract_entities(payload.content)
        
        # Inject system metadata
        post_doc["author_id"] = current_user["_id"]
        post_doc["hashtags"] = hashtags
        post_doc["mentions"] = mentions
        post_doc["like_count"] = 0
        post_doc["comment_count"] = 0
        post_doc["is_flagged_nsfw"] = False
        post_doc["is_deleted"] = False
        post_doc["created_at"] = datetime.now(timezone.utc)
        post_doc["updated_at"] = None

        # Persist to MongoDB
        result = await db.posts.insert_one(post_doc)
        post_doc["_id"] = result.inserted_id

        # Hydrate the author profile response block from active session memory
        post_doc["author"] = {
            "_id": current_user["_id"],
            "username": current_user["username"],
            "profile_picture": current_user.get("profile_picture")
        }
        post_doc["has_liked"] = False

        return post_doc

    @staticmethod
    async def get_post_by_id(
        post_id: str, 
        current_user_id: ObjectId, 
        db: AsyncIOMotorDatabase
    ) -> dict:
        """
        Fetches a single post by its ID. Rejects soft-deleted entries.
        Includes an aggregation look-up step to populate author details.
        """
        if not ObjectId.is_valid(post_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid Post ID format"
            )

        # Run aggregation to grab post + author information in one pass
        pipeline = [
            {"$match": {"_id": ObjectId(post_id), "is_deleted": False}},
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
        
        cursor = db.posts.aggregate(pipeline)
        results = await cursor.to_list(length=1)
        
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Post not found"
            )
            
        post_doc = results[0]
        
        # Map back to the required AuthorInfo response format
        post_doc["author"] = {
            "_id": post_doc["author_data"]["_id"],
            "username": post_doc["author_data"]["username"],
            "profile_picture": post_doc["author_data"].get("profile_picture")
        }
        
        # Check if the current user has liked this post
        like_exists = await db.likes.find_one({
            "post_id": ObjectId(post_id), 
            "user_id": current_user_id
        })
        post_doc["has_liked"] = bool(like_exists)

        return post_doc

    @staticmethod
    async def update_post(
        post_id: str, 
        payload: PostUpdate, 
        current_user_id: ObjectId, 
        db: AsyncIOMotorDatabase
    ) -> dict:
        """
        Updates a post's text. Re-parses entities if text changes.
        Enforces strict ownership validation.
        """
        # Fetch the active post to verify ownership first
        post = await PostService.get_post_by_id(post_id, current_user_id, db)
        
        if post["author_id"] != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="You do not have permission to edit this post"
            )

        new_hashtags, new_mentions = PostService._extract_entities(payload.content)

        update_data = {
            "content": payload.content,
            "hashtags": new_hashtags,
            "mentions": new_mentions,
            "updated_at": datetime.now(timezone.utc)
        }

        await db.posts.update_one(
            {"_id": ObjectId(post_id)}, 
            {"$set": update_data}
        )
        
        # Merge changes with existing document info for response
        post.update(update_data)
        return post

    @staticmethod
    async def soft_delete_post(
        post_id: str, 
        current_user_id: ObjectId, 
        db: AsyncIOMotorDatabase
    ) -> None:
        """
        Performs an enterprise soft delete by toggling the `is_deleted` flag.
        """
        if not ObjectId.is_valid(post_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid Post ID format"
            )

        post = await db.posts.find_one({"_id": ObjectId(post_id), "is_deleted": False})
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Post not found"
            )
            
        if post["author_id"] != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="You do not have permission to delete this post"
            )

        # Toggle soft delete flag rather than using .delete_one()
        await db.posts.update_one(
            {"_id": ObjectId(post_id)}, 
            {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc)}}
        )