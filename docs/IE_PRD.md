# Product Requirements Document (PRD) — IronEye

## 1. Document Overview
- **Project Name:** IronEye
- **System Classification:** Real-time AI-Powered Workplace Safety & Threat Prevention Platform
- **Target Environments:** Desktop (SOC Command Walls), Laptops (macOS/Windows), Tablets (iPadOS/Android), and Mobile Handhelds (iOS/Android)
- **Target Users:** Environmental Health & Safety (EHS) Managers, Security Operations Center (SOC) Guards, Plant Supervisors, Compliance Auditors

## 2. Problem Statement
Traditional industrial security relies on manual CCTV monitoring across dozens of simultaneous screens. Operator fatigue, split attention, and delayed reaction cause missed PPE non-compliance, uncontained fire or smoke spread, undetected worker falls, and slow intervention during restricted-zone breaches.

## 3. Product Goals & Business Objectives
- **Accident Reduction:** Decrease workplace incidents by 40% to 60% through preemptive real-time alerts.
- **Low Latency:** Maintain sub-200ms end-to-end inference and overlay pipeline per frame.
- **Hardware Agility:** Ingest streams from standard CCTV/RTSP, Android IP webcams, or pre-recorded MP4 evaluation files without proprietary hardware overhauls.
- **Auditable Safety Records:** Generate immutable incident logs with timestamped bounding-box screenshot evidence.

## 4. User Roles & Access Control
| Role | Capabilities | Primary Interface |
| :--- | :--- | :--- |
| **Admin / EHS Director** | Full system control: camera configuration, polygon zone definition, alert threshold overrides, worker directory management. | Desktop / Laptop |
| **SOC Operator** | Real-time monitoring, zone breach validation, incident lifecycle updates (`OPEN` -> `INVESTIGATING` -> `RESOLVED`). | Desktop Video Wall / Tablet |
| **Floor Supervisor** | Receive emergency SMS notifications, review assigned zone violations, acknowledge alerts. | Mobile Handheld (iOS/Android) |
| **Safety Auditor** | Read-only access to historical logs, evidence screenshots, and compliance export reports. | Laptop / Desktop |

## 5. Functional Requirements

### 5.1 Dynamic Video Ingestion & Stream Switching
- Ingest streams via HTTP, MJPEG, RTSP, and local MP4 file paths.
- Allow dynamic, zero-downtime switching of the active camera source via `POST /api/switch_source`.
- Provide automatic failover to fallback test footage if a physical camera feed drops.

### 5.2 AI Detection & Vision Capabilities
- **Person Detection:** Ultralytics YOLO baseline to detect workers and compute bounding boxes.
- **Restricted-Zone Intrusion:** Point-in-Polygon validation using the worker’s foot coordinate `((x1 + x2)/2, y2)` tested against dynamic 2D polygons using OpenCV `pointPolygonTest`.
- **PPE Compliance:** Track helmet and high-visibility vest presence; monitor continuous non-compliance duration per person.
- **Fire & Smoke Detection:** Detect luminous flame signatures and expanding smoke plumes with multi-frame temporal persistence (>= 10 consecutive frames) to reject transients.
- **Fall Detection:** Identify sudden vertical-to-horizontal bounding box ratio collapse.

### 5.3 Risk Classification & Cooldown Rules
- **WARNING:** PPE absence < 5s or boundary proximity contact. Displayed on live dashboard only.
- **HIGH:** PPE absence > 5s or confirmed restricted-zone breach. Logged to database with evidence image.
- **CRITICAL:** Verified fire, smoke, or worker fall. Immediate cloud database insertion and Twilio SMS notification.
- **Debounce Engine:** 5.0-second cooldown per incident key to prevent 30 FPS database flooding.

### 5.4 Operator Dashboard & Zone Management
- Low-latency processed video stream with bounding boxes and dynamic polygon overlays.
- Interactive SVG drawing layer on the stream to plot and save custom polygon zones via `POST /api/set_zone`.
- Real-time incident table updating automatically via PostgreSQL Change Data Capture (CDC) / WebSockets without manual page reloads.

## 6. Non-Functional Requirements
- **Performance:** Stream delivery and inference latency < 200ms at 640x480 resolution.
- **Availability:** Core edge inference and video loop must run uninterrupted even during cloud network loss.
- **Ergonomics & Accessibility:** WCAG 2.1 AA compliant color contrast, dual encoding for all safety states (color + icon + text).