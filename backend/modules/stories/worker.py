import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorDatabase
from .service import StoryService

logger = logging.getLogger(__name__)

async def run_story_janitor(db: AsyncIOMotorDatabase, interval_seconds: int = 300):
    """
    The background loop. Wakes up every 5 minutes (300 seconds), 
    cleans up expired stories, and goes back to sleep.
    """
    logger.info("Story Janitor background worker started.")
    
    while True:
        try:
            # 1. Run the cleanup logic we built in the service
            await StoryService.cleanup_expired_stories(db)
        except Exception as e:
            # If the database drops connection, we catch the error here 
            # so it doesn't crash the entire background task forever.
            logger.error(f"Story Janitor encountered a critical error: {e}")
        
        # 2. Go to sleep, yielding control back to FastAPI so it can handle user requests
        await asyncio.sleep(interval_seconds)