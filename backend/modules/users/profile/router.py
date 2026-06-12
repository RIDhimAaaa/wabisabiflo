from fastapi import APIRouter, Depends, status, Query, HTTPException
from uuid import uuid4
from shared.s3 import S3Service
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.mongo import get_database
from dependencies.auth import get_current_user
from .schemas import PublicProfileResponse, ProfileUpdate, UserSearchResult, AvatarUpdate
from .service import ProfileService

# We don't use a prefix here because we will mount this sub-router 
# directly onto the main /users router later.
router = APIRouter(tags=["Public Profiles"])

# search endpoint MUST come before the /{username} endpoint,
# otherwise FastAPI will try to interpret 'search' as a username and fail.
@router.get("/search", response_model=list[UserSearchResult], status_code=status.HTTP_200_OK)
async def search_users_directory(
    # Query(...) ensures the 'q' parameter is strictly required in the URL (e.g., ?q=ridhima)
    q: str = Query(..., min_length=1, description="The search query"),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Search for users by username or full name."""
    return await ProfileService.search_users(q, db)


@router.get("/{username}", response_model=PublicProfileResponse, status_code=status.HTTP_200_OK)
async def get_user_profile(
    username: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Fetch a public profile by username."""
    # Notice  get_current_user is not required here. 
    # Profiles are public, so anyone can view them without a JWT!
    return await ProfileService.get_public_profile(username, db)


@router.patch("/me/profile", response_model=PublicProfileResponse, status_code=status.HTTP_200_OK)
async def update_my_profile(
    payload: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update public-facing profile fields (bio, avatar, etc)."""
    return await ProfileService.update_profile(
        user_id=str(current_user["_id"]), 
        payload=payload, 
        db=db
    )


@router.get("/me/avatar/presigned-url", status_code=status.HTTP_200_OK)
async def get_avatar_upload_url(
    file_type: str = Query(..., description="e.g., image/jpeg or image/png"),
    current_user: dict = Depends(get_current_user)
):
    """
    Generates a secure, 5-minute URL so the user can upload a new profile picture.
    """
    
    return ProfileService.get_avatar_upload_presigned_url(
        user_id=current_user["_id"],
        file_type=file_type
    )

@router.patch("/me/avatar", response_model=UserSearchResult, status_code=status.HTTP_200_OK)
async def update_avatar_url(
    payload: AvatarUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Updates the user's profile picture URL in the database after a successful S3 upload.
    """
    # Look how clean the router is now! It just passes data to the service.
    updated_user = await ProfileService.update_avatar(
        user_id=current_user["_id"],
        avatar_url=payload.avatar_url,
        db=db
    )

    return UserSearchResult(**updated_user)