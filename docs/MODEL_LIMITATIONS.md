# IronEye — Model Limitations & Detection Accuracy

## Current Model: YOLOv8n (yolov8n.pt)

The project currently uses the **standard YOLOv8 nano model** (yolov8n.pt),
pre-trained on the **COCO dataset** (80 common object classes such as person,
car, dog, chair, etc.).

### Fire and Smoke Detection — IMPORTANT

**ire and smoke are NOT part of the COCO class set.**

The standard yolov8n.pt will **never** produce detections with
class == "fire" or class == "smoke" because those classes are absent
from its training data. As a result:

- The risk engine, confirmation logic, and incident pipeline are implemented
  correctly and can be exercised end-to-end.
- In the current deployment, the safety-zone risk engine will always see 0
  fire/smoke detections from the YOLO model, so no real incidents will be
  emitted during live monitoring.
- Evidence saving, Supabase persistence, and Twilio alerting remain untested
  against real fire/smoke detections.

### What is Required for Real Fire/Smoke Detection

To enable production-grade fire and smoke detection, one of the following
is required:

1. **Fine-tune or retrain YOLOv8** on a labelled fire/smoke dataset
   (e.g., FireNet, D-Fire, or a custom dataset).
2. **Use a pre-trained fire/smoke model** — several community-trained
   YOLOv8 weights are publicly available (verify license before use).
3. **Replace** yolov8n.pt with the custom weights file and update the
   model name in YOLODetector (src/engine/detector.py, line 32).

No model download, training, or replacement has been performed in this
codebase without explicit authorization.

## Risk Engine Status

The RiskEngine, confirmation-frame logic, debounce, and incident pipeline
are fully implemented and unit-tested. They are **class-agnostic** and will
function correctly once a model that can produce ire or smoke classes
is in place.

## API / Dashboard

The dashboard, streaming pipeline, and telemetry remain operational. The
detection count and class summary will show whichever COCO classes the model
detects in the video (people, vehicles, etc.) — those are displayed correctly
but do not trigger risk incidents unless a fire/smoke model is substituted.
