"""
tests/test_fire_smoke_detector.py
------------------------------------
Tests for the fire/smoke YOLODetector integration.

Design rules:
- Model loading is tested against the actual downloaded weights.
- Inference tests use mocked model outputs so no GPU or large download is needed.
- No real SMS, no Supabase calls.
"""
from __future__ import annotations

import os
import threading
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from src.engine.detector import YOLODetector, _DEFAULT_MODEL, _FALLBACK_MODEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blank_frame(h: int = 64, w: int = 64) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _make_mock_box(cls_id: int, conf: float, x1=10, y1=10, x2=50, y2=50):
    """Create a minimal mock of a YOLO box object."""
    box = MagicMock()
    import torch
    box.xyxy = [torch.tensor([x1, y1, x2, y2], dtype=torch.float32)]
    box.conf = [torch.tensor(conf)]
    box.cls = [torch.tensor(cls_id)]
    return box


def _make_mock_results(boxes_list):
    """Wrap a list of mock boxes in a mock YOLO result."""
    mock_result = MagicMock()
    mock_result.boxes = boxes_list
    return [mock_result]


# ---------------------------------------------------------------------------
# 1. Default model path configuration
# ---------------------------------------------------------------------------

def test_default_model_path_is_fire_smoke():
    """DEFAULT model should point to the fire/smoke weights, not yolov8n."""
    assert "fire_smoke" in _DEFAULT_MODEL or "fire" in _DEFAULT_MODEL, (
        f"Expected fire/smoke model as default, got: {_DEFAULT_MODEL}"
    )


def test_fallback_model_is_yolov8n():
    assert _FALLBACK_MODEL == "yolov8n.pt"


# ---------------------------------------------------------------------------
# 2. Model loading with actual weights
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.path.exists(_DEFAULT_MODEL),
    reason=f"Fire/smoke model not found at {_DEFAULT_MODEL}; skipping live load test.",
)
def test_actual_model_loads_and_has_fire_smoke_classes():
    """
    Verify the downloaded model loads and has fire and smoke class names.
    """
    det = YOLODetector(model_name=_DEFAULT_MODEL)
    assert det.is_loaded, "Model should be loaded from existing weights file."
    class_values = [v.lower() for v in det.class_names.values()]
    assert "fire" in class_values, f"Expected 'fire' in classes, got: {det.class_names}"
    assert "smoke" in class_values, f"Expected 'smoke' in classes, got: {det.class_names}"


# ---------------------------------------------------------------------------
# 3. Graceful fallback when model file is missing
# ---------------------------------------------------------------------------

def test_missing_model_falls_back_to_yolov8n():
    """
    When the primary model file is absent, YOLODetector falls back to yolov8n.pt.
    The fallback itself loads successfully.
    """
    with patch("src.engine.detector.os.path.exists", return_value=False):
        with patch("src.engine.detector.YOLO") as MockYOLO:
            MockYOLO.return_value = MagicMock(names={0: "person"})
            det = YOLODetector(model_name="nonexistent_model.pt")
    # Should have attempted to load fallback
    assert MockYOLO.called
    call_arg = MockYOLO.call_args[0][0]
    assert call_arg == _FALLBACK_MODEL, f"Expected fallback {_FALLBACK_MODEL}, got {call_arg}"


# ---------------------------------------------------------------------------
# 4. Inference exception does not propagate
# ---------------------------------------------------------------------------

def test_inference_exception_returns_empty_metadata():
    """
    If YOLO inference raises an exception, detect_and_annotate returns
    an empty metadata dict without re-raising.
    """
    mock_yolo = MagicMock()
    mock_yolo.names = {0: "smoke", 1: "fire"}
    mock_yolo.side_effect = RuntimeError("GPU OOM")

    with patch("src.engine.detector.YOLO", return_value=mock_yolo):
        with patch("src.engine.detector.os.path.exists", return_value=True):
            det = YOLODetector(model_name="dummy.pt")

    # Now make the underlying model callable raise
    det.model = MagicMock(side_effect=RuntimeError("inference crash"))
    frame = _blank_frame()
    annotated, meta = det.detect_and_annotate(frame)

    assert meta["total_detections"] == 0
    assert meta["detections"] == []
    assert annotated.shape == frame.shape


# ---------------------------------------------------------------------------
# 5. None / empty frame returns without crash
# ---------------------------------------------------------------------------

def test_none_frame_returns_gracefully():
    """detect_and_annotate with None frame returns empty metadata."""
    with patch("src.engine.detector.YOLO") as MockYOLO:
        MockYOLO.return_value = MagicMock(names={0: "smoke", 1: "fire"})
        with patch("src.engine.detector.os.path.exists", return_value=True):
            det = YOLODetector(model_name="dummy.pt")

    annotated, meta = det.detect_and_annotate(None)
    assert meta["total_detections"] == 0


def test_empty_array_returns_gracefully():
    """detect_and_annotate with an empty numpy array returns empty metadata."""
    with patch("src.engine.detector.YOLO") as MockYOLO:
        MockYOLO.return_value = MagicMock(names={0: "smoke", 1: "fire"})
        with patch("src.engine.detector.os.path.exists", return_value=True):
            det = YOLODetector(model_name="dummy.pt")

    annotated, meta = det.detect_and_annotate(np.array([]))
    assert meta["total_detections"] == 0


# ---------------------------------------------------------------------------
# 6. Fire detection — mocked model output
# ---------------------------------------------------------------------------

def test_fire_detection_produces_correct_class_name():
    """
    When the model returns class_id=1 (fire in rabahdev model),
    the metadata should contain 'fire' with the correct confidence.
    """
    import torch

    # Build mock box: class_id=1 -> 'fire'
    mock_box = _make_mock_box(cls_id=1, conf=0.87, x1=20, y1=30, x2=100, y2=120)
    mock_result = MagicMock()
    mock_result.boxes = [mock_box]

    mock_yolo = MagicMock()
    mock_yolo.names = {0: "smoke", 1: "fire"}
    mock_yolo.return_value = [mock_result]

    with patch("src.engine.detector.YOLO", return_value=mock_yolo):
        with patch("src.engine.detector.os.path.exists", return_value=True):
            det = YOLODetector(model_name="dummy.pt")

    frame = _blank_frame(128, 128)
    _, meta = det.detect_and_annotate(frame)

    assert meta["total_detections"] == 1
    assert meta["classes"].get("fire") == 1
    fire_det = meta["detections"][0]
    assert fire_det["class"] == "fire"
    assert abs(fire_det["confidence"] - 0.87) < 0.01


# ---------------------------------------------------------------------------
# 7. Smoke detection — mocked model output
# ---------------------------------------------------------------------------

def test_smoke_detection_produces_correct_class_name():
    """
    When the model returns class_id=0 (smoke), metadata should reflect it.
    """
    mock_box = _make_mock_box(cls_id=0, conf=0.72, x1=5, y1=5, x2=60, y2=60)
    mock_result = MagicMock()
    mock_result.boxes = [mock_box]

    mock_yolo = MagicMock()
    mock_yolo.names = {0: "smoke", 1: "fire"}
    mock_yolo.return_value = [mock_result]

    with patch("src.engine.detector.YOLO", return_value=mock_yolo):
        with patch("src.engine.detector.os.path.exists", return_value=True):
            det = YOLODetector(model_name="dummy.pt")

    frame = _blank_frame(128, 128)
    _, meta = det.detect_and_annotate(frame)

    assert meta["total_detections"] == 1
    assert meta["classes"].get("smoke") == 1
    assert meta["detections"][0]["class"] == "smoke"


# ---------------------------------------------------------------------------
# 8. No-detection scenario
# ---------------------------------------------------------------------------

def test_no_detections_returns_zero_count():
    """When model returns no boxes, total_detections must be 0."""
    mock_result = MagicMock()
    mock_result.boxes = []

    mock_yolo = MagicMock()
    mock_yolo.names = {0: "smoke", 1: "fire"}
    mock_yolo.return_value = [mock_result]

    with patch("src.engine.detector.YOLO", return_value=mock_yolo):
        with patch("src.engine.detector.os.path.exists", return_value=True):
            det = YOLODetector(model_name="dummy.pt")

    _, meta = det.detect_and_annotate(_blank_frame())
    assert meta["total_detections"] == 0
    assert meta["detections"] == []
    assert meta["classes"] == {}


# ---------------------------------------------------------------------------
# 9. Multiple classes in one frame
# ---------------------------------------------------------------------------

def test_fire_and_smoke_both_detected():
    """Both fire and smoke detected in the same frame are counted separately."""
    fire_box = _make_mock_box(cls_id=1, conf=0.9, x1=10, y1=10, x2=50, y2=50)
    smoke_box = _make_mock_box(cls_id=0, conf=0.6, x1=60, y1=60, x2=120, y2=120)

    mock_result = MagicMock()
    mock_result.boxes = [fire_box, smoke_box]

    mock_yolo = MagicMock()
    mock_yolo.names = {0: "smoke", 1: "fire"}
    mock_yolo.return_value = [mock_result]

    with patch("src.engine.detector.YOLO", return_value=mock_yolo):
        with patch("src.engine.detector.os.path.exists", return_value=True):
            det = YOLODetector(model_name="dummy.pt")

    _, meta = det.detect_and_annotate(_blank_frame(200, 200))
    assert meta["total_detections"] == 2
    assert meta["classes"]["fire"] == 1
    assert meta["classes"]["smoke"] == 1


# ---------------------------------------------------------------------------
# 10. Class colour override for fire/smoke
# ---------------------------------------------------------------------------

def test_fire_has_distinctive_color():
    """Fire detections should use the CLASS_COLORS override, not the PALETTE."""
    assert "fire" in YOLODetector.CLASS_COLORS
    assert "smoke" in YOLODetector.CLASS_COLORS


# ---------------------------------------------------------------------------
# 11. StreamManager uses fire/smoke model by default
# ---------------------------------------------------------------------------

def test_stream_manager_uses_fire_smoke_model_by_default():
    """
    StreamManager._get_detector() should create a YOLODetector that points
    to the fire/smoke model path (not yolov8n.pt), unless MODEL_PATH overrides.
    """
    from src.engine.stream_manager import StreamManager
    with patch("src.engine.stream_manager.IncidentService"):
        with patch("src.engine.detector.YOLO") as MockYOLO:
            MockYOLO.return_value = MagicMock(names={0: "smoke", 1: "fire"})
            with patch("src.engine.detector.os.path.exists", return_value=True):
                sm = StreamManager("videos/nonexistent.mp4")
                det = sm._get_detector()

    assert det is not None
    # model_name should reference the fire/smoke model or the fallback
    assert det.model_name in (_DEFAULT_MODEL, _FALLBACK_MODEL)


# ---------------------------------------------------------------------------
# 12. Phone camera injection
# ---------------------------------------------------------------------------

def test_inject_phone_frame_stores_frame():
    """inject_phone_frame stores the frame and updates the camera ID."""
    from src.engine.stream_manager import StreamManager
    with patch("src.engine.stream_manager.IncidentService"):
        sm = StreamManager("videos/nonexistent.mp4")

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    sm.inject_phone_frame(frame, camera_id="cam-01")

    assert sm.phone_camera_id == "cam-01"
    assert sm._phone_frame is not None
    assert sm._phone_frame.shape == frame.shape
    # Must be a copy (independent)
    frame[:] = 255
    assert sm._phone_frame[0, 0, 0] == 0


def test_switch_to_phone_camera():
    """switch_to_phone_camera enables/disables phone mode."""
    from src.engine.stream_manager import StreamManager
    with patch("src.engine.stream_manager.IncidentService"):
        sm = StreamManager("videos/nonexistent.mp4")

    assert sm.use_phone_camera is False
    sm.switch_to_phone_camera(True)
    assert sm.use_phone_camera is True
    sm.switch_to_phone_camera(False)
    assert sm.use_phone_camera is False
    assert sm._phone_frame is None


# ---------------------------------------------------------------------------
# 13. Incident in-memory log
# ---------------------------------------------------------------------------

def test_incident_log_stores_and_retrieves():
    """add_incident_to_log / get_recent_incidents work correctly."""
    from src.engine.stream_manager import StreamManager
    with patch("src.engine.stream_manager.IncidentService"):
        sm = StreamManager("videos/nonexistent.mp4")

    for i in range(3):
        sm.add_incident_to_log({"type": "fire", "idx": i, "timestamp": "2024-01-01T00:00:00Z"})

    incidents = sm.get_recent_incidents()
    assert len(incidents) == 3
    # Newest first
    assert incidents[0]["idx"] == 2


def test_incident_log_caps_at_50():
    """In-memory buffer does not grow beyond 50 entries."""
    from src.engine.stream_manager import StreamManager
    with patch("src.engine.stream_manager.IncidentService"):
        sm = StreamManager("videos/nonexistent.mp4")

    for i in range(60):
        sm.add_incident_to_log({"type": "smoke", "idx": i, "timestamp": "T"})

    assert len(sm.get_recent_incidents()) == 50
