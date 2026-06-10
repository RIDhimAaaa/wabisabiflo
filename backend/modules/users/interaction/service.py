from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timezone

from .schemas import FollowActionResponse, PendingRequestItem
from modules.users.profile.schemas import UserSearchResult

class InteractionService:
    @staticmethod
    async def follow_user(
        follower_id: str, 
        target_username: str, 
        db: AsyncIOMotorDatabase
    ) -> FollowActionResponse:
        """Handles the complex logic of following a public vs. private user."""
        
        # 1. Look up the target user
        target_user = await db.users.find_one({"username": target_username})
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        target_id = str(target_user["_id"])

        # 2. Prevent self-follows (You can't be your own biggest fan)
        if follower_id == target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="You cannot follow yourself"
            )

        # 3. Check if they are already actively following
        existing_follow = await db.follows.find_one({
            "follower_id": follower_id, 
            "following_id": target_id
        })
        if existing_follow:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="You are already following this user"
            )

        # 4. The Privacy Branch (The State Machine)
        is_private = target_user.get("is_private", False)

        if is_private:
            # Check if a pending request already exists
            existing_request = await db.follow_requests.find_one({
                "requester_id": follower_id,
                "target_id": target_id
            })
            if existing_request:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail="Follow request already sent"
                )
            
            # Create the Pending Request
            await db.follow_requests.insert_one({
                "requester_id": follower_id,
                "target_id": target_id,
                "created_at": datetime.now(timezone.utc)
            })
            return FollowActionResponse(
                message="Follow request sent successfully", 
                status="requested"
            )

        else:
            # Public Account: Create the instant Follow Edge
            await db.follows.insert_one({
                "follower_id": follower_id,
                "following_id": target_id,
                "created_at": datetime.now(timezone.utc)
            })
            return FollowActionResponse(
                message="Successfully followed user", 
                status="following"
            )

    @staticmethod
    async def unfollow_user(
        follower_id: str, 
        target_username: str, 
        db: AsyncIOMotorDatabase
    ):
        """Removes a follow edge OR cancels a pending follow request."""
        
        target_user = await db.users.find_one({"username": target_username})
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
        target_id = str(target_user["_id"])

        # Attempt to delete an active follow
        follow_result = await db.follows.delete_one({
            "follower_id": follower_id,
            "following_id": target_id
        })

        # If they weren't actively following, maybe they are trying to cancel a pending request?
        if follow_result.deleted_count == 0:
            request_result = await db.follow_requests.delete_one({
                "requester_id": follower_id,
                "target_id": target_id
            })
            
            if request_result.deleted_count == 0:
                # They didn't follow them, AND they didn't have a request pending.
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, 
                    detail="You are not following this user"
                )
                
            return {"message": "Follow request cancelled"}

        return {"message": "Successfully unfollowed user"}
    
    # ... accept/decline logic ...

    @staticmethod
    async def accept_follow_request(
        target_id: str, 
        requester_username: str, 
        db: AsyncIOMotorDatabase
    ):
        """Converts a pending request into an active follow edge."""
        
        # 1. Find the person who sent the request
        requester = await db.users.find_one({"username": requester_username})
        if not requester:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
        requester_id = str(requester["_id"])

        # 2. Find and delete the pending request atomically
        # find_one_and_delete ensures we don't accidentally duplicate data if they click twice
        deleted_request = await db.follow_requests.find_one_and_delete({
            "requester_id": requester_id,
            "target_id": target_id
        })

        if not deleted_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Follow request not found"
            )

        # 3. Create the official Follow Edge
        await db.follows.insert_one({
            "follower_id": requester_id,
            "following_id": target_id,
            "created_at": datetime.now(timezone.utc)
        })

        return {"message": f"Successfully accepted follow request from {requester_username}"}

    @staticmethod
    async def decline_follow_request(
        target_id: str, 
        requester_username: str, 
        db: AsyncIOMotorDatabase
    ):
        """Silently rejects a pending follow request."""
        
        requester = await db.users.find_one({"username": requester_username})
        if not requester:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
        requester_id = str(requester["_id"])

        # Just delete the request. No new edge is created.
        result = await db.follow_requests.delete_one({
            "requester_id": requester_id,
            "target_id": target_id
        })

        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Follow request not found"
            )

        return {"message": f"Declined follow request from {requester_username}"}
    
    # ... fetching the pending requests ...

    @staticmethod
    async def get_pending_requests(user_id: str, db: AsyncIOMotorDatabase) -> list[PendingRequestItem]:
        """Fetches all pending follow requests for the logged-in private user."""
        
        # 1. Pull all matching request documents
        cursor = db.follow_requests.find({"target_id": user_id})
        requests = await cursor.to_list(length=100) # Cap at 100 to avoid overloading memory
        
        if not requests:
            return []

        # 2. Extract all unique requester IDs into a list
        requester_ids = [ObjectId(req["requester_id"]) for req in requests]

        # 3. Fetch the public identities of all those requesters in a single batch query
        # Using $in is significantly faster than querying users one by one in a loop!
        users_cursor = db.users.find(
            {"_id": {"$in": requester_ids}},
            {"username": 1, "full_name": 1, "profile_picture": 1} # Projection: Only pull what we need
        )
        users = await users_cursor.to_list(length=len(requester_ids))

        # Map users by string ID for O(1) lookup speed when parsing the final array
        user_map = {str(u["_id"]): u for u in users}

        # 4. Synthesize the final payload matching the PendingRequestItem schema
        output = []
        for req in requests:
            req_id_str = req["requester_id"]
            user_info = user_map.get(req_id_str)
            
            # Defensive check: if a user was hard deleted, skip the orphaned request gracefully
            if not user_info:
                continue
                
            output.append(PendingRequestItem(
                request_id=str(req["_id"]),
                requester_username=user_info["username"],
                requester_full_name=user_info.get("full_name"),
                profile_picture=user_info.get("profile_picture"),
                created_at=req["created_at"]
            ))

        return output
    
    # ... (inside your InteractionService class, below your request logic) ...

    @staticmethod
    async def get_followers(
        target_username: str, 
        current_user_id: str, 
        db: AsyncIOMotorDatabase
    ) -> list[UserSearchResult]:
        """Fetches the list of people following a user, enforcing privacy rules."""
        
        target_user = await db.users.find_one({"username": target_username})
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
        target_id = str(target_user["_id"])

        # 🛑 THE PRIVACY GATE
        # If the account is private, AND the person asking is not the owner...
        if target_user.get("is_private", False) and target_id != current_user_id:
            # Check if the person asking is an approved follower
            is_follower = await db.follows.find_one({
                "follower_id": current_user_id,
                "following_id": target_id
            })
            if not is_follower:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="This account is private. Follow them to see their followers."
                )

        # 1. Get the Follow Edges (Who is following the target?)
        cursor = db.follows.find({"following_id": target_id})
        edges = await cursor.to_list(length=100) # Cap at 100 for pagination
        
        if not edges:
            return []

        # 2. Extract IDs and batch query the users
        follower_ids = [ObjectId(edge["follower_id"]) for edge in edges]
        
        users_cursor = db.users.find(
            {"_id": {"$in": follower_ids}},
            {"username": 1, "full_name": 1, "profile_picture": 1}
        )
        users = await users_cursor.to_list(length=len(follower_ids))

        # 3. Format as UserSearchResult
        return [UserSearchResult(**user) for user in users]

    @staticmethod
    async def get_following(
        target_username: str, 
        current_user_id: str, 
        db: AsyncIOMotorDatabase
    ) -> list[UserSearchResult]:
        """Fetches the list of people a user is following, enforcing privacy rules."""
        
        target_user = await db.users.find_one({"username": target_username})
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
        target_id = str(target_user["_id"])

        # 🛑 THE PRIVACY GATE
        if target_user.get("is_private", False) and target_id != current_user_id:
            is_follower = await db.follows.find_one({
                "follower_id": current_user_id,
                "following_id": target_id
            })
            if not is_follower:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="This account is private. Follow them to see who they follow."
                )

        # 1. Get the Follow Edges (Who is the target following?)
        cursor = db.follows.find({"follower_id": target_id})
        edges = await cursor.to_list(length=100)
        
        if not edges:
            return []

        # 2. Extract IDs and batch query the users
        following_ids = [ObjectId(edge["following_id"]) for edge in edges]
        
        users_cursor = db.users.find(
            {"_id": {"$in": following_ids}},
            {"username": 1, "full_name": 1, "profile_picture": 1}
        )
        users = await users_cursor.to_list(length=len(following_ids))

        return [UserSearchResult(**user) for user in users]