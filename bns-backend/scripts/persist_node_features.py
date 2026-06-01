# scripts/persist_node_features.py
import os
import torch
import numpy as np

MODEL_DIR = "model_data"
os.makedirs(MODEL_DIR, exist_ok=True)

# Example: save section_embeddings if you have a numpy array 'section_embeddings' available.
# If you ran scripts/build_faiss.py it already saved section_embeddings.npy into model_data.
# but if it's elsewhere:
src = "path/to/section_embeddings.npy"  # update if needed
if os.path.exists(src):
    import shutil
    shutil.copy(src, os.path.join(MODEL_DIR, "section_embeddings.npy"))
    print("Copied section_embeddings.npy to model_data/")

# Example: save a cooccurrence edge_index (torch tensor)
# suppose you built a PyTorch edge index named edge_index (shape [2, E])
# save it as:
# torch.save(edge_index, os.path.join(MODEL_DIR, "cooccur_edge_index.pt"))

# If you don't have one, it's optional — HGAT will work without it.
print("Done.")
