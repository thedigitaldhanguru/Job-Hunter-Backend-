from fastapi import APIRouter, HTTPException, Query
import boto3
from botocore.exceptions import ClientError
import os
import uuid

router = APIRouter(prefix="/uploads", tags=["Uploads"])

s3_client = boto3.client('s3', region_name=os.getenv("AWS_REGION", "ap-south-1"))
BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")

@router.get("/presigned-url")
async def get_presigned_url(file_name: str = Query(...), file_type: str = Query(...)):
    """
    Generates a secure presigned URL that the frontend can use to upload a file directly to S3.
    """
    if not BUCKET_NAME:
        raise HTTPException(status_code=500, detail="AWS_S3_BUCKET_NAME environment variable is not configured.")

    # Create a unique file name to prevent overwriting
    unique_filename = f"{uuid.uuid4()}-{file_name}"
    
    try:
        # Generate the presigned URL for PUT requests
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': unique_filename,
                'ContentType': file_type,
                # Optionally add ACL if bucket allows it:
                # 'ACL': 'public-read'
            },
            ExpiresIn=300 # URL expires in 5 minutes
        )
        
        region = os.getenv("AWS_REGION", "ap-south-1")
        file_url = f"https://{BUCKET_NAME}.s3.{region}.amazonaws.com/{unique_filename}"
        
        return {
            "upload_url": presigned_url,
            "file_url": file_url,
            "filename": unique_filename
        }
    except ClientError as e:
        print(f"Error generating presigned URL: {e}")
        raise HTTPException(status_code=500, detail="Could not generate upload URL.")
