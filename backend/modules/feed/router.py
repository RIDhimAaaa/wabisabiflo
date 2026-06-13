from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime

from db.mongo import get_database
from dependencies.auth import get_current_user

# Notice we import the exact schema we built in the Posts module earlier!
from modules.posts.schemas import PaginatedFeedResponse, PostResponse
from .service import FeedService

router = APIRouter(prefix="/feed", tags=["Content Distribution"])

@router.get("/following", response_model=PaginatedFeedResponse)
async def get_following_feed(
    cursor: datetime | None = Query(None, description="ISO timestamp for pagination"),
    limit: int = Query(15, ge=1, le=50, description="Items per page"),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Fetch the chronological timeline of posts from users the current user follows.
    Pass the 'next_cursor' from the previous response into the 'cursor' query param for infinite scroll.
    """
    return await FeedService.get_chronological_feed(
        current_user_id=current_user["_id"],
        db=db,
        cursor=cursor,
        limit=limit
    )



@router.get("/foryou", response_model=list[PostResponse])
async def get_foryou_feed(
    limit: int = Query(15, ge=1, le=50, description="Items per page"),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    The Algorithmic Feed. 
    Returns posts from across the platform, ranked by the user's specific interests.
    """
    posts = await FeedService.get_algorithmic_feed(
        current_user_id=current_user["_id"],
        db=db,
        limit=limit
    )
    
    return [PostResponse(**post) for post in posts]