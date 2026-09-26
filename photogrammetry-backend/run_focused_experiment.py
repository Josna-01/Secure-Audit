"""Run a reproducible object-focused reconstruction on a local video."""
import json
import shutil
from pathlib import Path

from services.frame_extractor import FrameExtractor
from services.frame_selector import FrameSelector
from services.roi_processor import ROIProcessor, NormalizedROI
from services.colmap_runner import ColmapRunner
from services.open3d_processor import Open3DProcessor

ROOT = Path(__file__).resolve().parent
VIDEO = ROOT / "jobs" / "cd8e0485-2e24-4bf9-9044-41eddad1a021" / "input_video.mp4"
RUN = ROOT / "focused_tower_validation_broad"
# Chosen from the contact sheet: central wooden tower + slides, while excluding
# sky, homes, trees, foreground benches and the distant swing set.
ROI = NormalizedROI(0.10, 0.08, 0.80, 0.75)
START_SECONDS, END_SECONDS, MAX_FRAMES = 0.0, 15.0, 30


def main():
    frames = FrameExtractor().extract(str(VIDEO), str(RUN / "frames"), fps=2,
                                      start_seconds=START_SECONDS, end_seconds=END_SECONDS)
    roi_frames = ROIProcessor().crop(frames, str(RUN / "roi_frames"), ROI)
    selector = FrameSelector()
    chosen = selector.select(roi_frames, max_frames=MAX_FRAMES, mode="PRODUCTION")
    source_order = {str(Path(path).resolve()).lower(): index for index, path in enumerate(roi_frames)}
    chosen.sort(key=lambda path: source_order[str(Path(path).resolve()).lower()])
    selected = RUN / "selected"
    selected.mkdir(parents=True, exist_ok=True)
    for index, path in enumerate(chosen):
        shutil.copy2(path, selected / f"frame_{index:03d}.jpg")
    colmap = ColmapRunner().reconstruct(str(selected), str(RUN / "colmap"), minimum_registration_ratio=0.8)
    processed = Open3DProcessor().process(colmap["dense_ply_path"], str(RUN / "output"))
    report = {"video": str(VIDEO), "object": "central wooden tower and slides",
              "interval_seconds": [START_SECONDS, END_SECONDS], "roi": ROI.__dict__,
              "extracted_frames": len(frames), "selected_frames": len(chosen),
              "selection": selector.last_diagnostics, "sparse": colmap["sparse_stats"],
              "processing": processed}
    (RUN / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
