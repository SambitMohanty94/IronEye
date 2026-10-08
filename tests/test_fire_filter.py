import numpy as np
from src.engine.detector import YOLODetector

def test_filtering():
    # Create detector
    detector = YOLODetector()
    
    # Mock class names to include dog (16) and person (0) just for the test
    detector.class_names = {0: 'person', 1: 'smoke', 2: 'fire', 16: 'dog', 53: 'pizza'}
    
    # Create fake boxes
    class FakeBox:
        def __init__(self, cls_id, conf):
            self.xyxy = np.array([[10, 10, 20, 20]])
            self.conf = np.array([conf])
            self.cls = np.array([cls_id])
            
    class FakeResults:
        def __init__(self):
            self.boxes = [
                FakeBox(0, 0.9),   # person
                FakeBox(16, 0.8),  # dog
                FakeBox(53, 0.95), # pizza
                FakeBox(1, 0.85),  # smoke
                FakeBox(2, 0.9),   # fire
            ]
            
    # Mock the model call
    detector.model = lambda *args, **kwargs: [FakeResults()]
    
    # Run
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    annotated, meta = detector.detect_and_annotate(frame)
    
    print("Classes in metadata:", meta['classes'])
    print("Detections length:", meta['total_detections'])
    
    assert 'person' not in meta['classes']
    assert 'dog' not in meta['classes']
    assert 'pizza' not in meta['classes']
    assert 'smoke' in meta['classes']
    assert 'fire' in meta['classes']
    assert meta['total_detections'] == 2

    print("PASS: Filter strictly removes person, dog, pizza.")

if __name__ == "__main__":
    test_filtering()
