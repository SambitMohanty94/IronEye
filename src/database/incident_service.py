from __future__ import annotations

from typing import Any, Optional

from src.database.evidence import save_evidence
from src.database.incident_writer import IncidentWriter
from src.alert_engine import AlertEngine


class IncidentService:
    """Coordinates evidence, persistence, and critical alerting."""

    def __init__(
        self,
        incident_writer: Optional[IncidentWriter] = None,
        alert_engine: Optional[AlertEngine] = None,
    ) -> None:
        self.incident_writer = incident_writer or IncidentWriter()
        self.alert_engine = alert_engine or AlertEngine()

    def handle_critical_incident(
        self,
        frame: Any,
        risk_result: Any,
        camera_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Process one emitted CRITICAL incident."""

        evidence_path = save_evidence(frame)

        incident = {
            "camera_id": camera_id,
            "incident_type": risk_result.detection_class,
            "risk_level": risk_result.risk_level,
            "confidence": risk_result.confidence,
            "foot_x": risk_result.foot_point[0] if risk_result.foot_point else None,
            "foot_y": risk_result.foot_point[1] if risk_result.foot_point else None,
            "evidence_path": evidence_path,
        }

        stored_incident = self.incident_writer.write_incident(incident)

        alert_sent = False

        if risk_result.risk_level == "CRITICAL":
            alert_sent = self.alert_engine.send_critical_alert(
                incident_type=risk_result.detection_class,
                evidence_path=evidence_path,
            )

        return {
            "evidence_path": evidence_path,
            "incident": stored_incident,
            "alert_sent": alert_sent,
        }