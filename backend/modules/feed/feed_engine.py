class RecommendationEngine:
    @staticmethod
    def calculate_post_score(post: dict, user_affinities: dict) -> float:
        """
        The core algorithm. 
        Score = Base Popularity + (Personal Affinity * Weight)
        """
        # 1. Base Engagement Score
        likes = post.get("like_count", 0)
        comments = post.get("comment_count", 0)
        base_score = (likes * 1.0) + (comments * 2.0)

        # 2. Affinity Multiplier
        affinity_score = 0.0
        hashtags = post.get("hashtags", [])
        
        for tag in hashtags:
            # If the user has a recorded interest in this tag, add massive points
            if tag in user_affinities:
                affinity_score += (user_affinities[tag] * 10.0)

        # 3. Final Algorithm Score
        return base_score + affinity_score

    @staticmethod
    def rank_candidates(candidate_posts: list[dict], user_affinities: dict) -> list[dict]:
        """Runs the scoring formula across all candidate posts and sorts them."""
        for post in candidate_posts:
            post["algorithmic_score"] = RecommendationEngine.calculate_post_score(post, user_affinities)
        
        # Sort descending by the highest algorithmic score
        candidate_posts.sort(key=lambda x: x["algorithmic_score"], reverse=True)
        return candidate_posts