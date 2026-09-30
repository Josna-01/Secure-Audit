import os
import cv2
import numpy as np

def generate_sample_dataset():
    """Generates synthetic sample images and video with recognizable objects for YOLOv8 testing."""
    sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
    os.makedirs(sample_dir, exist_ok=True)

    # 1. Generate Sample Image 1: Knife / Sharp Object Scene
    img1_path = os.path.join(sample_dir, "sample_knife_evidence.jpg")
    img1 = np.ones((600, 800, 3), dtype=np.uint8) * 40  # Dark grey background
    
    # Draw table outline
    cv2.rectangle(img1, (50, 100), (750, 550), (60, 60, 60), -1)
    
    # Draw knife-shaped object (blade + handle)
    # Blade (metallic grey/silver)
    pts_blade = np.array([[300, 280], [500, 270], [520, 290], [300, 300]], np.int32)
    cv2.fillPoly(img1, [pts_blade], (200, 200, 210))
    cv2.polylines(img1, [pts_blade], True, (240, 240, 250), 2)
    # Handle (dark brown/black)
    cv2.rectangle(img1, (180, 275), (300, 305), (20, 35, 70), -1)
    cv2.rectangle(img1, (180, 275), (300, 305), (10, 20, 40), 2)
    
    # Draw a bottle nearby
    cv2.rectangle(img1, (600, 220), (660, 400), (180, 100, 50), -1)
    cv2.rectangle(img1, (620, 170), (640, 220), (180, 100, 50), -1)
    
    # Text banner on image
    cv2.putText(img1, "FORENSIC EVIDENCE SAMPLE #1 - SUSPICIOUS OBJECT SCENE", (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(img1, "Objects: Sharp Metallic Blade / Bottle / Person Evidence", (30, 75),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)

    cv2.imwrite(img1_path, img1)
    print(f"[CREATED] Sample image saved to: {img1_path}")

    # 2. Generate Sample Image 2: Multi-Object Surveillance Photo
    img2_path = os.path.join(sample_dir, "sample_suspicious_scene.jpg")
    img2 = np.ones((600, 800, 3), dtype=np.uint8) * 30
    
    # Draw backpack shape
    cv2.ellipse(img2, (250, 350), (80, 120), 0, 0, 360, (50, 100, 180), -1)
    cv2.rectangle(img2, (200, 250), (300, 420), (40, 80, 150), -1)
    cv2.putText(img2, "BACKPACK", (205, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # Draw cell phone shape
    cv2.rectangle(img2, (500, 280), (580, 420), (10, 10, 10), -1)
    cv2.rectangle(img2, (505, 290), (575, 410), (120, 120, 120), -1)
    cv2.putText(img2, "PHONE", (515, 355), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    
    # Text header
    cv2.putText(img2, "FORENSIC EVIDENCE SAMPLE #2 - ABANDONED ITEMS", (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.imwrite(img2_path, img2)
    print(f"[CREATED] Sample image 2 saved to: {img2_path}")

    # 3. Generate Sample Video: Surveillance Stream (20 frames)
    vid_path = os.path.join(sample_dir, "sample_surveillance_stream.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(vid_path, fourcc, 10.0, (640, 480))

    for frame_idx in range(30):
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 35
        # Grid lines background
        for y in range(0, 480, 40):
            cv2.line(frame, (0, y), (640, y), (50, 50, 50), 1)
        for x in range(0, 640, 40):
            cv2.line(frame, (x, 0), (x, 480), (50, 50, 50), 1)

        # Moving object across frame
        pos_x = 100 + (frame_idx * 14)
        pos_y = 200 + int(np.sin(frame_idx * 0.3) * 20)
        
        # Draw moving knife/object outline
        cv2.rectangle(frame, (pos_x, pos_y), (pos_x + 120, pos_y + 35), (0, 0, 200), -1) # Red object
        cv2.rectangle(frame, (pos_x + 120, pos_y + 10), (pos_x + 200, pos_y + 25), (180, 180, 180), -1) # Blade extension
        
        cv2.putText(frame, f"CCTV SURVEILLANCE FEED - FRAME #{frame_idx+1:02d}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, "SUSPICIOUS OBJECT MOTION DETECTED", (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        out.write(frame)

    out.release()
    print(f"[CREATED] Sample video saved to: {vid_path}")

if __name__ == "__main__":
    generate_sample_dataset()
