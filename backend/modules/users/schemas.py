from pydantic import BaseModel, HttpUrl, Field
from typing import Optional

# What the user sends us when they click "Edit Profile"
class UserProfileUpdate(BaseModel):
    bio: Optional[str] = Field(None, max_length=160)
    profile_picture: Optional[HttpUrl] = None
    website: Optional[HttpUrl] = None

# What we send to the frontend when someone views a profile
class UserProfileResponse(BaseModel):
    id: str
    username: str
    bio: Optional[str] = None
    profile_picture: Optional[str] = None
    website: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    is_celebrity: bool