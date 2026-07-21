import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from myapp.analysis_engine.sam2_analyzer import SAM2Analyzer


def find_default_image():
    """
    Busca una imagen de prueba dentro de uploads/original.

    Esto permite probar SAM 2 sin escribir una ruta manual si ya existen
    micrografías cargadas desde React.
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


def main():
    parser = argparse.ArgumentParser(
        description="Prueba aislada del módulo SAM 2 integrado al backend."
    )

    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help=(
            "Ruta de la imagen a analizar. "
            "Si no se proporciona, se usará la imagen más reciente en uploads/original."
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
        default=str(PROJECT_ROOT / "outputs" / "sam2_test"),
        help="Carpeta donde se guardarán las salidas.",
    )

    parser.add_argument(
        "--profile",
        type=str,
        default="60",
        help="Perfil SAM 2 a usar: default, 0, 15, 30, 45 o 60.",
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
        help="Número de intervalos para las distribuciones.",
    )

    parser.add_argument(
        "--pixel-threshold",
        type=int,
        default=140,
        help="Umbral usado por los filtros heredados de Diego.",
    )

    parser.add_argument(
        "--max-image-size",
        type=int,
        default=1000,
        help=(
            "Tamaño máximo del lado mayor usado para ejecutar SAM 2. "
            "Reduce el consumo de memoria GPU."
        ),
    )

    parser.add_argument(
        "--points-per-side",
        type=int,
        default=None,
        help=(
            "Sobrescribe points_per_side del perfil seleccionado. "
            "Útil para pruebas con menor uso de memoria."
        ),
    )

    parser.add_argument(
        "--points-per-batch",
        type=int,
        default=None,
        help=(
            "Sobrescribe points_per_batch del perfil seleccionado. "
            "Útil para evitar errores CUDA out of memory."
        ),
    )

    parser.add_argument(
        "--disable-legacy-filters",
        action="store_true",
        help="Desactiva los filtros heredados y usa solo filtrado morfológico.",
    )

    args = parser.parse_args()

    if args.image:
        image_path = Path(args.image)
    else:
        image_path = find_default_image()

    if image_path is None:
        print("No se encontró una imagen de prueba.")
        print("Usa --image con una ruta manual o carga una micrografía desde React.")
        return

    image_path = Path(image_path)
    checkpoint_path = Path(args.checkpoint)
    output_dir = Path(args.output_dir)

    runtime_parameters = {
        "max_image_size": args.max_image_size,
    }

    if args.points_per_side is not None:
        runtime_parameters["points_per_side"] = args.points_per_side

    if args.points_per_batch is not None:
        runtime_parameters["points_per_batch"] = args.points_per_batch

    print("SAM 2 isolated test")
    print("-------------------")
    print(f"Project root:       {PROJECT_ROOT}")
    print(f"Image:              {image_path}")
    print(f"Checkpoint:         {checkpoint_path}")
    print(f"Output dir:         {output_dir}")
    print(f"Profile:            {args.profile}")
    print(f"Factor:             {args.factor}")
    print(f"Max image size:     {args.max_image_size}")
    print(f"Points per side:    {args.points_per_side}")
    print(f"Points per batch:   {args.points_per_batch}")
    print()

    result = SAM2Analyzer.analyze(
        image_path=image_path,
        output_dir=output_dir,
        checkpoint_path=checkpoint_path,
        profile_name=args.profile,
        factor=args.factor,
        step_number=args.step_number,
        pixel_threshold=args.pixel_threshold,
        filter_with_legacy_rules=not args.disable_legacy_filters,
        parameters=runtime_parameters,
    )

    metrics = result["metrics"]

    print("Analysis completed")
    print("------------------")
    print(f"Model:                     {metrics['model_name']}")
    print(f"SAM 2 model:               {metrics['sam2_model_name']}")
    print(f"Profile:                   {metrics['profile_name']}")
    print(f"Overlap level:             {metrics['overlap_level']}")
    print(f"Original image size:       {metrics['original_image_size']}")
    print(f"SAM2 runtime image size:   {metrics['sam2_runtime_image_size']}")
    print(f"SAM2 scale ratio:          {metrics['sam2_scale_ratio']}")
    print(f"Profile min area px:       {metrics['profile_min_area_px']}")
    print(f"Effective min area px:     {metrics['effective_min_area_px']}")
    print(f"Total masks:               {metrics['total_masks']}")
    print(f"Masks after legacy filter: {metrics['masks_after_legacy_filters']}")
    print(f"Valid masks:               {metrics['valid_masks']}")
    print(f"Rejected masks:            {metrics['rejected_masks']}")
    print(f"Rejected by legacy:        {metrics['rejected_by_legacy_filters']}")
    print(f"Rejected by morphology:    {metrics['rejected_by_morphology']}")
    print(f"Particle count:            {metrics['particle_count']}")
    print()
    print("Generated files")
    print("---------------")
    print(f"Annotated image: {result['annotated_image_path']}")
    print(f"Summary figure:  {result['summary_figure_path']}")
    print(f"Metrics JSON:    {result['metrics_path']}")


if __name__ == "__main__":
    main()