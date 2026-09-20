# IronEye — Real-Time Industrial Safety Intelligence Platform

IronEye converts passive CCTV, mobile IP feeds, and recorded video into an automated workplace safety monitoring and threat-prevention system. It leverages YOLO computer vision, Point-in-Polygon spatial analysis, multi-frame hazard verification, cloud incident logging, and emergency SMS alerts.

## Key Features
- **Dynamic Ingestion:** Switch on the fly between Android IP webcams, CCTV/RTSP, and local evaluation videos.
- **Spatial Zone Verification:** Point-in-Polygon restricted zone monitoring using worker foot coordinates.
- **Multi-Frame Hazard Filter:** 10+ frame temporal persistence validation for fire and smoke to prevent false positives.
- **Debounced Incident Pipeline:** 5-second cooldown suppresses alarm flooding while ensuring immediate logging of critical events.
- **Industrial SOC Dashboard:** Responsive dark-mode interface with interactive SVG zone drawing and real-time incident streaming.

## Tech Stack
- **Backend:** FastAPI, Python 3.11+, OpenCV, NumPy, Pydantic
- **AI / Computer Vision:** Ultralytics YOLOv8 / YOLOv11, PyTorch
- **Database & Realtime:** Supabase (PostgreSQL 15+, CDC WebSockets)
- **Alert Dispatch:** Twilio REST API
- **Frontend:** Vanilla JS / Modern CSS / SVG / HTML5

## Quickstart

### 1. Clone & Setup Environment
```bash
git clone [https://github.com/your-org/ironeye.git](https://github.com/your-org/ironeye.git)
cd ironeye
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt