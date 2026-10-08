import cv2
from ultralytics import YOLO

model = YOLO("models/ppe_best.pt")
cap = cv2.VideoCapture("videos/test_2.mp4")

found = 0

for frame_no in range(100):
    ok, frame = cap.read()

    if not ok:
        break

    result = model(frame, verbose=False)[0]

    if result.boxes is not None and len(result.boxes) > 0:
        names = [model.names[int(c)] for c in result.boxes.cls]
        print("Frame", frame_no, names)
        found += 1

        if found >= 5:
            break

cap.release()
print("PPE model test complete")
