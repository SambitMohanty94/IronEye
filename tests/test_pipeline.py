import os
import pytest
import numpy as np
from fastapi.testclient import TestClient
import main
from src.engine.video_source import VideoSource
from src.engine.detector import YOLODetector
from src.engine.stream_manager import StreamManager


def test_root_endpoint_json():
    """Verify GET / returns JSON health check when requested."""
    client = TestClient(main.app)
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    assert response.json() == {"message": "IronEye server is running!"}


def test_root_endpoint_dashboard_html():
    """Verify GET / returns HTML dashboard by default for browsers."""
    client = TestClient(main.app)
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "IRONEYE" in response.text
    assert "videoFeed" in response.text


def test_status_endpoint():
    """Verify /api/status telemetry endpoint."""
    client = TestClient(main.app)
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "video_source" in data
    assert "detection_count" in data


def test_yolo_detector_inference():
    """Verify YOLOv8n detector executes without error on a blank frame."""
    detector = YOLODetector()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    annotated, meta = detector.detect_and_annotate(frame)
    assert annotated.shape == (480, 640, 3)
    assert "total_detections" in meta
    assert isinstance(meta["total_detections"], int)


def test_video_source_missing_file_safety():
    """Verify VideoSource does not crash when file does not exist."""
    source = VideoSource("videos/non_existent_file.mp4")
    assert not source.is_file_available()
    success, frame = source.read_frame()
    assert not success
    assert frame is None
    assert source.error_message is not None
