import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from .extensions import db
from .models import User, Micrograph


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