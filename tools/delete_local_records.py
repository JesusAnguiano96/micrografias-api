import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from myapp import create_app
from myapp.extensions import db
from myapp.models import User, Micrograph, Analysis, AnalysisResult, Report


def list_users():
    users = User.query.all()

    print("\nUsuarios registrados:")
    if not users:
        print("No hay usuarios.")
        return

    for user in users:
        print(f"ID: {user.id} | Email: {user.email}")


def list_analyses():
    analyses = Analysis.query.order_by(Analysis.id.desc()).all()

    print("\nAnálisis registrados:")
    if not analyses:
        print("No hay análisis.")
        return

    for analysis in analyses:
        print(
            f"ID: {analysis.id} | "
            f"User ID: {analysis.user_id} | "
            f"Micrograph ID: {analysis.micrograph_id} | "
            f"Model: {analysis.model_name} | "
            f"Status: {analysis.status}"
        )


def delete_analysis(analysis_id):
    analysis = Analysis.query.get(analysis_id)

    if not analysis:
        print(f"No existe un análisis con ID {analysis_id}.")
        return

    print(f"\nEliminando análisis ID {analysis.id}...")

    Report.query.filter_by(analysis_id=analysis.id).delete()
    AnalysisResult.query.filter_by(analysis_id=analysis.id).delete()

    db.session.delete(analysis)
    db.session.commit()

    print(f"Análisis ID {analysis_id} eliminado correctamente.")


def delete_user(user_id):
    user = User.query.get(user_id)

    if not user:
        print(f"No existe un usuario con ID {user_id}.")
        return

    print(f"\nEliminando usuario ID {user.id} | {user.email}...")

    micrographs = Micrograph.query.filter_by(user_id=user.id).all()

    for micrograph in micrographs:
        analyses = Analysis.query.filter_by(micrograph_id=micrograph.id).all()

        for analysis in analyses:
            Report.query.filter_by(analysis_id=analysis.id).delete()
            AnalysisResult.query.filter_by(analysis_id=analysis.id).delete()
            db.session.delete(analysis)

        db.session.delete(micrograph)

    db.session.delete(user)
    db.session.commit()

    print(f"Usuario ID {user_id} eliminado correctamente junto con sus micrografías, análisis, resultados y reportes.")


def main():
    app = create_app()

    with app.app_context():
        print("\n=== LIMPIEZA LOCAL DE BASE DE DATOS MAS ===")
        print("1. Listar usuarios")
        print("2. Listar análisis")
        print("3. Eliminar análisis por ID")
        print("4. Eliminar usuario por ID")
        print("5. Salir")

        option = input("\nSelecciona una opción: ").strip()

        if option == "1":
            list_users()

        elif option == "2":
            list_analyses()

        elif option == "3":
            analysis_id = int(input("ID del análisis a eliminar: ").strip())
            confirm = input(f"Confirmar eliminación del análisis {analysis_id}? escribe SI: ")

            if confirm == "SI":
                delete_analysis(analysis_id)
            else:
                print("Operación cancelada.")

        elif option == "4":
            user_id = int(input("ID del usuario a eliminar: ").strip())
            confirm = input(f"Confirmar eliminación del usuario {user_id}? escribe SI: ")

            if confirm == "SI":
                delete_user(user_id)
            else:
                print("Operación cancelada.")

        else:
            print("Saliendo...")


if __name__ == "__main__":
    main()