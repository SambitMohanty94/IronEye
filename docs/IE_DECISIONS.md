# Architecture Decision Records (ADR) — IronEye

## ADR-001: Video Streaming Mechanism — MJPEG over Multipart HTTP
* **Status:** Accepted
* **Context:** The system must stream low-latency processed frames from FastAPI to diverse client platforms (macOS, Windows, iOS, Android) without heavyweight dependencies or proprietary media servers.
* **Decision:** Implement standard multipart HTTP streaming using the `multipart/x-mixed-replace; boundary=frame` MIME type.
* **Consequences:**
  * *Pros:* Native support in every modern browser using standard `<img>` tags; zero client-side JavaScript decoding libraries required; ultra-low CPU overhead on mobile receivers.
  * *Cons:* Higher bandwidth usage compared to H.264/WebRTC; frame transport lacks audio; unsuitable for poor cellular connections $< 1\text{ Mbps}$.

---

## ADR-002: Restricted Zone Positioning via Foot Coordinates
* **Status:** Accepted
* **Context:** Standard object detection yields 2D bounding boxes `(x1, y1, x2, y2)` encompassing the worker's entire posture. Using bounding box centers triggers false zone alarms when workers stand outside the zone but gesture, carry ladders, or lean into the camera's 2D field of view.
* **Decision:** Calculate the worker's ground contact point (feet) as `feet_x = (x1 + x2) / 2` and `feet_y = y2`, passing this single point to `cv2.pointPolygonTest`.
* **Consequences:**
  * *Pros:* Accurately models physical floor contact; eliminates false positives from shadows, extended arms, or equipment held above ground.
  * *Cons:* Requires the worker's lower body to be visible; occlusion by foreground objects can shift the bottom of the bounding box upward.

---

## ADR-003: Multi-Frame Temporal Verification for Environmental Hazards
* **Status:** Accepted
* **Context:** Computer vision models evaluated on single frames frequently confuse dust motes, solar glare, lens flares, and halogen lamps with flame and smoke plumes, triggering expensive false alarms and unwarranted panic.
* **Decision:** Implement a 10-frame consecutive confirmation buffer. A flame or smoke signature must register positively across 10 consecutive frames before escalating risk to `CRITICAL` and dispatching SMS alerts.
* **Consequences:**
  * *Pros:* Rejects transient optical noise and dust particles; stabilizes alarm confidence above 95%.
  * *Cons:* Introduces an intentional verification latency of $\sim 330\text{ms}$ at 30 FPS ($\sim 500\text{ms}$ at 20 FPS), which remains well within acceptable industrial safety thresholds for fire suppression.

---

## ADR-004: In-Memory Timestamp Debounce Architecture
* **Status:** Accepted
* **Context:** Processing high-framerate video (30 FPS) against persistent hazards generates up to 30 identical detection events per second. Unregulated database writes or SMS transmissions cause instant database quota exhaustion and SMS carrier rate-limiting.
* **Decision:** Maintain an in-memory debounce dictionary `last_alert_time[incident_key]` enforcing a hard 5.0-second cooldown window between persistent events of the same class.
* **Consequences:**
  * *Pros:* Zero latency overhead; operates entirely in RAM; bounds maximum database writes to $0.2\text{ writes/sec}$ per active hazard type.
  * *Cons:* State resets if the FastAPI backend process restarts; in multi-worker production setups, this dictionary must migrate to a shared Redis instance.

---

## ADR-005: Cloud Ingestion via PostgreSQL CDC and WebSockets
* **Status:** Accepted
* **Context:** The frontend dashboard must display safety incidents the moment they occur without requiring polling loops (`setInterval` fetch) that introduce latency and unnecessary server load.
* **Decision:** Utilize Supabase Realtime (built on PostgreSQL Change Data Capture and WebSockets) to push new row inserts directly to connected web clients.
* **Consequences:**
  * *Pros:* Sub-500ms end-to-end incident dispatch to the UI; zero database polling load; native client-side event binding.
  * *Cons:* Requires active outbound WebSocket connections from the client browser to Supabase infrastructure.

---

## ADR-006: Normalized Resolution Pipeline Standard (640x480)
* **Status:** Accepted
* **Context:** Video inputs originate from disparate sources with varying native resolutions (1080p RTSP, 720p Android IP streams, 480p test clips). Running inference directly on varying dimensions causes unpredictable frame times and model degradation.
* **Decision:** Normalize all incoming video frames to $640 \times 480$ immediately upon capture before passing them to the YOLO model and coordinate verification engine.
* **Consequences:**
  * *Pros:* Predictable inference execution times under 50ms on modest GPUs/CPUs; consistent coordinate space for the SVG drawing layer.
  * *Cons:* High-resolution details far in the camera distance can experience compression loss.