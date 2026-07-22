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
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()


def get_tuning_scenarios(profile_name="15", include_no_legacy=False):
    """
    Segunda ronda de pruebas.

    Partimos de que profile_15_safe_loose_morphology fue visualmente aceptable.
    Ahora probamos filtros intermedios para no dejar el sistema ni demasiado
    estricto ni demasiado permisivo.
    """
    base_parameters = {
        "sam2_profile": profile_name,
        "overlap_level": profile_name,
        "execution_mode": "safe_local",
        "max_image_size": 700,
        "points_per_batch": 8,
    }

    scenarios = [
        {
            "name": f"profile_{profile_name}_strict_default",
            "description": "Filtro actual estricto usado como referencia.",
            "profile": profile_name,
            "filter_with_legacy_rules": True,
            "parameters": {
                **base_parameters,
            },
        },
        {
            "name": f"profile_{profile_name}_moderate_1",
            "description": (
                "Filtro moderado 1: relaja circularidad, aspect ratio, "
                "solidez y área máxima."
            ),
            "profile": profile_name,
            "filter_with_legacy_rules": True,
            "parameters": {
                **base_parameters,
                "min_circularity": 0.55,
                "max_aspect_ratio": 1.60,
                "min_solidity": 0.75,
                "max_area_factor": 15.0,
            },
        },
        {
            "name": f"profile_{profile_name}_moderate_2",
            "description": (
                "Filtro moderado 2: circularidad un poco más estricta, "
                "aspect ratio más flexible."
            ),
            "profile": profile_name,
            "filter_with_legacy_rules": True,
            "parameters": {
                **base_parameters,
                "min_circularity": 0.60,
                "max_aspect_ratio": 1.70,
                "min_solidity": 0.75,
                "max_area_factor": 15.0,
            },
        },
        {
            "name": f"profile_{profile_name}_moderate_3",
            "description": (
                "Filtro moderado 3: circularidad flexible, solidez más exigente "
                "y área máxima controlada."
            ),
            "profile": profile_name,
            "filter_with_legacy_rules": True,
            "parameters": {
                **base_parameters,
                "min_circularity": 0.50,
                "max_aspect_ratio": 1.60,
                "min_solidity": 0.80,
                "max_area_factor": 12.0,
            },
        },
        {
            "name": f"profile_{profile_name}_moderate_4",
            "description": (
                "Filtro moderado 4: circularidad muy flexible, aspect ratio "
                "flexible, solidez intermedia."
            ),
            "profile": profile_name,
            "filter_with_legacy_rules": True,
            "parameters": {
                **base_parameters,
                "min_circularity": 0.45,
                "max_aspect_ratio": 1.80,
                "min_solidity": 0.80,
                "max_area_factor": 12.0,
            },
        },
        {
            "name": f"profile_{profile_name}_loose_reference",
            "description": (
                "Filtro flexible que ya se observó como visualmente aceptable."
            ),
            "profile": profile_name,
            "filter_with_legacy_rules": True,
            "parameters": {
                **base_parameters,
                "min_circularity": 0.50,
                "max_aspect_ratio": 1.80,
                "min_solidity": 0.70,
                "max_area_factor": 20.0,
            },
        },
        {
            "name": f"profile_{profile_name}_area_only_reference",
            "description": (
                "Referencia permisiva por área. No se recomienda como final, "
                "sirve para saber el máximo aproximado que SAM2 está proponiendo."
            ),
            "profile": profile_name,
            "filter_with_legacy_rules": False,
            "parameters": {
                **base_parameters,
                "mode": "pure",
                "max_area_factor": 20.0,
            },
        },
    ]

    if include_no_legacy:
        scenarios.extend(
            [
                {
                    "name": f"profile_{profile_name}_moderate_1_no_legacy",
                    "description": "Moderado 1 sin filtros heredados.",
                    "profile": profile_name,
                    "filter_with_legacy_rules": False,
                    "parameters": {
                        **base_parameters,
                        "min_circularity": 0.55,
                        "max_aspect_ratio": 1.60,
                        "min_solidity": 0.75,
                        "max_area_factor": 15.0,
                    },
                },
                {
                    "name": f"profile_{profile_name}_moderate_3_no_legacy",
                    "description": "Moderado 3 sin filtros heredados.",
                    "profile": profile_name,
                    "filter_with_legacy_rules": False,
                    "parameters": {
                        **base_parameters,
                        "min_circularity": 0.50,
                        "max_aspect_ratio": 1.60,
                        "min_solidity": 0.80,
                        "max_area_factor": 12.0,
                    },
                },
                {
                    "name": f"profile_{profile_name}_loose_no_legacy",
                    "description": "Filtro flexible sin filtros heredados.",
                    "profile": profile_name,
                    "filter_with_legacy_rules": False,
                    "parameters": {
                        **base_parameters,
                        "min_circularity": 0.50,
                        "max_aspect_ratio": 1.80,
                        "min_solidity": 0.70,
                        "max_area_factor": 20.0,
                    },
                },
            ]
        )

    return scenarios


def write_json(path, data):
    path = Path(path)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_summary_csv(path, rows):
    fieldnames = [
        "scenario",
        "status",
        "profile",
        "filter_with_legacy_rules",
        "mode",
        "min_circularity",
        "max_aspect_ratio",
        "min_solidity",
        "max_area_factor",
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

    with Path(path).open("w", newline="", encoding="utf-8") as csv_file:
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
    metrics_path = Path(metrics_path)

    if not metrics_path.exists():
        return

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    metrics["diagnostic_type"] = "sam2_morphology_tuning"
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
    filter_with_legacy_rules = bool(scenario["filter_with_legacy_rules"])

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
    filter_params = metrics.get("filter_params", {})

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
        "filter_with_legacy_rules": filter_with_legacy_rules,
        "mode": filter_params.get("mode"),
        "min_circularity": filter_params.get("min_circularity"),
        "max_aspect_ratio": filter_params.get("max_aspect_ratio"),
        "min_solidity": filter_params.get("min_solidity"),
        "max_area_factor": filter_params.get("max_area_factor"),
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
        description="Ajuste fino de filtros morfológicos para SAM 2."
    )

    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help=(
            "Ruta de la imagen a analizar. "
            "Si no se indica, se usa la imagen más reciente en uploads/original."
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
        default=str(PROJECT_ROOT / "outputs" / "sam2_morphology_tuning"),
        help="Carpeta donde se guardarán las pruebas.",
    )

    parser.add_argument(
        "--profile",
        type=str,
        default="15",
        help="Perfil de solapamiento a probar: 0, 15, 30, 45 o 60.",
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
        "--include-no-legacy",
        action="store_true",
        help="Incluye variantes sin filtros heredados.",
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

    scenarios = get_tuning_scenarios(
        profile_name=args.profile,
        include_no_legacy=args.include_no_legacy,
    )

    print("SAM 2 morphology tuning")
    print("-----------------------")
    print(f"Image:       {image_path}")
    print(f"Checkpoint:  {checkpoint_path}")
    print(f"Output dir:  {diagnostics_output_dir}")
    print(f"Profile:     {args.profile}")
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
                f"particle_count={row['particle_count']} | "
                f"circ={row['min_circularity']} | "
                f"ar={row['max_aspect_ratio']} | "
                f"sol={row['min_solidity']} | "
                f"area_factor={row['max_area_factor']}"
            )

        except RuntimeError as error:
            error_message = str(error)

            row = {
                "scenario": scenario["name"],
                "status": "failed",
                "profile": scenario["profile"],
                "filter_with_legacy_rules": scenario["filter_with_legacy_rules"],
                "error": error_message,
            }

            print("Failed")
            print(error_message)

            clear_cuda_cache()

        except Exception:
            error_message = traceback.format_exc()

            row = {
                "scenario": scenario["name"],
                "status": "failed",
                "profile": scenario["profile"],
                "filter_with_legacy_rules": scenario["filter_with_legacy_rules"],
                "error": error_message,
            }

            print("Failed")
            print(error_message)

            clear_cuda_cache()

        summary_rows.append(row)
        print()

    summary_json_path = diagnostics_output_dir / "morphology_tuning_summary.json"
    summary_csv_path = diagnostics_output_dir / "morphology_tuning_summary.csv"

    write_json(summary_json_path, summary_rows)
    write_summary_csv(summary_csv_path, summary_rows)

    print("Morphology tuning completed")
    print("---------------------------")
    print(f"Summary JSON: {summary_json_path}")
    print(f"Summary CSV:  {summary_csv_path}")
    print()
    print("Open the output folder with:")
    print(f'explorer "{diagnostics_output_dir}"')


if __name__ == "__main__":
    main()