import jwt
from datetime import timedelta
from fastapi import HTTPException, status, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import settings
from .schemas import UserCreate, UserResponse
from .utils import create_access_token, create_refresh_token, send_verification_email, verify_password, get_password_hash


class AuthService:

    @staticmethod
    async def register_new_user(user_data: UserCreate, background_tasks: BackgroundTasks, db: AsyncIOMotorDatabase):
        existing_user = await db.users.find_one({"email": user_data.email})
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        
        hashed_password = get_password_hash(user_data.password)
        user_dict = user_data.model_dump()
        user_dict["hashed_password"] = hashed_password
        del user_dict["password"]
        user_dict["is_verified"] = False
        
        result = await db.users.insert_one(user_dict)
        
        # Handle Background Verification Email
        # Note: This token will expire in 15 minutes because it uses create_access_token
        verification_token = create_access_token(data={"sub": user_data.email})
        background_tasks.add_task(send_verification_email, user_data.email, verification_token)

        return UserResponse(
            id=str(result.inserted_id), 
            username=user_data.username, 
            email=user_data.email, 
            is_verified=False
        )

    @staticmethod
    async def authenticate_user(email: str, password: str, db: AsyncIOMotorDatabase):
        """Authenticate user by email and password."""
        user = await db.users.find_one({"email": email})
        if not user:
            return False
            
        
        if not verify_password(password, user["hashed_password"]):
            return False
        
        if not user.get("is_verified", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Please verify your email before logging in"
            )
        
        return user

    @staticmethod
    def verify_and_refresh_token(refresh_token: str) -> str:
        """Verifies the refresh token and returns a new access token."""
        try:
            payload = jwt.decode(
                refresh_token, 
                settings.SECRET_KEY, 
                algorithms=[settings.ALGORITHM]
            )
            
            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, 
                    detail="Invalid token type"
                )
            
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, 
                    detail="Invalid token payload"
                )
                
            return create_access_token(data={"sub": user_id})
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Refresh token expired. Please log in again."
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid refresh token"
            )