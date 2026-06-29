import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db

from app.user.models import User
from app.social.models import Post, Comment, Like  # Register social models

from app.api.v1 import api_router
from app.logging_config import logger
from consts.docs import docs_desc


async def _init_db_with_retry(retries: int = 10, delay: float = 3.0) -> None:
    """
    Attempts to initialize the DB, retrying on transient connection failures.
    Docker's internal DNS can return EAI_AGAIN immediately after container start
    even when depends_on: service_healthy is satisfied.
    """
    for attempt in range(1, retries + 1):
        try:
            await init_db()
            return
        except Exception as exc:
            if attempt == retries:
                logger.error(
                    f"Database connection failed after {retries} attempts. Giving up."
                )
                raise
            logger.warning(
                f"Database not ready (attempt {attempt}/{retries}): {exc}. "
                f"Retrying in {delay}s..."
            )
            await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan handler.
    Performs database initialization and seeds the default admin user.
    """
    logger.info("Initializing database...")
    await _init_db_with_retry()

    yield
    logger.info("Shutting down application...")


app = FastAPI(
    title="Users API — Identity & Access Management",
    description=(docs_desc),
    version="1.0.0",
    lifespan=lifespan,
)

# Register global exception handlers
from app.core.exception_handlers import register_exception_handlers

register_exception_handlers(app)

# Set up CORS middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Register routers:
# Root-level to support exact specification requirements (e.g. /auth/signup, /me)
app.include_router(api_router)

# 3. Debug routes — only available when DEBUG=True (disabled in production)
if settings.DEBUG:
    from app.api.debug.router import router as debug_router

    app.include_router(debug_router)


@app.get("/", tags=["Health Check"])
async def root():
    """Health check endpoint containing basic API metadata."""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }
