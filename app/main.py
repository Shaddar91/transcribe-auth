"""FastAPI authentication service main application"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base
from .routers import auth, audio, admin

#Create database tables
Base.metadata.create_all(bind=engine)

#Initialize FastAPI app
app = FastAPI(
    title="Transcribe Auth Service",
    description="Authentication service for Cloud-Lord Transcription Stack",
    version="1.0.0"
)

#CORS configuration - only allow transcribe.cloud-lord.com
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "https://transcribe.cloud-lord.com")

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

#Include routers
app.include_router(auth.router)
app.include_router(audio.router)
app.include_router(admin.router)


#Health check endpoints
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
