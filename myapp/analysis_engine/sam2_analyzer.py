import contextlib
import gc
import json
import warnings
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import torch
from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator
from sam2.build_sam import build_sam2

from .mask_filters import filter_masks
from .sam2_morphology import filter_sam2_particle_masks
from .sam2_overlap_profiles import SAM2_MODEL_CONFIG, get_sam2_profile


def read_image_bgr(image_path):
    """
    Lee una imagen de forma robusta en Windows, incluso si la ruta contiene
    acentos o caracteres especiales.
    """
    image_path = Path(image_path)
    image_bytes = np.fromfile(str(image_path), dtype=np.uint8)
    image_bgr = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)

    return image_bgr


def write_image(image_path, image_bgr):
    """
    Escribe una imagen de forma robusta en Windows.
    """
    image_path = Path(image_path)
    extension = image_path.suffix

    success, encoded_image = cv2.imencode(extension, image_bgr)

    if not success:
        raise ValueError(f"No se pudo codificar la imagen: {image_path}")

    encoded_image.tofile(str(image_path))


def clear_torch_memory():
    """
    Libera memoria temporal de Python y CUDA.

    Esto no descarga necesariamente el modelo SAM2 cacheado, pero ayuda a
    evitar acumulación de memoria después de varias ejecuciones.
    """
    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass


def is_cuda_out_of_memory(error):
    error_message = str(error).lower()

    return (
        "out of memory" in error_message
        or "cuda error: out of memory" in error_message
        or "cuda out of memory" in error_message
    )


def get_device():
    """
    Selecciona el dispositivo disponible para ejecutar SAM 2.
    """
    if torch.cuda.is_available():
        return torch.device("cuda")

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")

    return torch.device("cpu")


def enable_runtime_optimizations():
    """
    Activa optimizaciones cuando hay GPU NVIDIA compatible.
    """
    warnings.filterwarnings(
        "ignore",
        message=r".*cannot import name '_C' from 'sam2'.*",
        category=UserWarning,
    )

    if torch.cuda.is_available():
        torch.set_float32_matmul_precision("high")

        properties = torch.cuda.get_device_properties(0)

        if properties.major >= 8:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True


def build_bins(values, number_of_bins):
    """
    Construye una distribución simple para gráficas y reportes.
    """
    values = [float(value) for value in values if value is not None]

    if not values:
        return {
            "labels": [],
            "counts": [],
        }

    if len(values) == 1:
        value = values[0]

        return {
            "labels": [f"{value:.0f}"],
            "counts": [1],
        }

    min_value = min(values)
    max_value = max(values)

    if min_value == max_value:
        return {
            "labels": [f"{min_value:.0f}"],
            "counts": [len(values)],
        }

    bins = np.linspace(min_value, max_value, number_of_bins + 1)
    counts, edges = np.histogram(values, bins=bins)

    labels = []

    for index in range(len(edges) - 1):
        left = edges[index]
        right = edges[index + 1]
        labels.append(f"{left:.0f} to {right:.0f}")

    return {
        "labels": labels,
        "counts": [int(count) for count in counts],
    }


def resize_image_for_sam2(image_rgb, max_image_size):
    """
    Reduce la imagen para ejecutar SAM 2 con menor consumo de memoria.

    La reducción solo afecta la ejecución de SAM 2. Después, las máscaras se
    restauran al tamaño original para medir y dibujar sobre la micrografía real.
    """
    original_height, original_width = image_rgb.shape[:2]
    largest_side = max(original_height, original_width)

    scale_ratio = 1.0
    sam2_image_rgb = image_rgb

    if max_image_size > 0 and largest_side > max_image_size:
        scale_ratio = float(max_image_size) / float(largest_side)

        resized_width = max(1, int(original_width * scale_ratio))
        resized_height = max(1, int(original_height * scale_ratio))

        sam2_image_rgb = cv2.resize(
            image_rgb,
            (resized_width, resized_height),
            interpolation=cv2.INTER_AREA,
        )

    return sam2_image_rgb, scale_ratio


def restore_masks_to_original_size(
    masks,
    original_width,
    original_height,
    scale_ratio,
):
    """
    Reescala las máscaras generadas sobre una imagen reducida al tamaño original.
    """
    if scale_ratio == 1.0:
        return masks

    restored_masks = []

    for mask in masks:
        restored_mask = dict(mask)

        restored_segmentation = cv2.resize(
            mask["segmentation"].astype(np.uint8),
            (original_width, original_height),
            interpolation=cv2.INTER_NEAREST,
        ).astype(bool)

        restored_mask["segmentation"] = restored_segmentation
        restored_mask["area"] = int(np.sum(restored_segmentation))

        if "bbox" in restored_mask:
            x, y, width, height = restored_mask["bbox"]

            restored_mask["bbox"] = [
                int(x / scale_ratio),
                int(y / scale_ratio),
                int(width / scale_ratio),
                int(height / scale_ratio),
            ]

        if "crop_box" in restored_mask:
            x, y, width, height = restored_mask["crop_box"]

            restored_mask["crop_box"] = [
                int(x / scale_ratio),
                int(y / scale_ratio),
                int(width / scale_ratio),
                int(height / scale_ratio),
            ]

        restored_masks.append(restored_mask)

    return restored_masks


def longest_diagonal_from_mask(segmentation):
    """
    Calcula la diagonal más larga aproximada dentro del contorno de una máscara.
    """
    segmentation_u8 = segmentation.astype(np.uint8)

    contours, _ = cv2.findContours(
        segmentation_u8,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    if not contours:
        return None

    contour = max(contours, key=cv2.contourArea)
    hull = cv2.convexHull(contour)
    points = hull.reshape(-1, 2)

    if len(points) < 2:
        return None

    if len(points) > 300:
        indices = np.linspace(0, len(points) - 1, 300).astype(int)
        points = points[indices]

    max_distance = 0.0
    best_pair = None

    for index, point_a in enumerate(points):
        differences = points[index + 1:] - point_a

        if len(differences) == 0:
            continue

        distances = np.sqrt(np.sum(differences * differences, axis=1))
        local_index = int(np.argmax(distances))
        distance = float(distances[local_index])

        if distance > max_distance:
            max_distance = distance
            point_b = points[index + 1:][local_index]
            best_pair = (point_a, point_b)

    if best_pair is None:
        return None

    point_a, point_b = best_pair

    return {
        "x1": int(point_a[0]),
        "y1": int(point_a[1]),
        "x2": int(point_b[0]),
        "y2": int(point_b[1]),
        "length_px": max_distance,
    }


def measure_sam2_masks(masks, factor=5.95, step_number=10):
    """
    Calcula áreas y diagonales para máscaras SAM 2.

    factor:
    - nm por pixel para longitudes.
    - factor^2 para áreas.
    """
    measurements = []
    areas_nm2 = []
    diagonals_nm = []

    for mask in masks:
        segmentation = mask["segmentation"].astype(bool)
        area_px = float(np.sum(segmentation))
        area_nm2 = area_px * (float(factor) ** 2)

        diagonal = longest_diagonal_from_mask(segmentation)

        if diagonal is None:
            continue

        diagonal_nm = diagonal["length_px"] * float(factor)

        x, y, width, height = cv2.boundingRect(segmentation.astype(np.uint8))

        measurement = {
            "area_px": area_px,
            "area_nm2": area_nm2,
            "diagonal_px": diagonal["length_px"],
            "diagonal_nm": diagonal_nm,
            "bbox": [int(x), int(y), int(width), int(height)],
            "diagonal": diagonal,
        }

        measurements.append(measurement)
        areas_nm2.append(area_nm2)
        diagonals_nm.append(diagonal_nm)

    area_distribution = build_bins(areas_nm2, step_number)
    length_distribution = build_bins(diagonals_nm, step_number)

    return {
        "measurements": measurements,
        "areas_nm2": areas_nm2,
        "diagonals_nm": diagonals_nm,
        "area_distribution": area_distribution,
        "length_distribution": length_distribution,
    }


def draw_sam2_measurements(image_rgb, measurements):
    """
    Dibuja bounding boxes y diagonales sobre la imagen.
    """
    annotated_image = image_rgb.copy()

    for measurement in measurements:
        x, y, width, height = measurement["bbox"]
        diagonal = measurement["diagonal"]

        cv2.rectangle(
            annotated_image,
            (x, y),
            (x + width, y + height),
            (0, 0, 255),
            1,
        )

        cv2.line(
            annotated_image,
            (diagonal["x1"], diagonal["y1"]),
            (diagonal["x2"], diagonal["y2"]),
            (0, 255, 0),
            2,
        )

    return annotated_image


def save_summary_figure(
    annotated_image,
    area_distribution,
    length_distribution,
    output_path,
):
    """
    Genera una figura resumen con:
    - imagen anotada
    - distribución de áreas
    - distribución de longitudes
    """
    fig = plt.figure(figsize=(14, 12))

    ax_image = fig.add_subplot(2, 2, 1)
    ax_area = fig.add_subplot(2, 2, 3)
    ax_length = fig.add_subplot(2, 2, 4)

    ax_image.imshow(annotated_image)
    ax_image.set_title("TEM/SEM micrograph with nanoparticles")
    ax_image.axis("off")

    area_labels = area_distribution.get("labels", [])
    area_counts = area_distribution.get("counts", [])

    if area_labels and area_counts:
        ax_area.bar(area_labels, area_counts)
        ax_area.set_title("Areas of the Nanoparticles")
        ax_area.set_ylabel("Number of nanoparticles")
        ax_area.set_xlabel("Nanometers²")
        ax_area.tick_params(axis="x", rotation=45)
    else:
        ax_area.set_title("Areas of the Nanoparticles")
        ax_area.text(0.5, 0.5, "No data", ha="center", va="center")
        ax_area.axis("off")

    length_labels = length_distribution.get("labels", [])
    length_counts = length_distribution.get("counts", [])

    if length_labels and length_counts:
        ax_length.bar(length_labels, length_counts)
        ax_length.set_title("Lengths of the Nanoparticles")
        ax_length.set_ylabel("Number of nanoparticles")
        ax_length.set_xlabel("Nanometers")
        ax_length.tick_params(axis="x", rotation=45)
    else:
        ax_length.set_title("Lengths of the Nanoparticles")
        ax_length.text(0.5, 0.5, "No data", ha="center", va="center")
        ax_length.axis("off")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


class SAM2Analyzer:
    """
    Analizador SAM 2 integrado al backend.

    Este módulo combina:
    - SAM 2 real.
    - perfiles de hiperparámetros obtenidos por PSO.
    - filtros heredados del prototipo de Diego.
    - filtro morfológico.
    - medición, visualización y generación de métricas.
    """

    _model_cache = {}

    @staticmethod
    def _get_model(checkpoint_path, device):
        checkpoint_path = Path(checkpoint_path)

        if not checkpoint_path.exists():
            raise FileNotFoundError(
                f"No se encontró el checkpoint SAM 2: {checkpoint_path}"
            )

        model_cfg = SAM2_MODEL_CONFIG["model_cfg"]

        cache_key = (
            str(checkpoint_path.resolve()),
            model_cfg,
            str(device),
        )

        if cache_key not in SAM2Analyzer._model_cache:
            enable_runtime_optimizations()
            clear_torch_memory()

            sam2_model = build_sam2(
                model_cfg,
                str(checkpoint_path),
                device=device,
                apply_postprocessing=False,
            )

            SAM2Analyzer._model_cache[cache_key] = sam2_model

        return SAM2Analyzer._model_cache[cache_key]

    @staticmethod
    def _build_mask_generator(sam2_model, mask_generator_params):
        """
        Crea un generador nuevo por análisis.

        No se cachea el mask generator para evitar acumulación de memoria
        cuando el usuario cambia entre perfiles y modos de ejecución.
        """
        return SAM2AutomaticMaskGenerator(
            model=sam2_model,
            **mask_generator_params,
        )

    @staticmethod
    def _build_runtime_parameters(profile, parameters):
        parameters = parameters or {}

        mask_generator_params = dict(profile["mask_generator"])
        filter_params = dict(profile["filter"])

        mask_keys = set(mask_generator_params.keys())
        filter_keys = set(filter_params.keys())

        for key, value in parameters.items():
            if key in mask_keys and value is not None:
                mask_generator_params[key] = value

            if key in filter_keys and value is not None:
                filter_params[key] = value

        return mask_generator_params, filter_params

    @staticmethod
    def _build_memory_attempts(requested_max_image_size, points_per_batch):
        """
        Define intentos de ejecución ante errores de memoria.

        El primer intento usa el valor solicitado. Los siguientes reducen
        resolución y batch para intentar completar el análisis.
        """
        requested_max_image_size = int(requested_max_image_size)
        points_per_batch = int(points_per_batch)

        candidates = [
            {
                "max_image_size": requested_max_image_size,
                "points_per_batch": points_per_batch,
            },
            {
                "max_image_size": min(requested_max_image_size, 600),
                "points_per_batch": min(points_per_batch, 4),
            },
            {
                "max_image_size": min(requested_max_image_size, 500),
                "points_per_batch": min(points_per_batch, 2),
            },
        ]

        unique_attempts = []
        seen = set()

        for candidate in candidates:
            key = (
                candidate["max_image_size"],
                candidate["points_per_batch"],
            )

            if key not in seen:
                unique_attempts.append(candidate)
                seen.add(key)

        return unique_attempts

    @staticmethod
    def _generate_masks_with_memory_recovery(
        image_rgb,
        sam2_model,
        mask_generator_params,
        requested_max_image_size,
        original_width,
        original_height,
        device,
    ):
        """
        Ejecuta SAM 2 con recuperación ante CUDA out of memory.

        Si el primer intento falla, reduce max_image_size y points_per_batch.
        """
        points_per_batch = int(mask_generator_params.get("points_per_batch", 64))

        attempts = SAM2Analyzer._build_memory_attempts(
            requested_max_image_size=requested_max_image_size,
            points_per_batch=points_per_batch,
        )

        errors = []

        for attempt_index, attempt in enumerate(attempts, start=1):
            clear_torch_memory()

            attempt_mask_generator_params = dict(mask_generator_params)
            attempt_mask_generator_params["points_per_batch"] = attempt[
                "points_per_batch"
            ]

            sam2_image_rgb, scale_ratio = resize_image_for_sam2(
                image_rgb=image_rgb,
                max_image_size=attempt["max_image_size"],
            )

            mask_generator = None

            try:
                mask_generator = SAM2Analyzer._build_mask_generator(
                    sam2_model=sam2_model,
                    mask_generator_params=attempt_mask_generator_params,
                )

                use_autocast = device.type == "cuda"
                autocast_context = (
                    torch.autocast("cuda", dtype=torch.float16)
                    if use_autocast
                    else contextlib.nullcontext()
                )

                with torch.inference_mode():
                    with autocast_context:
                        raw_masks = mask_generator.generate(
                            sam2_image_rgb.copy()
                        )

                raw_masks = restore_masks_to_original_size(
                    masks=raw_masks,
                    original_width=original_width,
                    original_height=original_height,
                    scale_ratio=scale_ratio,
                )

                clear_torch_memory()

                return {
                    "raw_masks": raw_masks,
                    "sam2_image_rgb": sam2_image_rgb,
                    "scale_ratio": scale_ratio,
                    "effective_max_image_size": attempt["max_image_size"],
                    "effective_points_per_batch": attempt["points_per_batch"],
                    "effective_mask_generator_params": attempt_mask_generator_params,
                    "memory_fallback_used": attempt_index > 1,
                    "memory_attempt_index": attempt_index,
                    "memory_attempts": attempts,
                    "memory_errors": errors,
                }

            except RuntimeError as error:
                clear_torch_memory()

                if not is_cuda_out_of_memory(error):
                    raise

                errors.append(
                    {
                        "attempt_index": attempt_index,
                        "max_image_size": attempt["max_image_size"],
                        "points_per_batch": attempt["points_per_batch"],
                        "error": str(error),
                    }
                )

            finally:
                del mask_generator
                clear_torch_memory()

        raise RuntimeError(
            "SAM 2 se quedó sin memoria GPU incluso usando fallback. "
            "Prueba cerrar Flask, reiniciar la terminal o usar una imagen menor."
        )

    @staticmethod
    def analyze(
        image_path,
        output_dir,
        checkpoint_path,
        profile_name=None,
        overlap_level=None,
        factor=5.95,
        step_number=10,
        pixel_threshold=140,
        filter_with_legacy_rules=True,
        parameters=None,
    ):
        """
        Ejecuta SAM 2 sobre una micrografía y guarda los resultados.
        """
        parameters = parameters or {}

        image_path = Path(image_path)
        output_dir = Path(output_dir)
        checkpoint_path = Path(checkpoint_path)

        output_dir.mkdir(parents=True, exist_ok=True)

        image_bgr = read_image_bgr(image_path)

        if image_bgr is None:
            raise ValueError(f"No se pudo abrir la imagen: {image_path}")

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        original_height, original_width = image_rgb.shape[:2]

        requested_max_image_size = int(parameters.get("max_image_size", 700))

        selected_profile_name = parameters.get("sam2_profile", profile_name)
        selected_overlap_level = parameters.get("overlap_level", overlap_level)

        profile = get_sam2_profile(
            profile_name=selected_profile_name,
            overlap_level=selected_overlap_level,
        )

        mask_generator_params, filter_params = SAM2Analyzer._build_runtime_parameters(
            profile=profile,
            parameters=parameters,
        )

        device = get_device()

        sam2_model = SAM2Analyzer._get_model(
            checkpoint_path=checkpoint_path,
            device=device,
        )

        generation_result = SAM2Analyzer._generate_masks_with_memory_recovery(
            image_rgb=image_rgb,
            sam2_model=sam2_model,
            mask_generator_params=mask_generator_params,
            requested_max_image_size=requested_max_image_size,
            original_width=original_width,
            original_height=original_height,
            device=device,
        )

        raw_masks = generation_result["raw_masks"]
        sam2_image_rgb = generation_result["sam2_image_rgb"]
        scale_ratio = generation_result["scale_ratio"]

        effective_mask_generator_params = generation_result[
            "effective_mask_generator_params"
        ]

        masks_after_legacy_filters = raw_masks

        if filter_with_legacy_rules:
            masks_after_legacy_filters = filter_masks(
                raw_masks,
                image_rgb,
                pixel_threshold=pixel_threshold,
            )

        profile_min_area_px = int(
            effective_mask_generator_params["min_mask_region_area"]
        )

        if scale_ratio != 1.0:
            effective_min_area_px = int(
                max(1, profile_min_area_px / (scale_ratio * scale_ratio))
            )
        else:
            effective_min_area_px = profile_min_area_px

        valid_masks, rejected_by_morphology = filter_sam2_particle_masks(
            masks=masks_after_legacy_filters,
            min_area_px=effective_min_area_px,
            max_area_px=parameters.get("max_area_px"),
            max_area_factor=float(filter_params.get("max_area_factor", 12.0)),
            min_circularity=float(filter_params.get("min_circularity", 0.45)),
            max_aspect_ratio=float(filter_params.get("max_aspect_ratio", 1.80)),
            min_solidity=float(filter_params.get("min_solidity", 0.80)),
            iou_threshold=float(filter_params.get("iou_threshold", 0.65)),
            mode=filter_params.get("mode", "filtered"),
        )

        measurement_result = measure_sam2_masks(
            valid_masks,
            factor=factor,
            step_number=step_number,
        )

        measurements = measurement_result["measurements"]
        annotated_image = draw_sam2_measurements(image_rgb, measurements)

        annotated_bgr = cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR)

        output_stem = f"{image_path.stem}_sam2_{profile['profile_name']}"

        annotated_path = output_dir / f"{output_stem}_annotated.png"
        summary_path = output_dir / f"{output_stem}_summary.png"
        metrics_path = output_dir / f"{output_stem}_metrics.json"

        write_image(annotated_path, annotated_bgr)

        save_summary_figure(
            annotated_image=annotated_image,
            area_distribution=measurement_result["area_distribution"],
            length_distribution=measurement_result["length_distribution"],
            output_path=summary_path,
        )

        rejected_by_legacy_count = len(raw_masks) - len(masks_after_legacy_filters)
        rejected_by_morphology_count = len(rejected_by_morphology)
        total_rejected_count = len(raw_masks) - len(valid_masks)

        metrics = {
            "model_name": "SAM2",
            "sam2_model_name": SAM2_MODEL_CONFIG["model_name"],
            "profile_name": profile["profile_name"],
            "overlap_level": profile.get("overlap_level"),
            "profile_description": profile.get("description"),
            "particle_count": len(valid_masks),
            "total_masks": len(raw_masks),
            "masks_after_legacy_filters": len(masks_after_legacy_filters),
            "valid_masks": len(valid_masks),
            "rejected_masks": total_rejected_count,
            "rejected_by_legacy_filters": rejected_by_legacy_count,
            "rejected_by_morphology": rejected_by_morphology_count,
            "factor": factor,
            "step_number": step_number,
            "pixel_threshold": pixel_threshold,
            "requested_max_image_size": requested_max_image_size,
            "max_image_size": generation_result["effective_max_image_size"],
            "sam2_scale_ratio": scale_ratio,
            "original_image_size": [original_width, original_height],
            "sam2_runtime_image_size": [
                int(sam2_image_rgb.shape[1]),
                int(sam2_image_rgb.shape[0]),
            ],
            "profile_min_area_px": profile_min_area_px,
            "effective_min_area_px": effective_min_area_px,
            "filter_with_legacy_rules": filter_with_legacy_rules,
            "mask_generator_params": effective_mask_generator_params,
            "filter_params": filter_params,
            "memory_fallback_used": generation_result["memory_fallback_used"],
            "memory_attempt_index": generation_result["memory_attempt_index"],
            "memory_attempts": generation_result["memory_attempts"],
            "memory_errors": generation_result["memory_errors"],
            "areas_nm2": measurement_result["areas_nm2"],
            "diagonals_nm": measurement_result["diagonals_nm"],
            "area_distribution": measurement_result["area_distribution"],
            "length_distribution": measurement_result["length_distribution"],
            "annotated_image_path": str(annotated_path),
            "summary_figure_path": str(summary_path),
            "metrics_path": str(metrics_path),
        }

        metrics_path.write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        clear_torch_memory()

        return {
            "metrics": metrics,
            "annotated_image_path": str(annotated_path),
            "summary_figure_path": str(summary_path),
            "metrics_path": str(metrics_path),
            "profile": profile,
        }