from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from fastapi import HTTPException
from .feed_engine import RecommendationEngine

class FeedService:
    @staticmethod
    async def get_chronological_feed(
        current_user_id: ObjectId, 
        db: AsyncIOMotorDatabase,
        cursor: datetime | None = None,
        limit: int = 15
    ) -> dict:
        """
        Generates the standard 'Following' timeline using Cursor Pagination.
        """
        # 1. Ask the Identity domain who this user follows
        following_cursor = db.follows.find({"follower_id": current_user_id})
        following_records = await following_cursor.to_list(length=None)
        
        # Extract the exact ObjectIds of the people they follow
        following_ids = [record["following_id"] for record in following_records]
        
        # Always include the user's OWN posts in their feed
        following_ids.append(current_user_id)

        # 2. Build the Base Query (Only active posts from these specific people)
        query = {
            "author_id": {"$in": following_ids},
            "is_deleted": False
        }

        # 3. Apply the Cursor (The Infinite Scroll Engine)
        if cursor:
            # If the frontend passes a cursor, ONLY fetch posts older than that exact millisecond
            query["created_at"] = {"$lt": cursor}

        # 4. Fetch the Posts
        pipeline = [
            {"$match": query},
            {"$sort": {"created_at": -1}}, # Newest first
            {"$limit": limit + 1}, # Fetch ONE extra to see if there is a "next page"
            {
                "$lookup": {
                    "from": "users",
                    "localField": "author_id",
                    "foreignField": "_id",
                    "as": "author_data"
                }
            },
            {"$unwind": "$author_data"}
        ]

        cursor_db = db.posts.aggregate(pipeline)
        posts = await cursor_db.to_list(length=limit + 1)

        # 5. Determine the Next Cursor
        next_cursor = None
        if len(posts) > limit:
            # We found an extra post, meaning there is more data!
            # Pop that extra post off the list, and use its timestamp as the next cursor
            extra_post = posts.pop()
            next_cursor = extra_post["created_at"]

        # 6. Hydrate the response (Author Info and Has_Liked state)
        formatted_posts = []
        for post in posts:
            post["author"] = {
                "_id": post["author_data"]["_id"],
                "username": post["author_data"]["username"],
                "profile_picture": post["author_data"].get("profile_picture")
            }
            
            # Check if current user liked this
            like_exists = await db.likes.find_one({
                "post_id": post["_id"], 
                "user_id": current_user_id
            })
            post["has_liked"] = bool(like_exists)
            
            formatted_posts.append(post)

        return {
            "items": formatted_posts,
            # We convert the datetime cursor to an ISO string so it can travel safely over HTTP
            "next_cursor": next_cursor.isoformat() if next_cursor else None
        }



    @staticmethod
    async def track_user_affinity(user_id: ObjectId, hashtags: list[str], db: AsyncIOMotorDatabase):
        """
        Call this in the background whenever a user likes or comments on a post.
        It updates their digital profile to say "I like these topics".
        """
        if not hashtags:
            return

        # Increment the user's affinity score for each hashtag by 1
        increments = {f"affinities.{tag}": 1 for tag in hashtags}
        
        await db.users.update_one(
            {"_id": user_id},
            {"$inc": increments}
        )

    @staticmethod
    async def get_algorithmic_feed(
        current_user_id: ObjectId, 
        db: AsyncIOMotorDatabase,
        limit: int = 15
    ) -> list[dict]:
        """
        The 'For You' Page. 
        Fetches global candidates, applies the math engine, and returns the customized result.
        """
        # 1. Fetch the user's specific affinity profile
        user = await db.users.find_one({"_id": current_user_id})
        user_affinities = user.get("affinities", {})

        # 2. Candidate Generation: Fetch 100 recent posts from ANYONE on the platform
        pipeline = [
            {"$match": {"is_deleted": False}},
            {"$sort": {"created_at": -1}}, 
            {"$limit": 100}, # Pool size for the algorithm to rank
            {
                "$lookup": {
                    "from": "users",
                    "localField": "author_id",
                    "foreignField": "_id",
                    "as": "author_data"
                }
            },
            {"$unwind": "$author_data"}
        ]
        
        cursor = db.posts.aggregate(pipeline)
        candidate_posts = await cursor.to_list(length=100)

        # 3. Apply the Math
        ranked_posts = RecommendationEngine.rank_candidates(candidate_posts, user_affinities)

        # 4. Format and slice the top results for the frontend
        formatted_posts = []
        # Take only the top 'limit' (e.g., 15) posts after sorting
        for post in ranked_posts[:limit]:
            post["author"] = {
                "_id": post["author_data"]["_id"],
                "username": post["author_data"]["username"],
                "profile_picture": post["author_data"].get("profile_picture")
            }
            
            like_exists = await db.likes.find_one({
                "post_id": post["_id"], 
                "user_id": current_user_id
            })
            post["has_liked"] = bool(like_exists)
            
            formatted_posts.append(post)

        return formatted_posts