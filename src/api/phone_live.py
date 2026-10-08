"""Isolated router serving the /phone camera page."""
from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

_PHONE_HTML = os.path.join(
    os.path.dirname(__file__), os.pardir, "static", "phone_camera.html"
)


@router.get("/phone")
def phone_page():
    """Serve the phone-camera streaming page."""
    return FileResponse(os.path.normpath(_PHONE_HTML), media_type="text/html")
