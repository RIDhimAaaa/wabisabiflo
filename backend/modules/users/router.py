from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.mongo import get_database
from dependencies.auth import get_current_user
from modules.users.schemas import UserProfileUpdate, UserProfileResponse
from modules.users.services import UserService

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Fetch the currently logged-in user's profile."""
    # current_user['_id'] is already an ObjectId, we just need to pass it as a string to our service
    return await UserService.get_user_profile_by_id(str(current_user["_id"]), db)


@router.put("/me", response_model=UserProfileResponse)
async def update_my_profile(
    profile_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update the currently logged-in user's profile information."""
    return await UserService.update_user_profile(
        user_id=str(current_user["_id"]), 
        profile_data=profile_data, 
        db=db
    )