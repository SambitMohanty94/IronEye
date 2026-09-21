import os
import cv2
import numpy as np
from ultralytics.utils import ASSETS

def create_sample_video():
    os.makedirs("videos", exist_ok=True)
    output_path = "videos/test.mp4"
    
    # Load sample asset image containing persons and bus
    bus_path = os.path.join(ASSETS, "bus.jpg")
    if not os.path.exists(bus_path):
        print(f"Asset not found at {bus_path}")
        return

    base_img = cv2.imread(bus_path)
    h, w, _ = base_img.shape
    
    # Target video specs: 720p or original aspect
    target_w, target_h = 800, int(800 * (h / w))
    target_w = target_w - (target_w % 2) # must be even
    target_h = target_h - (target_h % 2)

    resized_base = cv2.resize(base_img, (target_w, target_h))

    # FourCC codec: 'mp4v' for Windows compatibility
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    fps = 25.0
    num_frames = 125 # 5 seconds of video
    
    out = cv2.VideoWriter(output_path, fourcc, fps, (target_w, target_h))
    
    print(f"Generating synthetic test video at {output_path} ({target_w}x{target_h}, {fps} FPS, {num_frames} frames)...")
    
    for i in range(num_frames):
        # Add subtle pan/zoom effect to simulate a dynamic camera
        zoom_factor = 1.0 + 0.1 * np.sin(2 * np.pi * i / num_frames)
        crop_w = int(target_w / zoom_factor)
        crop_h = int(target_h / zoom_factor)
        
        start_x = (target_w - crop_w) // 2
        start_y = (target_h - crop_h) // 2
        
        cropped = resized_base[start_y:start_y + crop_h, start_x:start_x + crop_w]
        frame = cv2.resize(cropped, (target_w, target_h))
        out.write(frame)
        
    out.release()
    print(f"Sample test video generated successfully at {output_path} ({os.path.getsize(output_path)} bytes)")

if __name__ == "__main__":
    create_sample_video()
