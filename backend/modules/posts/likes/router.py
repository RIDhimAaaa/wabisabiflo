from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.mongo import get_database
from dependencies.auth import get_current_user
from ..schemas import LikeToggleResponse  # Pulling from the parent posts directory
from .service import LikeService

router = APIRouter(prefix="/posts", tags=["Post Engagement"])

@router.post("/{post_id}/like", response_model=LikeToggleResponse)
async def toggle_post_like(
    post_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Like or unlike a post in a single click."""
    return await LikeService.toggle_like(
        post_id=post_id,
        current_user_id=current_user["_id"],
        db=db
    )