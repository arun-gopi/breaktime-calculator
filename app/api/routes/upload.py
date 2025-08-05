"""
File upload and processing routes
"""
import os
import uuid
import shutil
import threading
from fastapi import APIRouter, Request, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import get_current_user
from app.core.database import db_manager
from app.services.file_processor import process_uploaded_file
from app.services.progress_tracker import progress_tracker

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


# @router.post("/upload")
# async def upload_file(request: Request, file: UploadFile = File(...)):
#     """Handle file upload and processing"""
#     user_id = get_current_user(request)
#     if not user_id:
#         return RedirectResponse(url="/login", status_code=302)
    
#     try:
#         # Validate file type
#         if not file.filename or not file.filename.endswith('.csv'):
#             raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
#         # Generate unique ID for this upload
#         file_id = str(uuid.uuid4())
        
#         # Save uploaded file with user-specific directory
#         user_upload_dir = f"uploads/user_{user_id}"
#         os.makedirs(user_upload_dir, exist_ok=True)
#         upload_path = f"{user_upload_dir}/{file_id}_{file.filename}"
        
#         with open(upload_path, "wb") as buffer:
#             shutil.copyfileobj(file.file, buffer)
        
#         # Store in database with user_id
#         db_manager.create_file_upload(file_id, user_id, file.filename, upload_path)
        
#         # Process the file
#         try:
#             result = process_uploaded_file(upload_path, file_id, user_id)
#             user = get_user_info(user_id)
#             return templates.TemplateResponse("results.html", {
#                 "request": request, 
#                 "file_id": file_id,
#                 "filename": file.filename,
#                 "result": result,
#                 "user": user
#             })
#         except Exception as e:
#             user = get_user_info(user_id)
#             return templates.TemplateResponse("error.html", {
#                 "request": request,
#                 "error": str(e),
#                 "user": user
#             })
            
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


def background_process_file(upload_path: str, file_id: str, user_id: int):
    """Background function to process file with progress tracking"""
    try:
        progress_tracker.start_task(file_id, total_steps=100)
        result = process_uploaded_file(upload_path, file_id, user_id, progress_tracker)
        # Complete task with minimal result data to avoid serialization issues
        summary_result = {
            'total_records': result.get('total_records', 0),
            'total_providers': result.get('total_providers', 0),
            'date_range': result.get('date_range', ''),
            'audit_issues_count': result.get('audit_issues_count', 0)
        }
        progress_tracker.complete_task(file_id, summary_result)
    except Exception as e:
        progress_tracker.error_task(file_id, str(e))


@router.post("/upload")
async def upload_file_async(request: Request, file: UploadFile = File(...)):
    """Handle file upload and start background processing"""
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
        
        # Start background processing
        thread = threading.Thread(target=background_process_file, args=(upload_path, file_id, user_id))
        thread.daemon = True
        thread.start()
        
        # Redirect to progress page
        user = get_user_info(user_id)
        return templates.TemplateResponse("processing.html", {
            "request": request,
            "file_id": file_id,
            "filename": file.filename,
            "user": user
        })
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/progress/{file_id}")
async def get_progress(request: Request, file_id: str):
    """Get processing progress for a file"""
    try:
        user_id = get_current_user(request)
        if not user_id:
            return JSONResponse({"error": "Not authenticated"}, status_code=401)
        
        # Verify the file belongs to the user
        upload = db_manager.get_upload_by_id(file_id)
        if not upload or upload.get('user_id') != user_id:
            return JSONResponse({"error": "File not found"}, status_code=404)
        
        progress = progress_tracker.get_progress(file_id)
        if not progress:
            return JSONResponse({"error": "Progress not found"}, status_code=404)
        
        return JSONResponse(progress)
    except Exception as e:
        return JSONResponse({"error": f"Failed to get progress: {str(e)}"}, status_code=500)


@router.get("/processing/{file_id}")
async def processing_page(request: Request, file_id: str):
    """Show processing page for a specific file"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)
    
    # Verify the file belongs to the user
    upload = db_manager.get_upload_by_id(file_id)
    if not upload or upload.get('user_id') != user_id:
        raise HTTPException(status_code=404, detail="File not found")
    
    user = get_user_info(user_id)
    
    # Check if processing is already completed
    progress = progress_tracker.get_progress(file_id)
    if progress and progress.get('status') == 'completed':
        return RedirectResponse(url=f"/results/{file_id}", status_code=302)
    
    return templates.TemplateResponse("processing.html", {
        "request": request,
        "file_id": file_id,
        "filename": upload.get('original_filename', 'Unknown'),
        "user": user
    })


@router.get("/results/{file_id}")
async def results_page(request: Request, file_id: str):
    """Show results page for a completed processing"""
    try:
        user_id = get_current_user(request)
        if not user_id:
            return RedirectResponse(url="/login", status_code=302)
        
        # Verify the file belongs to the user
        upload = db_manager.get_upload_by_id(file_id)
        if not upload or upload.get('user_id') != user_id:
            raise HTTPException(status_code=404, detail="File not found")
        
        user = get_user_info(user_id)
        
        # Get progress to check if completed and get results
        progress = progress_tracker.get_progress(file_id)
        if not progress or progress.get('status') != 'completed':
            return RedirectResponse(url=f"/processing/{file_id}", status_code=302)
        
        result = progress.get('result', {})
        
        # Load additional data from saved files for display
        try:
            import pandas as pd
            
            # Load audit results
            audit_output_path = upload.get('audit_output_path', '')
            audit_results = []
            if audit_output_path and os.path.exists(audit_output_path):
                audit_df = pd.read_csv(audit_output_path)
                if not audit_df.empty:
                    audit_results = audit_df.to_dict('records')
            
            # Load summary data (first 10 for display)
            summary_output_path = upload.get('summary_output_path', '')
            summary_data = []
            if summary_output_path and os.path.exists(summary_output_path):
                summary_df = pd.read_csv(summary_output_path)
                if not summary_df.empty:
                    # Get first 10 records for display
                    summary_data = summary_df.head(10).to_dict('records')
            
            # Add the loaded data to result
            result['audit_results'] = audit_results
            result['summary_data'] = summary_data
            result['summary_data_total_count'] = len(summary_data) if summary_data else 0
            
        except Exception as load_error:
            print(f"Error loading additional result data: {load_error}")
            # Provide empty defaults if file loading fails
            result['audit_results'] = []
            result['summary_data'] = []
            result['summary_data_total_count'] = 0
        
        # Ensure result has default values to prevent template errors
        default_result = {
            'total_records': 0,
            'total_providers': 0,
            'date_range': 'Unknown',
            'audit_issues_count': 0,
            'audit_results': [],
            'summary_data': [],
            'summary_data_total_count': 0
        }
        result = {**default_result, **result}
        
        return templates.TemplateResponse("results.html", {
            "request": request,
            "file_id": file_id,
            "filename": upload.get('original_filename', 'Unknown'),
            "result": result,
            "user": user
        })
    except Exception as e:
        # Log the error and return a user-friendly error page
        print(f"Error in results page: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading results: {str(e)}")
