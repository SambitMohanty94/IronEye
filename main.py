import os
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from src.api.routes import router as api_router

app = FastAPI(title="IronEye Safety Platform")

# Base paths
base_dir = os.path.dirname(__file__)
static_dir = os.path.join(base_dir, "src", "static")
dashboard_path = os.path.join(static_dir, "dashboard.html")

# Mount static assets (CSS, JS, icons)
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Register core IronEye routes
app.include_router(api_router)


@app.get("/")
def home(request: Request):
    """
    Root endpoint for IronEye.
    - Delivers the live monitoring dashboard to web browsers.
    - Preserves JSON compatibility for existing API health checks.
    """
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return {"message": "IronEye server is running!"}

    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type="text/html")
    
    return {"message": "IronEye server is running!"}
