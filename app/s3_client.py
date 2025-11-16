"""S3 client configuration and utilities"""
import os
import boto3


#S3 Configuration
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "transcribe-audio-bucket")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")


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
