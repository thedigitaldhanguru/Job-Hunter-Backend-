from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import database
# Import your route modules, including the new apply module
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.routes import jobs, profile, applications, apply, uploads, resume

# Initialize Rate Limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Job Hunter API", version="1.0.0")

# Add SlowAPI state and exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "https://jobhunter.in", 
        "https://www.jobhunter.in"
        # IMPORTANT: Replace the below with your actual pinned Extension ID
        # "chrome-extension://<your-extension-id>"
    ],
    allow_origin_regex=r"chrome-extension://.*", # Allow any extension for local dev, replace in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup(): 
    await database.connect()

@app.on_event("shutdown")
async def shutdown(): 
    await database.disconnect()

# Include all your routers, including the apply router
app.include_router(jobs.router)
app.include_router(profile.router)
app.include_router(applications.router)
app.include_router(apply.router)
app.include_router(uploads.router)
app.include_router(resume.router)

@app.get("/", tags=["System"])
async def root_health():
    return {"status": "Online", "message": "Job Hunter API is Live! 🚀 (CI/CD Automated Deployment!)"}

# AWS Lambda Handler
from mangum import Mangum
handler = Mangum(app, api_gateway_base_path="/default")