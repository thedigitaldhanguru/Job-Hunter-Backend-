from fastapi import APIRouter, HTTPException, Query
import boto3
from botocore.exceptions import ClientError
import os
import uuid

router = APIRouter(prefix="/uploads", tags=["Uploads"])

s3_client = boto3.client('s3', region_name=os.getenv("AWS_REGION", "ap-south-1"))
AVATAR_BUCKET_NAME = os.getenv("AWS_S3_AVATAR_BUCKET_NAME")
RESUME_BUCKET_NAME = os.getenv("AWS_S3_RESUME_BUCKET_NAME")

@router.get("/presigned-url")
async def get_presigned_url(file_name: str = Query(...), file_type: str = Query(...)):
    """
    Generates a secure presigned URL that the frontend can use to upload a file directly to S3.
    """
    if file_type.startswith("image/"):
        target_bucket = AVATAR_BUCKET_NAME
    else:
        target_bucket = RESUME_BUCKET_NAME
        
    if not target_bucket:
        raise HTTPException(status_code=500, detail="AWS S3 Bucket environment variables are not properly configured.")

    # Create a unique file name to prevent overwriting
    unique_filename = f"{uuid.uuid4()}-{file_name}"
    
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
        
        region = os.getenv("AWS_REGION", "ap-south-1")
        file_url = f"https://{target_bucket}.s3.{region}.amazonaws.com/{unique_filename}"
        
        return {
            "upload_url": presigned_url,
            "file_url": file_url,
            "filename": unique_filename
        }
    except ClientError as e:
        print(f"Error generating presigned URL: {e}")
        raise HTTPException(status_code=500, detail="Could not generate upload URL.")
