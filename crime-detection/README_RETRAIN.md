# Retraining on REAL Data (fixes the root cause)

## Why this document exists
`model/best.pt` in this project was fine-tuned using `create_sample_data.py`,
`train_model.py`, and `prepare_dataset.py`, which generate **synthetic
placeholder images** — OpenCV rectangles, ellipses and solid-color blobs
drawn on plain backgrounds, labeled "knife", "handgun", etc.

A model trained on those images does not know what a real knife or gun
looks like. It learned to recognize cartoon shapes on dark backgrounds.
When you feed it a real photo, it has no relevant features to match —
which is why it was flagging unrelated objects (fans, furniture, whatever
vaguely matched leftover COCO backbone features) instead of actual
suspicious objects.

**There is no code fix for this.** Filtering, thresholds, and whitelists
can't repair a model that never learned real object features. The dataset
itself has to be replaced with real, labeled photographs, and the model
retrained on that.

The app has been patched (see `objectdetection.py`) to use the pretrained
COCO YOLOv8 weights (`yolov8n.pt`) by default instead of the broken
`best.pt`, until you complete real training below. Pretrained COCO weights
reliably detect their real classes — for this project that's mainly
**knife**, **scissors**, and **person** — and nothing else, because it was
never trained on gun/blood/bomb/etc.

## Step 1 — Get a real, labeled dataset

Do NOT use `create_sample_data.py` / `prepare_dataset.py` — delete them
from your training pipeline, they only produce synthetic junk.

Real public datasets with actual photos + YOLO-format labels:

- **Weapon / knife / gun detection**: search Roboflow Universe
  (https://universe.roboflow.com) for "weapon detection", "knife
  detection", "gun detection", "pistol detection" — many public datasets
  with thousands of real, pre-labeled images, downloadable directly in
  YOLOv8 format with one click (no relabeling needed).
- **Blood**: there is no reliable, general-purpose public "blood
  detection" dataset. Sources that exist are mostly medical/forensic and
  not licensed for general use, or are small and low quality. Realistically,
  you have two options: (a) drop "blood" as a trained class and keep it as
  a clearly-labeled color heuristic (already implemented in
  `objectdetection.py` as `detect_blood_like_regions`), or (b) collect and
  label your own dataset of real blood-scene photos, which is a serious
  undertaking (data sourcing, labeling, and likely ethical/legal review
  given the sensitive subject matter) — worth thinking hard about before
  committing to it.
- **Person**: already well-covered by COCO — you don't need to retrain
  for this at all.

Download 1-2 real datasets covering the weapon classes you actually care
about (start narrow — knife + gun — rather than 26 categories with no
real data behind most of them).

## Step 2 — Combine into one dataset

Merge the downloaded datasets into a single `dataset/` folder with the
standard YOLO layout:

```
dataset/
  train/images/   train/labels/
  val/images/     val/labels/
  data.yaml
```

`data.yaml` should list only the classes you actually have real, labeled
images for:

```yaml
path: /absolute/path/to/dataset
train: train/images
val: val/images
names:
  0: knife
  1: gun
```

(Most Roboflow exports give you this structure and file already — you
mainly need to merge multiple exports' `images`/`labels` folders together
and reconcile class IDs in `data.yaml` if two datasets number classes
differently.)

## Step 3 — Train

```bash
pip install ultralytics
```

```python
from ultralytics import YOLO

model = YOLO("yolov8n.pt")  # start from COCO pretrained weights
model.train(
    data="dataset/data.yaml",
    epochs=100,
    imgsz=640,
    patience=20,   # stop early if validation stops improving
)
```

This produces `runs/detect/train/weights/best.pt`. Copy that into
`model/best.pt`, replacing the broken one.

## Step 4 — Validate honestly before trusting it

```python
metrics = model.val()
print(metrics.box.map)     # overall mAP
print(metrics.box.maps)    # per-class mAP
```

Test it on real photos it has never seen — not the synthetic samples in
`sample_data/`. Expect real-world mAP somewhere in the 70-90% range for a
reasonably sized, clean dataset — not 99%. If per-class mAP for a
particular class is low, that class needs more/better labeled examples,
not a lower confidence threshold.

## Step 5 — Turn the custom model back on

In `objectdetection.py`, `get_model_path()` now only uses `best.pt` when
the environment variable `USE_CUSTOM_MODEL=1` is set, specifically so a
broken model can't silently replace the working pretrained one again.
Once you've validated your retrained `best.pt` on real images:

```bash
export USE_CUSTOM_MODEL=1   # Windows (PowerShell): $env:USE_CUSTOM_MODEL="1"
python main.py
```
