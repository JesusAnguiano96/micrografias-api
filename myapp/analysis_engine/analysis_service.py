import json
import shutil
from datetime import datetime
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..models import Analysis, AnalysisResult, Micrograph


class AnalysisService:
    """
    Servicio encargado de coordinar la ejecución de análisis de micrografías.

    En esta etapa todavía no ejecuta SAM 2.
    Por ahora realiza un análisis simulado para validar el flujo completo:
    micrografía -> análisis -> resultado -> imagen segmentada simulada.
    """

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

            # Simulación temporal:
            # copiamos la imagen original como si fuera una imagen segmentada.
            # Más adelante esta parte será reemplazada por SAM 2.
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