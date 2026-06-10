from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserInDB(BaseModel):
    username: str
    email: EmailStr
    hashed_password: str
    is_verified: bool = False
    is_celebrity: bool = False
    
    # --- New Profile Fields ---
    bio: Optional[str] = None
    profile_picture: Optional[str] = None
    website: Optional[str] = None
    
    # --- Social Graph Counters ---
    # We store these counts directly on the user document so we don't 
    # have to count 10,000 follower records every time a profile loads.
    followers_count: int = 0
    following_count: int = 0
    
    created_at: datetime = Field(default_factory=datetime.utcnow)