from __future__ import annotations

import os
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()


class IncidentWriter:
    """Write IronEye incidents to Supabase PostgreSQL.

    If Supabase credentials are not configured, writes are skipped
    gracefully so local development and tests can continue.
    """

    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client

        if self.client is None:
            url = os.getenv("SUPABASE_URL", "").strip()
            key = os.getenv("SUPABASE_SECRET_KEY", "").strip()

            if url and key:
                from supabase import create_client

                self.client = create_client(url, key)

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def write_incident(self, incident: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Insert one incident into the incidents table.

        Returns the inserted row when Supabase is configured.
        Returns None when persistence is disabled or unavailable.
        """

        if not self.enabled:
            return None

        try:
            response = (
                self.client
                .table("incidents")
                .insert(incident)
                .execute()
            )

            data = getattr(response, "data", None)

            if isinstance(data, list) and data:
                return data[0]

            return None

        except Exception:
            # Persistence must never crash the video-processing loop.
            return None