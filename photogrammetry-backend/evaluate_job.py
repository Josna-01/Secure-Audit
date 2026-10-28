"""CLI entry point for Photogrammetry Evaluation and Research Reporting Module.

Usage examples:
    # 1. Generate OVERALL PIPELINE PERFORMANCE SUMMARY across all reconstruction jobs (Primary):
    python evaluate_job.py --all

    # 2. Generate overall summary for specific subset of jobs:
    python evaluate_job.py --compare c199a911-ac53-422e-b3a9-87444a5b766b 54f0cecd-0b11-4bb8-91ac-1046ddf89b3a

    # 3. Evaluate single job:
    python evaluate_job.py --job c199a911-ac53-422e-b3a9-87444a5b766b

    # 4. Evaluate single job with physical dimension accuracy against ground truth:
    python evaluate_job.py --job c199a911-ac53-422e-b3a9-87444a5b766b --gt-length 29.0 --gt-width 10.5 --gt-height 12.0 --unit cm
"""
import os
import sys
import argparse
import logging
from services.evaluator import PhotogrammetryEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("evaluate_job")


def main():
    parser = argparse.ArgumentParser(
        description="Secure Audit — Photogrammetry Research Evaluation & Aggregate Performance Module"
    )
    parser.add_argument("--job", type=str, help="Job ID or job directory path to evaluate individually")
    parser.add_argument("--jobs-root", type=str, default=None, help="Root directory holding all job workspaces")
    parser.add_argument("--gt-length", type=float, default=None, help="Ground truth length measurement (major axis)")
    parser.add_argument("--gt-width", type=float, default=None, help="Ground truth width measurement (intermediate axis)")
    parser.add_argument("--gt-height", type=float, default=None, help="Ground truth height measurement (minor axis)")
    parser.add_argument("--unit", type=str, default="cm", help="Measurement unit (e.g. cm, m, mm)")
    parser.add_argument("--scale", type=float, default=None, help="Pre-calibrated scale factor")
    parser.add_argument("--compare", nargs="+", help="List of specific job IDs to aggregate and compare")
    parser.add_argument("--all", action="store_true", help="Generate overall pipeline performance summary across all jobs")
    parser.add_argument("--summary", action="store_true", help="Alias for --all to generate overall aggregate summary")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for benchmark reports and charts")

    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    jobs_root = args.jobs_root or os.path.join(base_dir, "jobs")
    evaluator = PhotogrammetryEvaluator(jobs_root=jobs_root)

    # 1. Overall Pipeline Evaluation across All Jobs or Specified Jobs
    if args.all or args.summary or args.compare or not args.job:
        target_jobs = args.compare if args.compare else evaluator.list_available_jobs()
        if not target_jobs:
            print(f"[ERROR] No job directories found in {jobs_root}")
            sys.exit(1)

        out_dir = args.output_dir or os.path.join(base_dir, "evaluation_benchmark")
        logger.info(f"Generating overall pipeline performance summary across {len(target_jobs)} jobs...")
        res = evaluator.generate_overall_pipeline_summary(job_identifiers=target_jobs, output_dir=out_dir)

        print("\n" + "=" * 80)
        print(" SECURE AUDIT — 3D PHOTOGRAMMETRY OVERALL PIPELINE PERFORMANCE SUMMARY")
        print("=" * 80)
        print(f"Total Evaluated Runs:     {res['total_runs']}")
        print(f"Successful Runs:          {res['successful_runs']} ({res['pipeline_success_rate']}%)")
        print("-" * 80)
        print(f"Research Artifacts Generated:")
        print(f" - Primary Markdown:       {res['summary_md']}")
        print(f" - Aggregate Metrics JSON: {res['summary_json']}")
        print(f" - Aggregate Metrics CSV:  {res['summary_csv']}")
        print(f" - Job Traceability CSV:   {res['traceability_csv']}")
        print(f" - Master Research Chart:  {res['dashboard_png']}")
        print("=" * 80 + "\n")
        return

    # 2. Single Job Evaluation
    gt_dict = None
    if args.gt_length and args.gt_width and args.gt_height:
        gt_dict = {
            "length": args.gt_length,
            "width": args.gt_width,
            "height": args.gt_height
        }

    try:
        metrics = evaluator.evaluate_job(
            job_id_or_path=args.job,
            ground_truth=gt_dict,
            unit=args.unit,
            scale_factor=args.scale
        )
        eval_dir = os.path.join(metrics["job_directory"], "evaluation")
        print("\n" + "=" * 80)
        print(f" PHOTOGRAMMETRY RESEARCH EVALUATION — SINGLE JOB: {metrics['job_id']}")
        print("=" * 80)
        print(f"Video:             {metrics['video'].get('resolution')} @ {metrics['video'].get('fps')} FPS ({metrics['video'].get('duration_seconds')}s)")
        print(f"Keyframes:         {metrics['frame_processing'].get('selected_frames_count')} selected / {metrics['frame_processing'].get('extracted_frames_count')} extracted ({metrics['frame_processing'].get('selection_ratio_percent')}%)")
        print(f"SfM Registration:  {metrics['colmap_sfm'].get('registered_images')} registered ({metrics['colmap_sfm'].get('registration_percentage')}%)")
        print(f"Sparse Points:     {metrics['colmap_sfm'].get('sparse_points_count'):,} (Reprojection Error: {metrics['colmap_sfm'].get('mean_reprojection_error_px')} px)")
        print(f"Dense Points:      {metrics['geometry_and_mesh'].get('fused_point_count')} fused -> {metrics['geometry_and_mesh'].get('cleaned_point_count')} cleaned ({metrics['geometry_and_mesh'].get('points_removed_percent')}% outliers removed)")
        print(f"Mesh Geometry:     {metrics['geometry_and_mesh'].get('mesh_vertex_count')} vertices, {metrics['geometry_and_mesh'].get('mesh_triangle_count')} triangles")

        if metrics.get("physical_dimension_accuracy") and metrics["physical_dimension_accuracy"].get("status") == "evaluated":
            phys = metrics["physical_dimension_accuracy"]
            print(f"Physical Accuracy: MAE = {phys['mean_absolute_error']} {phys['unit']} | MAPE = {phys['mean_absolute_percentage_error']}% (Scale: {phys['scale_factor']})")

        print("-" * 80)
        print(f"Job Artifacts Exported to: {eval_dir}")
        print(f" - {os.path.join(eval_dir, 'metrics.json')}")
        print(f" - {os.path.join(eval_dir, 'evaluation_summary.json')}")
        print(f" - {os.path.join(eval_dir, 'metrics.csv')}")
        print("=" * 80 + "\n")
    except Exception as e:
        logger.exception(f"Single job evaluation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
