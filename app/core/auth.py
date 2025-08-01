import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request

from app.core.config import settings

# Session management
SESSIONS = {}  # In production, use Redis or database-backed sessions

def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return hashlib.sha256(password.encode()).hexdigest() == hashed

def create_session(user_id: int) -> str:
    """Create a new session for user"""
    session_id = secrets.token_urlsafe(32)
    SESSIONS[session_id] = {
        'user_id': user_id,
        'created_at': datetime.now(),
        'last_activity': datetime.now()
    }
    return session_id

def get_current_user(request: Request) -> Optional[int]:
    """Get current user from session"""
    session_id = request.cookies.get('session_id')
    if not session_id or session_id not in SESSIONS:
        return None
    
    session = SESSIONS[session_id]
    
    # Check if session is expired
    if datetime.now() - session['last_activity'] > settings.SESSION_TIMEOUT:
        del SESSIONS[session_id]
        return None
    
    # Update last activity
    session['last_activity'] = datetime.now()
    return session['user_id']

def delete_session(session_id: str) -> None:
    """Delete a session"""
    if session_id in SESSIONS:
        del SESSIONS[session_id]
