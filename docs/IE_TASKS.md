# Actionable Implementation Roadmap — IronEye

- [ ] **Phase 1: Environment & Cloud Persistence Setup**
  - [ ] Initialize Python 3.11 environment with `requirements.txt`.
  - [ ] Execute `database/schema.sql` on Supabase to configure `cameras`, `workers`, `incidents`, `alerts_log`.
  - [ ] Configure PostgreSQL Realtime CDC publication for the `incidents` table.

- [ ] **Phase 2: Core Video Engine & Stream Switching**
  - [ ] Implement `backend/video_engine.py` with multi-source video capture manager.
  - [ ] Implement dynamic source switcher and EOF looping for test MP4 files.
  - [ ] Expose `GET /video_feed` multipart MJPEG streaming endpoint.

- [ ] **Phase 3: AI Detection & Point-in-Polygon Engine**
  - [ ] Integrate YOLOv8 inference pipeline in `backend/ai_pipeline.py`.
  - [ ] Implement foot-coordinate calculation and `cv2.pointPolygonTest` in `backend/risk_engine.py`.
  - [ ] Add 10-frame consecutive confirmation buffer for fire and smoke.
  - [ ] Implement 5.0-second incident debounce engine.

- [ ] **Phase 4: Persistence, Escalation & Alerting**
  - [ ] Implement asynchronous Supabase incident writer with evidence snapshot JPEG saving.
  - [ ] Implement Twilio SMS dispatcher for `CRITICAL` risk alerts in `backend/alert_engine.py`.

- [ ] **Phase 5: Cross-Platform Industrial SOC Frontend**
  - [ ] Build responsive dark-theme dashboard shell (`frontend/index.html`).
  - [ ] Implement interactive SVG zone drawing canvas synced to `POST /api/set_zone`.
  - [ ] Connect WebSocket listener for live Supabase CDC incident feed updates.