"""Quality-aware, chronological video-frame selection for SfM/MVS."""
import os
import cv2
import logging
import numpy as np

logger = logging.getLogger(__name__)

FRAME_SELECTOR_CONFIGS = {
    "PRODUCTION": {"blur_threshold": 80.0, "lighting_threshold": 35.0, "duplicate_similarity": 0.985},
    "TEST": {"blur_threshold": 30.0, "lighting_threshold": 30.0, "duplicate_similarity": 0.990},
}


class FrameSelector:
    """Reject unusable frames, then retain sharp views distributed over the clip."""

    def __init__(self):
        self.last_diagnostics: dict = {}

    @staticmethod
    def _perceptual_similarity(first: np.ndarray, second: np.ndarray) -> float:
        first = cv2.resize(first, (160, 90), interpolation=cv2.INTER_AREA)
        second = cv2.resize(second, (160, 90), interpolation=cv2.INTER_AREA)
        return float(cv2.matchTemplate(first, second, cv2.TM_CCOEFF_NORMED)[0, 0])

    def select(self, frame_paths: list[str], max_frames: int = 30, mode: str | None = None) -> list[str]:
        if not frame_paths:
            self.last_diagnostics = {"input_frames": 0, "selected_frames": 0}
            return []
        mode = (mode or os.environ.get("PHOTOGRAMMETRY_MODE", "PRODUCTION")).upper()
        config = FRAME_SELECTOR_CONFIGS.get(mode, FRAME_SELECTOR_CONFIGS["PRODUCTION"])
        accepted: list[dict] = []
        previous_gray = None
        rejected = {"invalid": 0, "blur": 0, "dark": 0, "duplicate": 0}

        for source_index, path in enumerate(frame_paths):
            image = cv2.imread(path)
            if image is None:
                rejected["invalid"] += 1
                continue
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            exposure = float(cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 2].mean())
            if sharpness < config["blur_threshold"]:
                rejected["blur"] += 1
                continue
            if exposure < config["lighting_threshold"]:
                rejected["dark"] += 1
                continue
            similarity = self._perceptual_similarity(gray, previous_gray) if previous_gray is not None else 0.0
            if previous_gray is not None and similarity >= config["duplicate_similarity"]:
                rejected["duplicate"] += 1
                continue
            previous_gray = gray
            # Stop a highly textured background frame from winning every bin.
            quality = np.log1p(sharpness) + 0.015 * exposure
            accepted.append({"path": path, "index": source_index, "quality": float(quality)})

        if len(accepted) <= max_frames:
            selected = accepted
        else:
            # Each temporal bin contributes one strong frame. This preserves a
            # continuous viewpoint trajectory rather than quality-sorting it.
            edges = np.linspace(0, len(accepted), max_frames + 1, dtype=int)
            selected = []
            for start, stop in zip(edges[:-1], edges[1:]):
                selected.append(max(accepted[start:max(start + 1, stop)], key=lambda item: item["quality"]))
            selected.sort(key=lambda item: item["index"])

        self.last_diagnostics = {"input_frames": len(frame_paths), "passed_quality": len(accepted),
            "selected_frames": len(selected), "rejected": rejected, "mode": mode,
            "selection": "temporal_stratified_quality"}
        logger.info("Frame selection: %s", self.last_diagnostics)
        return [item["path"] for item in selected]
