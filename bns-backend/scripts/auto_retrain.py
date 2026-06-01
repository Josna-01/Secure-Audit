# scripts/auto_retrain.py
"""
Auto retrain loop: runs train_reranker.py weekly.
Note: run this in a managed environment (systemd, kubernetes CronJob, or container). 
If you want it to run once (CI), set env RUN_ONCE=1.
"""
import os
import time
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("auto-retrain")

MODEL_DIR = "model_data"
VAL_FILE = "data/val.jsonl"
RUN_ONCE = os.getenv("RUN_ONCE", "0") == "1"
SLEEP_SECONDS = 7 * 24 * 60 * 60  # 1 week

def run_train():
    LOG.info("Starting reranker training run...")
    cmd = ["python", "scripts/train_reranker.py"]
    env = os.environ.copy()
    p = subprocess.Popen(cmd, env=env)
    ret = p.wait()
    LOG.info(f"train_reranker.py exited with code {ret}")
    return ret

def main():
    if not os.path.exists(VAL_FILE):
        LOG.error(f"Validation file {VAL_FILE} missing — create it before running auto retrain.")
        return

    while True:
        rc = run_train()
        if RUN_ONCE:
            break
        LOG.info(f"Sleeping for {SLEEP_SECONDS} seconds until next run...")
        time.sleep(SLEEP_SECONDS)

if __name__ == "__main__":
    main()
