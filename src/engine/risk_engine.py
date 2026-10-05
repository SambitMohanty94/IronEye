from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import cv2
import numpy as np


Point = Tuple[int, int]
Polygon = Sequence[Point]


@dataclass(frozen=True)
class RiskResult:
    risk_level: str
    inside_zone: bool
    foot_point: Point
    confirmed: bool
    detection_class: Optional[str] = None
    confidence: float = 0.0
    bbox: Optional[Tuple[float, float, float, float]] = None
    incident_eligible: bool = False

    @property
    def class_name(self) -> str:
        return self.detection_class or ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class": self.detection_class,
            "confidence": self.confidence,
            "bbox": list(self.bbox) if self.bbox is not None else [],
            "foot_point": list(self.foot_point),
            "inside_zone": self.inside_zone,
            "risk_level": self.risk_level,
            "confirmed": self.confirmed,
            "incident_eligible": self.incident_eligible,
        }


@dataclass(frozen=True)
class FrameRiskResult:
    overall_risk: str
    results: List[RiskResult]
    fire_consecutive_frames: int
    smoke_consecutive_frames: int
    fire_confirmed: bool
    smoke_confirmed: bool
    incidents_eligible: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_risk": self.overall_risk,
            "results": [r.to_dict() for r in self.results],
            "fire_consecutive_frames": self.fire_consecutive_frames,
            "smoke_consecutive_frames": self.smoke_consecutive_frames,
            "fire_confirmed": self.fire_confirmed,
            "smoke_confirmed": self.smoke_confirmed,
            "incidents_eligible": list(self.incidents_eligible),
        }


class RiskEngine:
    """
    IronEye spatial risk engine (Phase 3).

    Responsibilities:
    - Calculate the bottom-center ("foot") point of a detection box.
    - Determine whether that point lies inside a configured polygon using cv2.pointPolygonTest.
    - Maintain independent consecutive-frame confirmation counters for fire and smoke (10 frames).
    - Classify detections into LOW, HIGH, or CRITICAL risk levels.
    - Implement a 5-second per-class incident debounce interval.
    - Support multiple detections in a single frame without double-incrementing counters.
    """

    CONFIRMATION_FRAMES = 10
    DEBOUNCE_SECONDS = 5.0
    MONITORED_CLASSES = {"fire", "smoke"}

    def __init__(self) -> None:
        self._consecutive_counts: Dict[str, int] = {
            "fire": 0,
            "smoke": 0,
        }
        self._last_incident_time: Dict[str, float] = {}
        self._current_frame_id: int = 0
        self._frame_classes_counted: set[str] = set()

    @staticmethod
    def calculate_foot_point(
        bounding_box: Sequence[float],
    ) -> Point:
        """
        Calculate the bottom-center point of [x1, y1, x2, y2].
        """
        if len(bounding_box) != 4:
            raise ValueError("Bounding box must contain exactly 4 coordinates.")

        x1, y1, x2, y2 = bounding_box
        foot_x = int(round((x1 + x2) / 2))
        foot_y = int(round(y2))

        return foot_x, foot_y

    @staticmethod
    def point_inside_zone(
        foot_point: Point,
        polygon: Optional[Polygon],
    ) -> bool:
        """
        Use OpenCV pointPolygonTest to determine whether a foot point
        lies inside or on the boundary of the configured polygon.
        """
        if not polygon or len(polygon) < 3:
            return False

        contour = np.asarray(polygon, dtype=np.int32).reshape((-1, 1, 2))

        result = cv2.pointPolygonTest(
            contour,
            (float(foot_point[0]), float(foot_point[1])),
            False,
        )

        return result >= 0

    def update_confirmation(
        self,
        detection_class: str,
        detected: bool,
    ) -> bool:
        """
        Update the consecutive-confirmation counter for a class.
        Fire/smoke require 10 consecutive positive frames.
        Other classes are immediately considered confirmed if detected.
        """
        name = detection_class.lower().strip()

        if name not in self.MONITORED_CLASSES:
            return bool(detected)

        if detected:
            self._consecutive_counts[name] = self._consecutive_counts.get(name, 0) + 1
        else:
            self._consecutive_counts[name] = 0

        return self._consecutive_counts[name] >= self.CONFIRMATION_FRAMES

    def reset_confirmation(self, detection_class: Optional[str] = None) -> None:
        """
        Reset the confirmation counter for one class, or all classes if None.
        """
        if detection_class is not None:
            name = detection_class.lower().strip()
            if name in self._consecutive_counts:
                self._consecutive_counts[name] = 0
        else:
            for k in self._consecutive_counts:
                self._consecutive_counts[k] = 0

    def get_consecutive_count(self, detection_class: str) -> int:
        """Return the current consecutive qualifying frame count for a class."""
        return self._consecutive_counts.get(detection_class.lower().strip(), 0)

    def is_confirmed(self, detection_class: str) -> bool:
        """Return True if the detection class has reached the 10-frame threshold."""
        name = detection_class.lower().strip()
        if name not in self.MONITORED_CLASSES:
            return True
        return self.get_consecutive_count(name) >= self.CONFIRMATION_FRAMES

    def can_emit_incident(
        self,
        detection_class: str,
        now: float,
    ) -> bool:
        """
        Check whether an incident event is eligible to be emitted under the 5-second debounce.
        Does NOT modify the last emitted timestamp.
        """
        name = detection_class.lower().strip()
        last_time = self._last_incident_time.get(name)

        if last_time is not None:
            if now - last_time < self.DEBOUNCE_SECONDS:
                return False

        return True

    def record_incident(
        self,
        detection_class: str,
        now: float,
    ) -> None:
        """
        Record that an incident was actually emitted, updating the per-class debounce timer.
        """
        name = detection_class.lower().strip()
        self._last_incident_time[name] = float(now)

    def incident_allowed(
        self,
        detection_class: str,
        now: float,
    ) -> bool:
        """
        Enforce the 5-second debounce window.
        Returns True and records the timestamp when a new incident may be emitted.
        Returns False and preserves the timestamp when suppressed.
        """
        if self.can_emit_incident(detection_class, now):
            self.record_incident(detection_class, now)
            return True
        return False

    def reset_incident_timer(self, detection_class: Optional[str] = None) -> None:
        """Reset the incident debounce timer for a class or all classes."""
        if detection_class is not None:
            name = detection_class.lower().strip()
            self._last_incident_time.pop(name, None)
        else:
            self._last_incident_time.clear()

    def evaluate(
        self,
        detection_class: str,
        bounding_box: Sequence[float],
        polygon: Optional[Polygon],
        detected: bool = True,
        now: Optional[float] = None,
        frame_id: Optional[int] = None,
        confidence: float = 0.0,
    ) -> RiskResult:
        """
        Evaluate one detection against the configured safety zone.
        Preserves backward compatibility with existing StreamManager and callers.
        """
        name = detection_class.lower().strip()
        foot_point = self.calculate_foot_point(bounding_box)
        inside_zone = self.point_inside_zone(foot_point, polygon)

        # Handle frame ID boundary if provided
        if frame_id is not None:
            if frame_id != self._current_frame_id:
                self._current_frame_id = frame_id
                self._frame_classes_counted.clear()

        already_counted = (frame_id is not None and name in self._frame_classes_counted)

        if not detected:
            self.reset_confirmation(name)
            confirmed = False
        elif inside_zone:
            if not already_counted:
                confirmed = self.update_confirmation(name, True)
                if frame_id is not None:
                    self._frame_classes_counted.add(name)
            else:
                confirmed = self.is_confirmed(name)
        else:
            # Outside zone: do NOT increment confirmation
            confirmed = False

        if not inside_zone:
            risk_level = "LOW"
        elif not confirmed:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        now_val = time.time() if now is None else float(now)
        incident_eligible = bool(confirmed and inside_zone and self.can_emit_incident(name, now_val))

        return RiskResult(
            risk_level=risk_level,
            inside_zone=inside_zone,
            foot_point=foot_point,
            confirmed=confirmed,
            detection_class=name,
            confidence=confidence,
            bbox=tuple(float(c) for c in bounding_box),
            incident_eligible=incident_eligible,
        )

    def process_frame(
        self,
        detections: Sequence[Dict[str, Any]],
        polygon: Optional[Polygon],
        now: Optional[float] = None,
        auto_emit: bool = False,
    ) -> FrameRiskResult:
        """
        Process all detections in a single video frame.

        - Evaluates each detection's foot point against the safety zone.
        - Updates fire and smoke confirmation counters per-frame (not per-detection).
        - If a class is absent from the zone in this frame, resets its counter.
        - Calculates individual detection risk and overall frame risk.
        - Evaluates 5-second debounce eligibility for CRITICAL incidents.
        """
        now_val = time.time() if now is None else float(now)
        self._current_frame_id += 1
        self._frame_classes_counted.clear()

        # Step 1: Pre-scan detections for qualifying monitored classes
        qualifying_classes: set[str] = set()
        parsed_detections: List[Tuple[Dict[str, Any], str, float, Sequence[float], Point, bool]] = []

        for det in detections:
            cls_raw = det.get("class", det.get("name", ""))
            cls_name = str(cls_raw).lower().strip()
            conf = float(det.get("confidence", 0.0))
            raw_box = det.get("box", det.get("bbox", []))

            if len(raw_box) != 4:
                continue

            foot_point = self.calculate_foot_point(raw_box)
            inside_zone = self.point_inside_zone(foot_point, polygon)

            if cls_name in self.MONITORED_CLASSES and inside_zone:
                qualifying_classes.add(cls_name)

            parsed_detections.append((det, cls_name, conf, raw_box, foot_point, inside_zone))

        # Step 2: Update per-frame confirmation counters for monitored classes
        for cls in ("fire", "smoke"):
            if cls in qualifying_classes:
                self._consecutive_counts[cls] = self._consecutive_counts.get(cls, 0) + 1
            else:
                self._consecutive_counts[cls] = 0

        fire_confirmed = self._consecutive_counts["fire"] >= self.CONFIRMATION_FRAMES
        smoke_confirmed = self._consecutive_counts["smoke"] >= self.CONFIRMATION_FRAMES

        # Step 3: Check debounce eligibility for CRITICAL classes
        incidents_eligible: List[str] = []
        if fire_confirmed and self.can_emit_incident("fire", now_val):
            incidents_eligible.append("fire")
            if auto_emit:
                self.record_incident("fire", now_val)

        if smoke_confirmed and self.can_emit_incident("smoke", now_val):
            incidents_eligible.append("smoke")
            if auto_emit:
                self.record_incident("smoke", now_val)

        # Step 4: Build RiskResult for all detections
        results: List[RiskResult] = []
        for det, cls_name, conf, raw_box, foot_point, inside_zone in parsed_detections:
            if cls_name in self.MONITORED_CLASSES:
                is_confirmed = (self._consecutive_counts.get(cls_name, 0) >= self.CONFIRMATION_FRAMES)
                if not inside_zone:
                    risk_level = "LOW"
                    confirmed = False
                    incident_eligible = False
                else:
                    confirmed = is_confirmed
                    risk_level = "CRITICAL" if is_confirmed else "HIGH"
                    incident_eligible = (is_confirmed and cls_name in incidents_eligible)
            else:
                risk_level = "LOW"
                confirmed = False
                incident_eligible = False

            results.append(
                RiskResult(
                    risk_level=risk_level,
                    inside_zone=inside_zone,
                    foot_point=foot_point,
                    confirmed=confirmed,
                    detection_class=cls_name,
                    confidence=conf,
                    bbox=tuple(float(c) for c in raw_box),
                    incident_eligible=incident_eligible,
                )
            )

        # Step 5: Overall frame risk
        if any(r.risk_level == "CRITICAL" for r in results):
            overall_risk = "CRITICAL"
        elif any(r.risk_level == "HIGH" for r in results):
            overall_risk = "HIGH"
        else:
            overall_risk = "LOW"

        return FrameRiskResult(
            overall_risk=overall_risk,
            results=results,
            fire_consecutive_frames=self._consecutive_counts["fire"],
            smoke_consecutive_frames=self._consecutive_counts["smoke"],
            fire_confirmed=fire_confirmed,
            smoke_confirmed=smoke_confirmed,
            incidents_eligible=incidents_eligible,
        )