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
    
    

    @staticmethod
    async def get_followers(
        target_username: str, 
        current_user_id: str, 
        db: AsyncIOMotorDatabase,
        cursor: str | None = None,
        limit: int = 20
    ) -> dict:
        """Fetches the list of people following a user, using cursor pagination."""
        
        target_user = await db.users.find_one({"username": target_username})
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
        target_id = str(target_user["_id"])

        # THE PRIVACY GATE (Unchanged)
        if target_user.get("is_private", False) and target_id != current_user_id:
            is_follower = await db.follows.find_one({
                "follower_id": current_user_id,
                "following_id": target_id
            })
            if not is_follower:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="This account is private. Follow them to see their followers."
                )

        # 1. Build the Paginated Query
        query = {"following_id": target_id}
        if cursor:
            # Fetch edges strictly older than the cursor
            query["_id"] = {"$lt": ObjectId(cursor)}

        # 2. Get the Follow Edges (Using Limit + 1 trick)
        db_cursor = db.follows.find(query).sort("_id", -1).limit(limit + 1)
        edges = await db_cursor.to_list(length=limit + 1)
        
        # 3. Determine the next cursor
        next_cursor = None
        if len(edges) > limit:
            extra_edge = edges.pop()
            next_cursor = str(extra_edge["_id"])

        if not edges:
            return {"items": [], "next_cursor": None}

        # 4. Extract IDs and batch query the users
        follower_ids = [ObjectId(edge["follower_id"]) for edge in edges]
        
        users_cursor = db.users.find(
            {"_id": {"$in": follower_ids}},
            {"username": 1, "full_name": 1, "profile_picture": 1}
        )
        users = await users_cursor.to_list(length=len(follower_ids))

        # 5. Format and return the paginated payload
        return {
            "items": [UserSearchResult(**user) for user in users],
            "next_cursor": next_cursor
        }

    @staticmethod
    async def get_following(
        target_username: str, 
        current_user_id: str, 
        db: AsyncIOMotorDatabase,
        cursor: str | None = None,
        limit: int = 20
    ) -> dict:
        """Fetches the list of people a user is following, using cursor pagination."""
        
        target_user = await db.users.find_one({"username": target_username})
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
        target_id = str(target_user["_id"])

        # THE PRIVACY GATE (Unchanged)
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

        # 1. Build the Paginated Query
        query = {"follower_id": target_id}
        if cursor:
            query["_id"] = {"$lt": ObjectId(cursor)}

        # 2. Get the Follow Edges (Using Limit + 1 trick)
        db_cursor = db.follows.find(query).sort("_id", -1).limit(limit + 1)
        edges = await db_cursor.to_list(length=limit + 1)
        
        # 3. Determine the next cursor
        next_cursor = None
        if len(edges) > limit:
            extra_edge = edges.pop()
            next_cursor = str(extra_edge["_id"])
        
        if not edges:
            return {"items": [], "next_cursor": None}

        # 4. Extract IDs and batch query the users
        following_ids = [ObjectId(edge["following_id"]) for edge in edges]
        
        users_cursor = db.users.find(
            {"_id": {"$in": following_ids}},
            {"username": 1, "full_name": 1, "profile_picture": 1}
        )
        users = await users_cursor.to_list(length=len(following_ids))

        # 5. Format and return the paginated payload
        return {
            "items": [UserSearchResult(**user) for user in users],
            "next_cursor": next_cursor
        }
    
    
    # ... block/unblock system ...

    @staticmethod
    async def block_user(
        blocker_id: str, 
        target_username: str, 
        db: AsyncIOMotorDatabase
    ):
        """Blocks a user and completely severs any existing social ties."""
        
        target_user = await db.users.find_one({"username": target_username})
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
        target_id = str(target_user["_id"])

        if blocker_id == target_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot block yourself")

        # 1. Check if already blocked
        existing_block = await db.blocks.find_one({
            "blocker_id": blocker_id,
            "blocked_id": target_id
        })
        if existing_block:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already blocked")

        # 2. Insert the Block Record
        await db.blocks.insert_one({
            "blocker_id": blocker_id,
            "blocked_id": target_id,
            "created_at": datetime.now(timezone.utc)
        })

        # 3. The Purge: Destroy all connections in BOTH directions
        # Using $or allows us to delete everything in a single database trip
        sever_query = {
            "$or": [
                {"follower_id": blocker_id, "following_id": target_id},
                {"follower_id": target_id, "following_id": blocker_id}
            ]
        }
        await db.follows.delete_many(sever_query)

        sever_requests_query = {
            "$or": [
                {"requester_id": blocker_id, "target_id": target_id},
                {"requester_id": target_id, "target_id": blocker_id}
            ]
        }
        await db.follow_requests.delete_many(sever_requests_query)

        return {"message": f"Successfully blocked {target_username}"}

    @staticmethod
    async def unblock_user(
        blocker_id: str, 
        target_username: str, 
        db: AsyncIOMotorDatabase
    ):
        """Removes a block. Does NOT restore previous follows."""
        
        target_user = await db.users.find_one({"username": target_username})
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
        target_id = str(target_user["_id"])

        result = await db.blocks.delete_one({
            "blocker_id": blocker_id,
            "blocked_id": target_id
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not blocked")

        return {"message": f"Successfully unblocked {target_username}"}
    
    # ... (get blocked users) ...

    @staticmethod
    async def get_blocked_users(
        current_user_id: str, 
        db: AsyncIOMotorDatabase
    ) -> list[UserSearchResult]:
        """Fetches the list of users that the current user has blocked."""
        
        # 1. Get the Block Edges (Who has the current user blocked?)
        cursor = db.blocks.find({"blocker_id": current_user_id})
        blocks = await cursor.to_list(length=100) # Capped for pagination/safety
        
        if not blocks:
            return []

        # 2. Extract the IDs of the blocked users
        blocked_ids = [ObjectId(block["blocked_id"]) for block in blocks]
        
        # 3. Batch query the users collection to get their public profiles
        users_cursor = db.users.find(
            {"_id": {"$in": blocked_ids}},
            {"username": 1, "full_name": 1, "profile_picture": 1} # Only pull what we need
        )
        users = await users_cursor.to_list(length=len(blocked_ids))

        # 4. Return as the lightweight UserSearchResult schema
        return [UserSearchResult(**user) for user in users]