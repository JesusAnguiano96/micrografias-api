from datetime import datetime
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..models import Analysis, Report


class ReportService:
    """
    Servicio encargado de generar reportes de análisis.

    En esta etapa se genera un reporte en formato TXT para validar el flujo
    de generación, almacenamiento y descarga de reportes.
    """

    @staticmethod
    def generate_text_report(analysis_id):
        analysis = db.session.get(Analysis, analysis_id)

        if analysis is None:
            return None, "Analysis not found"

        if analysis.result is None:
            return None, "Analysis result not found"

        micrograph = analysis.micrograph
        result = analysis.result

        reports_folder = Path(current_app.config["REPORTS_FOLDER"])
        reports_folder.mkdir(parents=True, exist_ok=True)

        filename = f"analysis_{analysis.id}_report.txt"
        file_path = reports_folder / filename

        report_content = f"""
Micrograph Analysis System
Analysis Report

Generated at: {datetime.utcnow().isoformat()}

Analysis information
--------------------
Analysis ID: {analysis.id}
Status: {analysis.status}
Model: {analysis.model_name}
Started at: {analysis.started_at}
Completed at: {analysis.completed_at}

Micrograph information
----------------------
Micrograph ID: {micrograph.id if micrograph else 'N/A'}
Original filename: {micrograph.original_filename if micrograph else 'N/A'}
Stored filename: {micrograph.stored_filename if micrograph else 'N/A'}
Micrograph type: {micrograph.micrograph_type if micrograph else 'N/A'}
Scale: {micrograph.scale_value if micrograph else 'N/A'} {micrograph.scale_unit if micrograph else ''}
Description: {micrograph.description if micrograph else 'N/A'}

Analysis result
---------------
Particle count: {result.particle_count}
Total masks: {result.total_masks}
Valid masks: {result.valid_masks}
Rejected masks: {result.rejected_masks}
Segmented image path: {result.segmented_image_path}

Note
----
This report was generated from the current prototype. At this stage, the
analysis result may correspond to a simulated analysis flow. The simulated
analysis will later be replaced by the SAM 2 segmentation and particle counting
pipeline.
""".strip()

        file_path.write_text(report_content, encoding="utf-8")

        existing_report = Report.query.filter_by(analysis_id=analysis.id).first()

        if existing_report:
            existing_report.filename = filename
            existing_report.file_path = str(file_path)
            existing_report.generated_at = datetime.utcnow()
            report = existing_report
        else:
            report = Report(
                analysis_id=analysis.id,
                filename=filename,
                file_path=str(file_path)
            )
            db.session.add(report)

        db.session.commit()

        return report, None