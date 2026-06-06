from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.mongo import get_database
# Import your Bouncer!
from dependencies.auth import get_current_user 

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    # The Bouncer already did the heavy lifting. 
    # If the code reaches this line, the user's token is valid and their DB document is in 'current_user'.
    
    # We must convert the MongoDB ObjectId to a string before returning it to the browser
    current_user["_id"] = str(current_user["_id"])
    
    # Delete the hashed password from the dictionary so we don't leak it to the frontend!
    del current_user["hashed_password"]
    
    return current_user