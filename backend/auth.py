from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta, timezone
import secrets
import os
from typing import Dict

security = HTTPBearer(auto_error=False)

# Simple in-memory session store
sessions: Dict[str, datetime] = {}
SESSION_TIMEOUT = timedelta(hours=24)

def create_session() -> str:
    """Create new session token"""
    token = secrets.token_urlsafe(32)
    sessions[token] = datetime.now(timezone.utc)
    return token

def validate_session(token: str) -> bool:
    """Check if session token is valid and not expired"""
    if token not in sessions:
        return False
    
    created_at = sessions[token]
    if datetime.now(timezone.utc) - created_at > SESSION_TIMEOUT:
        del sessions[token]
        return False
    
    # Refresh session
    sessions[token] = datetime.now(timezone.utc)
    return True

def verify_admin_password(password: str) -> bool:
    """Verify admin password against environment variable"""
    admin_password = os.environ.get('ADMIN_PASSWORD', '')
    return password == admin_password

async def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to require authentication on endpoints"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if not validate_session(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )
    
    return credentials.credentials
