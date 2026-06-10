from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from modules.users.schemas import UserProfileUpdate, UserProfileResponse

class UserService:
    @staticmethod
    async def update_user_profile(
        user_id: str, 
        profile_data: UserProfileUpdate, 
        db: AsyncIOMotorDatabase
    ) -> UserProfileResponse:
        
        # 1. Clean the incoming data
        # exclude_unset=True ensures we only update fields the user ACTUALLY sent.
        # If they only update their bio, we don't want to accidentally delete their profile picture.
        update_data = profile_data.model_dump(exclude_unset=True)
        
        # If the user hit "Save" without actually changing anything, just fetch and return their current profile
        if not update_data:
            return await UserService.get_user_profile_by_id(user_id, db)
            
        # 2. Execute the MongoDB Update
        # We use $set to modify only the specific fields, leaving everything else intact
        updated_user = await db.users.find_one_and_update(
            {"_id": ObjectId(user_id)},
            {"$set": update_data},
            return_document=True # Tells MongoDB to return the NEW updated document, not the old one
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
            
        # 3. Format the response for the frontend
        updated_user["id"] = str(updated_user["_id"])
        return UserProfileResponse(**updated_user)

    @staticmethod
    async def get_user_profile_by_id(user_id: str, db: AsyncIOMotorDatabase) -> UserProfileResponse:
        """Helper function to fetch a profile by its ID"""
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
        
        user["id"] = str(user["_id"])
        return UserProfileResponse(**user)