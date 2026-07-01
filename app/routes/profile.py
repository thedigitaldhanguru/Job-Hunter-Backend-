from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
from app.database import database
import json
from datetime import datetime

router = APIRouter(prefix="/profile", tags=["Profile"])

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = ""
    email: str
    degree: Optional[str] = ""
    university: Optional[str] = ""
    location: Optional[str] = ""
    experience: Optional[str] = ""
    phone: Optional[str] = ""
    gender: Optional[str] = ""
    dob: Optional[str] = ""
    profile_summary: Optional[str] = ""
    avatar_url: Optional[str] = ""
    extended_profile: Optional[Dict[str, Any]] = None
    current_ctc: Optional[str] = ""
    expected_ctc: Optional[str] = ""

@router.get("/{email}")
async def get_profile(email: str):
    query = "SELECT * FROM dbc.users WHERE email = :email"
    row = await database.fetch_one(query=query, values={"email": email})
    
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    profile_data = dict(row)
    
    if profile_data.get("extended_profile") and isinstance(profile_data["extended_profile"], str):
        profile_data["extended_profile"] = json.loads(profile_data["extended_profile"])
        
    if not profile_data.get("extended_profile"):
        profile_data["extended_profile"] = {}
        
    return profile_data

@router.post("/update")
async def update_profile(profile: ProfileUpdate):
    query = """
        INSERT INTO dbc.users (
            full_name, email, degree, university, location, experience, 
            phone, gender, dob, profile_summary, avatar_url, extended_profile,
            current_ctc, expected_ctc
        ) VALUES (
            :full_name, :email, :degree, :university, :location, :experience, 
            :phone, :gender, :dob, :profile_summary, :avatar_url, CAST(:extended_profile AS JSONB),
            :current_ctc, :expected_ctc
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
            current_ctc = EXCLUDED.current_ctc,
            expected_ctc = EXCLUDED.expected_ctc,
            updated_at = NOW()
        RETURNING *;
    """
    try:
        data = profile.dict()
        
        # 1. JSON Serialization of extended_profile
        data["extended_profile"] = json.dumps(data.get("extended_profile") or {})
        
        # 2. Sanitize optional string fields (default to "" if None to satisfy NOT NULL constraints)
        string_fields = [
            "full_name", "degree", "university", "location", "experience", 
            "phone", "gender", "profile_summary", "avatar_url"
        ]
        for field in string_fields:
            if data.get(field) is None:
                data[field] = ""

        # 3. Convert CTC fields to float or None for DB insertion
        for ctc_field in ["current_ctc", "expected_ctc"]:
            ctc_val = data.get(ctc_field)
            if ctc_val is not None:
                clean_val = "".join(c for c in str(ctc_val) if c.isdigit() or c == '.')
                try:
                    data[ctc_field] = float(clean_val) if clean_val else None
                except ValueError:
                    data[ctc_field] = None
            else:
                data[ctc_field] = None
        
        # 4. Date Parsing Logic safely
        dob_val = data.get("dob")
        dob_str = dob_val.strip() if isinstance(dob_val, str) else ""
        
        if not dob_str:
            data["dob"] = None
        else:
            try:
                data["dob"] = datetime.strptime(dob_str, "%Y-%m-%d").date()
            except ValueError:
                try:
                    data["dob"] = datetime.strptime(dob_str, "%d-%m-%Y").date()
                except ValueError:
                    data["dob"] = None
                    
        # Execute query
        result = await database.fetch_one(query=query, values=data)
        return {"status": "success", "data": dict(result)}
        
    except Exception as e:
        print(f"DATABASE ERROR: {str(e)}") 
        raise HTTPException(status_code=500, detail=str(e))