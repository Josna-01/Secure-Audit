"""Configurable image-space ROI preparation for object-focused reconstruction."""
from __future__ import annotations

import os
import cv2
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NormalizedROI:
    """A stable video-space ROI: x, y, width, height in [0, 1]."""
    x: float
    y: float
    width: float
    height: float

    @classmethod
    def from_environment(cls, value: str | None = None) -> "NormalizedROI | None":
        raw = value if value is not None else os.getenv("PHOTOGRAMMETRY_ROI")
        if not raw:
            return None
        try:
            x, y, width, height = (float(item.strip()) for item in raw.split(","))
        except ValueError as exc:
            raise ValueError("PHOTOGRAMMETRY_ROI must be x,y,width,height normalized to [0,1].") from exc
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
            raise ValueError("PHOTOGRAMMETRY_ROI must stay inside the normalized image bounds.")
        return cls(x, y, width, height)

    def pixels(self, image_width: int, image_height: int) -> tuple[int, int, int, int]:
        left, top = round(self.x * image_width), round(self.y * image_height)
        right, bottom = round((self.x + self.width) * image_width), round((self.y + self.height) * image_height)
        return left, top, right, bottom


class ROIProcessor:
    """Crop a consistent target region before frame selection and COLMAP.

    It deliberately does not guess an object: callers choose the target using
    an inspection pass, then can persist the normalized ROI in configuration.
    """

    def crop(self, frame_paths: list[str], output_dir: str, roi: NormalizedROI | None = None) -> list[str]:
        roi = roi or NormalizedROI.from_environment()
        if roi is None:
            return frame_paths
        os.makedirs(output_dir, exist_ok=True)
        results: list[str] = []
        for index, frame_path in enumerate(frame_paths):
            image = cv2.imread(frame_path)
            if image is None:
                logger.warning("Skipping unreadable ROI source frame: %s", frame_path)
                continue
            height, width = image.shape[:2]
            left, top, right, bottom = roi.pixels(width, height)
            cropped = image[top:bottom, left:right]
            if cropped.size == 0:
                raise ValueError(f"ROI has no pixels for frame {frame_path}")
            path = os.path.join(output_dir, f"roi_{index:03d}.jpg")
            if not cv2.imwrite(path, cropped, [cv2.IMWRITE_JPEG_QUALITY, 97]):
                raise RuntimeError(f"Unable to write ROI frame: {path}")
            results.append(path)
        logger.info("Prepared %s ROI frames using normalized ROI %s", len(results), roi)
        return results
