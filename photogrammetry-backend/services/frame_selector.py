import os
import cv2
import logging

logger = logging.getLogger(__name__)

class FrameSelector:
    """
    Service class responsible for filtering and selecting high-quality,
    distinct frame images for 3D reconstruction.
    """

    def select(self, frame_paths: list[str], max_frames: int = 25) -> list[str]:
        """
        Filters out low-quality (blurry, dark) and duplicate/similar frames,
        returning up to max_frames paths sorted by overall composite quality.

        Args:
            frame_paths (list[str]): List of file paths to the input frame images.
            max_frames (int): Maximum number of frames to return in the selection. Defaults to 25.

        Returns:
            list[str]: List of selected frame image paths, sorted by composite quality score descending.
        """
        total_input = len(frame_paths)
        if total_input == 0:
            logger.info("No frame paths provided for selection.")
            return []

        logger.info(f"Starting frame selection from {total_input} frames (target limit: {max_frames})")

        invalid_files = 0
        blur_rejected = 0
        lighting_rejected = 0
        similarity_rejected = 0

        passed_candidates = []  # List of tuples: (composite_score, path)
        last_accepted_gray = None

        for path in frame_paths:
            if not os.path.exists(path):
                logger.warning(f"Frame file does not exist: {path}")
                invalid_files += 1
                continue

            img = cv2.imread(path)
            if img is None:
                logger.warning(f"Could not read image frame: {path}")
                invalid_files += 1
                continue

            # Convert to Grayscale for blur and similarity analysis
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # 1. Sharpness/Blur Filter (Variance of Laplacian)
            blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
            if blur_score < 100.0:
                blur_rejected += 1
                continue

            # 2. Lighting/Exposure Filter (Mean of V channel in HSV)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            lighting_score = float(hsv[:, :, 2].mean())
            if lighting_score < 50.0:
                lighting_rejected += 1
                continue

            # 3. Near-Duplicate/Similarity Filter (Mean pixel difference vs. last accepted frame)
            if last_accepted_gray is not None:
                diff = cv2.absdiff(gray, last_accepted_gray)
                mean_diff = float(diff.mean())
                if mean_diff < 10.0:
                    similarity_rejected += 1
                    continue

            # Frame passed all filters. Keep track of it and update the comparison baseline.
            last_accepted_gray = gray
            composite_score = blur_score + lighting_score
            passed_candidates.append((composite_score, path))

        # Log filter statistics
        logger.info(
            f"Frame selection filtering statistics: "
            f"Total Input = {total_input}, "
            f"Invalid = {invalid_files}, "
            f"Rejected (Blurry) = {blur_rejected}, "
            f"Rejected (Dark) = {lighting_rejected}, "
            f"Rejected (Similar) = {similarity_rejected}, "
            f"Passed Filters = {len(passed_candidates)}"
        )

        # Sort candidate frames by composite score in descending order (highest quality first)
        passed_candidates.sort(key=lambda x: x[0], reverse=True)

        # Retrieve up to max_frames paths
        selected_paths = [path for _, path in passed_candidates[:max_frames]]
        logger.info(f"Successfully selected {len(selected_paths)} frames.")

        return selected_paths
