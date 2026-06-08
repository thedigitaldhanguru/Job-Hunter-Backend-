from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import database

router = APIRouter(prefix="/applications", tags=["Applications"])

# 1. Updated Model to accept the typed-in company, role, and use user_email
class Application(BaseModel):
    user_email: str  
    job_id: int = 0
    company_name: str
    job_title: str
    job_url: Optional[str] = None
    application_status: str = 'applied'

# 2. Model for updating status via JSON body
class StatusUpdate(BaseModel):
    status: str

@router.get("/{user_email}")
async def get_user_applications(user_email: str):
    """Fetch all applications directly from the applications table."""
    # Look how clean this is now! No complex JOINs to crash the server.
    query = """
        SELECT * FROM dbc.applications 
        WHERE user_email = :user_email 
        ORDER BY created_at DESC
    """
    try:
        rows = await database.fetch_all(query=query, values={"user_email": user_email})
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"DB Error Fetching Applications: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
async def create_application(app_data: Application):
    """Add a new job application with company and title."""
    query = """
        INSERT INTO dbc.applications (user_email, job_id, company_name, job_title, application_status, job_url)
        VALUES (:user_email, :job_id, :company_name, :job_title, :application_status, :job_url)
        RETURNING *;
    """
    try:
        result = await database.fetch_one(query=query, values=app_data.dict())
        return {"status": "success", "data": dict(result)}
    except Exception as e:
        print(f"DB Error Creating Application: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{id}/status")
async def update_status(id: int, payload: StatusUpdate):
    """Update status via JSON body."""
    query = """
        UPDATE dbc.applications 
        SET application_status = :status 
        WHERE id = :id 
        RETURNING *;
    """
    try:
        result = await database.fetch_one(query=query, values={"status": payload.status, "id": id})
        if not result:
            raise HTTPException(status_code=404, detail="Application not found")
        return {"status": "success", "data": dict(result)}
    except Exception as e:
        print(f"DB Error Updating Status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{id}")
async def delete_application(id: int):
    """Delete a specific application from the tracker."""
    query = """
        DELETE FROM dbc.applications 
        WHERE id = :id 
        RETURNING id;
    """
    try:
        result = await database.fetch_one(query=query, values={"id": id})
        if not result:
            raise HTTPException(status_code=404, detail="Application not found")
        return {"status": "success", "message": "Application deleted"}
    except Exception as e:
        print(f"DB Error Deleting Application: {e}")
        raise HTTPException(status_code=500, detail=str(e))