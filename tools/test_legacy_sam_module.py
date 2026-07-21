import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from myapp.analysis_engine.legacy_sam_analyzer import LegacySamAnalyzer


def main():
    parser = argparse.ArgumentParser(
        description="Prueba modular de SAM clásico."
    )

    parser.add_argument(
        "--image",
        required=True,
        help="Ruta de la micrografía a analizar."
    )

    parser.add_argument(
        "--checkpoint",
        default="checkpoints/sam_vit_h_4b8939.pth",
        help="Ruta del checkpoint de SAM."
    )

    parser.add_argument(
        "--output-dir",
        default="outputs/sam_legacy",
        help="Carpeta donde se guardarán las salidas."
    )

    parser.add_argument(
        "--factor",
        type=float,
        default=5.95,
        help="Factor de conversión usado por el prototipo."
    )

    args = parser.parse_args()

    result = LegacySamAnalyzer.analyze(
        image_path=Path(args.image),
        checkpoint_path=Path(args.checkpoint),
        output_dir=Path(args.output_dir),
        model_type="vit_h",
        factor=args.factor,
        parameters={
            "points_per_side": 44,
            "pred_iou_thresh": 0.85,
            "stability_score_thresh": 0.97,
            "crop_n_layers": 1,
            "crop_n_points_downscale_factor": 2,
            "min_mask_region_area": 1000,
        },
    )

    metrics = result["metrics"]

    print("Análisis SAM clásico completado.")
    print(f"Total masks: {metrics['total_masks']}")
    print(f"Valid masks: {metrics['valid_masks']}")
    print(f"Rejected masks: {metrics['rejected_masks']}")
    print(f"Particle count: {metrics['particle_count']}")
    print(f"Annotated image: {result['annotated_image_path']}")
    print(f"Summary figure: {result['summary_figure_path']}")
    print(f"Metrics JSON: {result['metrics_path']}")


if __name__ == "__main__":
    main()