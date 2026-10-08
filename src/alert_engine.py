from __future__ import annotations

import logging
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class AlertEngine:
    """Dispatch CRITICAL IronEye alerts through Twilio SMS."""

    def __init__(self, client=None) -> None:
        self.client = client
        self.from_number = os.getenv("TWILIO_FROM_NUMBER", "").strip()
        self.to_number = os.getenv("TWILIO_TO_NUMBER", "").strip()

        if self.client is None:
            account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
            auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()

            if account_sid and auth_token:
                from twilio.rest import Client

                self.client = Client(account_sid, auth_token)

    @property
    def enabled(self) -> bool:
        return (
            self.client is not None
            and bool(self.from_number)
            and bool(self.to_number)
        )

    def send_critical_alert(
        self,
        incident_type: str,
        evidence_path: Optional[str] = None,
    ) -> bool:
        """Send an SMS for a CRITICAL incident.

        Returns True only when a message is successfully submitted.
        """

        if not self.enabled:
            missing = []
            if not os.getenv("TWILIO_ACCOUNT_SID"):
                missing.append("TWILIO_ACCOUNT_SID")
            if not os.getenv("TWILIO_AUTH_TOKEN"):
                missing.append("TWILIO_AUTH_TOKEN")
            if not self.from_number:
                missing.append("TWILIO_FROM_NUMBER")
            if not self.to_number:
                missing.append("TWILIO_TO_NUMBER")

            if missing:
                logger.info(
                    "Twilio SMS not configured; missing environment variables: %s. Skipping alert for incident_type=%s.",
                    ", ".join(missing),
                    incident_type,
                )
            else:
                logger.info(
                    "Twilio client not initialized; skipping alert for incident_type=%s.",
                    incident_type,
                )
            return False

        message = (
            f"IronEye CRITICAL alert: {incident_type}. "
            f"Evidence: {evidence_path or 'not available'}"
        )

        try:
            result = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=self.to_number,
            )
            sid = getattr(result, "sid", None)
            if sid or result is not None:
                logger.info(
                    "SMS alert sent successfully for incident_type=%s.",
                    incident_type,
                )
                return True
            logger.warning(
                "Twilio SMS create call returned invalid response for incident_type=%s.",
                incident_type,
            )
            return False
        except Exception:
            # Alerting must never crash the video-processing loop.
            # Log without credentials — only incident context.
            logger.warning(
                "Twilio SMS failed for incident_type=%s (credentials not logged).",
                incident_type,
            )
            return False