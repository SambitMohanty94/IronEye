# IronEye System Memory & Project Invariants

## Core System Invariants
- **Resolution Lock:** All inference frames are scaled to $640 \times 480$. All zone polygon coordinates are normalized or matched to this resolution.
- **Debounce Interval:** 5.0 seconds per incident key is the invariant minimum to protect external databases and SMS rate limits.
- **Foot Coordinate Rule:** Zone tests always map to `feet_x = (x1 + x2)/2`, `feet_y = y2`.

## Active Video Source Keys
- `live_phone`: Android IP camera stream (`http://<PHONE_IP>:8080/video`).
- `ppe_test`: Local evaluation file (`assets/test_ppe.mp4`).
- `fire_test`: Local evaluation file (`assets/test_fire.mp4`).

## Incident Types & Risk Hierarchy
- `PPE_VIOLATION`: `WARNING` (< 5s) / `HIGH` (> 5s)
- `RESTRICTED_ACCESS`: `HIGH`
- `FIRE_ALERT`: `CRITICAL` (requires 10+ consecutive frames)
- `SMOKE_DETECTED`: `CRITICAL` (requires 10+ consecutive frames)