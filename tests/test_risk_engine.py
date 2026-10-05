import pytest
from src.engine.risk_engine import RiskEngine, RiskResult, FrameRiskResult
from src.engine.stream_manager import StreamManager


@pytest.fixture
def risk_engine() -> RiskEngine:
    return RiskEngine()


@pytest.fixture
def square_zone():
    # 200x200 square zone from (0,0) to (200,200)
    return [(0, 0), (200, 0), (200, 200), (0, 200)]


# ---------------------------------------------------------------------------
# 1. bottom-center foot-point calculation
# ---------------------------------------------------------------------------
def test_foot_point_calculation(risk_engine: RiskEngine):
    # Standard box: x1=100, y1=200, x2=300, y2=500 -> bottom-center = ((100+300)/2, 500) = (200, 500)
    foot = risk_engine.calculate_foot_point([100, 200, 300, 500])
    assert foot == (200, 500)

    # Float coordinates with rounding: ((10.2 + 30.6)/2 = 20.4 -> 20, 40.8 -> 41)
    foot_float = risk_engine.calculate_foot_point([10.2, 20.4, 30.6, 40.8])
    assert foot_float == (20, 41)

    # Invalid bounding box length must raise ValueError
    with pytest.raises(ValueError):
        risk_engine.calculate_foot_point([100, 200, 300])


# ---------------------------------------------------------------------------
# 2. point inside polygon
# ---------------------------------------------------------------------------
def test_point_inside_polygon(risk_engine: RiskEngine, square_zone):
    inside_point = (100, 100)
    assert risk_engine.point_inside_zone(inside_point, square_zone) is True


# ---------------------------------------------------------------------------
# 3. point outside polygon
# ---------------------------------------------------------------------------
def test_point_outside_polygon(risk_engine: RiskEngine, square_zone):
    outside_point = (250, 100)
    assert risk_engine.point_inside_zone(outside_point, square_zone) is False

    # No polygon configured or fewer than 3 points
    assert risk_engine.point_inside_zone((100, 100), None) is False
    assert risk_engine.point_inside_zone((100, 100), [(0, 0), (100, 0)]) is False


# ---------------------------------------------------------------------------
# 4. boundary point counts as inside
# ---------------------------------------------------------------------------
def test_boundary_point_counts_as_inside(risk_engine: RiskEngine, square_zone):
    # Point directly on top edge (y=0)
    edge_point = (100, 0)
    assert risk_engine.point_inside_zone(edge_point, square_zone) is True

    # Point directly on right edge (x=200)
    edge_point_2 = (200, 100)
    assert risk_engine.point_inside_zone(edge_point_2, square_zone) is True

    # Vertex point (0, 0)
    vertex_point = (0, 0)
    assert risk_engine.point_inside_zone(vertex_point, square_zone) is True


# ---------------------------------------------------------------------------
# 5. first inside-zone fire = HIGH
# ---------------------------------------------------------------------------
def test_first_inside_zone_fire_is_high(risk_engine: RiskEngine, square_zone):
    # Bounding box bottom-center at (100, 150) -> inside square zone
    inside_box = [50, 50, 150, 150]
    result = risk_engine.evaluate("fire", inside_box, square_zone)

    assert result.inside_zone is True
    assert result.confirmed is False
    assert result.risk_level == "HIGH"
    assert risk_engine.get_consecutive_count("fire") == 1


# ---------------------------------------------------------------------------
# 6. nine consecutive qualifying fire frames = HIGH
# ---------------------------------------------------------------------------
def test_nine_consecutive_fire_frames_is_high(risk_engine: RiskEngine, square_zone):
    inside_box = [50, 50, 150, 150]

    for frame in range(1, 10):
        result = risk_engine.evaluate("fire", inside_box, square_zone)
        assert result.inside_zone is True
        assert result.confirmed is False
        assert result.risk_level == "HIGH"
        assert risk_engine.get_consecutive_count("fire") == frame


# ---------------------------------------------------------------------------
# 7. tenth consecutive qualifying fire frame = CRITICAL
# ---------------------------------------------------------------------------
def test_tenth_consecutive_fire_frame_is_critical(risk_engine: RiskEngine, square_zone):
    inside_box = [50, 50, 150, 150]

    for _ in range(9):
        risk_engine.evaluate("fire", inside_box, square_zone)

    # 10th consecutive frame
    result = risk_engine.evaluate("fire", inside_box, square_zone)
    assert result.inside_zone is True
    assert result.confirmed is True
    assert result.risk_level == "CRITICAL"
    assert risk_engine.get_consecutive_count("fire") == 10
    assert risk_engine.is_confirmed("fire") is True


# ---------------------------------------------------------------------------
# 8. missing fire frame resets fire confirmation
# ---------------------------------------------------------------------------
def test_missing_fire_frame_resets_confirmation(risk_engine: RiskEngine, square_zone):
    inside_box = [50, 50, 150, 150]

    # Reach 10 frames (CRITICAL)
    for _ in range(10):
        risk_engine.process_frame([{"class": "fire", "box": inside_box}], square_zone)
    assert risk_engine.is_confirmed("fire") is True

    # Missing frame: frame with no fire detections
    empty_frame_res = risk_engine.process_frame([], square_zone)
    assert empty_frame_res.fire_consecutive_frames == 0
    assert empty_frame_res.fire_confirmed is False
    assert risk_engine.get_consecutive_count("fire") == 0
    assert risk_engine.is_confirmed("fire") is False

    # Next frame with fire restarts from 1 and is HIGH
    next_frame_res = risk_engine.process_frame([{"class": "fire", "box": inside_box}], square_zone)
    assert next_frame_res.results[0].risk_level == "HIGH"
    assert next_frame_res.results[0].confirmed is False
    assert risk_engine.get_consecutive_count("fire") == 1


# ---------------------------------------------------------------------------
# 9. outside-zone fire does not increment confirmation
# ---------------------------------------------------------------------------
def test_outside_zone_fire_does_not_increment_confirmation(risk_engine: RiskEngine, square_zone):
    # Box bottom-center at (300, 300) -> outside square zone (0..200)
    outside_box = [250, 200, 350, 300]

    for _ in range(5):
        result = risk_engine.evaluate("fire", outside_box, square_zone)
        assert result.inside_zone is False
        assert result.risk_level == "LOW"
        assert result.confirmed is False

    # Confirmation counter must stay at 0
    assert risk_engine.get_consecutive_count("fire") == 0


# ---------------------------------------------------------------------------
# 10. fire and smoke confirmation counters are independent
# ---------------------------------------------------------------------------
def test_fire_and_smoke_counters_are_independent(risk_engine: RiskEngine, square_zone):
    inside_box = [50, 50, 150, 150]

    # 10 frames of fire, but only 3 frames of smoke
    for i in range(10):
        dets = [{"class": "fire", "box": inside_box}]
        if i < 3:
            dets.append({"class": "smoke", "box": inside_box})
        risk_engine.process_frame(dets, square_zone)

    assert risk_engine.get_consecutive_count("fire") == 10
    assert risk_engine.is_confirmed("fire") is True

    # Smoke has only 3 frames and is not confirmed
    assert risk_engine.get_consecutive_count("smoke") == 0  # was absent in frames 4-10 so reset!

    # Test independent counting: 10 consecutive smoke frames while fire is absent
    for _ in range(10):
        risk_engine.process_frame([{"class": "smoke", "box": inside_box}], square_zone)

    assert risk_engine.get_consecutive_count("smoke") == 10
    assert risk_engine.is_confirmed("smoke") is True
    # Fire was absent, so fire counter reset to 0
    assert risk_engine.get_consecutive_count("fire") == 0


# ---------------------------------------------------------------------------
# 11. first CRITICAL fire event can emit
# ---------------------------------------------------------------------------
def test_first_critical_fire_event_can_emit(risk_engine: RiskEngine, square_zone):
    inside_box = [50, 50, 150, 150]
    t0 = 100.0

    # Feed 9 frames
    for i in range(9):
        risk_engine.process_frame([{"class": "fire", "box": inside_box}], square_zone, now=t0 + i * 0.1)

    # 10th frame reaches CRITICAL
    t10 = t0 + 1.0
    frame_res = risk_engine.process_frame([{"class": "fire", "box": inside_box}], square_zone, now=t10)
    assert frame_res.overall_risk == "CRITICAL"
    assert frame_res.results[0].risk_level == "CRITICAL"
    assert frame_res.results[0].incident_eligible is True
    assert "fire" in frame_res.incidents_eligible

    # Direct debounce check also confirms first event is allowed
    assert risk_engine.can_emit_incident("fire", now=t10) is True
    assert risk_engine.incident_allowed("fire", now=t10) is True


# ---------------------------------------------------------------------------
# 12. repeated CRITICAL fire within 5 seconds is suppressed
# ---------------------------------------------------------------------------
def test_repeated_critical_fire_within_5s_is_suppressed(risk_engine: RiskEngine):
    t_start = 200.0
    # First emission allowed at t=200.0
    assert risk_engine.incident_allowed("fire", now=t_start) is True

    # Within 5.0 seconds (e.g. at 201.0, 203.5, 204.99): suppressed
    assert risk_engine.can_emit_incident("fire", now=201.0) is False
    assert risk_engine.incident_allowed("fire", now=201.0) is False
    assert risk_engine.incident_allowed("fire", now=203.5) is False
    assert risk_engine.incident_allowed("fire", now=204.99) is False


# ---------------------------------------------------------------------------
# 13. CRITICAL fire after 5 seconds can emit again
# ---------------------------------------------------------------------------
def test_critical_fire_after_5s_can_emit_again(risk_engine: RiskEngine):
    t_start = 300.0
    assert risk_engine.incident_allowed("fire", now=t_start) is True

    # Suppressed at 302.0
    assert risk_engine.incident_allowed("fire", now=302.0) is False

    # After 5.0 seconds (at 305.1): eligible again!
    assert risk_engine.can_emit_incident("fire", now=305.1) is True
    assert risk_engine.incident_allowed("fire", now=305.1) is True

    # Subsequent event at 306.0 is suppressed based on the new emission at 305.1
    assert risk_engine.incident_allowed("fire", now=306.0) is False


# ---------------------------------------------------------------------------
# 14. fire and smoke debounce timers are independent
# ---------------------------------------------------------------------------
def test_fire_and_smoke_debounce_timers_are_independent(risk_engine: RiskEngine):
    t_fire = 400.0
    # Fire emits at 400.0
    assert risk_engine.incident_allowed("fire", now=t_fire) is True

    # Smoke at 401.0 (< 5s after fire) must NOT be suppressed by fire's timer
    assert risk_engine.can_emit_incident("smoke", now=401.0) is True
    assert risk_engine.incident_allowed("smoke", now=401.0) is True

    # Fire is still suppressed at 402.0
    assert risk_engine.incident_allowed("fire", now=402.0) is False

    # Smoke is now suppressed at 403.0 (within 5s of smoke emission at 401.0)
    assert risk_engine.incident_allowed("smoke", now=403.0) is False


# ---------------------------------------------------------------------------
# 15. multiple detections of the same class in one frame increment confirmation only once
# ---------------------------------------------------------------------------
def test_multiple_detections_in_one_frame_increment_once(risk_engine: RiskEngine, square_zone):
    box_inside_1 = [20, 20, 80, 80]
    box_inside_2 = [100, 100, 180, 180]
    box_outside = [250, 250, 350, 350]

    # Frame 1: Two inside fires and one outside fire
    frame_dets = [
        {"class": "fire", "box": box_inside_1, "confidence": 0.9},
        {"class": "fire", "box": box_inside_2, "confidence": 0.85},
        {"class": "fire", "box": box_outside, "confidence": 0.75},
    ]

    res = risk_engine.process_frame(frame_dets, square_zone)

    # Confirmation counter must only increment by 1 for this frame, not 2 or 3
    assert risk_engine.get_consecutive_count("fire") == 1
    assert res.fire_consecutive_frames == 1

    # Detections inside zone get HIGH risk; detection outside zone gets LOW risk
    assert res.results[0].inside_zone is True
    assert res.results[0].risk_level == "HIGH"

    assert res.results[1].inside_zone is True
    assert res.results[1].risk_level == "HIGH"

    assert res.results[2].inside_zone is False
    assert res.results[2].risk_level == "LOW"

    # Frame-level evaluate() with same frame_id also increments only once
    engine2 = RiskEngine()
    engine2.evaluate("fire", box_inside_1, square_zone, frame_id=1)
    engine2.evaluate("fire", box_inside_2, square_zone, frame_id=1)
    assert engine2.get_consecutive_count("fire") == 1


# ---------------------------------------------------------------------------
# 16. existing API/stream behavior remains compatible
# ---------------------------------------------------------------------------
def test_existing_api_and_stream_compatibility(risk_engine: RiskEngine, square_zone):
    # 1. Test evaluate() signature and return structure backward compatibility
    res: RiskResult = risk_engine.evaluate(
        detection_class="fire",
        bounding_box=[50, 50, 150, 150],
        polygon=square_zone,
        detected=True,
    )
    assert hasattr(res, "risk_level")
    assert hasattr(res, "inside_zone")
    assert hasattr(res, "foot_point")
    assert hasattr(res, "confirmed")
    assert hasattr(res, "detection_class")
    assert res.risk_level in {"LOW", "HIGH", "CRITICAL"}
    assert isinstance(res.to_dict(), dict)

    # 2. Test StreamManager integration
    sm = StreamManager("videos/test.mp4")
    sm.zone_polygon = square_zone

    # Frame risk processing
    test_dets = [{"class": "fire", "box": [50, 50, 150, 150], "confidence": 0.9}]
    frame_res = sm.risk_engine.process_frame(test_dets, sm.zone_polygon)
    assert isinstance(frame_res, FrameRiskResult)
    assert frame_res.overall_risk == "HIGH"
