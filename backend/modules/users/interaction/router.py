from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.mongo import get_database
from dependencies.auth import get_current_user
from .schemas import FollowActionResponse, PendingRequestItem
from .service import InteractionService
from modules.users.profile.schemas import UserSearchResult

# We don't use a prefix here because we will mount it under /users in main.py
router = APIRouter(tags=["Social Graph"])

@router.post("/{username}/follow", response_model=FollowActionResponse, status_code=status.HTTP_200_OK)
async def follow_user_endpoint(
    username: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Follow a user or send a follow request if their account is private."""
    return await InteractionService.follow_user(
        follower_id=str(current_user["_id"]),
        target_username=username,
        db=db
    )

@router.delete("/{username}/follow", status_code=status.HTTP_200_OK)
async def unfollow_user_endpoint(
    username: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Unfollow a user or cancel a pending follow request."""
    return await InteractionService.unfollow_user(
        follower_id=str(current_user["_id"]),
        target_username=username,
        db=db
    )


@router.post("/requests/{username}/accept", status_code=status.HTTP_200_OK)
async def accept_follow_request_endpoint(
    username: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Accept a pending follow request from a specific user."""
    return await InteractionService.accept_follow_request(
        target_id=str(current_user["_id"]),
        requester_username=username,
        db=db
    )


@router.delete("/requests/{username}/decline", status_code=status.HTTP_200_OK)
async def decline_follow_request_endpoint(
    username: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Decline and remove a pending follow request from a specific user."""
    return await InteractionService.decline_follow_request(
        target_id=str(current_user["_id"]),
        requester_username=username,
        db=db
    )

@router.get("/me/requests", response_model=list[PendingRequestItem], status_code=status.HTTP_200_OK)
async def get_my_follow_requests(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Retrieve all pending follow requests for the authenticated user."""
    return await InteractionService.get_pending_requests(
        user_id=str(current_user["_id"]),
        db=db
    )



@router.get("/{username}/followers", response_model=list[UserSearchResult], status_code=status.HTTP_200_OK)
async def get_user_followers_list(
    username: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a list of users following the target account."""
    return await InteractionService.get_followers(
        target_username=username,
        current_user_id=str(current_user["_id"]),
        db=db
    )

@router.get("/{username}/following", response_model=list[UserSearchResult], status_code=status.HTTP_200_OK)
async def get_user_following_list(
    username: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a list of users the target account is following."""
    return await InteractionService.get_following(
        target_username=username,
        current_user_id=str(current_user["_id"]),
        db=db
    )