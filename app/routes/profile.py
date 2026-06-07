from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict
from app.database import database
import json
from datetime import datetime # <-- 1. ADD THIS IMPORT

router = APIRouter(prefix="/profile", tags=["Profile"])

class ProfileUpdate(BaseModel):
    full_name: str
    email: str
    degree: str
    university: str
    location: str
    experience: str
    phone: str
    gender: str
    dob: str
    profile_summary: str
    avatar_url: str
    extended_profile: Dict[str, Any] 

@router.get("/{email}")
async def get_profile(email: str):
    query = "SELECT * FROM dbc.users WHERE email = :email"
    row = await database.fetch_one(query=query, values={"email": email})
    
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    # Convert the database row into a standard Python dictionary
    profile_data = dict(row)
    
    # THE FIX: If extended_profile is a string, parse it back into a dictionary!
    if profile_data.get("extended_profile") and isinstance(profile_data["extended_profile"], str):
        profile_data["extended_profile"] = json.loads(profile_data["extended_profile"])
        
    # If the database returns None for extended_profile, ensure it's an empty dict
    if not profile_data.get("extended_profile"):
        profile_data["extended_profile"] = {}
        
    return profile_data

@router.post("/update")
async def update_profile(profile: ProfileUpdate):
    query = """
        INSERT INTO dbc.users (
            full_name, email, degree, university, location, experience, 
            phone, gender, dob, profile_summary, avatar_url, extended_profile
        ) VALUES (
            :full_name, :email, :degree, :university, :location, :experience, 
            :phone, :gender, :dob, :profile_summary, :avatar_url, CAST(:extended_profile AS JSONB)
        )
        ON CONFLICT (email) DO UPDATE SET
            full_name = EXCLUDED.full_name,
            degree = EXCLUDED.degree,
            university = EXCLUDED.university,
            location = EXCLUDED.location,
            experience = EXCLUDED.experience,
            phone = EXCLUDED.phone,
            gender = EXCLUDED.gender,
            dob = EXCLUDED.dob,
            profile_summary = EXCLUDED.profile_summary,
            avatar_url = EXCLUDED.avatar_url,
            extended_profile = EXCLUDED.extended_profile,
            updated_at = NOW()
        RETURNING *;
    """
    try:
        data = profile.dict()
        
        # 2. JSON Serialization
        data["extended_profile"] = json.dumps(data.get("extended_profile", {}))
        
        # 3. CRUCIAL FIX: Date Parsing Logic
        dob_str = data.get("dob", "").strip()
        
        if not dob_str:
            # If the user leaves it empty, send None (NULL) to Postgres
            data["dob"] = None
        else:
            try:
                # Try to parse standard HTML5 Date (YYYY-MM-DD)
                data["dob"] = datetime.strptime(dob_str, "%Y-%m-%d").date()
            except ValueError:
                try:
                    # Fallback: Try to parse what you typed (DD-MM-YYYY)
                    data["dob"] = datetime.strptime(dob_str, "%d-%m-%Y").date()
                except ValueError:
                    # If it's a completely unreadable format, null it out so it doesn't crash the server
                    data["dob"] = None
                    
        # Execute query
        result = await database.fetch_one(query=query, values=data)
        return {"status": "success", "data": dict(result)}
        
    except Exception as e:
        print(f"DATABASE ERROR: {str(e)}") 
        raise HTTPException(status_code=500, detail=str(e))