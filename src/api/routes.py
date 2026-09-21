import os
from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from src.engine.stream_manager import StreamManager

router = APIRouter()

# Global stream manager singleton
stream_manager = StreamManager(video_path="videos/test.mp4")


@router.get("/video_feed")
def video_feed():
    """
    Streams YOLO-processed frames as multipart/x-mixed-replace.
    """
    return StreamingResponse(
        stream_manager.generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )


@router.get("/dashboard")
def get_dashboard():
    """
    Serves the IronEye monitoring dashboard.
    """
    dashboard_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type="text/html")
    return JSONResponse(
        {"error": "Dashboard template not found"},
        status_code=404
    )


@router.post("/api/start")
def start_monitoring():
    """
    Resume or start video monitoring.
    """
    stream_manager.start()
    return JSONResponse({
        "success": True,
        "message": "Monitoring started",
        "state": stream_manager.get_status()
    })


@router.post("/api/stop")
def stop_monitoring():
    """
    Pause video monitoring.
    """
    stream_manager.stop()
    return JSONResponse({
        "success": True,
        "message": "Monitoring paused",
        "state": stream_manager.get_status()
    })


@router.get("/api/status")
def get_status():
    """
    Get live stream status, detection metrics, and video source details.
    """
    return JSONResponse(stream_manager.get_status())
