from fastapi import APIRouter, HTTPException, Query
from app.database import database

router = APIRouter(tags=["Listings"])

@router.get("/jobs")
async def get_latest_jobs(limit: int = 20, offset: int = 0):
    try:
        query = """
            SELECT 
                j.id, 
                COALESCE(j.title, 'Untitled Position') AS title, 
                COALESCE(c.name, 'Unknown Company') AS company_raw 
            FROM dbc.jobs j
            LEFT JOIN dbc.companies c ON j.company_id = c.id
            ORDER BY j.id DESC 
            LIMIT :limit OFFSET :offset
        """
        rows = await database.fetch_all(query=query, values={"limit": limit, "offset": offset})
        
        return [
            {
                "id": str(row["id"]), 
                "title": row["title"], 
                "company_raw": row["company_raw"]
            } 
            for row in rows
        ]
    except Exception as e:
        print(f"❌ DATABASE CRASH IN /jobs: {str(e)}")
        raise HTTPException(status_code=500, detail="Database fetch failed.")

@router.get("/jobs/search")
async def search_jobs(q: str = Query(..., description="Search by job title or company name")):
    try:
        search_pattern = f"%{q}%"
        query = """
            SELECT 
                j.id, 
                COALESCE(j.title, 'Untitled Position') AS title, 
                COALESCE(c.name, 'Unknown Company') AS company_raw 
            FROM dbc.jobs j
            LEFT JOIN dbc.companies c ON j.company_id = c.id
            WHERE j.title ILIKE :title_query 
               OR c.name ILIKE :company_query
            ORDER BY j.id DESC
            LIMIT 50
        """
        values = {
            "title_query": search_pattern,
            "company_query": search_pattern
        }
        
        rows = await database.fetch_all(query=query, values=values)
        
        if not rows:
            raise HTTPException(status_code=404, detail=f"No jobs found matching '{q}'.")
            
        return [
            {
                "id": str(row["id"]), 
                "title": row["title"], 
                "company_raw": row["company_raw"]
            } 
            for row in rows
        ]
    except Exception as e:
        print(f"❌ DATABASE CRASH IN /jobs/search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database search failed: {str(e)}")