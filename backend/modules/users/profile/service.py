import asyncio
from uuid import uuid4
from fastapi import HTTPException, status
from shared.s3 import S3Service
from bson import ObjectId
from pymongo import ReturnDocument
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from .schemas import PublicProfileResponse, ProfileUpdate, UserSearchResult

class ProfileService:
    @staticmethod
    async def get_public_profile(username: str, db: AsyncIOMotorDatabase) -> PublicProfileResponse:
        """
        Fetches a user's public profile and concurrently calculates their social graph stats.
        """
        # 1. Fetch the core user document
        # We query by username since this powers the URL (e.g., wabisabiflo.com/ridhima)
        user = await db.users.find_one({"username": username})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )

        user_id_str = str(user["_id"])

        # 2. The Concurrency Engine
        # We define the two count queries but DO NOT await them yet.
        followers_task = db.follows.count_documents({"following_id": user_id_str})
        following_task = db.follows.count_documents({"follower_id": user_id_str})

        # We use asyncio.gather to fire both queries to the database at the exact same time.
        # This cuts the database latency in half.
        follower_count, following_count = await asyncio.gather(followers_task, following_task)

        # 3. Assemble the payload
        # Notice we don't have to manually delete the email or password here.
        # When we pass this dict into PublicProfileResponse, Pydantic acts as a firewall 
        # and automatically drops any fields that shouldn't be public!
        profile_data = {
            **user, # Unpack the user dictionary
            "follower_count": follower_count,
            "following_count": following_count
        }

        return PublicProfileResponse(**profile_data)

    @staticmethod
    async def update_profile(user_id: str, payload: ProfileUpdate, db: AsyncIOMotorDatabase) -> PublicProfileResponse:
        """
        Allows a user to update their public-facing information (bio, avatar, etc).
        """
        # model_dump(exclude_unset=True) ensures we only update fields the user ACTUALLY sent.
        # If they only send a new bio, it won't overwrite their profile_picture with None.
        update_data = payload.model_dump(exclude_unset=True)
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="No valid fields provided for update"
            )

        # Update the document and return the NEW version
        from pymongo import ReturnDocument
        updated_user = await db.users.find_one_and_update(
            {"_id": ObjectId(user_id)},
            {"$set": update_data},
            return_document=ReturnDocument.AFTER
        )

        if not updated_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # To return the updated PublicProfileResponse, we need to recalculate their counts.
        # We just re-use the function we already wrote!
        return await ProfileService.get_public_profile(updated_user["username"], db)
    
    # ... search engine logic ...

    @staticmethod
    async def search_users(query: str, db: AsyncIOMotorDatabase) -> list[UserSearchResult]:
        """
        Searches for users by username or full name. 
        Strictly limited to 20 results to prevent memory spikes.
        """
        # If the user just clicks the search bar but hasn't typed anything, return empty
        if not query or len(query.strip()) == 0:
            return []

        # Sanitize the query to prevent Regex injection attacks
        import re
        safe_query = re.escape(query.strip())
        
        # The $or operator allows us to search both fields simultaneously.
        # ^ means "starts with", and $options: "i" means case-insensitive.
        search_filter = {
            "$or": [
                {"username": {"$regex": f"^{safe_query}", "$options": "i"}},
                {"full_name": {"$regex": f"^{safe_query}", "$options": "i"}}
            ]
        }

        # We chain .limit(20) directly to the database cursor. 
        # The database stops searching the millisecond it finds 20 matches.
        cursor = db.users.find(search_filter).limit(20)
        
        # Unpack the cursor into a list of dictionaries
        users = await cursor.to_list(length=20)
        
        return [UserSearchResult(**user) for user in users]
    
    # ... avatar logic ...

    @staticmethod
    async def update_avatar(
        user_id: str | ObjectId, 
        avatar_url: str, 
        db: AsyncIOMotorDatabase
    ) -> dict:
        """Updates the user's profile picture URL in the database."""
        
        updated_user = await db.users.find_one_and_update(
            {"_id": user_id},
            {"$set": {"profile_picture": avatar_url}},
            return_document=ReturnDocument.AFTER
        )

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )

        return updated_user

    @staticmethod
    def get_avatar_upload_presigned_url(user_id: str | ObjectId, file_type: str) -> dict:
        """
        Business logic to validate file type, generate a unique S3 key, 
        and request a presigned upload URL from the storage engine.
        """
        # 1. Strict business rule validation
        if not file_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="File must be an image"
            )

        # 2. Process file extension and unique object name
        extension = file_type.split("/")[-1]
        random_hash = uuid4().hex[:8]
        object_name = f"avatars/{str(user_id)}_{random_hash}.{extension}"

        # 3. Call the S3 engine
        return S3Service.generate_presigned_upload(
            object_name=object_name,
            file_type=file_type
        )