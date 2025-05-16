from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
import logging
import os
from logging.handlers import RotatingFileHandler
import psutil

from app.api.routes import auth, users, groups, documents, chat, email, export, tags
from app.api.routes import export_word
from app.core.config import settings
from app.db.session import engine
from app.db import models

# Configure logging with rotating file handler to prevent log overflow
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Remove existing handlers to avoid duplicates
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Add rotating file handler (10MB max size, keep 5 backup files)
file_handler = RotatingFileHandler(
    os.path.join(log_dir, "app.log"),
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
root_logger.addHandler(file_handler)

# Add console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
root_logger.addHandler(console_handler)

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Log system information
logger = logging.getLogger(__name__)
logger.info("Starting GRANTHIK API")
logger.info(f"Python process ID: {os.getpid()}")
memory_info = psutil.virtual_memory()
logger.info(f"System memory: Total={memory_info.total/1024/1024:.1f}MB, Available={memory_info.available/1024/1024:.1f}MB")

app = FastAPI(
    title="GRANTHIK API",
    description="API for GRANTHIK document management and retrieval system",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.API_V1_STR, tags=["Authentication"])
app.include_router(users.router, prefix=settings.API_V1_STR, tags=["Users"])
app.include_router(groups.router, prefix=settings.API_V1_STR, tags=["Groups"])
app.include_router(documents.router, prefix=settings.API_V1_STR, tags=["Documents"])
app.include_router(tags.router, prefix=settings.API_V1_STR, tags=["Tags"])
app.include_router(chat.router, prefix=settings.API_V1_STR, tags=["Chat"])
app.include_router(email.router, prefix=settings.API_V1_STR, tags=["Email"])
app.include_router(export.router, prefix=settings.API_V1_STR, tags=["Export"])
app.include_router(export_word.router, prefix=settings.API_V1_STR, tags=["Export"])

@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}