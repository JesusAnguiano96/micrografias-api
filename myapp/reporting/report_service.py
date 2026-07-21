import json
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
    def _load_sam_metrics(segmented_image_path):
        """
        Intenta cargar el archivo JSON de métricas generado por SAM clásico.

        A partir de:
        imagen_sam_legacy_annotated.png

        Busca:
        imagen_sam_legacy_metrics.json
        """
        if not segmented_image_path:
            return None

        segmented_path = Path(segmented_image_path)

        if not segmented_path.exists():
            return None

        metrics_path = Path(
            str(segmented_path).replace(
                "_sam_legacy_annotated.png",
                "_sam_legacy_metrics.json"
            )
        )

        if not metrics_path.exists():
            return None

        try:
            return json.loads(metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _get_summary_figure_path(segmented_image_path):
        """
        Intenta obtener la ruta de la figura resumen generada por SAM clásico.
        """
        if not segmented_image_path:
            return None

        summary_path = Path(
            str(segmented_image_path).replace(
                "_sam_legacy_annotated.png",
                "_sam_legacy_summary.png"
            )
        )

        if summary_path.exists():
            return str(summary_path)

        return None

    @staticmethod
    def _format_distribution(title, distribution):
        """
        Convierte una distribución en texto para el reporte.
        """
        if not distribution:
            return f"{title}\nNo distribution data available.\n"

        labels = distribution.get("labels", [])
        counts = distribution.get("counts", [])

        if not labels or not counts:
            return f"{title}\nNo distribution data available.\n"

        lines = [title]

        for label, count in zip(labels, counts):
            lines.append(f"- {label}: {count}")

        return "\n".join(lines) + "\n"

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

        sam_metrics = ReportService._load_sam_metrics(
            result.segmented_image_path
        )

        summary_figure_path = ReportService._get_summary_figure_path(
            result.segmented_image_path
        )

        area_distribution_text = ""
        length_distribution_text = ""

        if sam_metrics:
            area_distribution_text = ReportService._format_distribution(
                "Area distribution",
                sam_metrics.get("area_distribution")
            )

            length_distribution_text = ReportService._format_distribution(
                "Length distribution",
                sam_metrics.get("length_distribution")
            )

        if analysis.model_name.upper() == "SAM":
            note = (
                "This report was generated using the legacy SAM model "
                "adapted from the previous prototype. The analysis includes "
                "automatic mask generation, filtering, bounding boxes, "
                "longest-diagonal measurement and distribution charts."
            )
        else:
            note = (
                "This report was generated from the current prototype. "
                "At this stage, the SAM 2 analysis flow is simulated and "
                "will later be replaced by the SAM 2 segmentation pipeline."
            )

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

Generated files
---------------
Annotated image path: {result.segmented_image_path}
Summary figure path: {summary_figure_path if summary_figure_path else 'N/A'}

{area_distribution_text}
{length_distribution_text}
Note
----
{note}
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