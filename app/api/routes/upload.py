"""
File upload and processing routes
"""
import os
import uuid
import shutil
from fastapi import APIRouter, Request, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import get_current_user
from app.core.database import db_manager
from app.services.file_processor import process_uploaded_file

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_user_info(user_id: int):
    """Get user information by ID"""
    return db_manager.get_user_by_id(user_id)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with file upload form"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)
    
    user = get_user_info(user_id)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@router.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """Handle file upload and processing"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        # Validate file type
        if not file.filename or not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
        # Generate unique ID for this upload
        file_id = str(uuid.uuid4())
        
        # Save uploaded file with user-specific directory
        user_upload_dir = f"uploads/user_{user_id}"
        os.makedirs(user_upload_dir, exist_ok=True)
        upload_path = f"{user_upload_dir}/{file_id}_{file.filename}"
        
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Store in database with user_id
        db_manager.create_file_upload(file_id, user_id, file.filename, upload_path)
        
        # Process the file
        try:
            result = process_uploaded_file(upload_path, file_id, user_id)
            user = get_user_info(user_id)
            return templates.TemplateResponse("results.html", {
                "request": request, 
                "file_id": file_id,
                "filename": file.filename,
                "result": result,
                "user": user
            })
        except Exception as e:
            user = get_user_info(user_id)
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": str(e),
                "user": user
            })
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
