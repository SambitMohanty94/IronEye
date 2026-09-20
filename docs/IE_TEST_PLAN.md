# Comprehensive Quality Assurance & Verification Plan — IronEye

## 1. Scope and Objectives
This document establishes the test strategy, verification criteria, and test cases for the IronEye edge/cloud workplace safety platform. The objective is to ensure sub-200ms frame latency, fault-tolerant video ingestion, zero-leak cooldown suppression, accurate point-in-polygon spatial detection, and fail-safe cloud/SMS notifications.

---

## 2. Test Execution Levels

### 2.1 Unit Tests (Math, Geometry & State Logic)
* **Point-in-Polygon Computation (`cv2.pointPolygonTest`):**
  * *Test Case GEO-01:* Worker foot at coordinates $(300, 300)$ inside default polygon `[[100, 150], [500, 150], [550, 450], [50, 450]]`. Expected: Return value $> 0$, flag `breach = True`.
  * *Test Case GEO-02:* Worker foot at coordinates $(50, 50)$ outside polygon. Expected: Return value $< 0$, flag `breach = False`.
  * *Test Case GEO-03:* Worker foot resting precisely along the polygon boundary line. Expected: Return value $== 0$, treated as warning threshold.
* **Foot Coordinate Parsing:**
  * *Test Case GEO-04:* Given bounding box `(x1=120, y1=100, x2=240, y2=400)`, foot coordinates must compute strictly to `feet_x = (120 + 240) / 2 = 180`, `feet_y = 400`.
* **5-Second Alert Debounce State Machine:**
  * *Test Case DB-01:* Emit identical hazard key at $t=0.0\text{s}$. Expected: Allowed, timestamp updated.
  * *Test Case DB-02:* Emit identical hazard key at $t=2.1\text{s}$. Expected: Suppressed, return `False`.
  * *Test Case DB-03:* Emit identical hazard key at $t=5.05\text{s}$. Expected: Allowed, timestamp updated.
  * *Test Case DB-04:* Emit differing hazard keys concurrently at $t=1.0\text{s}$ (e.g., `PPE_VIOLATION` vs `FIRE_ALERT`). Expected: Evaluated independently without mutual lock-out.

### 2.2 Temporal Filtering & False-Positive Rejection
* **10-Frame Fire/Smoke Verification Buffer:**
  * *Test Case TMP-01 (Transient Artifact):* Inject 8 consecutive frames with positive flame bounding boxes followed by 2 clean frames. Expected: Suppression of `CRITICAL` risk; no database write or SMS triggered.
  * *Test Case TMP-02 (Confirmed Hazard):* Inject 10 consecutive frames with positive flame bounding boxes. Expected: Instant promotion to `CRITICAL` risk; trigger Supabase insert and Twilio SMS payload dispatch.
* **PPE Violation Duration Accumulator:**
  * *Test Case TMP-03:* Track non-compliant worker track for $3.2\text{s}$. Expected: Tagged as `WARNING`, restricted to local dashboard UI.
  * *Test Case TMP-04:* Track continuous non-compliant worker track exceeding $5.0\text{s}$. Expected: Tagged as `HIGH`, trigger evidence screenshot and Supabase write.

### 2.3 Resiliency & Failover Tests
* **Video Ingestion Drop & Recovery:**
  * *Test Case RES-01 (Physical Disconnect):* Simulate network drop on `live_phone` (Android HTTP MJPEG) during active stream. Expected: Capture loop intercepts `read() == False`, outputs an in-band "RECONNECTING" placeholder frame, attempts non-blocking socket recovery every 1s, and prevents the FastAPI server thread from dying.
  * *Test Case RES-02 (End-of-File Looping):* Read `assets/test_ppe.mp4` to final frame. Expected: Capture head resets smoothly to frame index 0 (`cap.set(cv2.CAP_PROP_POS_FRAMES, 0)`) without dropping clients.
* **Network Partition & Offline Degradation:**
  * *Test Case RES-03 (Supabase Outage):* Mock network failure on Supabase API during a confirmed breach. Expected: Exception caught gracefully, logged locally to standard error, video pipeline latency remains unaffected.
  * *Test Case RES-04 (Twilio Timeout):* Mock HTTP timeout on Twilio SMS dispatch. Expected: Asynchronous task fails isolated from the main video loop; no dropped frames on `/video_feed`.

### 2.4 End-to-End & Integration Tests
* **Dynamic Source Switch:**
  * *Test Case E2E-01:* Send `POST /api/switch_source` with `{"source_key": "fire_test"}`. Expected: Active OpenCV reader switches from current input to `assets/test_fire.mp4` within 300ms without restarting the server.
* **Dynamic Zone Update:**
  * *Test Case E2E-02:* Send `POST /api/set_zone` with custom 4-point array. Expected: Global polygon updates immediately; subsequent video frames render the updated overlay.
* **Realtime CDC Broadcast:**
  * *Test Case E2E-03:* Insert incident row into Supabase. Expected: Connected web dashboard receives WebSocket notification via Supabase Realtime channel within 500ms and inserts row at top of incident grid.

---

## 3. Hardware & Multi-Device Target Matrix

| Device Profile | Operating System | Browser / Runtime | Verification Criteria |
| :--- | :--- | :--- | :--- |
| **SOC Video Wall** | Linux / Windows 11 | Chrome 120+, Edge | Uninterrupted 24/7 playback, memory leak $< 50\text{MB}/24\text{hr}$ |
| **Workstation / Laptop** | macOS Sonoma, Windows 10/11 | Safari, Chrome, Firefox | Responsive 3-column layout, SVG zone editing functional |
| **Plant Tablet** | iPadOS 17, Android 13+ | Safari Mobile, Chrome Mobile | Responsive touch handles for zone drawing, card view collapse |
| **Field Mobile** | iOS 16+, Android 12+ | Safari, Chrome | Viewport adaptation, full-width incident action controls |

---

## 4. Acceptance Sign-off Criteria
1. Latency from frame ingest to MJPEG client delivery is $< 200\text{ms}$ at $640 \times 480$.
2. Cooldown mechanism prevents identical incident writes within 5 seconds under a 30 FPS stream.
3. 100% test pass on point-in-polygon verification unit tests.
4. Edge server continues serving local video stream even if external WAN connectivity drops completely.