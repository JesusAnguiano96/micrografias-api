import json
import shutil
from datetime import datetime
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..models import Analysis, AnalysisResult, Micrograph
from .legacy_sam_analyzer import LegacySamAnalyzer


class AnalysisService:
    """
    Servicio encargado de coordinar la ejecución de análisis de micrografías.

    Flujo actual:
    - model_name = "SAM": ejecuta SAM clásico real.
    - model_name = "SAM2": mantiene análisis simulado temporal.
    """

    @staticmethod
    def run_analysis(
        micrograph_id,
        user_id=None,
        model_name="SAM2",
        parameters=None
    ):
        normalized_model_name = (model_name or "SAM2").upper()

        if normalized_model_name == "SAM":
            return AnalysisService.run_legacy_sam_analysis(
                micrograph_id=micrograph_id,
                user_id=user_id,
                parameters=parameters
            )

        return AnalysisService.run_simulated_analysis(
            micrograph_id=micrograph_id,
            user_id=user_id,
            model_name=model_name,
            parameters=parameters
        )

    @staticmethod
    def run_simulated_analysis(
        micrograph_id,
        user_id=None,
        model_name="SAM2",
        parameters=None
    ):
        parameters = parameters or {}

        micrograph = db.session.get(Micrograph, micrograph_id)

        if micrograph is None:
            return None, None, "Micrograph not found"

        analysis = Analysis(
            user_id=user_id,
            micrograph_id=micrograph.id,
            model_name=model_name,
            status="processing",
            parameters_json=json.dumps(parameters)
        )

        db.session.add(analysis)
        db.session.commit()

        try:
            original_path = Path(micrograph.file_path)

            if not original_path.exists():
                raise FileNotFoundError(
                    f"Original micrograph file not found: {original_path}"
                )

            segmented_folder = Path(current_app.config["UPLOAD_SEGMENTED_FOLDER"])
            segmented_folder.mkdir(parents=True, exist_ok=True)

            simulated_segmented_filename = (
                f"{original_path.stem}_analysis_{analysis.id}_simulated_segmented"
                f"{original_path.suffix}"
            )

            simulated_segmented_path = segmented_folder / simulated_segmented_filename

            shutil.copyfile(original_path, simulated_segmented_path)

            result = AnalysisResult(
                analysis_id=analysis.id,
                particle_count=0,
                total_masks=0,
                valid_masks=0,
                rejected_masks=0,
                segmented_image_path=str(simulated_segmented_path)
            )

            analysis.status = "completed"
            analysis.completed_at = datetime.utcnow()

            db.session.add(result)
            db.session.commit()

            return analysis, result, None

        except Exception as error:
            analysis.status = "failed"
            analysis.error_message = str(error)
            analysis.completed_at = datetime.utcnow()
            db.session.commit()

            return analysis, None, str(error)

    @staticmethod
    def run_legacy_sam_analysis(
        micrograph_id,
        user_id=None,
        parameters=None
    ):
        parameters = parameters or {}

        micrograph = db.session.get(Micrograph, micrograph_id)

        if micrograph is None:
            return None, None, "Micrograph not found"

        analysis = Analysis(
            user_id=user_id,
            micrograph_id=micrograph.id,
            model_name="SAM",
            status="processing",
            parameters_json=json.dumps(parameters)
        )

        db.session.add(analysis)
        db.session.commit()

        try:
            original_path = Path(micrograph.file_path)

            if not original_path.exists():
                raise FileNotFoundError(
                    f"Original micrograph file not found: {original_path}"
                )

            project_root = Path(current_app.root_path).parent
            checkpoint_path = project_root / "checkpoints" / "sam_vit_h_4b8939.pth"

            segmented_folder = Path(current_app.config["UPLOAD_SEGMENTED_FOLDER"])
            segmented_folder.mkdir(parents=True, exist_ok=True)

            legacy_sam_result = LegacySamAnalyzer.analyze(
                image_path=original_path,
                output_dir=segmented_folder,
                checkpoint_path=checkpoint_path,
                model_type="vit_h",
                factor=float(parameters.get("factor", 5.95)),
                step_number=int(parameters.get("step_number", 10)),
                pixel_threshold=int(parameters.get("pixel_threshold", 140)),
                parameters={
                    "points_per_side": parameters.get("points_per_side", 44),
                    "pred_iou_thresh": parameters.get("pred_iou_thresh", 0.85),
                    "stability_score_thresh": parameters.get(
                        "stability_score_thresh",
                        0.97
                    ),
                    "crop_n_layers": parameters.get("crop_n_layers", 1),
                    "crop_n_points_downscale_factor": parameters.get(
                        "crop_n_points_downscale_factor",
                        2
                    ),
                    "min_mask_region_area": parameters.get(
                        "min_mask_region_area",
                        1000
                    ),
                }
            )

            metrics = legacy_sam_result["metrics"]

            result = AnalysisResult(
                analysis_id=analysis.id,
                particle_count=metrics["particle_count"],
                total_masks=metrics["total_masks"],
                valid_masks=metrics["valid_masks"],
                rejected_masks=metrics["rejected_masks"],
                segmented_image_path=str(legacy_sam_result["annotated_image_path"])
            )

            analysis.status = "completed"
            analysis.completed_at = datetime.utcnow()

            db.session.add(result)
            db.session.commit()

            return analysis, result, None

        except Exception as error:
            analysis.status = "failed"
            analysis.error_message = str(error)
            analysis.completed_at = datetime.utcnow()
            db.session.commit()

            return analysis, None, str(error)