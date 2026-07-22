import json
import shutil
from datetime import datetime
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..models import Analysis, AnalysisResult, Micrograph
from .legacy_sam_analyzer import LegacySamAnalyzer
from .sam2_analyzer import SAM2Analyzer


class AnalysisService:
    """
    Servicio encargado de coordinar la ejecución de análisis de micrografías.

    Flujo actual:
    - model_name = "SAM": ejecuta SAM clásico real.
    - model_name = "SAM2": ejecuta SAM 2 real con perfiles por solapamiento.

    En SAM2 se separan dos conceptos:
    - Perfil científico: hiperparámetros PSO por nivel de solapamiento.
    - Modo de ejecución: ajustes técnicos de memoria/calidad.

    Nota:
    max_image_size puede afectar el nivel de detalle de segmentación porque
    reduce temporalmente la imagen antes de inferir con SAM 2.
    points_per_batch controla consumo de memoria y velocidad, pero no debería
    modificar de forma importante las máscaras obtenidas.
    """

    SAM2_EXECUTION_MODES = {
        "safe_local": {
            "label": "Safe local",
            "max_image_size": 500,
            "points_per_batch": 2,
        },
        "balanced": {
            "label": "Balanced",
            "max_image_size": 700,
            "points_per_batch": 4,
        },
        "quality": {
            "label": "Quality",
            "max_image_size": 850,
            "points_per_batch": 4,
        },
    }

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

        if normalized_model_name == "SAM2":
            return AnalysisService.run_sam2_analysis(
                micrograph_id=micrograph_id,
                user_id=user_id,
                parameters=parameters
            )

        return None, None, f"Unsupported model_name: {model_name}"

    @staticmethod
    def run_simulated_analysis(
        micrograph_id,
        user_id=None,
        model_name="SAM2",
        parameters=None
    ):
        """
        Flujo simulado conservado como referencia/fallback.
        Ya no se usa para SAM2 en el flujo principal.
        """
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

    @staticmethod
    def get_sam2_execution_settings(parameters):
        """
        Resuelve los parámetros efectivos de ejecución.

        execution_mode controla memoria/calidad.
        No modifica los pesos, checkpoint ni arquitectura de SAM 2.
        """
        parameters = parameters or {}

        execution_mode = str(parameters.get("execution_mode", "safe_local"))

        if execution_mode not in AnalysisService.SAM2_EXECUTION_MODES:
            execution_mode = "safe_local"

        mode_settings = AnalysisService.SAM2_EXECUTION_MODES[execution_mode]

        max_image_size = int(
            parameters.get(
                "max_image_size",
                mode_settings["max_image_size"]
            )
        )

        points_per_batch = int(
            parameters.get(
                "points_per_batch",
                mode_settings["points_per_batch"]
            )
        )

        return {
            "execution_mode": execution_mode,
            "execution_mode_label": mode_settings["label"],
            "max_image_size": max_image_size,
            "points_per_batch": points_per_batch,
        }

    @staticmethod
    def build_effective_sam2_parameters(parameters):
        """
        Construye los parámetros reales que se mandarán a SAM2Analyzer.

        Esto permite que, aunque el frontend solo mande:
        execution_mode = safe_local

        el backend agregue:
        max_image_size = 500
        points_per_batch = 2
        """
        parameters = dict(parameters or {})

        selected_sam2_profile = str(parameters.get("sam2_profile", "60"))
        selected_overlap_level = str(
            parameters.get("overlap_level", selected_sam2_profile)
        )

        execution_settings = AnalysisService.get_sam2_execution_settings(
            parameters
        )

        effective_parameters = dict(parameters)

        effective_parameters["sam2_profile"] = selected_sam2_profile
        effective_parameters["overlap_level"] = selected_overlap_level
        effective_parameters["execution_mode"] = execution_settings[
            "execution_mode"
        ]
        effective_parameters["execution_mode_label"] = execution_settings[
            "execution_mode_label"
        ]
        effective_parameters["max_image_size"] = execution_settings[
            "max_image_size"
        ]
        effective_parameters["points_per_batch"] = execution_settings[
            "points_per_batch"
        ]

        return effective_parameters

    @staticmethod
    def run_sam2_analysis(
        micrograph_id,
        user_id=None,
        parameters=None
    ):
        effective_parameters = AnalysisService.build_effective_sam2_parameters(
            parameters
        )

        micrograph = db.session.get(Micrograph, micrograph_id)

        if micrograph is None:
            return None, None, "Micrograph not found"

        selected_sam2_profile = effective_parameters["sam2_profile"]
        selected_overlap_level = effective_parameters["overlap_level"]

        analysis = Analysis(
            user_id=user_id,
            micrograph_id=micrograph.id,
            model_name="SAM2",
            status="processing",
            parameters_json=json.dumps(
                effective_parameters,
                ensure_ascii=False
            )
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
            checkpoint_path = project_root / "checkpoints" / "sam2.1_hiera_large.pt"

            segmented_folder = Path(current_app.config["UPLOAD_SEGMENTED_FOLDER"])
            segmented_folder.mkdir(parents=True, exist_ok=True)

            sam2_runtime_parameters = {
                "sam2_profile": selected_sam2_profile,
                "overlap_level": selected_overlap_level,

                # Estos parámetros controlan la ejecución y memoria.
                "execution_mode": effective_parameters["execution_mode"],
                "execution_mode_label": effective_parameters[
                    "execution_mode_label"
                ],
                "max_image_size": effective_parameters["max_image_size"],
                "points_per_batch": effective_parameters["points_per_batch"],
            }

            optional_sam2_parameters = [
                "points_per_side",
                "pred_iou_thresh",
                "stability_score_thresh",
                "stability_score_offset",
                "crop_n_layers",
                "crop_n_points_downscale_factor",
                "min_mask_region_area",
                "box_nms_thresh",
                "use_m2m",
                "max_area_px",
                "max_area_factor",
                "min_circularity",
                "max_aspect_ratio",
                "min_solidity",
                "iou_threshold",
                "mode",
            ]

            for parameter_name in optional_sam2_parameters:
                if effective_parameters.get(parameter_name) is not None:
                    sam2_runtime_parameters[parameter_name] = (
                        effective_parameters.get(parameter_name)
                    )

            sam2_result = SAM2Analyzer.analyze(
                image_path=original_path,
                output_dir=segmented_folder,
                checkpoint_path=checkpoint_path,
                profile_name=selected_sam2_profile,
                overlap_level=selected_overlap_level,
                factor=float(effective_parameters.get("factor", 5.95)),
                step_number=int(effective_parameters.get("step_number", 10)),
                pixel_threshold=int(
                    effective_parameters.get("pixel_threshold", 140)
                ),
                filter_with_legacy_rules=bool(
                    effective_parameters.get("filter_with_legacy_rules", True)
                ),
                parameters=sam2_runtime_parameters,
            )

            metrics = sam2_result["metrics"]

            result = AnalysisResult(
                analysis_id=analysis.id,
                particle_count=metrics["particle_count"],
                total_masks=metrics["total_masks"],
                valid_masks=metrics["valid_masks"],
                rejected_masks=metrics["rejected_masks"],
                segmented_image_path=str(sam2_result["annotated_image_path"])
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