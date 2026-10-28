# scripts/validate_rerank.py
import os
import argparse
import json
import sys
sys.path.append(os.getcwd())

from app.model_wrapper import RAGHGATWrapper

def load_val(path):
    if not os.path.exists(path):
        print(f"Validation file not found: {path}")
        print("Create data/val.jsonl or run: python scripts/train_reranker.py --val-file path/to/val.jsonl")
        sys.exit(1)
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            items.append(json.loads(line))
    return items

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--val-file", type=str, default="data/val.jsonl")
    parser.add_argument("--model-dir", type=str, default="model_data")
    args = parser.parse_args()

    items = load_val(args.val_file)
    wrapper = RAGHGATWrapper(model_dir=args.model_dir)

    # basic validation: run predict on first N items
    N = min(50, len(items))
    print(f"Validating reranker on {N} items from {args.val_file}")
    for i, item in enumerate(items[:N]):
        facts = item.get("facts", "")
        try:
            out = wrapper.predict(facts=facts, top_k=20)
        except Exception as e:
            print(f"Error predicting item {i}: {e}")
            continue
        # simple print
        print(f"ITEM {i}: predicted sections: {out.get('sections', [])[:5]}")

if __name__ == "__main__":
    main()
