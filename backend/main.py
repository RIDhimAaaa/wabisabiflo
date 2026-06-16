import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from config import settings
from db.mongo import connect_to_mongo, close_mongo_connection, get_database
from db.redis import check_redis_connection

# Routers
from modules.auth.router import router as auth_router
from modules.users.router import router as users_router
from modules.users.profile.router import router as profile_router 
from modules.users.interaction.router import router as interaction_router
from modules.posts.router import router as posts_router
from modules.feed.router import router as feed_router
from modules.chat.router import router as chat_router
from modules.stories.router import router as stories_router

# Background Worker
from modules.stories.worker import run_story_janitor
from dependencies.exceptions import validation_exception_handler

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Unified Application Lifecycle Manager.
    Handles startup configuration and graceful shutdowns.
    """
    # ---- STARTUP PHASE ----
    # 1. Boot the storage and caching layer connections
    await connect_to_mongo()
    await check_redis_connection()
    
    # 2. Extract the internal database client engine
    # We call this helper directly here to get the DB connection instance
    db_instance = get_database()
    
    # 3. Spawn the background worker loop in an independent ASGI task
    # This prevents the loop from blocking incoming HTTP/WebSocket traffic
    asyncio.create_task(run_story_janitor(db=db_instance))
    
    yield
    
    # ---- SHUTDOWN PHASE ----
    await close_mongo_connection()

# Initialize FastAPI with the lifespan engine
app = FastAPI(
    title=settings.PROJECT_NAME, 
    lifespan=lifespan,
    exception_handlers={
        RequestValidationError: validation_exception_handler
    }
)

# Routing Table Assembly
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profile_router, prefix="/users") 
app.include_router(interaction_router, prefix="/users")
app.include_router(posts_router)
app.include_router(feed_router)
app.include_router(chat_router)
app.include_router(stories_router)

@app.get("/")
async def health_check():
    return {"status": f"{settings.PROJECT_NAME} backend is alive, cached, and well!"}