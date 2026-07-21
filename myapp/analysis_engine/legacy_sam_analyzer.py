import json
from pathlib import Path

import cv2

from .chart_generator import save_summary_figure
from .mask_filters import filter_masks
from .measurement import build_bins, measure_masks
from .visualization import draw_measurements


class LegacySamAnalyzer:
    """
    Analizador basado en SAM clásico.

    Este módulo adapta el prototipo final de Diego a una estructura reutilizable
    dentro del backend Flask.
    """

    _mask_generator_cache = {}

    @classmethod
    def _get_device(cls):
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"

    @classmethod
    def _get_mask_generator(
        cls,
        checkpoint_path,
        model_type="vit_h",
        points_per_side=44,
        pred_iou_thresh=0.85,
        stability_score_thresh=0.97,
        crop_n_layers=1,
        crop_n_points_downscale_factor=2,
        min_mask_region_area=1000,
    ):
        import torch
        from segment_anything import SamAutomaticMaskGenerator, sam_model_registry

        device = cls._get_device()

        cache_key = (
            str(Path(checkpoint_path).resolve()),
            model_type,
            device,
            points_per_side,
            pred_iou_thresh,
            stability_score_thresh,
            crop_n_layers,
            crop_n_points_downscale_factor,
            min_mask_region_area,
        )

        if cache_key in cls._mask_generator_cache:
            return cls._mask_generator_cache[cache_key], device

        sam = sam_model_registry[model_type](checkpoint=str(checkpoint_path))
        sam.to(device=device)

        mask_generator = SamAutomaticMaskGenerator(
            model=sam,
            points_per_side=points_per_side,
            pred_iou_thresh=pred_iou_thresh,
            stability_score_thresh=stability_score_thresh,
            crop_n_layers=crop_n_layers,
            crop_n_points_downscale_factor=crop_n_points_downscale_factor,
            min_mask_region_area=min_mask_region_area,
        )

        cls._mask_generator_cache[cache_key] = mask_generator

        if device == "cuda":
            torch.cuda.empty_cache()

        return mask_generator, device

    @classmethod
    def analyze(
        cls,
        image_path,
        output_dir,
        checkpoint_path="checkpoints/sam_vit_h_4b8939.pth",
        model_type="vit_h",
        factor=5.95,
        step_number=10,
        pixel_threshold=140,
        parameters=None,
    ):
        """
        Ejecuta SAM clásico sobre una micrografía y genera archivos de salida.

        Salidas:
        - imagen anotada
        - figura resumen
        - JSON de métricas
        """
        import torch

        parameters = parameters or {}

        checkpoint_path = Path(checkpoint_path)
        image_path = Path(image_path)
        output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        if not image_path.exists():
            raise FileNotFoundError(f"No se encontró la imagen: {image_path}")

        if not checkpoint_path.exists():
            raise FileNotFoundError(
                f"No se encontró el checkpoint: {checkpoint_path}"
            )

        image_bgr = cv2.imread(str(image_path))

        if image_bgr is None:
            raise ValueError(f"No se pudo abrir la imagen: {image_path}")

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        points_per_side = int(parameters.get("points_per_side", 44))
        pred_iou_thresh = float(parameters.get("pred_iou_thresh", 0.85))
        stability_score_thresh = float(
            parameters.get("stability_score_thresh", 0.97)
        )
        crop_n_layers = int(parameters.get("crop_n_layers", 1))
        crop_n_points_downscale_factor = int(
            parameters.get("crop_n_points_downscale_factor", 2)
        )
        min_mask_region_area = int(
            parameters.get("min_mask_region_area", 1000)
        )

        mask_generator, device = cls._get_mask_generator(
            checkpoint_path=checkpoint_path,
            model_type=model_type,
            points_per_side=points_per_side,
            pred_iou_thresh=pred_iou_thresh,
            stability_score_thresh=stability_score_thresh,
            crop_n_layers=crop_n_layers,
            crop_n_points_downscale_factor=crop_n_points_downscale_factor,
            min_mask_region_area=min_mask_region_area,
        )

        with torch.inference_mode():
            masks = mask_generator.generate(image_rgb)

        valid_masks = filter_masks(
            masks,
            image_rgb,
            pixel_threshold=pixel_threshold
        )

        measurements = measure_masks(valid_masks, factor=factor)

        annotated_image = draw_measurements(
            image_rgb=image_rgb,
            measurements=measurements
        )

        areas_nm2 = [
            measurement["area_nm2"]
            for measurement in measurements
        ]

        diagonals_nm = [
            measurement["diagonal_nm"]
            for measurement in measurements
            if measurement["diagonal_nm"] is not None
        ]

        area_labels, area_counts = build_bins(
            areas_nm2,
            number_of_bins=step_number
        )

        length_labels, length_counts = build_bins(
            diagonals_nm,
            number_of_bins=step_number
        )

        stem = image_path.stem

        annotated_path = output_dir / f"{stem}_sam_legacy_annotated.png"
        summary_path = output_dir / f"{stem}_sam_legacy_summary.png"
        metrics_path = output_dir / f"{stem}_sam_legacy_metrics.json"

        annotated_bgr = cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR)
        cv2.imwrite(str(annotated_path), annotated_bgr)

        save_summary_figure(
            annotated_image=annotated_image,
            area_labels=area_labels,
            area_counts=area_counts,
            length_labels=length_labels,
            length_counts=length_counts,
            output_path=summary_path
        )

        metrics = {
            "image": str(image_path),
            "model_name": "SAM",
            "model_type": model_type,
            "checkpoint": str(checkpoint_path),
            "device": device,
            "total_masks": len(masks),
            "valid_masks": len(valid_masks),
            "rejected_masks": len(masks) - len(valid_masks),
            "particle_count": len(valid_masks),
            "areas_nm2": areas_nm2,
            "diagonals_nm": diagonals_nm,
            "area_distribution": {
                "labels": area_labels,
                "counts": area_counts,
            },
            "length_distribution": {
                "labels": length_labels,
                "counts": length_counts,
            },
            "annotated_image_path": str(annotated_path),
            "summary_figure_path": str(summary_path),
            "parameters": {
                "points_per_side": points_per_side,
                "pred_iou_thresh": pred_iou_thresh,
                "stability_score_thresh": stability_score_thresh,
                "crop_n_layers": crop_n_layers,
                "crop_n_points_downscale_factor": crop_n_points_downscale_factor,
                "min_mask_region_area": min_mask_region_area,
                "factor": factor,
                "step_number": step_number,
                "pixel_threshold": pixel_threshold,
            },
        }

        metrics_path.write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        return {
            "metrics": metrics,
            "annotated_image_path": annotated_path,
            "summary_figure_path": summary_path,
            "metrics_path": metrics_path,
        }