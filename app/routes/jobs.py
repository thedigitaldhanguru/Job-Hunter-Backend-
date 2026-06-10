import json
import re
from fastapi import APIRouter, HTTPException, Query, Path
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

@router.get("/jobs/recommended/{user_id}")
async def get_recommended_jobs(user_id: str = Path(..., description="The ID of the user to score jobs for")):
    try:
        # 1. Fetch user profile
        user_query = "SELECT extended_profile FROM dbc.users WHERE id = :user_id"
        user_row = await database.fetch_one(query=user_query, values={"user_id": user_id})
        
        if not user_row or not user_row["extended_profile"]:
            raise HTTPException(status_code=404, detail="User profile not found or incomplete.")
            
        profile_data = json.loads(user_row["extended_profile"])
        user_skills = [s.lower() for s in profile_data.get("skills", [])]
        user_prefs = profile_data.get("preferences", {})
        user_job_type = user_prefs.get("jobType", "").lower().strip()
        user_location = user_prefs.get("location", "").lower().strip()
        
        # 2. Fetch jobs (fetching jd_full_text)
        jobs_query = """
            SELECT 
                j.id, 
                COALESCE(j.title, 'Untitled Position') AS title, 
                COALESCE(c.name, 'Unknown Company') AS company_raw,
                j.location,
                j.jd_full_text
            FROM dbc.jobs j
            LEFT JOIN dbc.companies c ON j.company_id = c.id
            ORDER BY j.id DESC
            LIMIT 1000
        """
        job_rows = await database.fetch_all(query=jobs_query)
        
        # 3. Score jobs based on Profile vs JD text
        scored_jobs = []
        for row in job_rows:
            score = 0
            job_title = row["title"].lower()
            job_location = (row["location"] or "").lower()
            jd_text = (row["jd_full_text"] or "").lower()
            
            # A) Title Match (Smart Keyword Matching)
            title_score = 0
            if user_job_type:
                # Split preferred title into words (e.g. "Full stack developer" -> ["full", "stack", "developer"])
                keywords = [word for word in user_job_type.split() if len(word) > 2]
                for word in keywords:
                    if word in job_title:
                        title_score += 15
            score += title_score
                
            # B) Location Match (Strict location vs Remote)
            if user_location and user_location != "remote" and user_location in job_location:
                score += 30  # High score for exact city match (e.g. Pune)
            elif "remote" in job_location:
                score += 5   # Small fallback bonus for remote jobs
                
            # C) Skill Match (10 pts per matching skill found in JD)
            matched_skills = []
            for skill in user_skills:
                if not skill: continue
                # We use Regex \b to ensure we only match whole words
                if re.search(r'\b' + re.escape(skill) + r'\b', jd_text):
                    score += 10
                    matched_skills.append(skill)
                    
            # D) Filter out completely irrelevant jobs
            # Only include jobs that have at least one matching skill OR a matching title keyword
            if len(matched_skills) > 0 or title_score > 0:
                scored_jobs.append({
                    "id": str(row["id"]),
                    "title": row["title"],
                    "company_raw": row["company_raw"],
                    "location": row["location"],
                    "score": score,
                    "matched_skills": matched_skills
                })
            
        # 4. Sort highest score first, and return top 50
        scored_jobs.sort(key=lambda x: x["score"], reverse=True)
        return scored_jobs[:50]
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ DATABASE CRASH IN /jobs/recommended: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to calculate job recommendations.")