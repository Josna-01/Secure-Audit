"""Regenerates figures for the paper that need corrected or converted data."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
IMG = os.environ.get("SRC_IMAGES", "")

# pdflatex cannot read WebP, so the two supplied diagrams are converted to PNG.
for src, dst in (("9.webp", "fig_evidence_flow.png"), ("10.webp", "fig_architecture.png")):
    path = os.path.join(IMG, src)
    if os.path.exists(path):
        Image.open(path).convert("RGB").save(os.path.join(FIG, dst), dpi=(300, 300))

# Custody events: live database snapshot (77 evidence_custody_records rows).
# Gas: measured on Ganache (docs/technical-report/07-blockchain-module.md, 7.12.5).
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.6))
labels = ["Registered", "Verified", "Custody\ntransfer", "Tamper\ndetected"]
counts = [24, 45, 8, 0]
a.bar(labels, counts, color=["#10b981", "#3b82f6", "#8b5cf6", "#ef4444"], edgecolor="#1f2937", width=0.55)
for i, v in enumerate(counts):
    a.text(i, v + 1, str(v), ha="center", fontweight="bold")
a.set_ylabel("On-chain custody events")
a.set_title("A. Custody events in the evaluation ledger (77)", fontweight="bold")
a.set_ylim(0, 52)
a.grid(axis="y", ls="--", alpha=0.35)

ops = ["registerEvidence", "verifyEvidence", "addCustodyRecord"]
gas = [509737, 38075, 104658]
b.bar(ops, gas, color="#6366f1", edgecolor="#1f2937", width=0.5)
for i, v in enumerate(gas):
    b.text(i, v + 9000, f"{v:,}", ha="center", fontweight="bold")
b.set_ylabel("Gas used")
b.set_title("B. Measured gas per contract call (Ganache)", fontweight="bold")
b.set_ylim(0, 580000)
b.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{int(x/1000)}k"))
b.grid(axis="y", ls="--", alpha=0.35)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig_blockchain_integrity.png"), dpi=300)
print("ok")
