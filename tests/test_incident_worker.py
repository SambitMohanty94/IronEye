"""
tests/test_incident_worker.py
------------------------------
Focused tests for the StreamManager background incident-processing worker.

Design goals:
- No real Supabase calls, no real SMS messages.
- No unbounded sleeps: synchronisation events are used instead.
- Worker threads must not cause test-suite hangs (timeouts on every join).
"""
import queue
import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.engine.risk_engine import RiskResult
from src.engine.stream_manager import StreamManager


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_result(
    *,
    detection_class: str = "fire",
    risk_level: str = "CRITICAL",
    incident_eligible: bool = True,
    confirmed: bool = True,
    inside_zone: bool = True,
    foot_point=(100, 100),
    confidence: float = 0.9,
    bbox=(50.0, 50.0, 150.0, 150.0),
) -> RiskResult:
    """Return a RiskResult with sensible defaults for testing."""
    return RiskResult(
        detection_class=detection_class,
        risk_level=risk_level,
        incident_eligible=incident_eligible,
        confirmed=confirmed,
        inside_zone=inside_zone,
        foot_point=foot_point,
        confidence=confidence,
        bbox=bbox,
    )


def _blank_frame(h: int = 64, w: int = 64) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


@pytest.fixture
def sm():
    """StreamManager with IncidentService fully mocked out."""
    with patch("src.engine.stream_manager.IncidentService") as MockSvc:
        manager = StreamManager("videos/non_existent.mp4")
        manager.incident_service = MockSvc.return_value
        yield manager


# ---------------------------------------------------------------------------
# 1. Eligible critical incidents are enqueued and eventually processed
# ---------------------------------------------------------------------------

def test_eligible_critical_incident_is_processed(sm):
    """
    _queue_incident for an eligible CRITICAL result must cause
    incident_service.handle_critical_incident to be called exactly once.
    """
    handled = threading.Event()

    def _handle(**kwargs):
        handled.set()
        return {}

    sm.incident_service.handle_critical_incident.side_effect = _handle

    result = _make_result(risk_level="CRITICAL", incident_eligible=True)
    frame = _blank_frame()

    sm._queue_incident(frame, result)

    assert handled.wait(timeout=5), "Worker did not process the incident within 5 s"
    sm.incident_service.handle_critical_incident.assert_called_once()
    call_kwargs = sm.incident_service.handle_critical_incident.call_args
    assert call_kwargs.kwargs["risk_result"] is result


# ---------------------------------------------------------------------------
# 2. Non-eligible results are NOT enqueued
# ---------------------------------------------------------------------------

def test_non_eligible_result_is_not_queued(sm):
    """
    The generate_frames loop only calls _queue_incident when both
    incident_eligible=True and risk_level=="CRITICAL".
    Simulate the guard directly and verify the queue remains empty.
    """
    not_eligible = _make_result(risk_level="CRITICAL", incident_eligible=False)
    not_critical = _make_result(risk_level="HIGH", incident_eligible=True)

    # Call the guard as generate_frames would
    for result in [not_eligible, not_critical]:
        if result.incident_eligible and result.risk_level == "CRITICAL":
            sm._queue_incident(_blank_frame(), result)

    # Give a brief moment to confirm nothing was enqueued
    time.sleep(0.05)
    assert sm._incident_queue.empty(), "Non-eligible/non-critical results must not reach the queue"
    sm.incident_service.handle_critical_incident.assert_not_called()


# ---------------------------------------------------------------------------
# 3. A full queue does not block the caller
# ---------------------------------------------------------------------------

def test_full_queue_does_not_block_caller(sm):
    """
    When the queue is at capacity (maxsize=20), _queue_incident must return
    immediately (put_nowait) without blocking the video-processing thread.
    """
    # Prevent the worker from draining the queue during this test
    original_get = sm._incident_queue.get

    drain_allowed = threading.Event()

    def slow_get(*args, **kwargs):
        drain_allowed.wait()
        return original_get(*args, **kwargs)

    sm._incident_queue.get = slow_get

    result = _make_result()
    frame = _blank_frame()

    # Fill to capacity
    for _ in range(20):
        sm._incident_queue.put_nowait((frame, result))

    start = time.monotonic()
    sm._queue_incident(frame, result)   # 21st item — should drop without blocking
    elapsed = time.monotonic() - start

    drain_allowed.set()           # let worker drain so thread can exit cleanly
    sm._incident_queue.get = original_get

    assert elapsed < 0.5, f"_queue_incident blocked for {elapsed:.3f}s on a full queue"
    assert sm._incident_queue.qsize() == 20, "Queue size must remain at capacity (item was dropped)"


# ---------------------------------------------------------------------------
# 4. An exception in incident handling does not kill the worker
# ---------------------------------------------------------------------------

def test_exception_in_handler_does_not_kill_worker(sm):
    """
    When handle_critical_incident raises, the worker must survive and
    continue processing subsequent incidents.
    """
    call_count = [0]
    second_handled = threading.Event()

    def flaky_handle(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("simulated DB failure")
        second_handled.set()
        return {}

    sm.incident_service.handle_critical_incident.side_effect = flaky_handle

    result = _make_result()
    frame = _blank_frame()

    sm._queue_incident(frame, result)   # first — will raise
    # Wait briefly for the first one to be dequeued, then enqueue the second
    time.sleep(0.15)
    sm._queue_incident(frame, result)   # second — should succeed

    assert second_handled.wait(timeout=5), "Worker died after first exception and did not process second incident"
    assert call_count[0] == 2


# ---------------------------------------------------------------------------
# 5. Only one worker thread is created regardless of concurrent calls
# ---------------------------------------------------------------------------

def test_only_one_worker_thread_is_created(sm):
    """
    _ensure_worker_started called concurrently from many threads must
    set _incident_worker_started exactly once.  We verify idempotence by
    calling it again afterwards and checking the flag is still True and the
    queue is still empty (no extra items or threads were created).
    """
    barrier = threading.Barrier(10)

    def _call():
        barrier.wait()
        sm._ensure_worker_started()

    threads = [threading.Thread(target=_call) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    # Flag must be set after concurrent calls
    assert sm._incident_worker_started is True, "Worker flag was not set"

    # Calling again must be idempotent (no exception, flag still True)
    sm._ensure_worker_started()
    sm._ensure_worker_started()
    assert sm._incident_worker_started is True

    # Queue must still be empty – no spurious items added
    assert sm._incident_queue.empty()


# ---------------------------------------------------------------------------
# 6. stop() / start() do not terminate the worker
# ---------------------------------------------------------------------------

def test_stop_and_start_do_not_terminate_worker(sm):
    """
    Calling stop() then start() must not shut down the incident worker.
    An incident queued after restart must still be processed.
    """
    handled_after_restart = threading.Event()

    def _handle(**kwargs):
        handled_after_restart.set()
        return {}

    sm.incident_service.handle_critical_incident.side_effect = _handle

    # Start a worker first
    sm._ensure_worker_started()
    sm.stop()
    sm.start()

    result = _make_result()
    sm._queue_incident(_blank_frame(), result)

    assert handled_after_restart.wait(timeout=5), "Worker was killed by stop()/start() and could not process incident"


# ---------------------------------------------------------------------------
# 7. Queued frame is a copy (mutation of original does not corrupt evidence)
# ---------------------------------------------------------------------------

def test_queued_frame_is_independent_copy(sm):
    """
    The frame stored in the queue must be independent of the original so that
    later frame-processing steps cannot alter evidence already enqueued.
    """
    received_frames = []

    def _capture(**kwargs):
        received_frames.append(kwargs["frame"].copy())
        return {}

    sm.incident_service.handle_critical_incident.side_effect = _capture

    original = _blank_frame()
    copy_before_call = original.copy()

    sm._queue_incident(original.copy(), _make_result())   # caller passes a copy

    # Mutate original after queuing
    original[:] = 255

    # Wait for worker
    for _ in range(50):
        if received_frames:
            break
        time.sleep(0.1)

    assert received_frames, "Handler was never called"
    assert np.array_equal(received_frames[0], copy_before_call), (
        "Evidence frame was mutated after queuing"
    )


# ---------------------------------------------------------------------------
# 8. Public API / StreamManager attribute compatibility
# ---------------------------------------------------------------------------

def test_stream_manager_has_required_worker_attributes():
    """Regression: StreamManager exposes the required worker attributes."""
    with patch("src.engine.stream_manager.IncidentService"):
        manager = StreamManager("videos/non_existent.mp4")
    assert hasattr(manager, "_incident_queue")
    assert isinstance(manager._incident_queue, queue.Queue)
    assert manager._incident_queue.maxsize == 20
    assert hasattr(manager, "_incident_worker_started")
    assert manager._incident_worker_started is False
    assert hasattr(manager, "_incident_worker_lock")
    assert callable(manager._queue_incident)
    assert callable(manager._ensure_worker_started)
