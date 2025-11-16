"""FastAPI authentication service main application"""
import os
import uuid
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Response, Cookie, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from typing import Optional
import boto3
from botocore.exceptions import ClientError
import magic

from .database import engine, get_db, Base
from .models import User
from . import auth

#Create database tables
Base.metadata.create_all(bind=engine)

#Initialize FastAPI app
app = FastAPI(
    title="Transcribe Auth Service",
    description="Authentication service for Cloud-Lord Transcription Stack",
    version="1.0.0"
)

#CORS configuration - only allow transcribe.cloudlord.com
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "https://transcribe.cloudlord.com")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        ALLOWED_ORIGIN,
        "http://localhost:3000",
        "http://localhost:3002",
        "http://0.0.0.0:3002",
        "http://127.0.0.1:3002"
    ],  #Add localhost and 0.0.0.0 for development
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


#Request/Response models
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_admin: bool
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    success: bool
    message: str
    user: Optional[UserResponse] = None


#Health check endpoint
@app.get("/")
async def root():
    return {
        "service": "Transcribe Auth Service",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


#Authentication endpoints
@app.post("/api/auth/register", response_model=LoginResponse)
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


@app.post("/api/auth/login", response_model=LoginResponse)
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


@app.post("/api/auth/logout")
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


@app.get("/api/auth/me", response_model=UserResponse)
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


@app.get("/api/auth/verify")
async def verify_session(
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """Verify if a session is valid"""
    if not session_token:
        return {"valid": False}

    user = auth.validate_session(db, session_token)

    return {"valid": user is not None}


#Audio upload endpoint
#S3 Configuration
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "transcribe-audio-bucket")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

#Initialize S3 client
def get_s3_client():
    """Get S3 client with credentials from environment"""
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        return boto3.client(
            's3',
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
    else:
        #Use default credential chain (IAM role, etc.)
        return boto3.client('s3', region_name=AWS_REGION)


class AudioUploadResponse(BaseModel):
    success: bool
    message: str
    filename: str
    s3_key: str
    size: int
    upload_timestamp: str


@app.post("/api/audio/upload", response_model=AudioUploadResponse)
async def upload_audio(
    audio: UploadFile = File(...),
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """Upload audio file to S3 (requires authentication)"""
    #Validate session
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = auth.validate_session(db, session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    #Validate file type
    ALLOWED_MIME_TYPES = [
        'audio/wav',
        'audio/wave',
        'audio/x-wav',
        'audio/webm',
        'audio/mpeg',
        'audio/mp3',
        'audio/ogg',
        'audio/x-m4a',
        'audio/mp4'
    ]

    #Read file content
    content = await audio.read()

    #Validate file size (min 1KB, max 50MB)
    file_size = len(content)
    MIN_SIZE = 1024  #1KB
    MAX_SIZE = 50 * 1024 * 1024  #50MB

    if file_size < MIN_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too small ({file_size} bytes). Minimum size is {MIN_SIZE} bytes."
        )

    if file_size > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({file_size} bytes). Maximum size is {MAX_SIZE} bytes."
        )

    #Detect MIME type
    mime = magic.from_buffer(content, mime=True)
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {mime}. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        )

    #Generate unique filename
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    file_extension = os.path.splitext(audio.filename)[1] or '.wav'
    s3_key = f"audio/{user.username}/{timestamp}_{unique_id}{file_extension}"

    try:
        #Upload to S3
        s3_client = get_s3_client()
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=content,
            ContentType=mime,
            Metadata={
                'user_id': str(user.id),
                'username': user.username,
                'original_filename': audio.filename,
                'upload_timestamp': datetime.utcnow().isoformat()
            }
        )

        return AudioUploadResponse(
            success=True,
            message="Audio file uploaded successfully",
            filename=audio.filename,
            s3_key=s3_key,
            size=file_size,
            upload_timestamp=datetime.utcnow().isoformat()
        )

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        raise HTTPException(
            status_code=500,
            detail=f"S3 upload failed: {error_code} - {error_message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


#Admin endpoints
class CreateUserRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    is_admin: bool = False


class UpdateUserRequest(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    full_name: Optional[str] = None


class UserListResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: str
    last_login_at: Optional[str]

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    id: int
    user_id: int
    username: str
    created_at: str
    expires_at: str
    is_valid: bool

    class Config:
        from_attributes = True


@app.get("/api/admin/users", response_model=list[UserListResponse])
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


@app.post("/api/admin/users", response_model=UserListResponse)
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


@app.put("/api/admin/users/{user_id}", response_model=UserListResponse)
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


@app.delete("/api/admin/users/{user_id}")
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


@app.get("/api/admin/sessions", response_model=list[SessionListResponse])
async def list_sessions(
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """List all active sessions (admin only)"""
    from .models import Session as SessionModel

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


@app.delete("/api/admin/sessions/{session_id}")
async def revoke_session(
    session_id: int,
    session_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """Revoke a session (admin only)"""
    from .models import Session as SessionModel

    admin_user = auth.get_admin_user(db, session_token)
    if not admin_user:
        raise HTTPException(status_code=403, detail="Admin access required")

    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_valid = False
    db.commit()

    return {"success": True, "message": "Session revoked successfully"}
