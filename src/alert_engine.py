from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


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
            return False

        message = (
            f"IronEye CRITICAL alert: {incident_type}. "
            f"Evidence: {evidence_path or 'not available'}"
        )

        try:
            self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=self.to_number,
            )
            return True
        except Exception:
            # Alerting must never crash the video-processing loop.
            return False