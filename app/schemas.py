"""Pydantic request/response models for API"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


#Authentication schemas
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


#Audio upload schemas
class AudioUploadResponse(BaseModel):
    success: bool
    message: str
    filename: str
    s3_key: str
    size: int
    upload_timestamp: str


#Admin schemas
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
