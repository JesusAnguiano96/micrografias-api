import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from .extensions import db
from .models import User, Micrograph, Analysis
from .analysis_engine.analysis_service import AnalysisService
from .reporting.report_service import ReportService


main = Blueprint("main", __name__)


ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "tif", "tiff", "bmp"}


@main.route("/", methods=["GET"])
def index():
    return jsonify({
        "message": "Micrograph Analysis System API",
        "status": "running"
    }), 200


@main.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "service": "Micrograph Analysis System API",
        "status": "ok",
        "version": "0.1.0"
    }), 200


def _get_json_data():
    data = request.get_json(silent=True)

    if data is None:
        return None, (jsonify({
            "message": "Invalid or missing JSON body"
        }), 400)

    return data, None


def _allowed_image(filename):
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_IMAGE_EXTENSIONS


def _verify_password(stored_password, provided_password):
    """
    Verifica una contraseña.

    Primero intenta validar la contraseña como hash.
    Si falla, compara contra texto plano para soportar usuarios legados
    del proyecto original.
    """
    try:
        if check_password_hash(stored_password, provided_password):
            return True
    except ValueError:
        pass

    return stored_password == provided_password


def _register_user(data):
    email = data.get("email")
    password = data.get("password")
    occupation = data.get("occupation", "student")

    if not email or not password:
        return jsonify({
            "message": "Email and password are required"
        }), 400

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        return jsonify({
            "message": "Email already in use"
        }), 400

    hashed_password = generate_password_hash(password)

    user = User(
        email=email,
        password=hashed_password,
        occupation=occupation
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "User registered successfully",
        "user": user.to_dict()
    }), 201


def _login_user(data):
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({
            "message": "Email and password are required"
        }), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({
            "message": "User does not exist"
        }), 404

    if not _verify_password(user.password, password):
        return jsonify({
            "message": "Incorrect password"
        }), 401

    # Si el usuario venía del sistema anterior con contraseña en texto plano,
    # aquí actualizamos su contraseña a formato hash.
    if user.password == password:
        user.password = generate_password_hash(password)
        db.session.commit()

    return jsonify({
        "message": "User validated successfully",
        "user": user.to_dict()
    }), 200


@main.route("/api/auth/register", methods=["POST"])
def register():
    data, error_response = _get_json_data()

    if error_response:
        return error_response

    return _register_user(data)


@main.route("/api/auth/login", methods=["POST"])
def login():
    data, error_response = _get_json_data()

    if error_response:
        return error_response

    return _login_user(data)


@main.route("/api/micrographs/upload", methods=["POST"])
def upload_micrograph():
    """
    Recibe una micrografía TEM o SEM y la guarda en uploads/original.

    La imagen debe enviarse como multipart/form-data usando el campo "file".
    También puede recibir datos adicionales como:
    - user_id
    - micrograph_type
    - scale_value
    - scale_unit
    - description
    """
    if "file" not in request.files:
        return jsonify({
            "message": "No file field was provided. Use field name 'file'."
        }), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({
            "message": "No selected file"
        }), 400

    if not _allowed_image(file.filename):
        return jsonify({
            "message": "Invalid image format",
            "allowed_formats": sorted(ALLOWED_IMAGE_EXTENSIONS)
        }), 400

    original_filename = secure_filename(file.filename)
    extension = original_filename.rsplit(".", 1)[1].lower()
    stored_filename = f"{uuid.uuid4().hex}.{extension}"

    upload_folder = Path(current_app.config["UPLOAD_ORIGINAL_FOLDER"])
    file_path = upload_folder / stored_filename

    file.save(file_path)

    user_id = request.form.get("user_id")
    micrograph_type = request.form.get("micrograph_type")
    scale_value = request.form.get("scale_value")
    scale_unit = request.form.get("scale_unit")
    description = request.form.get("description")

    if user_id:
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({
                "message": "user_id must be an integer"
            }), 400
    else:
        user_id = None

    if scale_value:
        try:
            scale_value = float(scale_value)
        except ValueError:
            return jsonify({
                "message": "scale_value must be numeric"
            }), 400
    else:
        scale_value = None

    if micrograph_type:
        micrograph_type = micrograph_type.upper()

    if micrograph_type and micrograph_type not in {"TEM", "SEM"}:
        return jsonify({
            "message": "micrograph_type must be TEM or SEM"
        }), 400

    micrograph = Micrograph(
        user_id=user_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_path=str(file_path),
        micrograph_type=micrograph_type,
        scale_value=scale_value,
        scale_unit=scale_unit,
        description=description
    )

    db.session.add(micrograph)
    db.session.commit()

    return jsonify({
        "message": "Micrograph uploaded successfully",
        "micrograph": micrograph.to_dict()
    }), 201


@main.route("/api/micrographs", methods=["GET"])
def list_micrographs():
    """
    Devuelve las micrografías registradas.
    Por ahora funciona como endpoint de prueba para verificar que la carga
    se guardó correctamente en la base de datos.
    """
    micrographs = Micrograph.query.order_by(Micrograph.uploaded_at.desc()).all()

    return jsonify({
        "micrographs": [micrograph.to_dict() for micrograph in micrographs]
    }), 200


@main.route("/api/analysis/run", methods=["POST"])
def run_analysis():
    """
    Ejecuta un análisis sobre una micrografía previamente cargada.

    En esta etapa el análisis es simulado. Es decir, todavía no ejecuta SAM 2.
    Su objetivo es validar el flujo:
    micrografía -> análisis -> resultado -> respuesta JSON.
    """
    data, error_response = _get_json_data()

    if error_response:
        return error_response

    micrograph_id = data.get("micrograph_id")
    user_id = data.get("user_id")
    model_name = data.get("model_name", "SAM2")
    parameters = data.get("parameters", {})

    if not micrograph_id:
        return jsonify({
            "message": "micrograph_id is required"
        }), 400

    try:
        micrograph_id = int(micrograph_id)
    except ValueError:
        return jsonify({
            "message": "micrograph_id must be an integer"
        }), 400

    if user_id:
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({
                "message": "user_id must be an integer"
            }), 400
    else:
        user_id = None

    analysis, result, error = AnalysisService.run_simulated_analysis(
        micrograph_id=micrograph_id,
        user_id=user_id,
        model_name=model_name,
        parameters=parameters
    )

    if analysis is None:
        return jsonify({
            "message": error
        }), 404

    if error:
        return jsonify({
            "message": "Analysis failed",
            "error": error,
            "analysis": analysis.to_dict()
        }), 500

    return jsonify({
        "message": "Analysis completed successfully",
        "analysis": analysis.to_dict(),
        "result": result.to_dict()
    }), 200

@main.route("/api/analysis/<int:analysis_id>", methods=["GET"])
def get_analysis(analysis_id):
    """
    Devuelve la información de un análisis específico.
    """
    analysis = Analysis.query.get(analysis_id)

    if not analysis:
        return jsonify({
            "message": "Analysis not found"
        }), 404

    response = {
        "analysis": analysis.to_dict(),
        "micrograph": analysis.micrograph.to_dict() if analysis.micrograph else None,
        "result": analysis.result.to_dict() if analysis.result else None,
        "report": analysis.report.to_dict() if analysis.report else None
    }

    return jsonify(response), 200


@main.route("/api/analysis/history", methods=["GET"])
def analysis_history():
    """
    Devuelve el historial de análisis registrados.
    Si se envía user_id como parámetro, filtra por usuario.
    """
    user_id = request.args.get("user_id")

    query = Analysis.query

    if user_id:
        try:
            user_id = int(user_id)
        except ValueError:
            return jsonify({
                "message": "user_id must be an integer"
            }), 400

        query = query.filter_by(user_id=user_id)

    analyses = query.order_by(Analysis.started_at.desc()).all()

    return jsonify({
        "analyses": [
            {
                "analysis": analysis.to_dict(),
                "micrograph": analysis.micrograph.to_dict() if analysis.micrograph else None,
                "result": analysis.result.to_dict() if analysis.result else None
            }
            for analysis in analyses
        ]
    }), 200

@main.route("/api/files/original/<path:filename>", methods=["GET"])
def get_original_file(filename):
    """
    Devuelve una micrografía original almacenada en uploads/original.
    """
    return send_from_directory(
        current_app.config["UPLOAD_ORIGINAL_FOLDER"],
        filename
    )


@main.route("/api/files/segmented/<path:filename>", methods=["GET"])
def get_segmented_file(filename):
    """
    Devuelve una imagen segmentada almacenada en uploads/segmented.
    """
    return send_from_directory(
        current_app.config["UPLOAD_SEGMENTED_FOLDER"],
        filename
    )

@main.route("/api/reports/generate", methods=["POST"])
def generate_report():
    """
    Genera un reporte para un análisis existente.
    """
    data, error_response = _get_json_data()

    if error_response:
        return error_response

    analysis_id = data.get("analysis_id")

    if not analysis_id:
        return jsonify({
            "message": "analysis_id is required"
        }), 400

    try:
        analysis_id = int(analysis_id)
    except ValueError:
        return jsonify({
            "message": "analysis_id must be an integer"
        }), 400

    report, error = ReportService.generate_text_report(analysis_id)

    if error:
        return jsonify({
            "message": error
        }), 404

    return jsonify({
        "message": "Report generated successfully",
        "report": report.to_dict()
    }), 201


@main.route("/api/reports/<int:report_id>/download", methods=["GET"])
def download_report(report_id):
    """
    Descarga un reporte generado.
    """
    from .models import Report

    report = Report.query.get(report_id)

    if report is None:
        return jsonify({
            "message": "Report not found"
        }), 404

    report_path = Path(report.file_path)

    return send_from_directory(
        report_path.parent,
        report_path.name,
        as_attachment=True
    )

# Rutas temporales de compatibilidad con el frontend original.
# Más adelante actualizaremos React para usar /api/auth/register y /api/auth/login.
@main.route("/add", methods=["POST"])
def legacy_add_user():
    data, error_response = _get_json_data()

    if error_response:
        return error_response

    return _register_user(data)


@main.route("/userValidation", methods=["POST"])
def legacy_user_validation():
    data, error_response = _get_json_data()

    if error_response:
        return error_response

    return _login_user(data)