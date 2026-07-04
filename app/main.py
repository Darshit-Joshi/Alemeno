import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import jobs
from app.database import engine
from app.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Modern FastAPI Lifespan manager.
    Executes startup logic before accepting requests, and cleanup logic on shutdown.
    """
    logger.info("Initializing application startup...")
    
    
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified successfully.")
    except Exception as e:
        logger.error(f"Failed to connect or initialize database: {e}")
        raise e
        
    yield  # Application runs and serves traffic here
    
    logger.info("Application shutting down. Cleaning up resources...")
    # Add any graceful shutdown logic here (e.g., disposing database engines)
    engine.dispose()

# Instantiate FastAPI with the lifespan manager
app = FastAPI(
    title="Alemeno AI-Powered Transaction Pipeline",
    description="Asynchronous financial transaction processing, cleaning, and LLM anomaly detection API.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for seamless frontend / testing tool integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to trusted frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the transaction processing router
app.include_router(jobs.router, prefix="/api/v1", tags=["Transaction Jobs"])

@app.get("/", tags=["Health Check"])
def read_root():
    """
    Lightweight container health-check endpoint.
    """
    return {
        "status": "online",
        "service": "AI Transaction Processing API",
        "docs_url": "/docs"
    }