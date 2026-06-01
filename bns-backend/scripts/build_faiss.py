# scripts/build_faiss.py
# Build section embeddings + FAISS index from app.bns.BNS_SECTION_DETAILS
# Robust import: tries app.bns, else loads bns.py from common locations.
import os
import json
import argparse
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import importlib.util
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("build_faiss")

def load_bns_sections():
    """
    Try to import BNS_SECTION_DETAILS from app.bns.
    If that fails, try to load bns.py from common paths (./app/bns.py, ./bns.py, /mnt/data/bns.py).
    """
    try:
        # Preferred: package import
        from app.bns import BNS_SECTION_DETAILS  # preferred package import
        logger.info("Imported BNS_SECTION_DETAILS from app.bns")
        return BNS_SECTION_DETAILS
    except Exception as e:
        logger.warning(f"Failed to import app.bns ({e}). Attempting fallback file import...")

    # candidate paths to search for bns.py (project root, app folder, /mnt/data)
    candidates = [
        os.path.join(os.getcwd(), "app", "bns.py"),
        os.path.join(os.getcwd(), "bns.py"),
        "/mnt/data/bns.py",  # uploaded location in this environment
    ]
    for path in candidates:
        if os.path.exists(path):
            logger.info(f"Loading BNS_SECTION_DETAILS from {path}")
            spec = importlib.util.spec_from_file_location("bns_fallback", path)
            bns_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bns_mod)
            if hasattr(bns_mod, "BNS_SECTION_DETAILS"):
                return getattr(bns_mod, "BNS_SECTION_DETAILS")
            else:
                raise RuntimeError(f"{path} loaded but BNS_SECTION_DETAILS not found inside.")
    # if nothing found raise
    raise RuntimeError("Could not find bns.py or app.bns.BNS_SECTION_DETAILS. Place bns.py in ./app or project root or /mnt/data.")

def build(model_name: str, out_dir: str):
    # load sections dict (robust)
    BNS_SECTION_DETAILS = load_bns_sections()  # may raise
    os.makedirs(out_dir, exist_ok=True)

    meta_list = []
    texts = []
    # BNS_SECTION_DETAILS assumed to be dict mapping section_id -> metadata dict
    for sid, info in BNS_SECTION_DETAILS.items():
        title = info.get("title", "")
        desc = info.get("description", "")
        kws = info.get("keywords", [])
        if isinstance(kws, list):
            kws = " ".join(kws)
        full_text = " | ".join([title, desc, kws]).strip()
        meta_list.append({"id": sid, "text": full_text})
        texts.append(full_text)

    # encode with sentence-transformers
    logger.info(f"Encoding {len(texts)} section texts with {model_name} ...")
    model = SentenceTransformer(model_name)
    embs = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
    logger.info(f"Embeddings shape: {embs.shape}")

    # save embeddings & meta
    emb_path = os.path.join(out_dir, "section_embeddings.npy")
    meta_path = os.path.join(out_dir, "sections_meta.json")
    np.save(emb_path, embs)
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta_list, fh, ensure_ascii=False, indent=2)
    logger.info(f"Saved embeddings to {emb_path} and meta to {meta_path}")

    # build FAISS index (use inner product on normalized vectors for cosine similarity)
    d = embs.shape[1]
    logger.info(f"Building FAISS Index (dimension={d}) ...")
    # normalize embeddings for cosine via inner product
    embs_norm = embs.astype("float32")
    faiss.normalize_L2(embs_norm)
    index = faiss.IndexFlatIP(d)
    index.add(embs_norm)
    faiss_path = os.path.join(out_dir, "faiss.index")
    faiss.write_index(index, faiss_path)
    logger.info(f"FAISS index written to {faiss_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build FAISS index for BNS sections")
    parser.add_argument("--sent_model", default="sentence-transformers/all-MiniLM-L6-v2", help="SentenceTransformer model")
    parser.add_argument("--out", default="model_data", help="Output directory")
    args = parser.parse_args()
    build(model_name=args.sent_model, out_dir=args.out)
    print("FAISS build complete.")
