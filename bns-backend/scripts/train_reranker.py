# scripts/train_reranker.py
import os
import json
import pickle
import numpy as np
from tqdm import tqdm
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from torch.utils.tensorboard import SummaryWriter
import sys
sys.path.append(os.getcwd())

from app.model_wrapper import RAGHGATWrapper
from app.postprocess import SECTION_TO_CLUSTER

def cluster_one_hot(cluster, cluster_list):
    vec = [1.0 if cl == cluster else 0.0 for cl in cluster_list]
    return vec

def extract_features_for_section(wrapper, facts, sid, model_score, raw_retrieval_hits):
    # encode
    cls_emb, rag_vec, raw_hits = wrapper._encode_for_reranker(facts, top_k=20)
    cls_mean = float(np.mean(cls_emb)) if cls_emb is not None else 0.0
    rag_mean = float(np.mean(rag_vec)) if rag_vec is not None else 0.0
    # find rag_score for this sid
    rag_score = 0.0
    for h in raw_retrieval_hits:
        if str(h.get("section_id")) == str(sid):
            rag_score = float(h.get("score", 0.0))
            break
    return np.array([cls_mean, rag_mean, float(model_score), rag_score], dtype=np.float32)

def main(val_file="data/val.jsonl", model_dir="model_data", log_dir="runs/reranker_train"):
    if not os.path.exists(val_file):
        print(f"Validation file {val_file} not found. Create it or pass --val-file path/to/val.jsonl")
        return 1

    wrapper = RAGHGATWrapper(model_dir=model_dir)
    cluster_list = sorted(list(set(SECTION_TO_CLUSTER.values())))

    X = []
    y = []

    writer = SummaryWriter(log_dir=log_dir)

    with open(val_file, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    if not lines:
        print("Validation file empty — nothing to train on.")
        return 1

    for i, line in enumerate(tqdm(lines, desc="Building dataset")):
        item = json.loads(line)
        facts = item.get("facts", "")
        true = set([str(s) for s in item.get("true_sections", [])])

        raw = wrapper.predict(facts=facts, top_k=20)
        raw_hits = raw.get("raw_retrieval", {}).get("hits", []) if isinstance(raw.get("raw_retrieval", {}), dict) else raw.get("raw_retrieval", [])
        for sid, score, evidence in raw.get("sections", []):
            sid = str(sid)
            feat_base = extract_features_for_section(wrapper, facts, sid, score, raw_hits)

            cluster = SECTION_TO_CLUSTER.get(sid, "default")
            cluster_vec = cluster_one_hot(cluster, cluster_list)

            feat = np.concatenate([feat_base, np.array(cluster_vec, dtype=np.float32)])
            X.append(feat)
            y.append(1 if sid in true else 0)

    if len(X) == 0:
        print("No feature rows were generated (empty X). Aborting training.")
        return 1

    X = np.vstack(X)
    y = np.array(y)

    # train logistic regression
    model = LogisticRegression(max_iter=400)
    model.fit(X, y)
    preds = model.predict(X)
    acc = accuracy_score(y, preds)
    writer.add_scalar("reranker/train_accuracy", float(acc), 0)
    writer.close()

    os.makedirs(model_dir, exist_ok=True)
    with open(os.path.join(model_dir, "reranker.pkl"), "wb") as fh:
        pickle.dump(model, fh)
    cfg = {"clusters": cluster_list, "alpha": 0.7}
    with open(os.path.join(model_dir, "reranker_config.json"), "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)

    print(f"Saved reranker with train accuracy {acc:.4f} to {os.path.join(model_dir, 'reranker.pkl')}")
    print(f"TensorBoard logs saved to {log_dir} (run: tensorboard --logdir {log_dir})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
