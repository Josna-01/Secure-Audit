import os
import cv2
import logging

logger = logging.getLogger(__name__)

class FrameExtractor:
    """
    Service class responsible for extracting individual frame images from a video file
    at a target frame rate (FPS).
    """

    def extract(self, video_path: str, output_dir: str, fps: int = 1) -> list[str]:
        """
        Extracts frames from a video file and saves them as JPEGs.

        Args:
            video_path (str): Absolute or relative path to the input video.
            output_dir (str): Directory where extracted frame JPEGs will be saved.
            fps (int): Target frame rate per second to extract. Defaults to 1.

        Returns:
            list[str]: List of paths to the saved frame image files.

        Raises:
            FileNotFoundError: If the source video file does not exist.
            ValueError: If the video cannot be opened or is unreadable by OpenCV.
        """
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Extracting frames from video '{video_path}' into directory '{output_dir}'")

        saved_frame_paths = []
        cap = cv2.VideoCapture(video_path)

        try:
            if not cap.isOpened():
                logger.error(f"OpenCV could not open video file (unreadable or invalid format): {video_path}")
                raise ValueError(f"OpenCV could not open video file: {video_path}")

            video_fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            logger.info(f"Video properties: Original FPS = {video_fps}, Total Frames = {total_frames}")

            if video_fps <= 0:
                logger.warning("Retrieved video FPS is invalid (<= 0). Defaulting to 25.0 FPS.")
                video_fps = 25.0

            # Calculate how many frames to skip to match target FPS
            interval = max(1, round(video_fps / fps))
            logger.info(f"Target extraction rate: {fps} FPS. Extracting 1 frame every {interval} frames.")

            current_frame_idx = 0
            saved_frame_count = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if current_frame_idx % interval == 0:
                    saved_frame_count += 1
                    frame_name = f"frame_{saved_frame_count:03d}.jpg"
                    frame_path = os.path.join(output_dir, frame_name)

                    # Save the frame image as JPEG
                    success = cv2.imwrite(frame_path, frame)
                    if success:
                        # Normalize path delimiters for compatibility
                        normalized_path = os.path.normpath(frame_path).replace(os.sep, '/')
                        saved_frame_paths.append(normalized_path)
                    else:
                        logger.error(f"Failed to write frame to: {frame_path}")

                current_frame_idx += 1

            logger.info(f"Frame extraction completed. Successfully saved {len(saved_frame_paths)} frames.")

        except Exception as e:
            logger.error(f"Error occurred during frame extraction: {str(e)}")
            raise

        finally:
            cap.release()
            logger.info("Video capture resource released.")

        return saved_frame_paths
