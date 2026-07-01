from fastapi import APIRouter, HTTPException, Query, Depends
import boto3
from botocore.exceptions import ClientError
import os
import uuid

from botocore.client import Config
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/uploads", tags=["Uploads"])

region = os.getenv("AWS_REGION", "ap-south-1")
s3_client = boto3.client(
    's3', 
    region_name=region,
    endpoint_url=f"https://s3.{region}.amazonaws.com",
    config=Config(s3={'addressing_style': 'virtual'})
)
AVATAR_BUCKET_NAME = os.getenv("AWS_S3_AVATAR_BUCKET_NAME", "job-hunter-user-avatars")
RESUME_BUCKET_NAME = os.getenv("AWS_S3_RESUME_BUCKET_NAME", "job-hunter-resumes")

@router.get("/presigned-url")
async def get_presigned_url(
    file_name: str = Query(...),
    file_type: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Generates a secure presigned URL that the frontend can use to upload a file directly to S3.
    """
    if file_type.startswith("image/"):
        target_bucket = AVATAR_BUCKET_NAME or "job-hunter-user-avatars"
    else:
        target_bucket = RESUME_BUCKET_NAME or "job-hunter-resumes"
    # Debug: log bucket environment variables
    print(f"[DEBUG] AVATAR_BUCKET_NAME={AVATAR_BUCKET_NAME}, RESUME_BUCKET_NAME={RESUME_BUCKET_NAME}, REGION={region}")
    if not target_bucket:
        msg = "AWS S3 Bucket environment variables are not properly configured."
        print(f"[ERROR] {msg}")
        raise HTTPException(status_code=500, detail=msg)


    # Create a unique file name to prevent overwriting
    email = current_user["email"]
    unique_filename = f"{email}/{file_name}"
    
    try:
        # Generate the presigned URL for PUT requests
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': target_bucket,
                'Key': unique_filename,
                'ContentType': file_type,
                # Optionally add ACL if bucket allows it:
                # 'ACL': 'public-read'
            },
            ExpiresIn=300 # URL expires in 5 minutes
        )
        
        file_url = f"https://{target_bucket}.s3.{region}.amazonaws.com/{unique_filename}"
        
        return {
            "upload_url": presigned_url,
            "file_url": file_url,
            "filename": unique_filename
        }
    except ClientError as e:
        print(f"Error generating presigned URL: {e}")
        raise HTTPException(status_code=500, detail="Could not generate upload URL.")
