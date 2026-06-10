from fastapi import HTTPException, status, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from modules.auth.utils import verify_password, get_password_hash
from .schemas import ChangePasswordRequest, AccountSettingsResponse, AccountDeleteRequest, PrivacySettingsUpdate

class AccountService:
    @staticmethod
    async def get_account_settings(user_id: str, db: AsyncIOMotorDatabase) -> AccountSettingsResponse:
        """Fetches the private, core account details for the logged-in user."""
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        user["id"] = str(user["_id"])
        return AccountSettingsResponse(**user)

    @staticmethod
    async def change_password(user_id: str, payload: ChangePasswordRequest, db: AsyncIOMotorDatabase):
        """Securely verifies the old password and updates to the new one."""
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # 1. Verify the current password
        if not verify_password(payload.current_password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Incorrect current password"
            )
        
        # 2. Prevent changing to the exact same password
        if payload.current_password == payload.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="New password cannot be the same as the old password"
            )

        # 3. Hash and save the new password
        new_hashed_password = get_password_hash(payload.new_password)
        
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"hashed_password": new_hashed_password}}
        )
        
        return {"message": "Password updated successfully"}
    
    # ... to update the privacy settings ...

    @staticmethod
    async def update_privacy_settings(
        user_id: str, 
        payload: PrivacySettingsUpdate, 
        db: AsyncIOMotorDatabase
    ):
        """Toggles the account's public/private status."""
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_private": payload.is_private}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
            
        status_text = "private" if payload.is_private else "public"
        return {"message": f"Account is now {status_text}", "is_private": payload.is_private}

    @staticmethod
    async def delete_account(
        user_id: str, 
        payload: AccountDeleteRequest, 
        background_tasks: BackgroundTasks, 
        db: AsyncIOMotorDatabase
    ):
        """Permanently deletes the user account and triggers cleanup of their data."""
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # 1. The Nuclear Key: Verify their password one last time
        if not verify_password(payload.password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Incorrect password. Deletion aborted."
            )

        # 2. Delete the core authentication/identity document
        result = await db.users.delete_one({"_id": ObjectId(user_id)})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Failed to delete account"
            )

        # 3. The Cascade: Trigger the background worker
        # We will write this worker later when we build the interactions and posts modules.
        # It will asynchronously delete their FollowEdges, Posts, and Comments without 
        # making the user wait on a loading screen.
        
        # background_tasks.add_task(cleanup_orphaned_user_data, user_id, db)

        return {"message": "Account permanently deleted. We are sorry to see you go."}