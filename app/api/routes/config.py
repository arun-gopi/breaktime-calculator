"""
Configuration management routes
"""
from fastapi import APIRouter, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Dict, Any

from app.core.database import db_manager
from app.api.routes.auth import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request, user: dict = Depends(get_current_user)):
    """Configuration management page"""
    configs = db_manager.get_all_config()
    
    # Group configs by category for better display
    break_configs = [c for c in configs if c['config_key'].startswith('break_') or c['config_key'] in ['continuous_hours', 'shift_gap_threshold']]
    excluded_configs = [c for c in configs if c['config_key'] == 'excluded_procedure_codes']
    
    return templates.TemplateResponse("config.html", {
        "request": request,
        "user": user,
        "break_configs": break_configs,
        "excluded_configs": excluded_configs,
        "all_configs": configs
    })


@router.post("/config/update")
async def update_config(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Update configuration values"""
    form_data = await request.form()
    
    # Update each configuration value
    for key, value in form_data.items():
        if key.startswith('config_'):
            config_key = key.replace('config_', '')
            
            # Determine config type based on key
            if 'threshold' in config_key or 'shift_gap' in config_key:
                config_type = 'float'
            elif 'duration' in config_key:
                config_type = 'int'
            elif 'continuous_hours' == config_key:
                config_type = 'boolean'
            elif 'excluded_procedure_codes' == config_key:
                config_type = 'list'
            else:
                config_type = 'string'
            
            # Get description for this config
            existing = db_manager.get_config(config_key)
            description = existing['description'] if existing else ''
            
            # Update the configuration
            db_manager.set_config(config_key, str(value), config_type, description)
    
    return RedirectResponse(url="/config", status_code=303)


@router.get("/config/reset")
async def reset_config(request: Request, user: dict = Depends(get_current_user)):
    """Reset configuration to defaults"""
    # Reset to default values
    defaults = [
        ('excluded_procedure_codes', '10 Minute Break,Lead BT,Lunch Break,Sick Leave', 'list', 'Comma-separated list of procedure codes to exclude from work time calculations'),
        ('break_threshold_1', '4.0', 'float', 'First break threshold in hours'),
        ('break_threshold_2', '8.0', 'float', 'Second break threshold in hours'),
        ('break_threshold_3', '12.0', 'float', 'Third break threshold in hours'),
        ('break_duration_1', '10', 'int', 'Duration for first break in minutes'),
        ('break_duration_2', '20', 'int', 'Total duration for two breaks in minutes'),
        ('break_duration_3', '30', 'int', 'Total duration for three breaks in minutes'),
        ('continuous_hours', 'true', 'boolean', 'Use continuous hours for break calculations: timestamps when available, otherwise work + drive time'),
    ]
    
    for config_key, config_value, config_type, description in defaults:
        db_manager.set_config(config_key, config_value, config_type, description)
    
    return RedirectResponse(url="/config", status_code=303)
