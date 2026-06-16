from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List

from db.mongo import get_database
from dependencies.auth import get_current_user
from .schemas import StoryCreate, StoryResponse
from .service import StoryService

router = APIRouter(prefix="/stories", tags=["Stories"])

@router.post("/", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
async def create_new_story(
    story_in: StoryCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Creates a new story in the database. 
    (Assumes the frontend already uploaded the video to S3 using your presigned URL endpoint).
    """
    user_id = str(current_user["_id"])
    return await StoryService.create_story(user_id=user_id, story_in=story_in, db=db)


@router.post("/{story_id}/view", status_code=status.HTTP_200_OK)
async def register_story_view(
    story_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Registers that a user watched a story. 
    Protected by Redis to prevent duplicate views from the same user.
    """
    viewer_id = str(current_user["_id"])
    
    is_new_view = await StoryService.view_story(story_id=story_id, viewer_id=viewer_id, db=db)
    
    if is_new_view:
        return {"message": "View recorded successfully."}
    return {"message": "Already viewed. Ignored."}


@router.get("/feed", response_model=List[StoryResponse])
async def get_active_stories_feed(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Pulls all stories that haven't expired yet.
    (In a fully scaled app, you'd filter this to only show stories from people the user follows).
    """
    from datetime import datetime, timezone
    
    cursor = db.stories.find({
        "expires_at": {"$gt": datetime.now(timezone.utc)},
        "is_deleted": False
    }).sort("created_at", -1).limit(50)
    
    stories = await cursor.to_list(length=50)
    
    # Format for the response
    return [
        StoryResponse(
            id=str(story["_id"]),
            author_id=str(story["author_id"]),
            media_url=story["media_url"],
            media_type=story["media_type"],
            caption=story.get("caption"),
            created_at=story["created_at"],
            expires_at=story["expires_at"],
            views_count=story.get("views_count", 0)
        ) for story in stories
    ]