from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import database
# Import your route modules, including the new apply module
from app.routes import jobs, profile, applications, apply, uploads

app = FastAPI(title="Job Hunter API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "https://jobhunterrr.netlify.app"],
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

@app.get("/", tags=["System"])
async def root_health():
    return {"status": "Online", "message": "Job Hunter API is Live! 🚀 (CI/CD Automated Deployment!)"}

# AWS Lambda Handler
from mangum import Mangum
handler = Mangum(app, api_gateway_base_path="/default")