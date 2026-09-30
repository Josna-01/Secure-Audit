"""
train_crime_model.py  -  train a REAL knife / gun / bullet / blood detector.

Run this on a machine with a GPU (Google Colab free tier is fine). Training on
CPU works but takes many hours.

HOW IT WORKS
------------
1. You download 1+ real labeled datasets from Roboflow Universe in
   "YOLOv8" format and put each one (zip or unzipped folder) inside
   ./datasets_raw/
2. This script reads every dataset's class names, maps them onto 4 unified
   classes (knife, gun, bullet, blood), throws away everything else, merges
   all images/labels into ./dataset_merged/, and trains YOLOv8.
3. The result is copied to model/crime_best.pt, which objectdetection.py
   loads automatically. ("person" is NOT trained here - the pretrained COCO
   model already handles people well.)

USAGE
-----
    pip install ultralytics pyyaml
    python train_crime_model.py --prepare-only     # merge + show stats, no training
    python train_crime_model.py                    # merge + train + copy weights
    python train_crime_model.py --epochs 150 --model yolov8s.pt --imgsz 640

HONEST NOTE ON ACCURACY
-----------------------
Final accuracy depends on your data. Typical results on decent datasets:
knife/gun roughly 70-90% mAP50; bullet/casing lower; blood is the hardest
(few good datasets). The script prints per-class instance counts and per-class
mAP so you can see exactly which class is weak. A class with < ~300 labeled
instances will be unreliable - add more data for it rather than lowering the
confidence threshold.
"""

import argparse
import random
import shutil
import sys
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "datasets_raw"
OUT_DIR = ROOT / "dataset_merged"
MODEL_OUT = ROOT / "model" / "crime_best.pt"

# Unified classes the final model will detect (order = class id).
UNIFIED = ["knife", "gun", "bullet", "blood"]

# Keywords used to map each dataset's own class names onto the unified classes.
# Edit these if a dataset uses different names. Matching is case-insensitive
# substring matching on the class name (underscores/dashes treated as spaces).
KEYWORDS = {
    "knife":  ["knife", "knives", "blade", "dagger", "machete", "cleaver"],
    "gun":    ["gun", "pistol", "handgun", "revolver", "rifle", "firearm",
               "shotgun", "glock", "weapon"],
    "bullet": ["bullet", "ammo", "ammunition", "cartridge", "casing", "shell casing"],
    "blood":  ["blood", "bloodstain", "blood stain", "blood pool", "splatter", "gore"],
}

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def norm(name: str) -> str:
    return str(name).lower().replace("_", " ").replace("-", " ").strip()


def map_name(name: str):
    n = norm(name)
    for uid, cname in enumerate(UNIFIED):
        if any(k in n for k in KEYWORDS[cname]):
            return uid
    return None


def extract_zips():
    RAW_DIR.mkdir(exist_ok=True)
    for z in RAW_DIR.glob("*.zip"):
        target = RAW_DIR / z.stem
        if target.exists():
            continue
        print(f"[unzip] {z.name}")
        with zipfile.ZipFile(z) as zf:
            zf.extractall(target)


def find_datasets():
    """A dataset = any folder under datasets_raw containing data.yaml."""
    return sorted({p.parent for p in RAW_DIR.rglob("data.yaml")})


def load_names(yaml_path: Path):
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    names = data.get("names", [])
    if isinstance(names, dict):
        return {int(k): v for k, v in names.items()}
    return {i: n for i, n in enumerate(names)}


def convert_label_line(parts, cls_map):
    """Return a YOLO bbox line with the unified class id, or None to drop it.
    Handles both bbox (5 values) and polygon/segmentation (>5 values) labels."""
    try:
        old_id = int(float(parts[0]))
        vals = [float(v) for v in parts[1:]]
    except ValueError:
        return None
    new_id = cls_map.get(old_id)
    if new_id is None:
        return None
    if len(vals) == 4:
        cx, cy, w, h = vals
    elif len(vals) >= 6 and len(vals) % 2 == 0:
        xs, ys = vals[0::2], vals[1::2]
        x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
        cx, cy, w, h = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
    else:
        return None
    if w <= 0 or h <= 0:
        return None
    return f"{new_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def split_dirs(ds: Path):
    """Yield (split_name, images_dir, labels_dir) for a Roboflow-style dataset."""
    for split, target in (("train", "train"), ("valid", "val"), ("val", "val"), ("test", "val")):
        img_dir, lbl_dir = ds / split / "images", ds / split / "labels"
        if img_dir.is_dir() and lbl_dir.is_dir():
            yield target, img_dir, lbl_dir


def prepare(seed=0, val_fraction=0.15):
    extract_zips()
    datasets = find_datasets()
    if not datasets:
        sys.exit(f"No datasets found. Put Roboflow YOLOv8 exports (zip or folder) in {RAW_DIR}")

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    for s in ("train", "val"):
        (OUT_DIR / "images" / s).mkdir(parents=True)
        (OUT_DIR / "labels" / s).mkdir(parents=True)

    counts = {"train": {c: 0 for c in UNIFIED}, "val": {c: 0 for c in UNIFIED}}
    images = {"train": 0, "val": 0}

    for ds in datasets:
        names = load_names(ds / "data.yaml")
        cls_map = {i: map_name(n) for i, n in names.items()}
        print(f"\n[dataset] {ds.relative_to(RAW_DIR)}")
        for i, n in names.items():
            tgt = cls_map[i]
            print(f"    {i:>3} '{n}' -> {UNIFIED[tgt] if tgt is not None else '(dropped)'}")
        if all(v is None for v in cls_map.values()):
            print("    !! none of this dataset's classes matched - skipped. "
                  "Edit KEYWORDS at the top of this script if the names differ.")
            continue

        tag = ds.name.replace(" ", "_")
        for target, img_dir, lbl_dir in split_dirs(ds):
            for img in img_dir.iterdir():
                if img.suffix.lower() not in IMG_EXT:
                    continue
                lbl = lbl_dir / (img.stem + ".txt")
                if not lbl.exists():
                    continue
                lines = []
                for raw in lbl.read_text().splitlines():
                    parts = raw.split()
                    if len(parts) < 5:
                        continue
                    out = convert_label_line(parts, cls_map)
                    if out:
                        lines.append(out)
                if not lines:
                    continue  # image has none of our classes
                new_stem = f"{tag}_{target}_{img.stem}"
                shutil.copy2(img, OUT_DIR / "images" / target / (new_stem + img.suffix))
                (OUT_DIR / "labels" / target / (new_stem + ".txt")).write_text("\n".join(lines) + "\n")
                images[target] += 1
                for ln in lines:
                    counts[target][UNIFIED[int(ln.split()[0])]] += 1

    # If no dataset had a validation split, carve one out of train.
    if images["val"] == 0 and images["train"] > 0:
        print("\n[split] no validation images found - moving 15% of train to val")
        random.seed(seed)
        train_imgs = sorted((OUT_DIR / "images" / "train").iterdir())
        random.shuffle(train_imgs)
        n_val = max(1, int(len(train_imgs) * val_fraction))
        for img in train_imgs[:n_val]:
            lbl = OUT_DIR / "labels" / "train" / (img.stem + ".txt")
            shutil.move(str(img), OUT_DIR / "images" / "val" / img.name)
            shutil.move(str(lbl), OUT_DIR / "labels" / "val" / lbl.name)
            for ln in (OUT_DIR / "labels" / "val" / lbl.name).read_text().splitlines():
                c = UNIFIED[int(ln.split()[0])]
                counts["train"][c] -= 1
                counts["val"][c] += 1
        images["train"] -= n_val
        images["val"] += n_val

    if images["train"] == 0:
        sys.exit("No usable training images after mapping classes. Check the class-mapping table above.")

    (OUT_DIR / "data.yaml").write_text(yaml.safe_dump({
        "path": str(OUT_DIR),
        "train": "images/train",
        "val": "images/val",
        "names": {i: n for i, n in enumerate(UNIFIED)},
    }, sort_keys=False))

    print("\n================ MERGED DATASET ================")
    print(f"images: train={images['train']}  val={images['val']}")
    print(f"{'class':<8}{'train inst':>12}{'val inst':>10}")
    weak = []
    for c in UNIFIED:
        tr, va = counts["train"][c], counts["val"][c]
        print(f"{c:<8}{tr:>12}{va:>10}")
        if tr < 300:
            weak.append((c, tr))
    if weak:
        print("\nWARNING: too little data for: " +
              ", ".join(f"{c} ({n} instances)" for c, n in weak))
        print("These classes will be unreliable. Add more real labeled datasets "
              "for them into datasets_raw/ and re-run.")
    missing = [c for c in UNIFIED if counts["train"][c] == 0]
    if missing:
        print(f"\nNo training data at all for: {missing}. "
              "The model cannot detect a class it has never seen.")
    return images


def train(args):
    from ultralytics import YOLO
    model = YOLO(args.model)
    model.train(
        data=str(OUT_DIR / "data.yaml"),
        epochs=args.epochs,
        imgsz=args.imgsz,
        patience=25,
        project=str(ROOT / "runs"),
        name="crime",
        exist_ok=True,
    )
    best = ROOT / "runs" / "crime" / "weights" / "best.pt"
    metrics = YOLO(str(best)).val(data=str(OUT_DIR / "data.yaml"))
    print("\n================ VALIDATION (held-out images) ================")
    print(f"overall mAP50: {metrics.box.map50:.3f}   mAP50-95: {metrics.box.map:.3f}")
    for i, name in enumerate(UNIFIED):
        try:
            print(f"  {name:<8} mAP50-95: {metrics.box.maps[i]:.3f}")
        except IndexError:
            pass
    MODEL_OUT.parent.mkdir(exist_ok=True)
    shutil.copy2(best, MODEL_OUT)
    print(f"\nSaved -> {MODEL_OUT}\nRestart the app (python main.py); it loads this automatically.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare-only", action="store_true")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--model", default="yolov8s.pt")
    a = ap.parse_args()
    prepare()
    if not a.prepare_only:
        train(a)
