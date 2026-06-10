from pydantic import BaseModel, Field, HttpUrl

# ---------------------------------------
# Inbound: Updating the Profile
# ---------------------------------------
class ProfileUpdate(BaseModel):
    """Payload for updating public-facing profile information."""
    full_name: str | None = Field(None, max_length=50, description="Display name, separate from username")
    bio: str | None = Field(None, max_length=160, description="Short biography, Twitter/Instagram style limits")
    website: str | None = Field(None, max_length=100, description="Personal website link")
    profile_picture: str | None = Field(None, description="URL to the hosted avatar image")


# ---------------------------------------
# Outbound: Viewing the Profile
# ---------------------------------------
class PublicProfileResponse(BaseModel):
    """
    The safe, sanitized payload returned to the frontend.
    -> email, passwords, and verification status are STRIPPED.
    """
    username: str
    full_name: str | None = None
    bio: str | None = None
    website: str | None = None
    profile_picture: str | None = None
    
    #will calculate these dynamically from the 'follows' collection later
    follower_count: int = 0
    following_count: int = 0
    
    # The frontend needs to know this so it can render a padlock icon on private accounts
    is_private: bool = False


class UserSearchResult(BaseModel):
    """
    A highly compressed payload used specifically for the search dropdown.
    Keeps the network response lightning fast.
    """
    username: str
    full_name: str | None = None
    profile_picture: str | None = None