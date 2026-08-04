import os
import sys
import time
import cv2
from services.frame_extractor import FrameExtractor

def generate_dummy_video(video_path: str, duration_sec: int = 5, fps: int = 30):
    """Generates a simple sample MP4 video using OpenCV if none exists."""
    os.makedirs(os.path.dirname(video_path) or ".", exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, fps, (640, 480))
    
    total_frames = duration_sec * fps
    for i in range(total_frames):
        color = ((i * 5) % 256, (i * 10) % 256, (i * 15) % 256)
        import numpy as np
        frame = np.full((480, 640, 3), color, dtype=np.uint8)
        cv2.putText(frame, f"Sample Video Frame {i+1}", (50, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        out.write(frame)
    out.release()

def main():
    print("------------------------------------------------")
    print("Testing Frame Extractor...\n")

    video_path = os.path.join("test_data", "sampleVideo.mp4")
    output_dir = os.path.join("output", "frames")

    # If sample video does not exist, auto-generate a sample video for testing
    if not os.path.exists(video_path):
        print(f"Sample video not found at '{video_path}'. Creating test sample video...")
        generate_dummy_video(video_path, duration_sec=5, fps=30)
        print(f"Created sample video at '{video_path}'.\n")

    print(f"Video:\n{video_path}\n")
    print(f"Output:\n{output_dir}/\n")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    extractor = FrameExtractor()

    start_time = time.time()
    try:
        extracted_files = extractor.extract(video_path=video_path, output_dir=output_dir, fps=1)
        elapsed_time = time.time() - start_time

        print(f"Extracted:\n{len(extracted_files)} frames\n")
        print(f"Time:\n{elapsed_time:.1f} seconds\n")

        print("First files:")
        for path in extracted_files[:5]:
            print(os.path.basename(path))

        print("\nFrame extraction completed successfully.")
        print("------------------------------------------------")

    except Exception as e:
        print(f"\n[ERROR] Frame extraction failed: {e}")
        print("------------------------------------------------")
        sys.exit(1)

if __name__ == "__main__":
    main()
