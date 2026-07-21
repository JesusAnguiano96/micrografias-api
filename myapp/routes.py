from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db
from .models import User


main = Blueprint("main", __name__)


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