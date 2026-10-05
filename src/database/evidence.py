from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np


EVIDENCE_DIR = Path("videos") / "evidence"


def save_evidence(frame: Any) -> str | None:
    """Save a frame as a uniquely named JPEG evidence file."""

    if frame is None:
        return None

    if not isinstance(frame, np.ndarray) or frame.size == 0:
        return None

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    filename = f"incident_{timestamp}.jpg"
    path = EVIDENCE_DIR / filename

    if not cv2.imwrite(str(path), frame):
        return None

    return str(path)