from datetime import datetime

from .extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    occupation = db.Column(db.String(100), nullable=True)
    password = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    micrographs = db.relationship("Micrograph", backref="user", lazy=True)
    analyses = db.relationship("Analysis", backref="user", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "occupation": self.occupation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Micrograph(db.Model):
    __tablename__ = "micrographs"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)

    micrograph_type = db.Column(db.String(20), nullable=True)  # TEM o SEM
    scale_value = db.Column(db.Float, nullable=True)
    scale_unit = db.Column(db.String(50), nullable=True)

    description = db.Column(db.Text, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    analyses = db.relationship("Analysis", backref="micrograph", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "file_path": self.file_path,
            "micrograph_type": self.micrograph_type,
            "scale_value": self.scale_value,
            "scale_unit": self.scale_unit,
            "description": self.description,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


class Analysis(db.Model):
    __tablename__ = "analyses"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    micrograph_id = db.Column(db.Integer, db.ForeignKey("micrographs.id"), nullable=False)

    model_name = db.Column(db.String(50), nullable=False, default="SAM2")
    status = db.Column(db.String(50), nullable=False, default="pending")

    # Guardaremos parámetros como texto JSON.
    # Ejemplo: {"points_per_side": 44, "pred_iou_thresh": 0.85}
    parameters_json = db.Column(db.Text, nullable=True)

    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    result = db.relationship("AnalysisResult", backref="analysis", uselist=False)
    report = db.relationship("Report", backref="analysis", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "micrograph_id": self.micrograph_id,
            "model_name": self.model_name,
            "status": self.status,
            "parameters_json": self.parameters_json,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }


class AnalysisResult(db.Model):
    __tablename__ = "analysis_results"

    id = db.Column(db.Integer, primary_key=True)

    analysis_id = db.Column(db.Integer, db.ForeignKey("analyses.id"), nullable=False)

    particle_count = db.Column(db.Integer, nullable=True)
    total_masks = db.Column(db.Integer, nullable=True)
    valid_masks = db.Column(db.Integer, nullable=True)
    rejected_masks = db.Column(db.Integer, nullable=True)

    segmented_image_path = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "particle_count": self.particle_count,
            "total_masks": self.total_masks,
            "valid_masks": self.valid_masks,
            "rejected_masks": self.rejected_masks,
            "segmented_image_path": self.segmented_image_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)

    analysis_id = db.Column(db.Integer, db.ForeignKey("analyses.id"), nullable=False)

    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)

    generated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
        }


# Modelo legado del proyecto original.
# Se conserva temporalmente porque routes.py todavía lo importa.
# Más adelante se eliminará cuando limpiemos las rutas relacionadas con plantas.
class PlantEntry(db.Model):
    __tablename__ = "plant_entries"

    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(100))
    nombre = db.Column(db.String(100))
    frecuenciaRiego = db.Column(db.Integer)
    descripcion = db.Column(db.Text)
    recomendaciones = db.Column(db.Text)
    lastWateredTime = db.Column(db.DateTime, default=datetime.utcnow)