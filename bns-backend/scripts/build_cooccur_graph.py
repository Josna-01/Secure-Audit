# scripts/build_cooccur_graph.py
import json
import os
from collections import defaultdict
import torch
import sys

sys.path.append(os.getcwd())

try:
    from app.bns import BNS_SECTION_DETAILS
except:
    BNS_SECTION_DETAILS = {}

OUT_DIR = "model_data/"

def build_cooccurrence():
    print("Building co-occurrence graph...")

    sections = list(BNS_SECTION_DETAILS.keys())
    sections_sorted = sorted(sections, key=lambda x: str(x))

    kw_map = {}
    for sid, info in BNS_SECTION_DETAILS.items():
        kw_map[str(sid)] = info.get("keywords", [])

    idx = {sid: i for i, sid in enumerate(sections_sorted)}
    N = len(sections_sorted)

    adj = defaultdict(set)

    for sid_a in sections_sorted:
        kw_a = set(kw_map.get(sid_a, []))
        for sid_b in sections_sorted:
            kw_b = set(kw_map.get(sid_b, []))
            if kw_a & kw_b and sid_a != sid_b:
                adj[idx[sid_a]].add(idx[sid_b])
                adj[idx[sid_b]].add(idx[sid_a])

    edge_src = []
    edge_dst = []
    for i in range(N):
        for j in adj[i]:
            edge_src.append(i)
            edge_dst.append(j)

    edge_index = torch.tensor([edge_src, edge_dst], dtype=torch.long)

    os.makedirs(OUT_DIR, exist_ok=True)
    torch.save(edge_index, os.path.join(OUT_DIR, "cooccur_edge_index.pt"))

    with open(os.path.join(OUT_DIR, "section_keywords.json"), "w") as f:
        json.dump(kw_map, f, indent=2)

    print("Saved → model_data/cooccur_edge_index.pt")
    print("Saved → model_data/section_keywords.json")

if __name__ == "__main__":
    build_cooccurrence()
