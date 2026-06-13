from datetime import datetime, timezone

class RecommendationEngine:
    @staticmethod
    def calculate_post_score(post: dict, user_affinities: dict) -> float:
        """
        The core algorithm. 
        Score = Base Popularity + (Personal Affinity * Weight) + Recency Boost
        """
        # 1. Base Engagement Score
        likes = post.get("like_count", 0)
        comments = post.get("comment_count", 0)
        base_score = (likes * 1.0) + (comments * 2.0)

        # 2. Affinity Multiplier
        affinity_score = 0.0
        hashtags = post.get("hashtags", [])
        
        for tag in hashtags:
            if tag in user_affinities:
                affinity_score += (user_affinities[tag] * 10.0)

        # 3. Recency Boost (The Cold Start Fix)
        recency_boost = 0.0
        created_at = post.get("created_at")
        
        if created_at:
            # Calculate how many hours old the post is
            age_in_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
            age_in_hours = max(0, age_in_seconds / 3600)
            
            # Inverse decay: Starts at 100 points, rapidly drops as hours pass
            recency_boost = 100.0 / (1.0 + age_in_hours)

        # 4. Final Algorithm Score
        return base_score + affinity_score + recency_boost

    @staticmethod
    def rank_candidates(candidate_posts: list[dict], user_affinities: dict) -> list[dict]:
        for post in candidate_posts:
            post["algorithmic_score"] = RecommendationEngine.calculate_post_score(post, user_affinities)
        
        candidate_posts.sort(key=lambda x: x["algorithmic_score"], reverse=True)
        return candidate_posts