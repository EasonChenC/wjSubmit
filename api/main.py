# api/main.py
"""
FastAPI Application Entry Point

Questionnaire Automation REST API Service.
"""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from db.session import init_engine, close_engine
from .routers import questionnaire, ai, auth, users


load_dotenv()


def _cors_origins() -> list[str]:
    """Read the comma-separated CORS allow-list from the environment.

    CORS_ORIGINS is intentionally the single source of truth; no localhost
    origins are added implicitly when the setting is absent.
    """
    raw = os.getenv("CORS_ORIGINS", "")
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
    if "*" in origins:
        raise RuntimeError("CORS_ORIGINS must list explicit origins; '*' is not allowed with credentials")
    return origins


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create the DB engine/connection pool once for the app lifetime
    init_engine()
    yield
    # Shutdown: dispose the connection pool
    await close_engine()


# Create FastAPI application
app = FastAPI(
    title="Questionnaire Automation API",
    description="Provides questionnaire analysis, batch submission and reverse item detection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS (allow cross-origin requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# Register router
app.include_router(questionnaire.router)
app.include_router(ai.router)
app.include_router(auth.router)
app.include_router(users.router)


@app.get("/")
async def root():
    """
    Root endpoint

    Returns:
        API basic information
    """
    return {
        "name": "Questionnaire Automation API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "analyze": "POST /api/questionnaire/analyze",
            "submit": "POST /api/questionnaire/submit",
            "task_status": "GET /api/questionnaire/submit/{task_id}",
            "detect": "POST /api/questionnaire/reverse-items",
            "ai_config_get": "GET /api/ai/config",
            "ai_config_set": "POST /api/ai/config",
            "ai_test": "POST /api/ai/test"
        }
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint

    Returns:
        Service status, including database connectivity
    """
    from db.session import check_connection

    db_status = "unknown"
    try:
        await check_connection()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "healthy",
        "service": "questionnaire-automation-api",
        "database": db_status,
    }
