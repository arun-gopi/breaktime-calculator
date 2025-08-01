"""
Legacy entry point for backward compatibility
This file maintains compatibility with existing deployment scripts
"""
from app.main import app

if __name__ == "__main__":
    import uvicorn
    import os
    
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
