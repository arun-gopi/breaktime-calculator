from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from dotenv import load_dotenv

from app.api.routes import auth, upload, files
from app.core.database import db_manager

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Break Time Calculator",
    description="Calculate employee break times from timesheet data",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(auth.router, tags=["authentication"])
app.include_router(upload.router, tags=["file-upload"])
app.include_router(files.router, tags=["file-management"])

@app.on_event("startup")
async def startup_event():
    """Initialize database and directories on startup"""
    db_manager.init_database()
    
    # Ensure required directories exist
    directories = ["output", "uploads", "static"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    # Print startup info
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:changeme123@localhost:5432/breaktime_calculator")
    secure_cookies = os.getenv("SECURE_COOKIES", "false").lower() == "true"
    
    print(f"🚀 Break Time Calculator starting...")
    print(f"📄 Database: {database_url}")
    print(f"🔒 Secure cookies: {secure_cookies}")
    print(f"📁 Upload directory: uploads/")
    print(f"📊 Output directory: output/")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
