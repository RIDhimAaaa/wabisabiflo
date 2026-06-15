from fastapi import APIRouter, Depends, status, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.mongo import get_database
from dependencies.auth import get_current_user
from .schemas import FollowActionResponse, PendingRequestItem, PaginatedUserResult
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



@router.get("/{username}/followers", response_model=PaginatedUserResult, status_code=status.HTTP_200_OK)
async def get_user_followers_list(
    username: str,
    cursor: str | None = Query(None, description="Pagination cursor (ObjectId string)"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a paginated list of users following the target account."""
    return await InteractionService.get_followers(
        target_username=username,
        current_user_id=str(current_user["_id"]),
        db=db,
        cursor=cursor,
        limit=limit
    )

@router.get("/{username}/following", response_model=PaginatedUserResult, status_code=status.HTTP_200_OK)
async def get_user_following_list(
    username: str,
    cursor: str | None = Query(None, description="Pagination cursor (ObjectId string)"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a paginated list of users the target account is following."""
    return await InteractionService.get_following(
        target_username=username,
        current_user_id=str(current_user["_id"]),
        db=db,
        cursor=cursor,
        limit=limit
    )


@router.post("/{username}/block", status_code=status.HTTP_200_OK)
async def block_user_endpoint(
    username: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Block a user and instantly sever all existing follows/requests."""
    return await InteractionService.block_user(
        blocker_id=str(current_user["_id"]),
        target_username=username,
        db=db
    )


@router.delete("/{username}/block", status_code=status.HTTP_200_OK)
async def unblock_user_endpoint(
    username: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Unblock a user."""
    return await InteractionService.unblock_user(
        blocker_id=str(current_user["_id"]),
        target_username=username,
        db=db
    )


@router.get("/me/blocked", response_model=list[UserSearchResult], status_code=status.HTTP_200_OK)
async def get_blocked_users_list(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Retrieve the list of users currently blocked by the authenticated user."""
    return await InteractionService.get_blocked_users(
        current_user_id=str(current_user["_id"]),
        db=db
    )