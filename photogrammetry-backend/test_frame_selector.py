import os
import sys
import time
import shutil
import cv2
import numpy as np
from services.frame_selector import FrameSelector
from services.frame_extractor import FrameExtractor

def generate_sharp_dummy_video(video_path: str, duration_sec: int = 5, fps: int = 30):
    """Generates a high-contrast sharp MP4 video with high Laplacian variance and motion."""
    os.makedirs(os.path.dirname(video_path) or ".", exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, fps, (640, 480))
    
    total_frames = duration_sec * fps
    for i in range(total_frames):
        # Create a frame with high-frequency noise & sharp geometric shapes to pass Laplacian blur filter (>100)
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Add checkerboard pattern
        square_size = 20 + (i % 5) * 4
        for y in range(0, 480, square_size):
            for x in range(0, 640, square_size):
                if ((x // square_size) + (y // square_size) + i) % 2 == 0:
                    img[y:y+square_size, x:x+square_size] = (220, 220, 220)
                else:
                    img[y:y+square_size, x:x+square_size] = (30, 30, 30)

        # Add sharp text
        cv2.putText(img, f"FRAME {i+1} - DETECTABLE MOTION", (30, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
        out.write(img)
    out.release()

def ensure_sample_frames(frames_dir: str) -> list[str]:
    """Ensures input frames exist in output/frames/. Generates them if missing or low quality."""
    os.makedirs(frames_dir, exist_ok=True)
    existing = [
        os.path.normpath(os.path.join(frames_dir, f)).replace(os.sep, '/')
        for f in os.listdir(frames_dir)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
    ]
    
    # Check if existing frames pass quality filters
    selector = FrameSelector()
    if existing and len(selector.select(existing, max_frames=25)) > 0:
        return sorted(existing)
    
    # Otherwise generate high-quality video and extract frames
    video_path = os.path.join("test_data", "sampleVideo.mp4")
    generate_sharp_dummy_video(video_path, duration_sec=5, fps=30)
    
    extractor = FrameExtractor()
    return extractor.extract(video_path, frames_dir, fps=1)

def main():
    print("------------------------------------------------")
    print("Testing Frame Selector...\n")

    input_dir = os.path.join("output", "frames")
    output_dir = os.path.join("output", "selected")

    frame_paths = ensure_sample_frames(input_dir)
    input_count = len(frame_paths)

    print(f"Input:\n{input_dir}/ ({input_count} frames)\n")
    print(f"Output:\n{output_dir}/\n")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    selector = FrameSelector()

    start_time = time.time()
    try:
        selected_paths = selector.select(frame_paths, max_frames=25)
        elapsed_time = time.time() - start_time

        selected_count = len(selected_paths)
        removed_count = input_count - selected_count

        # Copy selected frames to output/selected directory
        copied_filenames = []
        for src_path in selected_paths:
            filename = os.path.basename(src_path)
            dest_path = os.path.join(output_dir, filename)
            shutil.copy2(src_path, dest_path)
            copied_filenames.append(filename)

        print(f"Selected:\n{selected_count} frames\n")
        print(f"Removed:\n{removed_count} frames\n")
        print(f"Time:\n{elapsed_time:.1f} seconds\n")

        print("First files:")
        for name in copied_filenames[:5]:
            print(name)

        print("\nFrame selection completed successfully.")
        print("------------------------------------------------")

    except Exception as e:
        print(f"\n[ERROR] Frame selection failed: {e}")
        print("------------------------------------------------")
        sys.exit(1)

if __name__ == "__main__":
    main()
