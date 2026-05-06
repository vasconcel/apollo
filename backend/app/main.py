from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.db.session import init_db
from app.api.routes import screening, stats, articles, extraction, auth
from app.middleware.rate_limit import RateLimitMiddleware


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Initializing database...")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="AIMS API",
    description="Research Synthesis Platform API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

app.include_router(auth.router)
app.include_router(screening.router)
app.include_router(stats.router)
app.include_router(articles.router)
app.include_router(extraction.router)


@app.get("/")
def root():
    return {
        "service": "AIMS API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)