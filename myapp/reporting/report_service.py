import json
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..extensions import db
from ..models import Analysis, Report


class ReportService:
    """
    Servicio encargado de generar reportes de análisis en formato PDF.
    """

    @staticmethod
    def _load_sam_metrics(segmented_image_path):
        """
        Intenta cargar el archivo JSON de métricas generado por SAM clásico
        o por SAM 2.

        SAM clásico:
        imagen_sam_legacy_annotated.png
        imagen_sam_legacy_metrics.json

        SAM 2:
        imagen_sam2_60_annotated.png
        imagen_sam2_60_metrics.json
        """
        if not segmented_image_path:
            return None

        segmented_path = Path(segmented_image_path)

        if not segmented_path.exists():
            return None

        metrics_path = None

        if segmented_path.name.endswith("_sam_legacy_annotated.png"):
            metrics_path = Path(
                str(segmented_path).replace(
                    "_sam_legacy_annotated.png",
                    "_sam_legacy_metrics.json"
                )
            )

        elif "_sam2_" in segmented_path.name and segmented_path.name.endswith("_annotated.png"):
            metrics_path = Path(
                str(segmented_path).replace(
                    "_annotated.png",
                    "_metrics.json"
                )
            )

        if metrics_path is None or not metrics_path.exists():
            return None

        try:
            return json.loads(metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _get_summary_figure_path(segmented_image_path):
        """
        Intenta obtener la ruta de la figura resumen generada por SAM clásico
        o por SAM 2.
        """
        if not segmented_image_path:
            return None

        segmented_path = Path(segmented_image_path)

        summary_path = None

        if segmented_path.name.endswith("_sam_legacy_annotated.png"):
            summary_path = Path(
                str(segmented_path).replace(
                    "_sam_legacy_annotated.png",
                    "_sam_legacy_summary.png"
                )
            )

        elif "_sam2_" in segmented_path.name and segmented_path.name.endswith("_annotated.png"):
            summary_path = Path(
                str(segmented_path).replace(
                    "_annotated.png",
                    "_summary.png"
                )
            )

        if summary_path and summary_path.exists():
            return str(summary_path)

        return None

    @staticmethod
    def _safe_text(value):
        """
        Convierte valores a texto seguro para ReportLab Paragraph.
        """
        if value is None:
            return "N/A"

        return escape(str(value))

    @staticmethod
    def _make_info_table(rows, styles):
        """
        Crea una tabla de dos columnas para datos generales.
        """
        table_data = []

        for label, value in rows:
            table_data.append(
                [
                    Paragraph(f"<b>{ReportService._safe_text(label)}</b>", styles["Body"]),
                    Paragraph(ReportService._safe_text(value), styles["Body"]),
                ]
            )

        table = Table(table_data, colWidths=[1.9 * inch, 4.7 * inch])

        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )

        return table

    @staticmethod
    def _make_distribution_table(title, distribution, styles):
        """
        Crea una tabla para distribuciones de área o longitud.

        Soporta estructuras tipo:
        {
            "labels": [...],
            "counts": [...]
        }
        """
        elements = [
            Paragraph(title, styles["SectionTitle"]),
            Spacer(1, 8),
        ]

        if not distribution:
            elements.append(
                Paragraph("No distribution data available.", styles["Body"])
            )
            return elements

        labels = []
        counts = []

        if isinstance(distribution, dict):
            labels = distribution.get("labels", [])
            counts = distribution.get("counts", [])

        if not labels or not counts:
            elements.append(
                Paragraph("No distribution data available.", styles["Body"])
            )
            return elements

        table_data = [
            [
                Paragraph("<b>Range</b>", styles["Body"]),
                Paragraph("<b>Count</b>", styles["Body"]),
            ]
        ]

        for label, count in zip(labels, counts):
            table_data.append(
                [
                    Paragraph(ReportService._safe_text(label), styles["Body"]),
                    Paragraph(ReportService._safe_text(count), styles["Body"]),
                ]
            )

        table = Table(table_data, colWidths=[4.8 * inch, 1.8 * inch])

        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#102A56")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )

        elements.append(table)

        return elements

    @staticmethod
    def _make_image_element(image_path, max_width=6.6 * inch, max_height=5.8 * inch):
        """
        Crea un elemento de imagen ajustado al tamaño máximo disponible.
        """
        if not image_path:
            return None

        image_path = Path(image_path)

        if not image_path.exists():
            return None

        try:
            reader = ImageReader(str(image_path))
            width, height = reader.getSize()

            scale = min(max_width / width, max_height / height)

            image = Image(str(image_path))
            image.drawWidth = width * scale
            image.drawHeight = height * scale

            return image
        except Exception:
            return None

    @staticmethod
    def _add_footer(canvas, document):
        """
        Agrega pie de página simple al PDF.
        """
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))

        footer_text = f"Micrograph Analysis System - Page {document.page}"

        canvas.drawString(
            document.leftMargin,
            0.45 * inch,
            footer_text
        )

        canvas.restoreState()

    @staticmethod
    def generate_text_report(analysis_id):
        """
        Genera un reporte PDF para el análisis indicado.

        Se mantiene el nombre del método para no modificar las rutas existentes,
        pero la salida generada ahora es PDF.
        """
        analysis = db.session.get(Analysis, analysis_id)

        if analysis is None:
            return None, "Analysis not found"

        if analysis.result is None:
            return None, "Analysis result not found"

        micrograph = analysis.micrograph
        result = analysis.result

        reports_folder = Path(current_app.config["REPORTS_FOLDER"])
        reports_folder.mkdir(parents=True, exist_ok=True)

        filename = f"analysis_{analysis.id}_report.pdf"
        file_path = reports_folder / filename

        sam_metrics = ReportService._load_sam_metrics(
            result.segmented_image_path
        )

        summary_figure_path = ReportService._get_summary_figure_path(
            result.segmented_image_path
        )

        styles = getSampleStyleSheet()

        styles.add(
            ParagraphStyle(
                name="MainTitle",
                parent=styles["Title"],
                fontName="Helvetica-Bold",
                fontSize=22,
                leading=27,
                textColor=colors.HexColor("#102A56"),
                spaceAfter=14,
            )
        )

        styles.add(
            ParagraphStyle(
                name="SectionTitle",
                parent=styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=14,
                leading=18,
                textColor=colors.HexColor("#102A56"),
                spaceBefore=14,
                spaceAfter=8,
            )
        )

        styles.add(
            ParagraphStyle(
                name="Body",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=9,
                leading=12,
                textColor=colors.HexColor("#111827"),
            )
        )

        styles.add(
            ParagraphStyle(
                name="Note",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=9,
                leading=13,
                textColor=colors.HexColor("#374151"),
                backColor=colors.HexColor("#F8FAFC"),
                borderColor=colors.HexColor("#CBD5E1"),
                borderWidth=0.5,
                borderPadding=8,
                spaceBefore=8,
                spaceAfter=8,
            )
        )

        document = SimpleDocTemplate(
            str(file_path),
            pagesize=letter,
            rightMargin=0.7 * inch,
            leftMargin=0.7 * inch,
            topMargin=0.7 * inch,
            bottomMargin=0.7 * inch,
            title=f"Analysis {analysis.id} Report",
            author="Micrograph Analysis System",
        )

        elements = []

        elements.append(
            Paragraph("Micrograph Analysis System", styles["MainTitle"])
        )
        elements.append(
            Paragraph("Analysis Report", styles["SectionTitle"])
        )
        elements.append(
            Paragraph(
                f"Generated at: {datetime.utcnow().isoformat()} UTC",
                styles["Body"],
            )
        )

        if analysis.model_name.upper() == "SAM":
            note = (
                "This report was generated using the legacy SAM model adapted "
                "from the previous prototype. The analysis includes automatic "
                "mask generation, filtering, bounding boxes, longest-diagonal "
                "measurement and distribution charts."
            )
        else:
            note = (
                "This report was generated from the current prototype. At this "
                "stage, the SAM 2 analysis flow is simulated and will later be "
                "replaced by the SAM 2 segmentation pipeline."
            )

        elements.append(Spacer(1, 12))
        elements.append(Paragraph(note, styles["Note"]))

        elements.append(Paragraph("Analysis information", styles["SectionTitle"]))
        elements.append(
            ReportService._make_info_table(
                [
                    ("Analysis ID", analysis.id),
                    ("Status", analysis.status),
                    ("Model", analysis.model_name),
                    ("Started at", analysis.started_at),
                    ("Completed at", analysis.completed_at),
                    ("Error message", analysis.error_message),
                ],
                styles,
            )
        )

        elements.append(Paragraph("Micrograph information", styles["SectionTitle"]))
        elements.append(
            ReportService._make_info_table(
                [
                    ("Micrograph ID", micrograph.id if micrograph else "N/A"),
                    (
                        "Original filename",
                        micrograph.original_filename if micrograph else "N/A",
                    ),
                    (
                        "Stored filename",
                        micrograph.stored_filename if micrograph else "N/A",
                    ),
                    (
                        "Micrograph type",
                        micrograph.micrograph_type if micrograph else "N/A",
                    ),
                    (
                        "Scale",
                        (
                            f"{micrograph.scale_value} {micrograph.scale_unit}"
                            if micrograph and micrograph.scale_value
                            else "Not specified"
                        ),
                    ),
                    (
                        "Description",
                        micrograph.description if micrograph else "N/A",
                    ),
                ],
                styles,
            )
        )

        elements.append(Paragraph("Analysis result", styles["SectionTitle"]))
        elements.append(
            ReportService._make_info_table(
                [
                    ("Particle count", result.particle_count),
                    ("Total masks", result.total_masks),
                    ("Valid masks", result.valid_masks),
                    ("Rejected masks", result.rejected_masks),
                    ("Annotated image path", result.segmented_image_path),
                    (
                        "Summary figure path",
                        summary_figure_path if summary_figure_path else "N/A",
                    ),
                ],
                styles,
            )
        )

        if sam_metrics:
            elements.append(Spacer(1, 8))

            elements.extend(
                ReportService._make_distribution_table(
                    "Area distribution",
                    sam_metrics.get("area_distribution"),
                    styles,
                )
            )

            elements.append(Spacer(1, 12))

            elements.extend(
                ReportService._make_distribution_table(
                    "Length distribution",
                    sam_metrics.get("length_distribution"),
                    styles,
                )
            )

        annotated_image = ReportService._make_image_element(
            result.segmented_image_path
        )

        if annotated_image:
            elements.append(Paragraph("Annotated image", styles["SectionTitle"]))
            elements.append(annotated_image)

        summary_image = ReportService._make_image_element(summary_figure_path)

        if summary_image:
            elements.append(Paragraph("Summary figure", styles["SectionTitle"]))
            elements.append(summary_image)

        document.build(
            elements,
            onFirstPage=ReportService._add_footer,
            onLaterPages=ReportService._add_footer,
        )

        existing_report = Report.query.filter_by(analysis_id=analysis.id).first()

        if existing_report:
            old_file_path = Path(existing_report.file_path) if existing_report.file_path else None

            existing_report.filename = filename
            existing_report.file_path = str(file_path)
            existing_report.generated_at = datetime.utcnow()
            report = existing_report

            if (
                old_file_path
                and old_file_path.exists()
                and old_file_path != file_path
                and old_file_path.suffix.lower() == ".txt"
            ):
                old_file_path.unlink(missing_ok=True)
        else:
            report = Report(
                analysis_id=analysis.id,
                filename=filename,
                file_path=str(file_path)
            )
            db.session.add(report)

        db.session.commit()

        return report, None