from fastapi import HTTPException, status, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase
import jwt
from datetime import timedelta
from config import settings
from .schemas import UserCreate, UserResponse, Token
from .models import UserInDB
from .utils import get_password_hash, verify_password, create_access_token, send_verification_email

class AuthService:
    @staticmethod
    async def register_new_user(
        user: UserCreate, 
        background_tasks: BackgroundTasks, 
        db: AsyncIOMotorDatabase
    ) -> UserResponse:
        # 1. Check existing user
        existing_user = await db.users.find_one({
            "$or": [{"email": user.email}, {"username": user.username}]
        })
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Username or email already registered"
            )

        # 2. Hash & Prepare Document
        hashed_password = get_password_hash(user.password)
        user_in_db = UserInDB(
            username=user.username,
            email=user.email,
            hashed_password=hashed_password
        )
        result = await db.users.insert_one(user_in_db.model_dump())

        # 3. Handle Background Verification Email
        verification_token = create_access_token(
            data={"sub": user.email}, 
            expires_delta=timedelta(hours=24)
        )
        background_tasks.add_task(send_verification_email, user.email, verification_token)

        return UserResponse(
            id=str(result.inserted_id), 
            username=user.username, 
            email=user.email, 
            is_verified=False
        )

    @staticmethod
    async def authenticate_user(form_data, db: AsyncIOMotorDatabase) -> Token:
        user = await db.users.find_one({"email": form_data.username})
        if not user or not verify_password(form_data.password, user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Incorrect email or password"
            )
        
        if not user.get("is_verified", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Please verify your email before logging in"
            )

        access_token = create_access_token(data={"sub": str(user["_id"])})
        return Token(access_token=access_token, token_type="bearer")