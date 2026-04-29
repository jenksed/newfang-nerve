from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="NewFang Agency Tool",
    description="Local web command center for project planning and documentation.",
    version="0.1.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Welcome to the NewFang Agency Tool",
        "status": "online",
        "endpoints": {
            "projects": "/projects",
            "docs": "/docs",
        }
    }

@app.get("/projects")
async def list_projects():
    # TODO: Implement project listing logic
    return {"projects": []}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
