"""Database configuration and session management"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

#Database URL from environment variable - convert to psycopg3 format
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:changeme@localhost:5432/transcribe"
)

#Convert to psycopg3 format if needed
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

#Create database engine
engine = create_engine(DATABASE_URL)

#Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

#Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
