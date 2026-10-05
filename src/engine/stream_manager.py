import os
import time
import threading
from typing import Generator, Dict, Any, Optional
import cv2
import numpy as np

from src.engine.video_source import VideoSource
from src.engine.detector import YOLODetector
from src.engine.risk_engine import RiskEngine


class StreamManager:
    """
    Coordinates VideoSource and YOLODetector to provide a continuous MJPEG stream
    and telemetry stats for the IronEye dashboard.
    """

    def __init__(self, video_path: str = "videos/test.mp4"):
        self.video_path = video_path
        self.video_source = VideoSource(self.video_path)
        self.detector: Optional[YOLODetector] = None
        self.risk_engine = RiskEngine()
        self.zone_polygon = None
        self.latest_frame_risk = None
        
        self.is_running: bool = True
        self._lock = threading.Lock()
        
        # Telemetry state
        self.detection_count: int = 0
        self.detected_classes: Dict[str, int] = {}
        self.fps_metric: float = 0.0
        self._last_frame_time = time.time()

    def _get_detector(self) -> YOLODetector:
        """Lazy-load YOLO detector to optimize startup time."""
        if self.detector is None:
            self.detector = YOLODetector(model_name="yolov8n.pt", conf_threshold=0.35)
        return self.detector

    def start(self):
        """Start or resume video monitoring."""
        with self._lock:
            self.is_running = True
            if not self.video_source.is_initialized and self.video_source.is_file_available():
                self.video_source.open()

    def stop(self):
        """Pause video monitoring."""
        with self._lock:
            self.is_running = False

    def get_status(self) -> Dict[str, Any]:
        """Return real-time status and telemetry for dashboard API."""
        file_exists = self.video_source.is_file_available()
        
        if not file_exists:
            status = f"ERROR: {self.video_source.error_message or f'{self.video_path} not found'}"
            is_active = False
        elif not self.is_running:
            status = "STOPPED"
            is_active = False
        else:
            status = "MONITORING"
            is_active = True

        return {
            "status": status,
            "is_running": self.is_running,
            "file_available": file_exists,
            "video_source": os.path.basename(self.video_path),
            "video_source_path": self.video_path,
            "detection_count": self.detection_count,
            "detected_classes": self.detected_classes,
            "fps": round(self.fps_metric, 1)
        }

    def _create_placeholder_frame(self, title: str, subtitle: str, color: tuple = (0, 165, 255)) -> np.ndarray:
        """Generate a sleek, dark cyber-aesthetic placeholder/standby frame."""
        width, height = 854, 480
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Dark grid background pattern
        for y in range(0, height, 40):
            cv2.line(frame, (0, y), (width, y), (20, 25, 30), 1)
        for x in range(0, width, 40):
            cv2.line(frame, (x, 0), (x, height), (20, 25, 30), 1)

        # Header accent bar
        cv2.rectangle(frame, (40, 40), (width - 40, 44), (0, 240, 255), -1)

        # Brand title
        cv2.putText(
            frame,
            "IRONEYE AI MONITORING SYSTEM",
            (40, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 240, 255),
            1,
            lineType=cv2.LINE_AA
        )

        # Center card
        center_x, center_y = width // 2, height // 2
        cv2.rectangle(
            frame,
            (center_x - 300, center_y - 80),
            (center_x + 300, center_y + 80),
            (25, 32, 40),
            -1
        )
        cv2.rectangle(
            frame,
            (center_x - 300, center_y - 80),
            (center_x + 300, center_y + 80),
            color,
            2
        )

        # Status title
        cv2.putText(
            frame,
            title,
            (center_x - 260, center_y - 15),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
            lineType=cv2.LINE_AA
        )

        # Subtitle details
        cv2.putText(
            frame,
            subtitle,
            (center_x - 260, center_y + 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (180, 190, 200),
            1,
            lineType=cv2.LINE_AA
        )

        return frame

    def generate_frames(self) -> Generator[bytes, None, None]:
        """
        Generator producing multipart/x-mixed-replace JPEG frames.
        Handles missing files, stopped state, and active YOLO detection stream.
        """
        while True:
            # Check file availability
            if not self.video_source.is_file_available():
                self.detection_count = 0
                self.detected_classes = {}
                frame = self._create_placeholder_frame(
                    title="VIDEO SOURCE NOT FOUND",
                    subtitle=f"Place test video at: {self.video_path}",
                    color=(0, 0, 255)  # Red warning
                )
                time.sleep(0.5)

            elif not self.is_running:
                self.detection_count = 0
                self.detected_classes = {}
                frame = self._create_placeholder_frame(
                    title="MONITORING STOPPED",
                    subtitle="Click 'Start Monitoring' on dashboard to resume",
                    color=(0, 200, 255)  # Amber
                )
                time.sleep(0.3)

            else:
                # Active monitoring: read frame
                start_time = time.time()
                success, raw_frame = self.video_source.read_frame()

                if not success or raw_frame is None:
                    error_msg = self.video_source.error_message or f"Cannot read from {self.video_path}"
                    frame = self._create_placeholder_frame(
                        title="ERROR READING VIDEO",
                        subtitle=error_msg,
                        color=(0, 0, 255)
                    )
                    time.sleep(0.5)
                else:
                    # Run YOLO inference & annotation
                    detector = self._get_detector()
                    annotated_frame, metadata = detector.detect_and_annotate(raw_frame)
                                        # Evaluate fire/smoke detections against the configured safety zone.
                    frame_risk = self.risk_engine.process_frame(
                        detections=metadata.get("detections", []),
                        polygon=self.zone_polygon,
                        now=start_time,
                    )
                    self.latest_frame_risk = frame_risk

                    risk_results = [
                        {
                            "class": r.detection_class,
                            "confidence": r.confidence,
                            "bbox": list(r.bbox) if r.bbox else [],
                            "foot_point": r.foot_point,
                            "inside_zone": r.inside_zone,
                            "risk_level": r.risk_level,
                            "confirmed": r.confirmed,
                            "incident_eligible": r.incident_eligible,
                        }
                        for r in frame_risk.results
                        if r.detection_class in {"fire", "smoke"}
                    ]

                    # Update telemetry
                    self.detection_count = metadata["total_detections"]
                    self.detected_classes = metadata["classes"]

                    # Compute FPS metric
                    curr_time = time.time()
                    elapsed = curr_time - self._last_frame_time
                    if elapsed > 0:
                        self.fps_metric = 1.0 / elapsed
                    self._last_frame_time = curr_time

                    # Top HUD bar on processed frame
                    source_name = os.path.basename(self.video_path)
                    cv2.rectangle(annotated_frame, (0, 0), (annotated_frame.shape[1], 36), (15, 20, 25), -1)
                    cv2.putText(
                        annotated_frame,
                        f"IRONEYE | SOURCE: {source_name} | STATUS: MONITORING | DETECTIONS: {self.detection_count}",
                        (15, 24),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 242, 254),
                        1,
                        cv2.LINE_AA
                    )

                    frame = annotated_frame

                    # Pace playback matching source FPS (~25-30fps)
                    processing_duration = time.time() - start_time
                    target_delay = 1.0 / max(self.video_source.fps, 10.0)
                    if processing_duration < target_delay:
                        time.sleep(target_delay - processing_duration)

            # Encode frame to JPEG
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ret:
                continue

            frame_bytes = buffer.tobytes()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
