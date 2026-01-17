"""
FastAPI application entry point for Grader Vision API.

This is the main application file that configures and runs the FastAPI server.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db, close_db
from .api.v0 import grading as grading_v0
from .api.v0 import users as users_v0
from .api.v0 import auth as auth_v0
from .api.v0 import rubric_generator as rubric_generator_v0
from .services.temp_storage_service import start_cleanup_worker

# Configure logging
import os
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_tracing():
    """Configure LangChain/LangSmith tracing based on settings."""
    if settings.langchain_tracing_v2.lower() == "true":
        logger.info("Enabling LangSmith tracing...")
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
        if settings.langchain_api_key:
            os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        if settings.langchain_project:
            os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        logger.info(f"LangSmith project: {os.environ.get('LANGCHAIN_PROJECT')}")
    else:
        logger.info("LangSmith tracing is disabled")



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Grader Vision API...")
    
    # Configure tracing
    setup_tracing()
    
    import asyncio
    asyncio.create_task(init_db())
    logger.info("Database initialization started in background")
    
    # Start temp storage cleanup worker (capture task for cancellation)
    cleanup_task = start_cleanup_worker()
    logger.info("Temp storage cleanup worker started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Grader Vision API...")
    
    # Cancel cleanup worker
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            logger.info("Cleanup worker cancelled")
    
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="Grader Vision API",
    description="""
    Automated test grading API using Vision AI.
    
    ## Features
    
    * **Rubric Extraction**: Upload rubric PDFs and extract structured grading criteria
    * **Test Grading**: Grade student tests against rubrics using GPT-4
    * **PDF Annotation**: Create annotated PDFs with grading feedback
    * **Data Retrieval**: Access stored rubrics, graded tests, and annotated PDFs
    
    ## Endpoints
    
    All grading endpoints are under `/api/v0/grading/`
    """,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
# Parse allowed origins from config (comma-separated string)
allowed_origins = [origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()]
logger.info(f"CORS allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(grading_v0.router)
app.include_router(users_v0.router)
app.include_router(auth_v0.router)
app.include_router(rubric_generator_v0.router)


@app.get("/", tags=["health"])
async def root():
    """Root endpoint - API information."""
    return {
        "name": "Grader Vision API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy"}
