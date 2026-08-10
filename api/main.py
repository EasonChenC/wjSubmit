# api/main.py
"""
FastAPI Application Entry Point

Questionnaire Automation REST API Service.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.session import init_engine, close_engine
from .routers import questionnaire, ai


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
    allow_origins=["*"],  # Should restrict to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register router
app.include_router(questionnaire.router)
app.include_router(ai.router)


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
