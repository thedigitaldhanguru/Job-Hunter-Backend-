from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import database

router = APIRouter(prefix="/apply", tags=["Apply"])

# This model ensures the frontend sends all required data
class ApplyRequest(BaseModel):
    user_email: str
    job_id: int
    company_name: str
    job_title: str
    application_status: str = "applied"

@router.post("/")
async def apply_to_job(request: ApplyRequest):
    """
    1. Saves the job to the application tracker.
    2. Fetches the URL from the jobs table to allow redirect.
    """
    # 1. First, save the application to the tracker
    insert_query = """
        INSERT INTO dbc.applications (user_email, job_id, company_name, job_title, application_status)
        VALUES (:user_email, :job_id, :company_name, :job_title, :application_status)
        RETURNING id;
    """
    
    # 2. Fetch the URL from the jobs table to send back to the frontend
    url_query = "SELECT job_url FROM dbc.jobs WHERE id = :job_id"
    
    try:
        # Execute the insert
        await database.execute(query=insert_query, values=request.dict())
        
        # Get the URL
        job_record = await database.fetch_one(query=url_query, values={"job_id": request.job_id})
        job_url = job_record["job_url"] if job_record else None
        
        return {
            "status": "success",
            "message": "Application tracked successfully",
            "redirect_url": job_url
        }
    except Exception as e:
        print(f"Error in apply API: {e}")
        raise HTTPException(status_code=500, detail=str(e))