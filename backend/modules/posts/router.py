from fastapi import APIRouter, Depends, status, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from db.mongo import get_database
from dependencies.auth import get_current_user
from .schemas import PostCreate, PostUpdate, PostResponse
from .service import PostService

router = APIRouter(prefix="/posts", tags=["Posts Core"])

@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_new_post(
    payload: PostCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Publish a new post. Automatically extracts mentions and tags."""
    new_post = await PostService.create_post(
        payload=payload, 
        current_user=current_user, 
        db=db
    )
    return PostResponse(**new_post)

@router.get("/{post_id}", response_model=PostResponse)
async def get_single_post(
    post_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Retrieve details for a specific post by ID."""
    post = await PostService.get_post_by_id(
        post_id=post_id, 
        current_user_id=current_user["_id"], 
        db=db
    )
    return PostResponse(**post)

@router.put("/{post_id}", response_model=PostResponse)
async def update_existing_post(
    post_id: str,
    payload: PostUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Modify text content of an existing post. Must be the original author."""
    updated_post = await PostService.update_post(
        post_id=post_id,
        payload=payload,
        current_user_id=current_user["_id"],
        db=db
    )
    return PostResponse(**updated_post)

@router.delete("/{post_id}", status_code=status.HTTP_24_NO_CONTENT)
async def delete_post(
    post_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Soft delete a post. Document remains archived in DB but hidden from APIs."""
    await PostService.soft_delete_post(
        post_id=post_id,
        current_user_id=current_user["_id"],
        db=db
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)