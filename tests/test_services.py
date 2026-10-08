"""
tests/test_services.py
------------------------
Tests for IncidentWriter, AlertEngine, evidence saving, and IncidentService.

Rules:
- No live Supabase calls, no real SMS messages.
- Mocks are used for all external dependencies.
- Tests verify honest return values (no false successes).
"""
import logging
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from src.alert_engine import AlertEngine
from src.database.evidence import save_evidence
from src.database.incident_writer import IncidentWriter
from src.database.incident_service import IncidentService
from src.engine.risk_engine import RiskResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _blank_frame(h: int = 32, w: int = 32) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _make_risk_result(**overrides) -> RiskResult:
    defaults = dict(
        detection_class="fire",
        risk_level="CRITICAL",
        incident_eligible=True,
        confirmed=True,
        inside_zone=True,
        foot_point=(100, 100),
        confidence=0.9,
        bbox=(50.0, 50.0, 150.0, 150.0),
    )
    defaults.update(overrides)
    return RiskResult(**defaults)


# ===========================================================================
# IncidentWriter tests
# ===========================================================================

class TestIncidentWriter:

    def test_disabled_when_no_credentials(self):
        """IncidentWriter with no client is disabled and write_incident returns None."""
        writer = IncidentWriter(client=None)
        # Patch env so create_client is not attempted
        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_SECRET_KEY": ""}):
            writer2 = IncidentWriter()
        assert writer2.enabled is False
        result = writer2.write_incident({"incident_type": "fire", "risk_level": "CRITICAL"})
        assert result is None

    def test_write_incident_returns_row_on_success(self):
        """write_incident returns the first data row when Supabase succeeds."""
        mock_client = MagicMock()
        expected_row = {"id": "abc-123", "incident_type": "fire"}
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[expected_row]
        )
        writer = IncidentWriter(client=mock_client)
        result = writer.write_incident({"incident_type": "fire", "risk_level": "CRITICAL"})
        assert result == expected_row

    def test_write_incident_returns_none_on_empty_response(self):
        """
        When Supabase returns an empty data list (e.g., RLS blocked),
        write_incident must return None, not fabricate success.
        """
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[]
        )
        writer = IncidentWriter(client=mock_client)
        result = writer.write_incident({"incident_type": "fire", "risk_level": "CRITICAL"})
        assert result is None

    def test_write_incident_returns_none_on_exception(self):
        """DB exceptions are caught; write_incident returns None without raising."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.side_effect = RuntimeError(
            "connection refused"
        )
        writer = IncidentWriter(client=mock_client)
        result = writer.write_incident({"incident_type": "fire", "risk_level": "CRITICAL"})
        assert result is None

    def test_write_incident_logs_exception(self, caplog):
        """Exceptions during persistence are logged at ERROR level."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.side_effect = RuntimeError(
            "timeout"
        )
        writer = IncidentWriter(client=mock_client)
        with caplog.at_level(logging.ERROR, logger="src.database.incident_writer"):
            writer.write_incident({"incident_type": "smoke", "risk_level": "CRITICAL"})
        assert any("persist" in r.message.lower() or "supabase" in r.message.lower()
                   for r in caplog.records), "Expected an error log entry for persistence failure"

    def test_write_incident_logs_warning_on_empty_response(self, caplog):
        """Empty response rows are logged as a warning."""
        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[]
        )
        writer = IncidentWriter(client=mock_client)
        with caplog.at_level(logging.WARNING, logger="src.database.incident_writer"):
            writer.write_incident({"incident_type": "fire", "risk_level": "CRITICAL"})
        assert any("no rows" in r.message.lower() or "rls" in r.message.lower()
                   for r in caplog.records), "Expected a warning log for empty response"


# ===========================================================================
# AlertEngine tests
# ===========================================================================

class TestAlertEngine:

    def test_disabled_when_no_credentials(self):
        """AlertEngine without client is disabled; send_critical_alert returns False."""
        engine = AlertEngine(client=None)
        # Force disable by clearing numbers
        engine.from_number = ""
        engine.to_number = ""
        result = engine.send_critical_alert(incident_type="fire")
        assert result is False

    def test_returns_true_on_successful_send(self):
        """send_critical_alert returns True when Twilio API call succeeds."""
        mock_client = MagicMock()
        engine = AlertEngine(client=mock_client)
        engine.from_number = "+15550001111"
        engine.to_number = "+15550002222"

        result = engine.send_critical_alert(incident_type="fire", evidence_path="/tmp/ev.jpg")

        assert result is True
        mock_client.messages.create.assert_called_once()

    def test_returns_false_on_twilio_exception(self):
        """Twilio failures return False; the exception does not propagate."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("auth error")
        engine = AlertEngine(client=mock_client)
        engine.from_number = "+15550001111"
        engine.to_number = "+15550002222"

        result = engine.send_critical_alert(incident_type="fire")

        assert result is False

    def test_twilio_failure_is_logged_without_credentials(self, caplog):
        """Twilio failure log entry must not contain from_number or to_number."""
        mock_client = MagicMock()
        secret_from = "+15550001111"
        secret_to = "+15550002222"
        mock_client.messages.create.side_effect = RuntimeError("auth error")
        engine = AlertEngine(client=mock_client)
        engine.from_number = secret_from
        engine.to_number = secret_to

        with caplog.at_level(logging.WARNING, logger="src.alert_engine"):
            engine.send_critical_alert(incident_type="smoke")

        combined = " ".join(r.message for r in caplog.records)
        assert secret_from not in combined, "Phone number must not appear in logs"
        assert secret_to not in combined, "Phone number must not appear in logs"

    def test_sms_only_attempted_for_critical_incidents(self):
        """
        IncidentService must call send_critical_alert only for CRITICAL risk_level.
        """
        mock_writer = MagicMock()
        mock_writer.write_incident.return_value = None
        mock_alert = MagicMock()
        mock_alert.send_critical_alert.return_value = False

        service = IncidentService(incident_writer=mock_writer, alert_engine=mock_alert)

        high_result = _make_risk_result(risk_level="HIGH")
        service.handle_critical_incident(frame=_blank_frame(), risk_result=high_result)
        mock_alert.send_critical_alert.assert_not_called()

        mock_alert.reset_mock()
        critical_result = _make_risk_result(risk_level="CRITICAL")
        service.handle_critical_incident(frame=_blank_frame(), risk_result=critical_result)
        mock_alert.send_critical_alert.assert_called_once()


# ===========================================================================
# Evidence saving tests
# ===========================================================================

class TestSaveEvidence:

    def test_none_frame_returns_none(self):
        assert save_evidence(None) is None

    def test_empty_array_returns_none(self):
        assert save_evidence(np.array([])) is None

    def test_valid_frame_saves_and_returns_path(self, tmp_path, monkeypatch):
        """A valid frame must be saved to EVIDENCE_DIR and the path returned."""
        import src.database.evidence as ev_mod
        monkeypatch.setattr(ev_mod, "EVIDENCE_DIR", tmp_path / "evidence")

        frame = _blank_frame()
        path = save_evidence(frame)

        assert path is not None, "Expected a path, got None"
        assert Path(path).exists(), f"Evidence file not found: {path}"
        assert path.endswith(".jpg")

    def test_oserror_on_mkdir_returns_none(self, monkeypatch):
        """OSError from mkdir (e.g., disk full) must return None without raising."""
        import src.database.evidence as ev_mod
        # Patch Path.mkdir at class level (instance attribute is read-only on Windows).
        monkeypatch.setattr("pathlib.Path.mkdir", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")))

        frame = _blank_frame()
        result = save_evidence(frame)
        assert result is None

    def test_imwrite_failure_returns_none(self, tmp_path, monkeypatch):
        """When cv2.imwrite returns False, save_evidence must return None."""
        import src.database.evidence as ev_mod
        monkeypatch.setattr(ev_mod, "EVIDENCE_DIR", tmp_path / "evidence")
        monkeypatch.setattr(ev_mod.cv2, "imwrite", lambda *_: False)

        frame = _blank_frame()
        result = save_evidence(frame)
        assert result is None

    def test_returned_path_matches_saved_file(self, tmp_path, monkeypatch):
        """The returned string path must correspond to an actual file on disk."""
        import src.database.evidence as ev_mod
        monkeypatch.setattr(ev_mod, "EVIDENCE_DIR", tmp_path / "evidence")

        frame = np.full((10, 10, 3), 128, dtype=np.uint8)
        path = save_evidence(frame)
        assert path is not None
        assert os.path.isfile(path)


# ===========================================================================
# IncidentService integration
# ===========================================================================

class TestIncidentService:

    def test_handle_critical_incident_returns_dict(self):
        """handle_critical_incident always returns a dict with expected keys."""
        mock_writer = MagicMock()
        mock_writer.write_incident.return_value = {"id": "123"}
        mock_alert = MagicMock()
        mock_alert.send_critical_alert.return_value = True

        service = IncidentService(incident_writer=mock_writer, alert_engine=mock_alert)
        result = service.handle_critical_incident(
            frame=_blank_frame(), risk_result=_make_risk_result()
        )

        assert isinstance(result, dict)
        assert "evidence_path" in result
        assert "incident" in result
        assert "alert_sent" in result

    def test_persistence_failure_does_not_crash(self):
        """If incident_writer raises, handle_critical_incident must not propagate."""
        mock_writer = MagicMock()
        mock_writer.write_incident.side_effect = RuntimeError("db down")
        mock_alert = MagicMock()

        service = IncidentService(incident_writer=mock_writer, alert_engine=mock_alert)
        # Should not raise
        try:
            service.handle_critical_incident(
                frame=_blank_frame(), risk_result=_make_risk_result()
            )
        except RuntimeError:
            pytest.fail("handle_critical_incident propagated an exception from incident_writer")

    def test_alert_failure_does_not_crash(self):
        """If alert_engine raises, handle_critical_incident must not propagate."""
        mock_writer = MagicMock()
        mock_writer.write_incident.return_value = None
        mock_alert = MagicMock()
        mock_alert.send_critical_alert.side_effect = RuntimeError("twilio down")

        service = IncidentService(incident_writer=mock_writer, alert_engine=mock_alert)
        try:
            service.handle_critical_incident(
                frame=_blank_frame(), risk_result=_make_risk_result()
            )
        except RuntimeError:
            pytest.fail("handle_critical_incident propagated an exception from alert_engine")

    def test_alert_sent_reflects_actual_outcome(self):
        """alert_sent in the returned dict must match what send_critical_alert returns."""
        mock_writer = MagicMock()
        mock_writer.write_incident.return_value = None
        mock_alert_fail = MagicMock()
        mock_alert_fail.send_critical_alert.return_value = False

        service = IncidentService(incident_writer=mock_writer, alert_engine=mock_alert_fail)
        result = service.handle_critical_incident(
            frame=_blank_frame(), risk_result=_make_risk_result(risk_level="CRITICAL")
        )
        assert result["alert_sent"] is False

        mock_alert_ok = MagicMock()
        mock_alert_ok.send_critical_alert.return_value = True
        service2 = IncidentService(incident_writer=mock_writer, alert_engine=mock_alert_ok)
        result2 = service2.handle_critical_incident(
            frame=_blank_frame(), risk_result=_make_risk_result(risk_level="CRITICAL")
        )
        assert result2["alert_sent"] is True
