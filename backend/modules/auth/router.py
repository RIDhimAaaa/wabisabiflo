from fastapi import APIRouter, status, Depends, BackgroundTasks, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase
import jwt

from db.mongo import get_database
from config import settings
from .schemas import UserCreate, UserResponse, Token
from .services import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user: UserCreate, 
    background_tasks: BackgroundTasks, 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await AuthService.register_new_user(user, background_tasks, db)

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await AuthService.authenticate_user(form_data, db)

@router.get("/verify/{token}")
async def verify_email(token: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=400, detail="Invalid token payload")
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    result = await db.users.update_one({"email": email}, {"$set": {"is_verified": True}})
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="User not found or already verified")

    return {"message": "Email successfully verified!"}