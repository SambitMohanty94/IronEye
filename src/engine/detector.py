import threading
from typing import Tuple, Dict, Any, List
import cv2
import numpy as np
from ultralytics import YOLO


class YOLODetector:
    """
    YOLO Object Detector using Ultralytics YOLOv8.
    Performs inference, draws bounding boxes, class names, and confidence scores.
    """

    # Color palette for distinct classes in BGR format
    PALETTE = [
        (0, 242, 254),    # Cyan/Neon Blue
        (0, 255, 128),    # Neon Green
        (255, 102, 0),    # Bright Amber
        (255, 0, 128),    # Neon Pink
        (138, 43, 226),   # Violet
        (255, 215, 0),    # Gold
        (0, 191, 255),    # Deep Sky Blue
        (50, 205, 50),    # Lime Green
    ]

    def __init__(self, model_name: str = "yolov8n.pt", conf_threshold: float = 0.35):
        self.model_name = model_name
        self.conf_threshold = conf_threshold
        self._lock = threading.Lock()
        
        # Load the pretrained model (caches to local weights directory automatically)
        self.model = YOLO(self.model_name)
        self.class_names = self.model.names

    def detect_and_annotate(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Run inference on the frame and draw bounding boxes, class name, and confidence score.
        Returns:
            annotated_frame: np.ndarray with bounding boxes and labels drawn
            metadata: Dict with detection count, detected classes, and list of detections
        """
        annotated_frame = frame.copy()
        metadata: Dict[str, Any] = {
            "total_detections": 0,
            "classes": {},
            "detections": []
        }

        with self._lock:
            results = self.model(frame, conf=self.conf_threshold, verbose=False)

        if not results or len(results) == 0:
            return annotated_frame, metadata

        result = results[0]
        boxes = result.boxes

        if boxes is None or len(boxes) == 0:
            return annotated_frame, metadata

        total_count = len(boxes)
        class_summary: Dict[str, int] = {}
        detections_list: List[Dict[str, Any]] = []

        for box in boxes:
            # Coordinates
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            cls_name = self.class_names.get(cls_id, f"cls_{cls_id}")

            class_summary[cls_name] = class_summary.get(cls_name, 0) + 1
            detections_list.append({
                "class": cls_name,
                "confidence": round(conf, 2),
                "box": [x1, y1, x2, y2]
            })

            # Style bounding box
            color = self.PALETTE[cls_id % len(self.PALETTE)]
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)

            # Label text with class and confidence percentage
            label_text = f"{cls_name.upper()} {conf * 100:.1f}%"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.55
            thickness = 1
            (label_w, label_h), baseline = cv2.getTextSize(label_text, font, font_scale, thickness)

            # Draw label background badge
            badge_y1 = max(0, y1 - label_h - baseline - 6)
            badge_y2 = y1
            cv2.rectangle(
                annotated_frame,
                (x1, badge_y1),
                (x1 + label_w + 8, badge_y2),
                color,
                -1
            )

            # Draw label text (dark contrast text on bright background)
            cv2.putText(
                annotated_frame,
                label_text,
                (x1 + 4, y1 - 4),
                font,
                font_scale,
                (10, 15, 20),
                thickness,
                lineType=cv2.LINE_AA
            )

        metadata["total_detections"] = total_count
        metadata["classes"] = class_summary
        metadata["detections"] = detections_list

        return annotated_frame, metadata
