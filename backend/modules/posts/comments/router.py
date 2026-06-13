from fastapi import APIRouter, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.mongo import get_database
from dependencies.auth import get_current_user
from ..schemas import CommentCreate, CommentResponse
from .service import CommentService

router = APIRouter(prefix="/posts", tags=["Post Engagement"])

@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    post_id: str,
    payload: CommentCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Write a new comment on a specific post."""
    new_comment = await CommentService.create_comment(
        post_id=post_id,
        payload=payload,
        current_user=current_user,
        db=db
    )
    return CommentResponse(**new_comment)

@router.get("/{post_id}/comments", response_model=list[CommentResponse])
async def get_comments(
    post_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Load the comment thread for a post."""
    comments = await CommentService.get_comments_for_post(post_id=post_id, db=db)
    return [CommentResponse(**comment) for comment in comments]


@router.get("/comments/{parent_comment_id}/replies", response_model=list[CommentResponse])
async def get_comment_replies(
    parent_comment_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Load the replies for a specific top-level comment."""
    replies = await CommentService.get_replies_for_comment(parent_comment_id=parent_comment_id, db=db)
    return [CommentResponse(**reply) for reply in replies]