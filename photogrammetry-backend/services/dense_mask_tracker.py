"""Tracked, dense-stage-only masks for COLMAP stereo fusion.

This intentionally never modifies SfM inputs.  It tracks a user-configured
object rectangle through chronological registered images, refines it with
GrabCut, and writes COLMAP-compatible white=keep PNG masks.
"""
from __future__ import annotations
import json
from pathlib import Path
import cv2
import numpy as np


class DenseMaskTracker:
    def __init__(self, initial_box: tuple[float, float, float, float], margin: float = 0.12, use_grabcut: bool = False):
        """Box is normalized (x,y,width,height) in the first selected image."""
        self.initial_box, self.margin, self.use_grabcut = initial_box, margin, use_grabcut

    @staticmethod
    def _pixels(box, width, height):
        x, y, w, h = box
        return (round(x * width), round(y * height), round(w * width), round(h * height))

    @staticmethod
    def _expanded(box, width, height, margin):
        x, y, w, h = box; pad_x, pad_y = w * margin, h * margin
        return max(0, int(x-pad_x)), max(0, int(y-pad_y)), min(width, int(x+w+pad_x)), min(height, int(y+h+pad_y))

    def create(self, image_dir: str, mask_dir: str, preview_dir: str) -> dict:
        images = sorted(Path(image_dir).glob("*.jpg"))
        if not images: raise ValueError("No selected images for mask tracking.")
        Path(mask_dir).mkdir(parents=True, exist_ok=True); Path(preview_dir).mkdir(parents=True, exist_ok=True)
        first = cv2.imread(str(images[0])); height, width = first.shape[:2]
        tracker = cv2.TrackerMIL_create()
        box = self._pixels(self.initial_box, width, height)
        # OpenCV Python builds differ: init returns either None (success) or a
        # boolean. Treat only an explicit False as failure.
        initialized = tracker.init(first, box)
        if initialized is False: raise RuntimeError("Could not initialize OpenCV mask tracker.")
        records=[]
        for index, path in enumerate(images):
            image = cv2.imread(str(path)); h,w=image.shape[:2]
            if index:
                ok, candidate = tracker.update(image)
                if not ok:
                    # Graceful reinitialization keeps the last trusted target
                    # rather than emitting an unbounded/background mask.
                    tracker=cv2.TrackerMIL_create(); tracker.init(image, box); candidate=box
                box=tuple(map(int,candidate))
            left,top,right,bottom=self._expanded(box,w,h,self.margin)
            # A conservative ellipse within the tracked rectangle is robust to
            # GrabCut failures and retains rails/posts through the safety margin.
            mask=np.zeros((h,w),np.uint8)
            center=((left+right)//2,(top+bottom)//2)
            axes=(max(1,(right-left)//2),max(1,(bottom-top)//2))
            cv2.ellipse(mask,center,axes,0,0,360,cv2.GC_PR_FGD,-1)
            gc=np.full((h,w),cv2.GC_BGD,np.uint8); gc[mask==cv2.GC_PR_FGD]=cv2.GC_PR_FGD
            try:
                if not self.use_grabcut: raise cv2.error("masked", "skip", "disabled", -1)
                cv2.grabCut(image,gc,None,None,None,3,cv2.GC_INIT_WITH_MASK)
                keep=np.where((gc==cv2.GC_FGD)|(gc==cv2.GC_PR_FGD),255,0).astype(np.uint8)
                # Never permit GrabCut to make the tracked region sparse enough
                # to erase the object; fall back to its safe geometric envelope.
                if np.count_nonzero(keep) < 0.12*(right-left)*(bottom-top): keep=mask*255
            except cv2.error:
                keep=mask*255
            cv2.imwrite(str(Path(mask_dir)/(path.name+".png")),keep)
            overlay=image.copy(); overlay[keep==0]=(overlay[keep==0]*0.20).astype(np.uint8)
            cv2.rectangle(overlay,(left,top),(right,bottom),(0,255,255),2)
            if index in {0,len(images)//2,len(images)-1}: cv2.imwrite(str(Path(preview_dir)/f"mask_{index:03d}.jpg"),overlay)
            records.append({"image":path.name,"box":[left,top,right-left,bottom-top],"kept_pixels":int(np.count_nonzero(keep))})
        report={"frames":len(records),"margin":self.margin,"grabcut":self.use_grabcut,"records":records}
        Path(preview_dir,"mask_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        return report
