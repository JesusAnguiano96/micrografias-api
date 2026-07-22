import argparse
import csv
import json
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import torch
except ImportError:
    torch = None

from myapp.analysis_engine.sam2_analyzer import SAM2Analyzer


def find_default_image():
    """
    Busca la imagen más reciente en uploads/original.
    """
    uploads_original = PROJECT_ROOT / "uploads" / "original"

    allowed_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
        ".bmp",
    }

    if not uploads_original.exists():
        return None

    image_files = [
        image_path
        for image_path in uploads_original.iterdir()
        if image_path.is_file()
        and image_path.suffix.lower() in allowed_extensions
    ]

    if not image_files:
        return None

    image_files.sort(key=lambda path: path.stat().st_mtime, reverse=True)

    return image_files[0]


def clear_cuda_cache():
    """
    Libera caché de CUDA entre pruebas.
    """
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()


def get_diagnostic_scenarios(include_balanced=False):
    """
    Define las pruebas que queremos comparar.

    Objetivo:
    - Distinguir si el problema viene del perfil SAM2.
    - Distinguir si viene de la reducción de imagen.
    - Distinguir si viene de los filtros heredados.
    - Distinguir si viene del filtro morfológico.
    """
    scenarios = [
        {
            "name": "profile_60_safe_default",
            "description": "Perfil 60%, modo seguro, filtros normales.",
            "profile": "60",
            "parameters": {
                "sam2_profile": "60",
                "overlap_level": "60",
                "execution_mode": "safe_local",
                "max_image_size": 700,
                "points_per_batch": 8,
                "filter_with_legacy_rules": True,
            },
        },
        {
            "name": "profile_15_safe_default",
            "description": "Perfil 15%, modo seguro, filtros normales.",
            "profile": "15",
            "parameters": {
                "sam2_profile": "15",
                "overlap_level": "15",
                "execution_mode": "safe_local",
                "max_image_size": 700,
                "points_per_batch": 8,
                "filter_with_legacy_rules": True,
            },
        },
        {
            "name": "profile_15_safe_no_legacy",
            "description": "Perfil 15%, sin filtros heredados de Diego.",
            "profile": "15",
            "parameters": {
                "sam2_profile": "15",
                "overlap_level": "15",
                "execution_mode": "safe_local",
                "max_image_size": 700,
                "points_per_batch": 8,
                "filter_with_legacy_rules": False,
            },
        },
        {
            "name": "profile_15_safe_loose_morphology",
            "description": "Perfil 15%, filtros morfológicos más flexibles.",
            "profile": "15",
            "parameters": {
                "sam2_profile": "15",
                "overlap_level": "15",
                "execution_mode": "safe_local",
                "max_image_size": 700,
                "points_per_batch": 8,
                "filter_with_legacy_rules": True,
                "min_circularity": 0.50,
                "max_aspect_ratio": 1.80,
                "min_solidity": 0.70,
                "max_area_factor": 20.0,
            },
        },
        {
            "name": "profile_15_safe_no_legacy_loose_morphology",
            "description": (
                "Perfil 15%, sin filtros heredados y con filtros morfológicos "
                "más flexibles."
            ),
            "profile": "15",
            "parameters": {
                "sam2_profile": "15",
                "overlap_level": "15",
                "execution_mode": "safe_local",
                "max_image_size": 700,
                "points_per_batch": 8,
                "filter_with_legacy_rules": False,
                "min_circularity": 0.50,
                "max_aspect_ratio": 1.80,
                "min_solidity": 0.70,
                "max_area_factor": 20.0,
            },
        },
        {
            "name": "profile_15_safe_area_only",
            "description": (
                "Perfil 15%, conteo flexible por área. "
                "Sirve para ver si circularidad/solidez/aspect ratio rechazan demasiado."
            ),
            "profile": "15",
            "parameters": {
                "sam2_profile": "15",
                "overlap_level": "15",
                "execution_mode": "safe_local",
                "max_image_size": 700,
                "points_per_batch": 8,
                "filter_with_legacy_rules": False,
                "mode": "pure",
                "max_area_factor": 20.0,
            },
        },
    ]

    if include_balanced:
        scenarios.append(
            {
                "name": "profile_15_balanced_default",
                "description": "Perfil 15%, modo balanceado, filtros normales.",
                "profile": "15",
                "parameters": {
                    "sam2_profile": "15",
                    "overlap_level": "15",
                    "execution_mode": "balanced",
                    "max_image_size": 850,
                    "points_per_batch": 8,
                    "filter_with_legacy_rules": True,
                },
            }
        )

        scenarios.append(
            {
                "name": "profile_60_balanced_default",
                "description": "Perfil 60%, modo balanceado, filtros normales.",
                "profile": "60",
                "parameters": {
                    "sam2_profile": "60",
                    "overlap_level": "60",
                    "execution_mode": "balanced",
                    "max_image_size": 850,
                    "points_per_batch": 8,
                    "filter_with_legacy_rules": True,
                },
            }
        )

    return scenarios


def write_json(path, data):
    path = Path(path)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_summary_csv(path, rows):
    path = Path(path)

    fieldnames = [
        "scenario",
        "status",
        "profile",
        "execution_mode",
        "max_image_size",
        "points_per_batch",
        "filter_with_legacy_rules",
        "total_masks",
        "masks_after_legacy_filters",
        "valid_masks",
        "rejected_masks",
        "rejected_by_legacy_filters",
        "rejected_by_morphology",
        "particle_count",
        "sam2_scale_ratio",
        "original_image_size",
        "sam2_runtime_image_size",
        "effective_min_area_px",
        "annotated_image_path",
        "summary_figure_path",
        "metrics_path",
        "error",
    ]

    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    fieldname: row.get(fieldname, "")
                    for fieldname in fieldnames
                }
            )


def update_metrics_with_diagnostic_info(metrics_path, scenario, parameters):
    """
    Agrega información del diagnóstico al JSON de métricas generado.
    """
    metrics_path = Path(metrics_path)

    if not metrics_path.exists():
        return

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    metrics["diagnostic_scenario"] = scenario["name"]
    metrics["diagnostic_description"] = scenario["description"]
    metrics["diagnostic_parameters"] = parameters

    write_json(metrics_path, metrics)


def run_scenario(
    scenario,
    image_path,
    checkpoint_path,
    diagnostics_output_dir,
    factor,
    step_number,
    pixel_threshold,
):
    scenario_name = scenario["name"]
    scenario_output_dir = diagnostics_output_dir / scenario_name
    scenario_output_dir.mkdir(parents=True, exist_ok=True)

    parameters = dict(scenario["parameters"])

    filter_with_legacy_rules = bool(
        parameters.pop("filter_with_legacy_rules", True)
    )

    clear_cuda_cache()

    result = SAM2Analyzer.analyze(
        image_path=image_path,
        output_dir=scenario_output_dir,
        checkpoint_path=checkpoint_path,
        profile_name=parameters.get("sam2_profile", scenario["profile"]),
        overlap_level=parameters.get("overlap_level", scenario["profile"]),
        factor=factor,
        step_number=step_number,
        pixel_threshold=pixel_threshold,
        filter_with_legacy_rules=filter_with_legacy_rules,
        parameters=parameters,
    )

    metrics = result["metrics"]

    update_metrics_with_diagnostic_info(
        metrics_path=result["metrics_path"],
        scenario=scenario,
        parameters={
            **parameters,
            "filter_with_legacy_rules": filter_with_legacy_rules,
        },
    )

    clear_cuda_cache()

    return {
        "scenario": scenario_name,
        "status": "completed",
        "profile": metrics.get("profile_name"),
        "execution_mode": parameters.get("execution_mode"),
        "max_image_size": metrics.get("max_image_size"),
        "points_per_batch": metrics.get("mask_generator_params", {}).get(
            "points_per_batch"
        ),
        "filter_with_legacy_rules": filter_with_legacy_rules,
        "total_masks": metrics.get("total_masks"),
        "masks_after_legacy_filters": metrics.get(
            "masks_after_legacy_filters"
        ),
        "valid_masks": metrics.get("valid_masks"),
        "rejected_masks": metrics.get("rejected_masks"),
        "rejected_by_legacy_filters": metrics.get(
            "rejected_by_legacy_filters"
        ),
        "rejected_by_morphology": metrics.get("rejected_by_morphology"),
        "particle_count": metrics.get("particle_count"),
        "sam2_scale_ratio": metrics.get("sam2_scale_ratio"),
        "original_image_size": metrics.get("original_image_size"),
        "sam2_runtime_image_size": metrics.get("sam2_runtime_image_size"),
        "effective_min_area_px": metrics.get("effective_min_area_px"),
        "annotated_image_path": result.get("annotated_image_path"),
        "summary_figure_path": result.get("summary_figure_path"),
        "metrics_path": result.get("metrics_path"),
        "error": "",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Diagnóstico de perfiles y filtros SAM 2."
    )

    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help=(
            "Ruta de la imagen a analizar. "
            "Si no se indica, se usará la imagen más reciente en uploads/original."
        ),
    )

    parser.add_argument(
        "--checkpoint",
        type=str,
        default=str(PROJECT_ROOT / "checkpoints" / "sam2.1_hiera_large.pt"),
        help="Ruta del checkpoint SAM 2.",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT / "outputs" / "sam2_diagnostics"),
        help="Carpeta principal donde se guardarán los diagnósticos.",
    )

    parser.add_argument(
        "--factor",
        type=float,
        default=5.95,
        help="Factor de conversión de pixeles a nanómetros.",
    )

    parser.add_argument(
        "--step-number",
        type=int,
        default=10,
        help="Número de intervalos para distribuciones.",
    )

    parser.add_argument(
        "--pixel-threshold",
        type=int,
        default=140,
        help="Umbral usado por filtros heredados.",
    )

    parser.add_argument(
        "--include-balanced",
        action="store_true",
        help=(
            "Incluye pruebas adicionales en modo balanced. "
            "Consume más memoria GPU."
        ),
    )

    args = parser.parse_args()

    if args.image:
        image_path = Path(args.image)
    else:
        image_path = find_default_image()

    if image_path is None:
        print("No se encontró imagen de prueba.")
        print("Carga una micrografía desde React o usa --image con una ruta.")
        return

    checkpoint_path = Path(args.checkpoint)
    diagnostics_output_dir = Path(args.output_dir)
    diagnostics_output_dir.mkdir(parents=True, exist_ok=True)

    if not image_path.exists():
        print(f"No existe la imagen: {image_path}")
        return

    if not checkpoint_path.exists():
        print(f"No existe el checkpoint: {checkpoint_path}")
        return

    scenarios = get_diagnostic_scenarios(
        include_balanced=args.include_balanced
    )

    print("SAM 2 diagnostic run")
    print("--------------------")
    print(f"Image:       {image_path}")
    print(f"Checkpoint:  {checkpoint_path}")
    print(f"Output dir:  {diagnostics_output_dir}")
    print(f"Scenarios:   {len(scenarios)}")
    print()

    summary_rows = []

    for index, scenario in enumerate(scenarios, start=1):
        print(f"[{index}/{len(scenarios)}] Running {scenario['name']}")
        print(f"Description: {scenario['description']}")

        try:
            row = run_scenario(
                scenario=scenario,
                image_path=image_path,
                checkpoint_path=checkpoint_path,
                diagnostics_output_dir=diagnostics_output_dir,
                factor=args.factor,
                step_number=args.step_number,
                pixel_threshold=args.pixel_threshold,
            )

            print(
                "Completed | "
                f"total={row['total_masks']} | "
                f"after_legacy={row['masks_after_legacy_filters']} | "
                f"valid={row['valid_masks']} | "
                f"particle_count={row['particle_count']}"
            )

        except RuntimeError as error:
            error_message = str(error)

            row = {
                "scenario": scenario["name"],
                "status": "failed",
                "profile": scenario["profile"],
                "execution_mode": scenario["parameters"].get("execution_mode"),
                "max_image_size": scenario["parameters"].get("max_image_size"),
                "points_per_batch": scenario["parameters"].get(
                    "points_per_batch"
                ),
                "filter_with_legacy_rules": scenario["parameters"].get(
                    "filter_with_legacy_rules"
                ),
                "error": error_message,
            }

            print("Failed")
            print(error_message)

            clear_cuda_cache()

        except Exception as error:
            error_message = traceback.format_exc()

            row = {
                "scenario": scenario["name"],
                "status": "failed",
                "profile": scenario["profile"],
                "execution_mode": scenario["parameters"].get("execution_mode"),
                "max_image_size": scenario["parameters"].get("max_image_size"),
                "points_per_batch": scenario["parameters"].get(
                    "points_per_batch"
                ),
                "filter_with_legacy_rules": scenario["parameters"].get(
                    "filter_with_legacy_rules"
                ),
                "error": error_message,
            }

            print("Failed")
            print(error_message)

            clear_cuda_cache()

        summary_rows.append(row)
        print()

    summary_json_path = diagnostics_output_dir / "diagnostics_summary.json"
    summary_csv_path = diagnostics_output_dir / "diagnostics_summary.csv"

    write_json(summary_json_path, summary_rows)
    write_summary_csv(summary_csv_path, summary_rows)

    print("Diagnostic completed")
    print("--------------------")
    print(f"Summary JSON: {summary_json_path}")
    print(f"Summary CSV:  {summary_csv_path}")
    print()
    print("Open the output folder with:")
    print(f'explorer "{diagnostics_output_dir}"')


if __name__ == "__main__":
    main()