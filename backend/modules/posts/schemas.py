from pydantic import BaseModel, Field, ConfigDict, BeforeValidator
from typing import Annotated
from datetime import datetime

# -------------------------------------------------------------------
# 0. Custom Types
# -------------------------------------------------------------------
PyObjectId = Annotated[str, BeforeValidator(str)]

# -------------------------------------------------------------------
# 1. Reusable Sub-Entities
# -------------------------------------------------------------------
class MediaItem(BaseModel):
    """Production apps need dimensions and alt text before the image even loads."""
    url: str = Field(..., description="The S3 URL or CDN link")
    media_type: str = Field(..., pattern="^(image|video)$")
    aspect_ratio: float | None = Field(None, description="Width divided by height, prevents UI jumping")
    alt_text: str | None = Field(None, max_length=100, description="Screen reader accessibility")

class AuthorInfo(BaseModel):
    """Embedded inside Posts and Comments to prevent N+1 frontend query problems."""
    id: PyObjectId = Field(alias="_id")
    username: str
    profile_picture: str | None = None
    model_config = ConfigDict(populate_by_name=True)

class LocationMetadata(BaseModel):
    """Optional geo-tagging for posts."""
    name: str
    lat: float | None = None
    lng: float | None = None

# -------------------------------------------------------------------
# 2. Comments Schemas
# -------------------------------------------------------------------
class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)

class CommentResponse(BaseModel):
    id: PyObjectId = Field(alias="_id")
    post_id: PyObjectId
    author: AuthorInfo
    content: str
    created_at: datetime
    model_config = ConfigDict(populate_by_name=True)

# -------------------------------------------------------------------
# 3. Likes Schemas
# -------------------------------------------------------------------
class LikeToggleResponse(BaseModel):
    """Returned when a user likes/unlikes a post so the UI can update instantly."""
    post_id: PyObjectId
    has_liked: bool
    new_like_count: int

# -------------------------------------------------------------------
# 4. Posts Schemas (The Aggregate Root)
# -------------------------------------------------------------------
class PostCreate(BaseModel):
    content: str = Field(..., max_length=2200)
    media: list[MediaItem] = Field(default_factory=list, max_length=10)
    location: LocationMetadata | None = None
    
    # Granular Controls
    allow_comments: bool = True
    hide_like_count: bool = False
    is_close_friends_only: bool = False

class PostUpdate(BaseModel):
    """Typically, platforms only allow editing text/tags, not swapping media."""
    content: str = Field(..., min_length=1, max_length=2200)

class PostResponse(BaseModel):
    id: PyObjectId = Field(alias="_id")
    author: AuthorInfo
    
    # Core Content
    content: str
    media: list[MediaItem] = []
    location: LocationMetadata | None = None
    
    # Extracted Entities (Parsed by backend before saving)
    hashtags: list[str] = []
    mentions: list[str] = []
    
    # Counters & State
    like_count: int = 0
    comment_count: int = 0
    has_liked: bool = False
    
    # Controls & Moderation
    allow_comments: bool
    hide_like_count: bool
    is_flagged_nsfw: bool = False
    is_deleted: bool = False # Soft delete flag
    
    # Time & Audit
    created_at: datetime
    updated_at: datetime | None = None
    
    model_config = ConfigDict(populate_by_name=True)

# -------------------------------------------------------------------
# 5. Feed Pagination
# -------------------------------------------------------------------
class PaginatedFeedResponse(BaseModel):
    """Cursor-based pagination for infinite scrolling."""
    items: list[PostResponse]
    next_cursor: str | None = Field(None, description="Pass to next API call for older posts")