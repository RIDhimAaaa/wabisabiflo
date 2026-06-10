from fastapi import APIRouter, status, Depends, BackgroundTasks, HTTPException, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase
import jwt

from db.mongo import get_database
from config import settings
from .schemas import UserCreate, UserResponse
from .services import AuthService
from .utils import create_access_token, create_refresh_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

#------- register and verify endpoints -------#
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user: UserCreate, 
    background_tasks: BackgroundTasks, 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    return await AuthService.register_new_user(user, background_tasks, db)

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

@router.post("/login")
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    user = await AuthService.authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": str(user["_id"])})
    refresh_token = create_refresh_token(data={"sub": str(user["_id"])})
    
    # Inject the Refresh Token directly into a secure, HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True, 
        samesite="lax",
        max_age=7 * 24 * 60 * 60 
    )
    
    # Send only the Access Token to the JSON response
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/refresh")
async def refresh_token(refresh_token: str = Cookie(None)):
    """Reads the HttpOnly cookie and issues a new Access Token."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Refresh token missing. Please log in."
        )
    
    new_access_token = AuthService.verify_and_refresh_token(refresh_token)
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post("/logout")
async def logout(response: Response):
    """Logs the user out by commanding the browser to delete the refresh cookie."""
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return {"message": "Successfully logged out"}