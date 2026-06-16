from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
from typing import Optional

class StoryCreate(BaseModel):
    media_url: str
    media_type: str = Field(..., pattern="^(image|video)$")
    caption: Optional[str] = Field(None, max_length=100)

class StoryViewer(BaseModel):
    user_id: str
    username: str
    profile_picture: Optional[str]
    viewed_at: datetime

class StoryResponse(BaseModel):
    id: str
    author_id: str
    media_url: str
    media_type: str
    caption: Optional[str]
    created_at: datetime
    expires_at: datetime
    views_count: int = 0