from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

EVIDENCE_DIR = Path("videos") / "evidence"


def save_evidence(frame: Any) -> str | None:
    """Save a frame as a uniquely named JPEG evidence file.

    Returns the file path on success, or None if the frame is invalid
    or if any filesystem error occurs.  Never raises.
    """

    if frame is None:
        return None

    if not isinstance(frame, np.ndarray) or frame.size == 0:
        return None

    try:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        filename = f"incident_{timestamp}.jpg"
        path = EVIDENCE_DIR / filename

        if not cv2.imwrite(str(path), frame):
            logger.error(
                "cv2.imwrite failed for evidence file: %s "
                "(check available disk space and codec support).",
                path,
            )
            return None

        logger.debug("Evidence saved: %s", path)
        return str(path)

    except OSError:
        logger.exception(
            "Failed to create evidence directory or write evidence file."
        )
        return None
