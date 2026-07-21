import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from .extensions import db
from .routes import main


def create_app():
    app = Flask(__name__)

    # Ruta base del proyecto apiMAS
    base_dir = Path(__file__).resolve().parent.parent

    # Carpetas locales para guardar archivos del sistema
    upload_original_dir = base_dir / "uploads" / "original"
    upload_segmented_dir = base_dir / "uploads" / "segmented"
    reports_dir = base_dir / "reports"

    upload_original_dir.mkdir(parents=True, exist_ok=True)
    upload_segmented_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Configuración básica de Flask
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

    # Base de datos:
    # Si existe DATABASE_URL, se usa esa.
    # Si no existe, se crea una base SQLite local llamada mas_local.db.
    db_path = base_dir / "mas_local.db"
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{db_path.as_posix()}"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Rutas de carpetas disponibles para otros módulos
    app.config["UPLOAD_ORIGINAL_FOLDER"] = str(upload_original_dir)
    app.config["UPLOAD_SEGMENTED_FOLDER"] = str(upload_segmented_dir)
    app.config["REPORTS_FOLDER"] = str(reports_dir)

    # CORS permite que React pueda comunicarse con Flask.
    # localhost:3000 será usado por el frontend en desarrollo.
    allowed_origins = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:3000,https://frontmastest.onrender.com"
    ).split(",")

    CORS(app, resources={r"/*": {"origins": allowed_origins}})

    # Inicializar base de datos
    db.init_app(app)

    # Registrar rutas
    app.register_blueprint(main)

    # Importar modelos para que SQLAlchemy los conozca antes de crear tablas
    from . import models  # noqa: F401

    # Crear tablas si no existen.
    # Importante: esto NO borra la base de datos.
    with app.app_context():
        db.create_all()
        app.logger.info("Base de datos inicializada sin borrar información.")

    return app