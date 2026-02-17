"""
File download and history management routes
"""
import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import get_current_user
from app.core.database import db_manager

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_user_info(user_id: int):
    """Get user information by ID"""
    return db_manager.get_user_by_id(user_id)


@router.get("/download/{file_type}/{file_id}")
async def download_file(request: Request, file_type: str, file_id: str):
    """Download generated files"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)
    
    upload_record = db_manager.get_upload_by_id(file_id)
    
    if not upload_record or upload_record['user_id'] != user_id:
        raise HTTPException(status_code=404, detail="File not found")
    
    if file_type == "daily":
        file_path = upload_record.get('daily_output_path')
    elif file_type == "summary":
        file_path = upload_record.get('summary_output_path')
    elif file_type == "provider-date":
        file_path = upload_record.get('provider_date_output_path')
    elif file_type == "audit":
        file_path = upload_record.get('audit_output_path')
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
    
    original_filename = upload_record['original_filename']
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Generate appropriate filename
    base_name = original_filename.replace('.csv', '')
    if file_type == "daily":
        download_filename = f"{base_name}_daily_break_calculation.csv"
    elif file_type == "summary":
        download_filename = f"{base_name}_provider_break_summary.csv"
    elif file_type == "provider-date":
        download_filename = f"{base_name}_provider_date_totals.csv"
    elif file_type == "audit":
        download_filename = f"{base_name}_audit_report.csv"
    
    return FileResponse(
        path=file_path,
        filename=download_filename,
        media_type='text/csv'
    )


@router.get("/download-template")
async def download_template():
    """Download CSV template with required columns"""
    template_path = "static/breaktime_calculator_template.csv"
    
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Template file not found")
    
    return FileResponse(
        path=template_path,
        filename="breaktime_calculator_template.csv",
        media_type='text/csv'
    )


@router.get("/history", response_class=HTMLResponse)
async def file_history(request: Request):
    """View upload history for current user only"""
    user_id = get_current_user(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)
    
    uploads = db_manager.get_user_uploads(user_id)
    
    user = get_user_info(user_id)
    return templates.TemplateResponse("history.html", {
        "request": request,
        "uploads": uploads,
        "user": user
    })
