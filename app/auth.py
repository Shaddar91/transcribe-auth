"""Authentication logic and utilities"""
import os
import secrets
from datetime import datetime, timedelta
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from .models import User, Session as SessionModel

#Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#Session configuration
SESSION_EXPIRY_DAYS = int(os.getenv("SESSION_EXPIRY_DAYS", "7"))


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def generate_session_token() -> str:
    """Generate a cryptographically secure session token"""
    return secrets.token_urlsafe(32)


def create_session(db: Session, user_id: int) -> str:
    """Create a new session for a user and return the session token"""
    #Generate unique session token
    session_token = generate_session_token()

    #Calculate expiration time
    expires_at = datetime.utcnow() + timedelta(days=SESSION_EXPIRY_DAYS)

    #Create session record
    session = SessionModel(
        user_id=user_id,
        session_token=session_token,
        expires_at=expires_at,
        is_valid=True
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session_token


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """Authenticate a user by username and password"""
    #Find active user
    user = db.query(User).filter(
        User.username == username,
        User.is_active == True
    ).first()

    if not user:
        return None

    #Verify password
    if not verify_password(password, user.password_hash):
        return None

    #Update last login timestamp
    user.last_login_at = datetime.utcnow()
    db.commit()

    return user


def validate_session(db: Session, session_token: str) -> User | None:
    """Validate a session token and return the associated user"""
    #Find session
    session = db.query(SessionModel).filter(
        SessionModel.session_token == session_token,
        SessionModel.is_valid == True
    ).first()

    if not session:
        return None

    #Check if session is expired
    if session.expires_at < datetime.utcnow():
        #Invalidate expired session
        session.is_valid = False
        db.commit()
        return None

    #Get user
    user = db.query(User).filter(
        User.id == session.user_id,
        User.is_active == True
    ).first()

    return user


def invalidate_session(db: Session, session_token: str) -> bool:
    """Invalidate a session (logout)"""
    session = db.query(SessionModel).filter(
        SessionModel.session_token == session_token
    ).first()

    if not session:
        return False

    session.is_valid = False
    db.commit()
    return True


def verify_admin(user: User) -> bool:
    """Verify if a user has admin privileges"""
    return user.is_active and user.is_admin


def get_admin_user(db: Session, session_token: str) -> User | None:
    """Validate session and verify admin privileges"""
    user = validate_session(db, session_token)
    if not user or not verify_admin(user):
        return None
    return user
