from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "models/fire_smoke_yolov8n.pt"

class YOLODetector:
    """
    YOLO object detector strictly for fire/smoke detection.
    """

    PALETTE = [
        (0, 242, 254),
        (0, 255, 128),
        (255, 102, 0),
        (255, 0, 128),
        (138, 43, 226),
        (255, 215, 0),
        (0, 191, 255),
        (50, 205, 50),
    ]

    CLASS_COLORS: Dict[str, Tuple[int, int, int]] = {
        "fire": (0, 60, 255),
        "smoke": (160, 160, 160),
    }

    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL,
        conf_threshold: float = 0.35,
    ) -> None:
        self.model_name = model_name
        self.conf_threshold = conf_threshold
        self._lock = threading.Lock()
        self.model: Optional[YOLO] = None
        self.class_names: Dict[int, str] = {}
        self._load_model()

    def _load_model(self) -> None:
        """Load the configured fire/smoke model."""
        path = self.model_name

        if not os.path.exists(path):
            logger.error("Model file not found: %s. Fire/smoke detection is disabled.", path)
            self.model = None
            self.class_names = {}
            return

        try:
            self.model = YOLO(path)
            names = self.model.names
            self.class_names = (
                names
                if isinstance(names, dict)
                else dict(enumerate(names))
            )
            logger.info(
                "Loaded YOLO model: %s classes=%s",
                path,
                self.class_names,
            )
        except Exception:
            logger.exception("Failed to load YOLO model from %s.", path)
            self.model = None
            self.class_names = {}

    @property
    def is_loaded(self) -> bool:
        """Return whether a model was loaded successfully."""
        return self.model is not None

    def detect_and_annotate(
        self, frame: np.ndarray
    ) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        """
        Detect objects, annotate the frame, and return detection metadata.

        Each detection contains class, confidence, and box coordinates.
        Invalid or missing frames return empty metadata without inference.
        """
        metadata: Dict[str, Any] = {
            "total_detections": 0,
            "classes": {},
            "detections": [],
        }

        if (
            frame is None
            or not isinstance(frame, np.ndarray)
            or frame.size == 0
        ):
            return frame, metadata

        annotated_frame = frame.copy()

        if self.model is None:
            return annotated_frame, metadata

        try:
            with self._lock:
                results = self.model(
                    frame,
                    conf=self.conf_threshold,
                    verbose=False,
                )
        except Exception:
            logger.exception("YOLO inference failed; skipping frame.")
            return annotated_frame, metadata

        if results is None or len(results) == 0:
            return annotated_frame, metadata

        result = results[0]
        boxes = result.boxes

        if boxes is None or len(boxes) == 0:
            return annotated_frame, metadata

        class_summary: Dict[str, int] = {}
        detections_list: List[Dict[str, Any]] = []

        for box in boxes:
            try:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
            except (AttributeError, IndexError, TypeError, ValueError):
                logger.warning("Skipping an invalid detection box.")
                continue

            class_name = self.class_names.get(
                class_id,
                f"cls_{class_id}",
            ).lower()

            if class_name not in ("fire", "smoke"):
                continue

            class_summary[class_name] = (
                class_summary.get(class_name, 0) + 1
            )

            detections_list.append(
                {
                    "class": class_name,
                    "confidence": round(confidence, 2),
                    "box": [x1, y1, x2, y2],
                }
            )

            color = self.CLASS_COLORS.get(
                class_name,
                self.PALETTE[class_id % len(self.PALETTE)],
            )

            cv2.rectangle(
                annotated_frame,
                (x1, y1),
                (x2, y2),
                color,
                2,
            )

            label_text = f"{class_name.upper()} {confidence * 100:.1f}%"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.55
            thickness = 1

            (label_width, label_height), baseline = cv2.getTextSize(
                label_text,
                font,
                font_scale,
                thickness,
            )

            badge_y1 = max(0, y1 - label_height - baseline - 6)

            cv2.rectangle(
                annotated_frame,
                (x1, badge_y1),
                (x1 + label_width + 8, y1),
                color,
                -1,
            )

            cv2.putText(
                annotated_frame,
                label_text,
                (x1 + 4, max(label_height, y1 - 4)),
                font,
                font_scale,
                (10, 15, 20),
                thickness,
                lineType=cv2.LINE_AA,
            )

        metadata["total_detections"] = len(detections_list)
        metadata["classes"] = class_summary
        metadata["detections"] = detections_list

        return annotated_frame, metadata