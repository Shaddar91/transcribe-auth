"""Audio upload endpoints"""
import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Cookie, UploadFile, File
from sqlalchemy.orm import Session
from botocore.exceptions import ClientError
import magic

from ..database import get_db
from .. import auth
from ..schemas import AudioUploadResponse
from ..s3_client import get_s3_client, S3_BUCKET

router = APIRouter(prefix="/api/audio", tags=["audio"])


@router.post("/upload", response_model=AudioUploadResponse)
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
        'audio/x-wav'
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
    s3_key = f"uploads/{user.username}/{timestamp}_{unique_id}{file_extension}"

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
