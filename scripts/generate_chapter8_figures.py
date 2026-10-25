"""Generate reproducible Chapter 8 figures from retained Secure Audit results.

Sources:
* Blockchain ledger and gas readings recorded in the evaluation figure.
* BNS benchmark values in bns-backend/tests/benchmark_results.json.
* Aggregate photogrammetry metrics reported by the project's evaluation engine.

OCR and audio figures are deliberately excluded because their raw evaluation
outputs are not retained in this repository.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "chapter8" / "figures"
OUTPUT.mkdir(parents=True, exist_ok=True)
REPORT_FIGURES = ROOT / "report_figures"
REPORT_FIGURES.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})


def save(fig: plt.Figure, filename: str) -> None:
    fig.tight_layout()
    fig.savefig(OUTPUT / filename, dpi=300, bbox_inches="tight")
    plt.close(fig)


def blockchain_figure() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    events = {"Registered": 24, "Verified": 45, "Custody\ntransfer": 8, "Tamper\ndetected": 0}
    axes[0].bar(events.keys(), events.values(), color=["#18b982", "#4285e8", "#8956e8", "#e85d5d"], edgecolor="#202938")
    axes[0].set_title("A. Custody events in the evaluation ledger (77)", fontweight="bold")
    axes[0].set_ylabel("On-chain custody events")
    axes[0].set_ylim(0, 52)
    for index, value in enumerate(events.values()):
        axes[0].text(index, value + 0.8, str(value), ha="center", fontweight="bold")
    axes[0].grid(axis="y", alpha=0.3, linestyle="--")

    gas = {"registerEvidence": 509_737, "verifyEvidence": 38_075, "addCustodyRecord": 104_658}
    axes[1].bar(gas.keys(), gas.values(), color="#6461d9", edgecolor="#202938")
    axes[1].set_title("B. Measured gas per contract call (Ganache)", fontweight="bold")
    axes[1].set_ylabel("Gas used")
    axes[1].ticklabel_format(axis="y", style="plain")
    axes[1].grid(axis="y", alpha=0.3, linestyle="--")
    for index, value in enumerate(gas.values()):
        axes[1].text(index, value + 9_000, f"{value:,}", ha="center", fontweight="bold")
    save(fig, "figure_15_blockchain_ledger_and_gas.png")

    # A copy named exactly for the Chapter 8 LaTeX reference.
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    axes[0].bar(events.keys(), events.values(), color=["#18b982", "#4285e8", "#8956e8", "#e85d5d"], edgecolor="#202938")
    axes[0].set_title("A. Custody events in the evaluation ledger (77)", fontweight="bold")
    axes[0].set_ylabel("On-chain custody events")
    axes[0].set_ylim(0, 52)
    axes[0].grid(axis="y", alpha=0.3, linestyle="--")
    for index, value in enumerate(events.values()):
        axes[0].text(index, value + 0.8, str(value), ha="center", fontweight="bold")
    axes[1].bar(gas.keys(), gas.values(), color="#6461d9", edgecolor="#202938")
    axes[1].set_title("B. Measured gas per contract call (Ganache)", fontweight="bold")
    axes[1].set_ylabel("Gas used")
    axes[1].ticklabel_format(axis="y", style="plain")
    axes[1].grid(axis="y", alpha=0.3, linestyle="--")
    for index, value in enumerate(gas.values()):
        axes[1].text(index, value + 9_000, f"{value:,}", ha="center", fontweight="bold")
    fig.tight_layout()
    fig.savefig(REPORT_FIGURES / "figure15_ledger_gas.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def bns_figure() -> None:
    data_path = ROOT / "bns-backend" / "tests" / "benchmark_results.json"
    results = json.loads(data_path.read_text(encoding="utf-8"))
    labels = ["Precision", "Recall", "F1 score"]
    values = [results["micro_precision"], results["micro_recall"], results["micro_f1_score"]]
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    bars = ax.bar(labels, values, color=["#ed9b40", "#1bb982", "#557be8"], edgecolor="#202938")
    ax.set_title("BNS decision-support benchmark: 30 multi-offence FIR scenarios", fontweight="bold")
    ax.set_ylabel("Micro-average score")
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.03, f"{value:.3f}", ha="center", fontweight="bold")
    ax.text(0.5, -0.18, "Recall-oriented suggestions; all outputs require investigator review.",
            transform=ax.transAxes, ha="center", fontsize=9, color="#4d596b")
    save(fig, "figure_17_bns_benchmark.png")


def photogrammetry_figure() -> None:
    # Aggregate values emitted by the project's photogrammetry evaluation report.
    labels = ["Weighted\nmean", "Unweighted\nmean", "Median", "Reference\nthreshold"]
    values = [0.8756, 0.7942, 0.8369, 1.0000]
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    bars = ax.bar(labels, values, color=["#15ad82", "#557be8", "#f2a93b", "#8b93a1"], edgecolor="#202938")
    ax.set_title("Structure-from-Motion reprojection-error summary", fontweight="bold")
    ax.set_ylabel("Reprojection error (pixels)")
    ax.set_ylim(0, 1.15)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.035, f"{value:.4f} px", ha="center", fontweight="bold")
    ax.text(0.5, -0.18, "Aggregate evaluation: 1,996,707 feature observations.",
            transform=ax.transAxes, ha="center", fontsize=9, color="#4d596b")
    save(fig, "figure_16_photogrammetry_reprojection_summary.png")


def module_results_summary() -> None:
    """One composite figure for Sections 8.2--8.5.

    OCR and audio values are labelled as reference-paper values because their raw
    evaluation corpora are not retained in this checkout. BNS data comes from the
    retained benchmark JSON and photogrammetry values from its evaluation report.
    """
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.4))
    fig.suptitle("Chapter 8: Controlled Evaluation Summary", fontsize=17, fontweight="bold", y=0.98)

    # OCR CER: lower is better.
    ocr_labels = ["PaddleOCR", "Tesseract", "Hybrid"]
    ocr_values = [4.45, 4.17, 1.18]
    bars = axes[0, 0].bar(ocr_labels, ocr_values, color=["#ef9d37", "#6f7fdc", "#1bb982"], edgecolor="#202938")
    axes[0, 0].set_title("A. OCR mean character error rate", fontweight="bold")
    axes[0, 0].set_ylabel("CER (%) — lower is better")
    axes[0, 0].set_ylim(0, 5.4)
    axes[0, 0].grid(axis="y", alpha=0.3, linestyle="--")
    for bar, value in zip(bars, ocr_values):
        axes[0, 0].text(bar.get_x() + bar.get_width() / 2, value + 0.15, f"{value:.2f}%", ha="center", fontweight="bold")
    axes[0, 0].text(0.5, -0.22, "Reference-paper result; raw corpus not retained in repository.",
                    transform=axes[0, 0].transAxes, ha="center", fontsize=8, color="#4d596b")

    # BNS scores from retained JSON.
    data_path = ROOT / "bns-backend" / "tests" / "benchmark_results.json"
    results = json.loads(data_path.read_text(encoding="utf-8"))
    bns_labels = ["Precision", "Recall", "F1"]
    bns_values = [results["micro_precision"], results["micro_recall"], results["micro_f1_score"]]
    bars = axes[0, 1].bar(bns_labels, bns_values, color=["#ef9d37", "#1bb982", "#557be8"], edgecolor="#202938")
    axes[0, 1].set_title("B. Deployed BNS scorer: 30 FIRs", fontweight="bold")
    axes[0, 1].set_ylabel("Micro-average score")
    axes[0, 1].set_ylim(0, 1.05)
    axes[0, 1].grid(axis="y", alpha=0.3, linestyle="--")
    for bar, value in zip(bars, bns_values):
        axes[0, 1].text(bar.get_x() + bar.get_width() / 2, value + 0.03, f"{value:.3f}", ha="center", fontweight="bold")

    # Audio throughput only: no raw corpus for detection-rate plot.
    axes[1, 0].bar(["60-second\naudio clip"], [4.2], width=0.48, color="#7f55d9", edgecolor="#202938")
    axes[1, 0].set_title("C. Audio-analysis processing time", fontweight="bold")
    axes[1, 0].set_ylabel("Processing time (seconds)")
    axes[1, 0].set_ylim(0, 5.2)
    axes[1, 0].grid(axis="y", alpha=0.3, linestyle="--")
    axes[1, 0].text(0, 4.35, "4.2 s", ha="center", fontweight="bold")
    axes[1, 0].text(0.5, -0.22, "Reference-paper result; raw corpus not retained in repository.",
                    transform=axes[1, 0].transAxes, ha="center", fontsize=8, color="#4d596b")

    # Photogrammetry outcome counts.
    photo_labels = ["Completed", "Failed", "Incomplete"]
    photo_values = [20, 3, 3]
    bars = axes[1, 1].bar(photo_labels, photo_values, color=["#1bb982", "#e75d5d", "#ef9d37"], edgecolor="#202938")
    axes[1, 1].set_title("D. Photogrammetry jobs: 26 trials", fontweight="bold")
    axes[1, 1].set_ylabel("Number of jobs")
    axes[1, 1].set_ylim(0, 23)
    axes[1, 1].grid(axis="y", alpha=0.3, linestyle="--")
    for bar, value in zip(bars, photo_values):
        axes[1, 1].text(bar.get_x() + bar.get_width() / 2, value + 0.55, str(value), ha="center", fontweight="bold")
    axes[1, 1].text(0.5, -0.22, "Weighted reprojection error: 0.8756 px across 1,996,707 observations.",
                    transform=axes[1, 1].transAxes, ha="center", fontsize=8, color="#4d596b")

    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(REPORT_FIGURES / "figure16_module_results_summary.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def copy_object_detection_example() -> None:
    """Publish a retained annotated YOLO result for Chapter 8."""
    source = ROOT / "best" / "outputs" / "detected_0c605f60.jpg"
    if not source.exists():
        raise FileNotFoundError(f"Retained YOLO example not found: {source}")
    shutil.copy2(source, REPORT_FIGURES / "figure17_object_detection_example.jpg")


if __name__ == "__main__":
    blockchain_figure()
    bns_figure()
    photogrammetry_figure()
    module_results_summary()
    copy_object_detection_example()
    print(f"Created figures in {OUTPUT}")
