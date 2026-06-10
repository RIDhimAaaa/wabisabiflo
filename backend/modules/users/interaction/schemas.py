from pydantic import BaseModel, Field
from datetime import datetime, timezone

# ---------------------------------------
# Internal Database Representations
# ---------------------------------------
class FollowEdge(BaseModel):
    """
    The graph connection. Stored in the 'follows' collection.
    Represents an active, approved relationship.
    """
    follower_id: str = Field(..., description="The person who clicked follow")
    following_id: str = Field(..., description="The person being followed")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FollowRequestEdge(BaseModel):
    """
    The pending connection. Stored in the 'follow_requests' collection.
    Used exclusively when the target account is private.
    """
    requester_id: str
    target_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ---------------------------------------
# API Responses (Outbound to Frontend)
# ---------------------------------------
class FollowActionResponse(BaseModel):
    """
    Tells the frontend what actually happened when they clicked 'Follow'.
    """
    message: str
    # 'status' tells the frontend whether to render a 'Following' or 'Requested' button
    status: str = Field(..., description="Will be 'following' or 'requested'")

class PendingRequestItem(BaseModel):
    """
    A mini-profile payload used to populate the 'Follow Requests' screen
    for private users so they can see who wants to follow them.
    """
    request_id: str
    requester_username: str
    requester_full_name: str | None = None
    profile_picture: str | None = None
    created_at: datetime