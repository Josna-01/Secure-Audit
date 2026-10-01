"""CLI entry point for Photogrammetry Evaluation and Research Reporting Module.

Usage examples:
    # 1. Evaluate single job
    python evaluate_job.py --job c199a911-ac53-422e-b3a9-87444a5b766b

    # 2. Evaluate single job with physical dimension accuracy
    python evaluate_job.py --job c199a911-ac53-422e-b3a9-87444a5b766b --gt-length 29.0 --gt-width 10.5 --gt-height 12.0 --unit cm

    # 3. Compare multiple specific jobs
    python evaluate_job.py --compare c199a911-ac53-422e-b3a9-87444a5b766b 54f0cecd-0b11-4bb8-91ac-1046ddf89b3a --output-dir comparison_results

    # 4. Evaluate and compare all available jobs
    python evaluate_job.py --all
"""
import os
import sys
import argparse
import logging
from services.evaluator import PhotogrammetryEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("evaluate_job")


def main():
    parser = argparse.ArgumentParser(description="Secure Audit — Photogrammetry Research Evaluation Module")
    parser.add_argument("--job", type=str, help="Job ID or job directory path to evaluate")
    parser.add_argument("--jobs-root", type=str, default=None, help="Root directory holding all job workspaces")
    parser.add_argument("--gt-length", type=float, default=None, help="Ground truth length measurement (major axis)")
    parser.add_argument("--gt-width", type=float, default=None, help="Ground truth width measurement (intermediate axis)")
    parser.add_argument("--gt-height", type=float, default=None, help="Ground truth height measurement (minor axis)")
    parser.add_argument("--unit", type=str, default="cm", help="Measurement unit (e.g. cm, m, mm)")
    parser.add_argument("--scale", type=float, default=None, help="Pre-calibrated scale factor (model units to real-world units)")
    parser.add_argument("--compare", nargs="+", help="List of job IDs to compare experimentally")
    parser.add_argument("--all", action="store_true", help="Evaluate and compare all jobs present in jobs root")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for comparison reports")

    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    jobs_root = args.jobs_root or os.path.join(base_dir, "jobs")
    evaluator = PhotogrammetryEvaluator(jobs_root=jobs_root)

    # 1. Compare multiple jobs
    if args.compare:
        out_dir = args.output_dir or os.path.join(base_dir, "evaluation_comparisons")
        logger.info(f"Comparing {len(args.compare)} jobs: {args.compare}")
        res = evaluator.compare_multiple_jobs(args.compare, output_dir=out_dir)
        print(f"\n[SUCCESS] Comparison generated successfully!")
        print(f"- CSV Report: {res['comparison_csv']}")
        print(f"- Markdown:   {res['comparison_md']}")
        print(f"- Summary:    {res['comparison_summary']}")
        return

    # 2. Evaluate all available jobs
    if args.all:
        job_dirs = [d for d in os.listdir(jobs_root) if os.path.isdir(os.path.join(jobs_root, d))]
        if not job_dirs:
            print(f"[ERROR] No job directories found in {jobs_root}")
            sys.exit(1)
        out_dir = args.output_dir or os.path.join(base_dir, "all_jobs_evaluation_comparison")
        logger.info(f"Evaluating and comparing all {len(job_dirs)} jobs in {jobs_root}...")
        res = evaluator.compare_multiple_jobs(job_dirs, output_dir=out_dir)
        print(f"\n[SUCCESS] All jobs evaluated and compared!")
        print(f"- Comparison CSV: {res['comparison_csv']}")
        print(f"- Comparison MD:  {res['comparison_md']}")
        print(f"- Comparison JSON:{res['comparison_summary']}")
        return

    # 3. Single job evaluation
    if not args.job:
        print("[ERROR] Please provide --job <job_id>, --compare <job1> <job2>, or --all")
        parser.print_help()
        sys.exit(1)

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
        print("\n" + "="*70)
        print(f" PHOTOGRAMMETRY RESEARCH EVALUATION SUMMARY — JOB: {metrics['job_id']}")
        print("="*70)
        print(f"Video:             {metrics['video'].get('resolution')} @ {metrics['video'].get('fps')} FPS ({metrics['video'].get('duration_seconds')}s)")
        print(f"Keyframes:         {metrics['frame_processing'].get('selected_frames_count')} selected / {metrics['frame_processing'].get('extracted_frames_count')} extracted ({metrics['frame_processing'].get('selection_ratio_percent')}%)")
        print(f"SfM Registration:  {metrics['colmap_sfm'].get('registered_images')} registered ({metrics['colmap_sfm'].get('registration_percentage')}%)")
        print(f"Sparse Points:     {metrics['colmap_sfm'].get('sparse_points_count'):,} (Reprojection Error: {metrics['colmap_sfm'].get('mean_reprojection_error_px')} px)")
        print(f"Dense Points:      {metrics['geometry_and_mesh'].get('fused_point_count')} fused -> {metrics['geometry_and_mesh'].get('cleaned_point_count')} cleaned ({metrics['geometry_and_mesh'].get('points_removed_percent')}% outliers removed)")
        print(f"Mesh Geometry:     {metrics['geometry_and_mesh'].get('mesh_vertex_count')} vertices, {metrics['geometry_and_mesh'].get('mesh_triangle_count')} triangles")

        if metrics.get("physical_dimension_accuracy") and metrics["physical_dimension_accuracy"].get("status") == "evaluated":
            phys = metrics["physical_dimension_accuracy"]
            print(f"Physical Accuracy: MAE = {phys['mean_absolute_error']} {phys['unit']} | MAPE = {phys['mean_absolute_percentage_error']}% (Scale: {phys['scale_factor']})")

        print("-"*70)
        print(f"Research Artifacts Exported to: {eval_dir}")
        print(f" - {os.path.join(eval_dir, 'metrics.json')}")
        print(f" - {os.path.join(eval_dir, 'metrics.csv')}")
        print(f" - {os.path.join(eval_dir, 'evaluation_report.md')}")
        print(f" - {os.path.join(eval_dir, 'evaluation_summary.json')}")
        print(f" - {os.path.join(eval_dir, 'point_count_comparison.png')}")
        if os.path.exists(os.path.join(eval_dir, "dimension_accuracy.png")):
            print(f" - {os.path.join(eval_dir, 'dimension_accuracy.png')}")
        print("="*70 + "\n")
    except Exception as e:
        logger.exception(f"Evaluation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
