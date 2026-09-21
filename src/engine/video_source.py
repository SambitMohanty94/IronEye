import os
import time
import threading
from typing import Optional, Tuple
import cv2
import numpy as np


class VideoSource:
    """
    Manages video frame reading from an MP4 file with automatic looping,
    FPS pacing, and robust error handling.
    Completely isolated from detection logic to enable future camera inputs.
    """

    def __init__(self, file_path: str = "videos/test.mp4"):
        self.file_path = file_path
        self.cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.RLock()
        self.fps: float = 30.0
        self.width: int = 0
        self.height: int = 0
        self.is_initialized: bool = False
        self.error_message: Optional[str] = None

    def is_file_available(self) -> bool:
        """Check if target video file exists and has non-zero size."""
        return os.path.exists(self.file_path) and os.path.getsize(self.file_path) > 0

    def open(self) -> bool:
        """Initialize and open the video capture stream with error catching."""
        with self._lock:
            if not os.path.exists(self.file_path):
                self.error_message = f"File not found: {self.file_path}"
                self.is_initialized = False
                return False

            if os.path.getsize(self.file_path) == 0:
                self.error_message = f"Video file is empty: {self.file_path}"
                self.is_initialized = False
                return False

            if self.cap is not None:
                self.cap.release()

            self.cap = cv2.VideoCapture(self.file_path)
            if not self.cap.isOpened():
                self.error_message = f"Failed to open video codec for: {self.file_path}"
                self.is_initialized = False
                return False

            fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.fps = fps if (fps and fps > 0) else 30.0
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.error_message = None
            self.is_initialized = True
            return True

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read the next frame. When the video reaches EOF, automatically restart
        from frame 0 for continuous looping.
        Returns: (success: bool, frame: Optional[np.ndarray])
        """
        with self._lock:
            if not self.is_initialized or self.cap is None or not self.cap.isOpened():
                if not self.open():
                    return False, None

            ret, frame = self.cap.read()

            # End of video reached or frame dropped: automatically loop back to frame 0
            if not ret or frame is None:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    self.error_message = f"Failed to restart video loop on {self.file_path}"
                    return False, None

            return True, frame

    def release(self):
        """Release OpenCV video capture resources cleanly."""
        with self._lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            self.is_initialized = False
