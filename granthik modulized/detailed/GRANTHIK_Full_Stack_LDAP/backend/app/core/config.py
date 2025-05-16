import os
from typing import List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # API settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "GRANTHIK"
    
    # CORS settings
    CORS_ORIGINS: List[str] = ["*", "http://localhost:8801", "http://localhost", "http://127.0.0.1:8801"]  # Allow all origins
    
    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-for-development-only")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200"))  # 30 days default
    
    # Database settings
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "8803")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "granthik")
    SQLALCHEMY_DATABASE_URI: str = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"
    
    # Vector DB settings
    VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", "chroma_data")
    
    # External services
    UNSTRUCTURED_URL: str = os.getenv("UNSTRUCTURED_URL", "http://host.docker.internal:9500/general/v0/general")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434/api/generate")
    
    # LLM settings
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "mistral:latest")
    MAX_TOKENS: int = 4096
    TOP_K: int = 10
    
    # File storage
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", 524288000))  # 500MB default to match Nginx
    
    # Email settings
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "aashit@erudites.in")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "ckqsuqhwkamrzsvw")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "aashit@erudites.in")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "True").lower() == "true"
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "False").lower() == "true"
    
    class Config:
        case_sensitive = True

settings = Settings()