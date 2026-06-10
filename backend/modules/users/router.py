from fastapi import APIRouter, Depends, status, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.mongo import get_database
from dependencies.auth import get_current_user
from .schemas import ChangePasswordRequest, AccountSettingsResponse, AccountDeleteRequest, PrivacySettingsUpdate
from .service import AccountService

# This is the master router for the /users prefix
router = APIRouter(prefix="/users", tags=["Account Settings"])

@router.get("/settings", response_model=AccountSettingsResponse)
async def get_my_settings(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Fetch private account settings (email, verification status)."""
    return await AccountService.get_account_settings(str(current_user["_id"]), db)


@router.put("/password", status_code=status.HTTP_200_OK)
async def update_password(
    payload: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Securely change the account password."""
    return await AccountService.change_password(str(current_user["_id"]), payload, db)


@router.patch("/me/privacy", status_code=status.HTTP_200_OK)
async def update_my_privacy(
    payload: PrivacySettingsUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Toggle public/private account status."""
    return await AccountService.update_privacy_settings(
        user_id=str(current_user["_id"]), 
        payload=payload, 
        db=db
    )


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_my_account(
    payload: AccountDeleteRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Permanently delete the account. Requires password confirmation."""
    return await AccountService.delete_account(
        user_id=str(current_user["_id"]),
        payload=payload,
        background_tasks=background_tasks,
        db=db
    )