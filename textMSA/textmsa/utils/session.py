from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from textmsa.services.data.session_db import get_session_db

serializer = URLSafeTimedSerializer("textmsa-secret-key-change")


def create_session(user_id: str):
    """创建一个新的 Session"""
    session_id = secrets.token_urlsafe(32)
    session_db = get_session_db()
    session_db.create_session(session_id, user_id)
    return session_id


def validate_session(session_id: str):
    """验证 Session ID 是否有效"""
    try:
        unsigned_session_id = serializer.loads(session_id)
    except BadSignature:
        print("Invalid session signature.")
        return None
    
    session_db = get_session_db()
    session_data = session_db.get_session(unsigned_session_id)
    session_db.update_session_expiry(unsigned_session_id)
    
    
    if not session_data:
        print("Session data not found in db.")
        return None
    expires_at = datetime.fromisoformat(session_data["expires_at"]).replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        print("Session expired.")
        return None
        
    return session_data


def get_user_id(request: Request):
    # 从请求中获取 Cookie
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session_data = validate_session(session_token)
    if not session_data:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    return session_data["user_id"]
