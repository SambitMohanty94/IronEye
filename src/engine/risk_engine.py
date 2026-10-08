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
            "results": [result.to_dict() for result in self.results],
            "fire_consecutive_frames": self.fire_consecutive_frames,
            "smoke_consecutive_frames": self.smoke_consecutive_frames,
            "fire_confirmed": self.fire_confirmed,
            "smoke_confirmed": self.smoke_confirmed,
            "incidents_eligible": list(self.incidents_eligible),
        }


class RiskEngine:
    """
    IronEye risk engine.

    Fire and smoke are tracked independently. Each class must be detected
    in 10 consecutive processed frames before reaching CRITICAL.

    If a valid safety-zone polygon is configured, detections are evaluated
    against it. If no valid polygon is configured, the whole frame is
    monitored instead of silently suppressing all fire/smoke detections.

    Incident eligibility uses a per-class 5-second debounce interval.
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
    def _normalize_class(detection_class: Any) -> str:
        return str(detection_class or "").lower().strip()

    @staticmethod
    def _valid_polygon(polygon: Optional[Polygon]) -> bool:
        if polygon is None:
            return False

        try:
            return len(polygon) >= 3
        except (TypeError, ValueError):
            return False

    @staticmethod
    def calculate_foot_point(
        bounding_box: Sequence[float],
    ) -> Point:
        """Return the bottom-center point of [x1, y1, x2, y2]."""
        if len(bounding_box) != 4:
            raise ValueError(
                "Bounding box must contain exactly 4 coordinates."
            )

        x1, y1, x2, y2 = (float(value) for value in bounding_box)

        return (
            int(round((x1 + x2) / 2.0)),
            int(round(y2)),
        )

    @staticmethod
    def point_inside_zone(
        foot_point: Point,
        polygon: Optional[Polygon],
    ) -> bool:
        """
        Check whether a point lies inside or on a polygon boundary.

        This geometric helper returns False for a missing/invalid polygon.
        The risk engine separately treats a missing polygon as full-frame
        monitoring.
        """
        if polygon is None:
            return False

        try:
            if len(polygon) < 3:
                return False

            contour = np.asarray(polygon, dtype=np.float32).reshape(
                (-1, 1, 2)
            )

            if not np.isfinite(contour).all():
                return False

            result = cv2.pointPolygonTest(
                contour,
                (float(foot_point[0]), float(foot_point[1])),
                False,
            )

            return result >= 0

        except (TypeError, ValueError, cv2.error):
            return False

    @classmethod
    def _point_is_monitored(
        cls,
        foot_point: Point,
        polygon: Optional[Polygon],
    ) -> bool:
        """
        A missing/invalid zone means full-frame monitoring.
        A configured zone restricts monitoring to points inside it.
        """
        if not cls._valid_polygon(polygon):
            return True

        return cls.point_inside_zone(foot_point, polygon)

    def update_confirmation(
        self,
        detection_class: str,
        detected: bool,
    ) -> bool:
        """Update the per-class consecutive-frame counter."""
        name = self._normalize_class(detection_class)

        if name not in self.MONITORED_CLASSES:
            return bool(detected)

        if detected:
            self._consecutive_counts[name] += 1
        else:
            self._consecutive_counts[name] = 0

        return (
            self._consecutive_counts[name]
            >= self.CONFIRMATION_FRAMES
        )

    def reset_confirmation(
        self,
        detection_class: Optional[str] = None,
    ) -> None:
        """Reset one class counter or all class counters."""
        if detection_class is not None:
            name = self._normalize_class(detection_class)

            if name in self._consecutive_counts:
                self._consecutive_counts[name] = 0
        else:
            for name in self._consecutive_counts:
                self._consecutive_counts[name] = 0

    def get_consecutive_count(self, detection_class: str) -> int:
        """Return the current consecutive-frame count for a class."""
        name = self._normalize_class(detection_class)
        return self._consecutive_counts.get(name, 0)

    def is_confirmed(self, detection_class: str) -> bool:
        """Check whether a monitored class has reached confirmation."""
        name = self._normalize_class(detection_class)

        if name not in self.MONITORED_CLASSES:
            return True

        return (
            self._consecutive_counts[name]
            >= self.CONFIRMATION_FRAMES
        )

    def can_emit_incident(
        self,
        detection_class: str,
        now: float,
    ) -> bool:
        """Check debounce eligibility without recording an incident."""
        name = self._normalize_class(detection_class)
        last_time = self._last_incident_time.get(name)

        if last_time is None:
            return True

        return float(now) - last_time >= self.DEBOUNCE_SECONDS

    def record_incident(
        self,
        detection_class: str,
        now: float,
    ) -> None:
        """Record an incident timestamp for the specified class."""
        name = self._normalize_class(detection_class)
        self._last_incident_time[name] = float(now)

    def incident_allowed(
        self,
        detection_class: str,
        now: float,
    ) -> bool:
        """Check and record incident eligibility in one operation."""
        if self.can_emit_incident(detection_class, now):
            self.record_incident(detection_class, now)
            return True

        return False

    def reset_incident_timer(
        self,
        detection_class: Optional[str] = None,
    ) -> None:
        """Reset one incident timer or all incident timers."""
        if detection_class is None:
            self._last_incident_time.clear()
        else:
            name = self._normalize_class(detection_class)
            self._last_incident_time.pop(name, None)

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
        """Evaluate a single detection."""
        name = self._normalize_class(detection_class)
        foot_point = self.calculate_foot_point(bounding_box)

        inside_zone = self._point_is_monitored(
            foot_point,
            polygon,
        )

        if frame_id is not None and frame_id != self._current_frame_id:
            self._current_frame_id = frame_id
            self._frame_classes_counted.clear()

        already_counted = (
            frame_id is not None
            and name in self._frame_classes_counted
        )

        if name not in self.MONITORED_CLASSES:
            confirmed = bool(detected)
            risk_level = "LOW"
            incident_eligible = False

        elif not detected or not inside_zone:
            if not detected:
                self.reset_confirmation(name)

            confirmed = False
            risk_level = "LOW"
            incident_eligible = False

        else:
            if not already_counted:
                confirmed = self.update_confirmation(name, True)

                if frame_id is not None:
                    self._frame_classes_counted.add(name)
            else:
                confirmed = self.is_confirmed(name)

            risk_level = "CRITICAL" if confirmed else "HIGH"

            now_val = time.time() if now is None else float(now)
            incident_eligible = (
                confirmed
                and self.can_emit_incident(name, now_val)
            )

        return RiskResult(
            risk_level=risk_level,
            inside_zone=inside_zone,
            foot_point=foot_point,
            confirmed=confirmed,
            detection_class=name,
            confidence=float(confidence),
            bbox=tuple(float(value) for value in bounding_box),
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
        Process a complete frame.

        Each monitored class increments at most once per frame, regardless
        of how many boxes of that class were detected.
        """
        now_val = time.time() if now is None else float(now)

        self._current_frame_id += 1
        self._frame_classes_counted.clear()

        parsed_detections: List[
            Tuple[str, float, Tuple[float, float, float, float], Point, bool]
        ] = []

        qualifying_classes: set[str] = set()

        for det in detections or []:
            if not isinstance(det, dict):
                continue

            cls_raw = det.get("class", det.get("name", ""))
            cls_name = self._normalize_class(cls_raw)

            try:
                conf = float(det.get("confidence", 0.0))
                raw_box = det.get("box", det.get("bbox", []))

                if raw_box is None or len(raw_box) != 4:
                    continue

                box = tuple(float(value) for value in raw_box)

                if not np.isfinite(box).all():
                    continue

                foot_point = self.calculate_foot_point(box)

            except (TypeError, ValueError, OverflowError):
                continue

            monitored = self._point_is_monitored(
                foot_point,
                polygon,
            )

            if (
                cls_name in self.MONITORED_CLASSES
                and monitored
            ):
                qualifying_classes.add(cls_name)

            parsed_detections.append(
                (cls_name, conf, box, foot_point, monitored)
            )

        # Increment once per class per processed frame.
        for cls_name in ("fire", "smoke"):
            if cls_name in qualifying_classes:
                self._consecutive_counts[cls_name] += 1
            else:
                self._consecutive_counts[cls_name] = 0

        fire_count = self._consecutive_counts["fire"]
        smoke_count = self._consecutive_counts["smoke"]

        fire_confirmed = fire_count >= self.CONFIRMATION_FRAMES
        smoke_confirmed = smoke_count >= self.CONFIRMATION_FRAMES

        incidents_eligible: List[str] = []

        if fire_confirmed and self.can_emit_incident("fire", now_val):
            incidents_eligible.append("fire")

            if auto_emit:
                self.record_incident("fire", now_val)

        if smoke_confirmed and self.can_emit_incident("smoke", now_val):
            incidents_eligible.append("smoke")

            if auto_emit:
                self.record_incident("smoke", now_val)

        results: List[RiskResult] = []

        for cls_name, conf, box, foot_point, monitored in parsed_detections:
            if cls_name not in self.MONITORED_CLASSES:
                results.append(
                    RiskResult(
                        risk_level="LOW",
                        inside_zone=monitored,
                        foot_point=foot_point,
                        confirmed=False,
                        detection_class=cls_name,
                        confidence=conf,
                        bbox=box,
                        incident_eligible=False,
                    )
                )
                continue

            confirmed = (
                fire_confirmed if cls_name == "fire"
                else smoke_confirmed
            )

            if not monitored:
                risk_level = "LOW"
                confirmed = False
                incident_eligible = False
            else:
                risk_level = (
                    "CRITICAL" if confirmed else "HIGH"
                )
                incident_eligible = (
                    confirmed
                    and cls_name in incidents_eligible
                )

            results.append(
                RiskResult(
                    risk_level=risk_level,
                    inside_zone=monitored,
                    foot_point=foot_point,
                    confirmed=confirmed,
                    detection_class=cls_name,
                    confidence=conf,
                    bbox=box,
                    incident_eligible=incident_eligible,
                )
            )

        if any(result.risk_level == "CRITICAL" for result in results):
            overall_risk = "CRITICAL"
        elif any(result.risk_level == "HIGH" for result in results):
            overall_risk = "HIGH"
        else:
            overall_risk = "LOW"

        return FrameRiskResult(
            overall_risk=overall_risk,
            results=results,
            fire_consecutive_frames=fire_count,
            smoke_consecutive_frames=smoke_count,
            fire_confirmed=fire_confirmed,
            smoke_confirmed=smoke_confirmed,
            incidents_eligible=incidents_eligible,
        )