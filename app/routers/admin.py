"""Admin endpoints"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Cookie
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Session as SessionModel
from .. import auth
from ..schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    UserListResponse,
    SessionListResponse
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[UserListResponse])
async def list_users(
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """List all users (admin only)"""
    admin_user = auth.get_admin_user(db, session_token)
    if not admin_user:
        raise HTTPException(status_code=403, detail="Admin access required")

    users = db.query(User).all()
    return [UserListResponse.from_orm(user) for user in users]


@router.post("/users", response_model=UserListResponse)
async def create_user(
    request: CreateUserRequest,
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """Create a new user (admin only)"""
    admin_user = auth.get_admin_user(db, session_token)
    if not admin_user:
        raise HTTPException(status_code=403, detail="Admin access required")

    #Check if username already exists
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    #Check if email already exists
    existing_email = db.query(User).filter(User.email == request.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")

    #Create new user
    hashed_password = auth.hash_password(request.password)
    new_user = User(
        username=request.username,
        email=request.email,
        password_hash=hashed_password,
        full_name=request.full_name,
        is_active=True,
        is_admin=request.is_admin
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserListResponse.from_orm(new_user)


@router.put("/users/{user_id}", response_model=UserListResponse)
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """Update a user (admin only)"""
    admin_user = auth.get_admin_user(db, session_token)
    if not admin_user:
        raise HTTPException(status_code=403, detail="Admin access required")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    #Prevent admin from disabling themselves
    if user.id == admin_user.id and request.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")

    #Prevent admin from removing their own admin privileges
    if user.id == admin_user.id and request.is_admin is False:
        raise HTTPException(status_code=400, detail="Cannot remove your own admin privileges")

    #Update user fields
    if request.is_active is not None:
        user.is_active = request.is_active
    if request.is_admin is not None:
        user.is_admin = request.is_admin
    if request.full_name is not None:
        user.full_name = request.full_name

    db.commit()
    db.refresh(user)

    return UserListResponse.from_orm(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """Delete a user (admin only)"""
    admin_user = auth.get_admin_user(db, session_token)
    if not admin_user:
        raise HTTPException(status_code=403, detail="Admin access required")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    #Prevent admin from deleting themselves
    if user.id == admin_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    db.delete(user)
    db.commit()

    return {"success": True, "message": "User deleted successfully"}


@router.get("/sessions", response_model=list[SessionListResponse])
async def list_sessions(
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """List all active sessions (admin only)"""
    admin_user = auth.get_admin_user(db, session_token)
    if not admin_user:
        raise HTTPException(status_code=403, detail="Admin access required")

    #Get all sessions with user information
    sessions = db.query(SessionModel).join(User).all()

    result = []
    for session in sessions:
        user = db.query(User).filter(User.id == session.user_id).first()
        result.append({
            "id": session.id,
            "user_id": session.user_id,
            "username": user.username if user else "Unknown",
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "is_valid": session.is_valid
        })

    return result


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: int,
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """Revoke a session (admin only)"""
    admin_user = auth.get_admin_user(db, session_token)
    if not admin_user:
        raise HTTPException(status_code=403, detail="Admin access required")

    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_valid = False
    db.commit()

    return {"success": True, "message": "Session revoked successfully"}
