from fastapi import Depends, HTTPException, status, WebSocketException
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
import jwt

from db.mongo import get_database
from config import settings

# This tells FastAPI exactly where the client should go to get a token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise credentials_exception
        
    return user

def verify_ws_token(token: str) -> str:
    """
    Manually decodes a JWT for WebSockets.
    Throws a ValueError if the token is expired or fake.
    """
    try:
        # NOTE: Make sure these variable names match your actual config/settings!
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Depending on how you created the token, this might be payload.get("user_id") 
        # or payload.get("sub"). Adjust accordingly!
        user_id = payload.get("sub") 
        
        if user_id is None:
            raise ValueError("Invalid token payload")
            
        return str(user_id)
        
    except Exception as e: # Catching generic exception to cover expired/invalid tokens
        raise ValueError(f"Token verification failed: {e}")