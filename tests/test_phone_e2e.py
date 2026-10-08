"""Test the phone-camera frame pipeline with a real JPEG."""
import cv2
import numpy as np
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import requests

# 1. Create a valid JPEG from a real OpenCV frame
frame = np.zeros((480, 640, 3), dtype=np.uint8)
cv2.putText(frame, "PHONE TEST FRAME", (100, 240),
            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
ok, buf = cv2.imencode('.jpg', frame)
assert ok, "Failed to encode JPEG"
jpeg_bytes = buf.tobytes()
print(f"Created valid JPEG: {len(jpeg_bytes)} bytes")

BASE = "https://localhost:8000"

# 2. Enable phone camera mode
r = requests.post(f"{BASE}/api/phone_camera/enable", verify=False)
print(f"Enable phone camera: {r.status_code} -> {r.json()}")
assert r.status_code == 200

# 3. POST the real JPEG frame
r = requests.post(
    f"{BASE}/api/phone_frame",
    data=jpeg_bytes,
    headers={"Content-Type": "image/jpeg", "X-Camera-Id": "test-phone"},
    verify=False,
)
print(f"POST phone_frame: {r.status_code} -> {r.json()}")
assert r.status_code == 200, f"Frame POST failed: {r.status_code}"

# 4. Check status reflects phone mode
r = requests.get(f"{BASE}/api/status", verify=False)
status = r.json()
print(f"Status use_phone_camera: {status.get('use_phone_camera')}")
assert status.get("use_phone_camera") is True, "Phone camera not enabled in status"

# 5. Verify the MJPEG stream returns frames
r = requests.get(f"{BASE}/video_feed", verify=False, stream=True, timeout=10)
print(f"video_feed status: {r.status_code}")
assert r.status_code == 200

# Read enough bytes to confirm MJPEG boundary + JPEG data
chunk = next(r.iter_content(chunk_size=8192))
print(f"First MJPEG chunk: {len(chunk)} bytes, starts with: {chunk[:40]}")
assert b"--frame" in chunk or b"\xff\xd8" in chunk, "No MJPEG frame found"
r.close()

# 6. Verify /phone page serves HTML
r = requests.get(f"{BASE}/phone", verify=False)
print(f"/phone page: {r.status_code}, content-type: {r.headers.get('content-type')}")
assert r.status_code == 200
assert "text/html" in r.headers.get("content-type", "")

# 7. Disable phone camera
r = requests.post(f"{BASE}/api/phone_camera/disable", verify=False)
print(f"Disable phone camera: {r.status_code} -> {r.json()}")
assert r.status_code == 200

# 8. Fire/smoke baseline check
from src.engine.risk_engine import RiskEngine
re = RiskEngine()
import time
for i in range(10):
    fr = re.process_frame(
        detections=[{"class": "fire", "confidence": 0.9, "box": [100, 100, 200, 200]}],
        polygon=None,
        now=time.time(),
    )
fire_ok = fr.fire_confirmed and fr.overall_risk == "CRITICAL"
print(f"Fire/Smoke baseline: confirmed={fr.fire_confirmed}, risk={fr.overall_risk}")
assert fire_ok, "Fire/Smoke baseline BROKEN"

print("\n=== ALL TESTS PASSED ===")
print("PHONE FRAME ENDPOINT: PASS")
print("PHONE FRAME DECODE: PASS")
print("PHONE STREAM RESPONSE: PASS")
print("/phone CLIENT: PASS")
print("FIRE/SMOKE: PASS")
