import os
import sys
import json

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from myapp import create_app
from myapp.extensions import db
from myapp.models import Analysis, Micrograph


def pretty_json(value):
    if not value:
        return "None"

    try:
        return json.dumps(json.loads(value), indent=2, ensure_ascii=False)
    except Exception:
        return str(value)


def print_model_columns(title, obj):
    print(f"\n=== {title} ===")

    if obj is None:
        print("No encontrado.")
        return

    for column in obj.__table__.columns:
        column_name = column.name
        value = getattr(obj, column_name, None)

        if column_name == "parameters_json":
            print(f"{column_name}:")
            print(pretty_json(value))
        else:
            print(f"{column_name}: {value}")


def main():
    app = create_app()

    with app.app_context():
        analysis = Analysis.query.order_by(Analysis.id.desc()).first()

        if not analysis:
            print("No hay análisis registrados.")
            return

        micrograph = db.session.get(Micrograph, analysis.micrograph_id)

        print_model_columns("ÚLTIMO ANÁLISIS", analysis)
        print_model_columns("MICROGRAFÍA ASOCIADA", micrograph)

        print("\n=== RESUMEN IMPORTANTE ===")
        print(f"Analysis ID: {analysis.id}")
        print(f"Status: {analysis.status}")
        print(f"Model: {analysis.model_name}")

        print("\n=== PARÁMETROS USADOS ===")
        print(pretty_json(getattr(analysis, "parameters_json", None)))

        print("\n=== ERROR MESSAGE ===")
        print(getattr(analysis, "error_message", None))


if __name__ == "__main__":
    main()