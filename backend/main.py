"""Cender API - FastAPI application entry point."""

from api.exception_handlers import register_exception_handlers
from api.routers import emails, gmail, recipients, templates, users
from config import settings
from database import Base, engine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from utils.logger import logger

app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.on_event("startup")
def on_startup():
    """Create database tables on startup."""
    Base.metadata.create_all(bind=engine)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register global exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(users.router)
app.include_router(gmail.router)
app.include_router(templates.router)
app.include_router(recipients.router)
app.include_router(emails.router)

logger.info(f"Starting {settings.app_name} v{settings.app_version}")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Cender API"}
