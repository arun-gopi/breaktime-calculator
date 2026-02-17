import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:changeme123@localhost:5432/breaktime_calculator")
    
    # Security
    SESSION_SECRET_KEY: str = os.getenv("SESSION_SECRET_KEY", "dev-secret-key-change-in-production")
    SECURE_COOKIES: bool = os.getenv("SECURE_COOKIES", "false").lower() == "true"
    SESSION_TIMEOUT: timedelta = timedelta(hours=8)
    
    # Server
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", 8000))
    
    # File Upload
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS: set = {".csv"}
    
    # Directories
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "output"
    STATIC_DIR: str = "static"
    TEMPLATES_DIR: str = "templates"

settings = Settings()
