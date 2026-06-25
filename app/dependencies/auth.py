from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import os
from app.database import database

security = HTTPBearer()

# Ensure you have this set in your .env or AWS Lambda environment variables
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-change-in-prod")
ALGORITHM = "HS256"

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Decodes the JWT issued by the Next.js frontend bridge and returns the user payload.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        email: str = payload.get("email")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # Optional: You can do a quick DB check here if you want to ensure the user still exists
        # query = "SELECT tier FROM dbc.users WHERE email = :email"
        # row = await database.fetch_one(query=query, values={"email": email})
        # if not row:
        #    raise HTTPException(status_code=404, detail="User not found")
        # tier = row["tier"] or "free"
            
        # The frontend will embed the tier in the token, but you can also look it up
        tier: str = payload.get("tier", "free")
        
        return {"email": email, "tier": tier}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_tier(allowed_tiers: list[str]):
    """
    Dependency factory to check if the user belongs to an allowed tier.
    Used for gating Smart Apply and Bedrock calls.
    """
    async def tier_checker(user: dict = Depends(get_current_user)):
        # Re-fetch tier from database to prevent token-tampering for upgrades
        # (Tokens can be stale, DB is source of truth for billing/tiers)
        query = "SELECT tier FROM dbc.users WHERE email = :email"
        row = await database.fetch_one(query=query, values={"email": user["email"]})
        
        db_tier = "free"
        if row and row["tier"]:
            db_tier = row["tier"]

        if db_tier not in allowed_tiers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail=f"Smart Apply is a Pro feature — upgrade to use this. Your current tier is {db_tier}."
            )
            
        # Return updated user info with fresh DB tier
        return {"email": user["email"], "tier": db_tier}
        
    return tier_checker
