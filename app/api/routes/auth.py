"""
Authentication routes for login, registration, and logout
"""
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import create_session, delete_session, get_current_user
from app.core.database import db_manager
from app.core.config import settings

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    # If already logged in, redirect to home
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Handle login"""
    user = db_manager.get_user_by_credentials(username, password)
    
    if user and user.get('is_active'):
        session_id = create_session(user['id'])
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session_id", 
            value=session_id, 
            max_age=int(settings.SESSION_TIMEOUT.total_seconds()),
            httponly=True,
            secure=settings.SECURE_COOKIES,
            samesite="lax"
        )
        return response
    else:
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid username or password"
        })


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page"""
    # If already logged in, redirect to home
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    confirm_password: str = Form(...)
):
    """Handle registration"""
    errors = []
    
    # Validation
    if len(password) < 6:
        errors.append("Password must be at least 6 characters long")
    if password != confirm_password:
        errors.append("Passwords do not match")
    
    # Check if username or email already exists
    result = db_manager.execute_query(
        "SELECT COUNT(*) as count FROM users WHERE username = %s OR email = %s", 
        (username, email), 
        fetch_one=True
    )
    user_count = 0
    if isinstance(result, dict) and 'count' in result:
        user_count = result['count']
    
    if user_count > 0:
        errors.append("Username or email already exists")
    
    if errors:
        return templates.TemplateResponse("register.html", {
            "request": request, 
            "errors": errors,
            "username": username,
            "email": email,
            "full_name": full_name
        })
    
    # Create user
    user_id = db_manager.create_user(username, email, password, full_name)
    
    # Auto-login after registration
    if user_id:
        session_id = create_session(user_id)
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="session_id", 
            value=session_id, 
            max_age=int(settings.SESSION_TIMEOUT.total_seconds()),
            httponly=True,
            secure=settings.SECURE_COOKIES,
            samesite="lax"
        )
        return response


@router.get("/logout")
async def logout(request: Request):
    """Handle logout"""
    session_id = request.cookies.get('session_id')
    if session_id:
        delete_session(session_id)
    
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session_id")
    return response
