from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from config import settings
from db.mongo import connect_to_mongo, close_mongo_connection
from modules.auth.router import router as auth_router
from modules.users.router import router as users_router

from modules.users.profile.router import router as profile_router 
from modules.users.interaction.router import router as interaction_router
from modules.posts.router import router as posts_router
from modules.feed.router import router as feed_router
from modules.chat.router import router as chat_router
from dependencies.exceptions import validation_exception_handler
from db.redis import check_redis_connection

# The lifespan context manager handles startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Everything before 'yield' happens when the server starts
    await connect_to_mongo()
    yield
    # Everything after 'yield' happens when the server shuts down
    await close_mongo_connection()

# Initialize FastAPI with the lifespan and project name from .env
app = FastAPI(
    title=settings.PROJECT_NAME, 
    lifespan=lifespan,
    exception_handlers={
        RequestValidationError: validation_exception_handler
    }
)
#testing commit
# Include all the routers here
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profile_router, prefix="/users") 
app.include_router(interaction_router, prefix="/users")
app.include_router(posts_router)
app.include_router(feed_router)
app.include_router(chat_router)

@app.get("/")
async def health_check():
    return {"status": f"{settings.PROJECT_NAME} backend is alive and well!"}

@app.on_event("startup")
async def startup_event():
    # Your existing startup code (like DB connection)
    await check_redis_connection()