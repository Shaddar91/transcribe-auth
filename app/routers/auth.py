"""Authentication endpoints"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from .. import auth
from ..schemas import (
    LoginRequest,
    RegisterRequest,
    LoginResponse,
    UserResponse
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=LoginResponse)
async def register(
    request: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """Register a new user"""
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
        is_active=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    #Create session
    session_token = auth.create_session(db, new_user.id)

    #Set session cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,  #7 days in seconds
        samesite="lax",
        secure=False  #Set to False for local development (HTTP)
    )

    return LoginResponse(
        success=True,
        message="Registration successful",
        user=UserResponse.from_orm(new_user)
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """Login a user and create a session"""
    #Authenticate user
    user = auth.authenticate_user(db, request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    #Create session
    session_token = auth.create_session(db, user.id)

    #Set session cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,  #7 days in seconds
        samesite="lax",
        secure=False  #Set to False for local development (HTTP)
    )

    return LoginResponse(
        success=True,
        message="Login successful",
        user=UserResponse.from_orm(user)
    )


@router.post("/logout")
async def logout(
    response: Response,
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """Logout a user by invalidating their session"""
    if session_token:
        auth.invalidate_session(db, session_token)

    #Clear session cookie
    response.delete_cookie(key="session_token")

    return {"success": True, "message": "Logout successful"}


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """Get current authenticated user"""
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = auth.validate_session(db, session_token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return UserResponse.from_orm(user)


@router.get("/verify")
async def verify_session(
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """Verify if a session is valid"""
    if not session_token:
        return {"valid": False}

    user = auth.validate_session(db, session_token)

    return {"valid": user is not None}
