import os
from jose import jwt
from datetime import datetime, timedelta

# Set a test secret
os.environ["JWT_SECRET"] = "test-secret"
from app.dependencies.auth import get_current_user, require_tier
from fastapi.security import HTTPAuthorizationCredentials
import asyncio

async def test_jwt():
    print("1. Testing JWT Generation...")
    secret = os.environ["JWT_SECRET"]
    expiresIn = datetime.utcnow() + timedelta(days=7)
    
    # Simulate what Next.js route.ts does
    token = jwt.encode(
        {
            "sub": "test@example.com",
            "email": "test@example.com",
            "tier": "pro"
        },
        secret,
        algorithm="HS256"
    )
    print(f"Generated Token: {token}")

    print("\n2. Testing get_current_user Decoding...")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(creds)
    print(f"Decoded User Payload: {user}")
    
    print("\n3. Testing Backend Imports...")
    try:
        from app.routes import apply
        print("Imports successful! No syntax errors in dependencies.")
    except Exception as e:
        print(f"Import Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_jwt())
