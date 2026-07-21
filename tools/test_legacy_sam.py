import argparse
import json
import math
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import torch
from matplotlib import gridspec
from matplotlib.ticker import MaxNLocator
from segment_anything import SamAutomaticMaskGenerator, sam_model_registry


def remove_containers(anns, min_height):
    candidate_anns = [ann for ann in anns if ann["bbox"][1] < min_height]
    filtered_anns = []

    for i in range(len(candidate_anns)):
        counter = 0
        keep_mask = True

        x_container = candidate_anns[i]["bbox"][0]
        y_container = candidate_anns[i]["bbox"][1]
        width_container = candidate_anns[i]["bbox"][2]
        height_container = candidate_anns[i]["bbox"][3]

        for j in range(i + 1, len(candidate_anns)):
            x_contained = candidate_anns[j]["bbox"][0]
            y_contained = candidate_anns[j]["bbox"][1]
            width_contained = candidate_anns[j]["bbox"][2]
            height_contained = candidate_anns[j]["bbox"][3]

            is_inside = (
                x_contained >= x_container - 5
                and (x_contained + width_contained)
                <= (x_container + width_container + 5)
                and y_contained >= y_container - 5
                and (y_contained + height_contained)
                <= (y_container + height_container + 5)
            )

            if is_inside:
                counter += 1

                if counter == 2:
                    keep_mask = False
                    break

        if keep_mask:
            filtered_anns.append(candidate_anns[i])

    return filtered_anns


def remove_by_pixel_value(anns, image_rgb, threshold=140):
    filtered_anns = []

    height_image, width_image = image_rgb.shape[:2]

    for ann in anns:
        x = int(ann["bbox"][0])
        y = int(ann["bbox"][1])
        width = int(ann["bbox"][2])
        height = int(ann["bbox"][3])

        x_start = max(0, x)
        y_start = max(0, y)
        x_end = min(width_image - 1, x + width)
        y_end = min(height_image - 1, y + height)

        if x_end <= x_start or y_end <= y_start:
            continue

        horizontal_y = min(height_image - 1, y_start + height // 2)
        vertical_x = min(width_image - 1, x_start + width // 2)

        average_pixel_value = 0
        pixel_counter = 0

        for pixel_x in range(x_start, x_end):
            r, g, b = image_rgb[horizontal_y, pixel_x]
            pixel_value = (int(r) + int(g) + int(b)) // 3
            average_pixel_value += pixel_value
            pixel_counter += 1

        for pixel_y in range(y_start, y_end):
            r, g, b = image_rgb[pixel_y, vertical_x]
            pixel_value = (int(r) + int(g) + int(b)) // 3
            average_pixel_value += pixel_value
            pixel_counter += 1

        if pixel_counter == 0:
            continue

        average_pixel_value /= pixel_counter

        if average_pixel_value < threshold:
            filtered_anns.append(ann)

    return filtered_anns


def detect_bottom_metadata_bar(sorted_anns, image_rgb):
    height_image, width_image = image_rgb.shape[:2]
    min_height = height_image

    for ann in sorted_anns:
        bbox = ann["bbox"]

        starts_near_left = bbox[0] < 10
        is_in_bottom_zone = bbox[1] > (height_image * 0.70)
        is_wide = bbox[2] > (width_image * 0.70)
        is_not_too_tall = bbox[3] < (height_image * 0.30)

        if starts_near_left and is_in_bottom_zone and is_wide and is_not_too_tall:
            min_height = int(bbox[1])

    return min_height


def longest_diagonal_from_mask(mask):
    binary_mask = np.uint8(mask)

    contours, _ = cv2.findContours(
        binary_mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    best_distance = 0
    best_pair = None

    for contour in contours:
        if len(contour) < 2:
            continue

        hull = cv2.convexHull(contour)
        points = hull.reshape(-1, 2)

        if len(points) < 2:
            continue

        max_points = 400

        if len(points) > max_points:
            step = math.ceil(len(points) / max_points)
            points = points[::step]

        diff = points[:, None, :] - points[None, :, :]
        distances = np.sqrt(np.sum(diff * diff, axis=2))

        max_index = np.unravel_index(np.argmax(distances), distances.shape)
        distance = float(distances[max_index])

        if distance > best_distance:
            best_distance = distance
            point_a = tuple(points[max_index[0]].astype(int))
            point_b = tuple(points[max_index[1]].astype(int))
            best_pair = (point_a, point_b)

    return best_distance, best_pair


def build_bins(values, number_of_bins):
    if not values:
        return [], []

    min_value = min(values)
    max_value = max(values)

    if min_value == max_value:
        return [f"{int(min_value)} to {int(max_value)}"], [len(values)]

    ranges = np.linspace(min_value, max_value, number_of_bins + 1)

    counts = []
    labels = []

    for i in range(len(ranges) - 1):
        if i == len(ranges) - 2:
            values_in_range = [
                value for value in values
                if ranges[i] <= value <= ranges[i + 1]
            ]
        else:
            values_in_range = [
                value for value in values
                if ranges[i] <= value < ranges[i + 1]
            ]

        counts.append(len(values_in_range))
        labels.append(f"{int(ranges[i])} to {int(ranges[i + 1])}")

    filtered_counts = []
    filtered_labels = []

    for label, count in zip(labels, counts):
        if count > 0:
            filtered_labels.append(label)
            filtered_counts.append(count)

    return filtered_labels, filtered_counts


def analyze_masks(masks, image_rgb, factor, step_number, pixel_threshold):
    if not masks:
        return {
            "annotated_image": image_rgb.copy(),
            "valid_masks": [],
            "areas": [],
            "diagonals": [],
            "area_labels": [],
            "area_counts": [],
            "length_labels": [],
            "length_counts": [],
        }

    sorted_anns = sorted(masks, key=lambda x: x["area"], reverse=True)

    min_height = detect_bottom_metadata_bar(sorted_anns, image_rgb)

    filtered_anns = remove_containers(sorted_anns, min_height)
    filtered_anns = remove_by_pixel_value(
        filtered_anns,
        image_rgb,
        threshold=pixel_threshold
    )

    annotated_image = image_rgb.copy()

    areas_nm2 = []
    diagonals_nm = []

    for ann in filtered_anns:
        bbox = ann["bbox"]
        area_px = ann["area"]
        area_nm2 = int(area_px * factor)

        distance_px, diagonal_pair = longest_diagonal_from_mask(ann["segmentation"])

        if diagonal_pair:
            pt1, pt2 = diagonal_pair
            diagonal_nm = round(distance_px * factor)
            diagonals_nm.append(diagonal_nm)
            cv2.line(annotated_image, pt1, pt2, (0, 255, 0), 2)

        x = int(bbox[0])
        y = int(bbox[1])
        width = int(bbox[2])
        height = int(bbox[3])

        cv2.rectangle(
            annotated_image,
            (x, y),
            (x + width, y + height),
            color=(0, 0, 255),
            thickness=1
        )

        areas_nm2.append(area_nm2)

    area_labels, area_counts = build_bins(areas_nm2, step_number)
    length_labels, length_counts = build_bins(diagonals_nm, step_number)

    return {
        "annotated_image": annotated_image,
        "valid_masks": filtered_anns,
        "areas": areas_nm2,
        "diagonals": diagonals_nm,
        "area_labels": area_labels,
        "area_counts": area_counts,
        "length_labels": length_labels,
        "length_counts": length_counts,
    }


def save_summary_figure(
    annotated_image,
    area_labels,
    area_counts,
    length_labels,
    length_counts,
    output_path
):
    fig = plt.figure(figsize=(10, 10))
    gs = gridspec.GridSpec(2, 2, figure=fig)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0])
    ax3 = fig.add_subplot(gs[1, 1])
    ax4 = fig.add_subplot(gs[0, 1])

    ax4.axis("off")

    ax1.set_title("TEM micrograph with Nanoparticles")
    ax1.imshow(annotated_image)
    ax1.set_yticklabels([])
    ax1.set_xticklabels([])

    ax2.set_title("Areas of the Nanoparticles")

    if area_labels and area_counts:
        ax2.bar(x=area_labels, height=area_counts)
        ax2.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax2.set_xticklabels(area_labels, rotation=45, ha="right", fontsize=9)

    ax2.set_ylabel("Number of nanoparticles")
    ax2.set_xlabel("Nanometers²")

    ax3.set_title("Lengths of the Nanoparticles")

    if length_labels and length_counts:
        ax3.bar(x=length_labels, height=length_counts)
        ax3.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax3.set_xticklabels(ax3.get_xticklabels(), rotation=45, ha="right", fontsize=9)

    ax3.set_ylabel("Number of nanoparticles")
    ax3.set_xlabel("Nanometers")

    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def load_sam_model(checkpoint_path, model_type, device):
    sam = sam_model_registry[model_type](checkpoint=str(checkpoint_path))
    sam.to(device=device)

    return SamAutomaticMaskGenerator(
        model=sam,
        points_per_side=44,
        pred_iou_thresh=0.85,
        stability_score_thresh=0.97,
        crop_n_layers=1,
        crop_n_points_downscale_factor=2,
        min_mask_region_area=1000,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Prueba local de SAM clásico con visualización estilo Diego."
    )

    parser.add_argument(
        "--image",
        required=True,
        help="Ruta de la micrografía a analizar."
    )

    parser.add_argument(
        "--checkpoint",
        default="checkpoints/sam_vit_h_4b8939.pth",
        help="Ruta del checkpoint de SAM."
    )

    parser.add_argument(
        "--model-type",
        default="vit_h",
        choices=["vit_h", "vit_l", "vit_b"],
        help="Tipo de modelo SAM."
    )

    parser.add_argument(
        "--factor",
        type=float,
        default=5.95,
        help="Factor de conversión usado por el prototipo de Diego."
    )

    parser.add_argument(
        "--step-number",
        type=int,
        default=10,
        help="Número de intervalos para las gráficas."
    )

    parser.add_argument(
        "--pixel-threshold",
        type=int,
        default=140,
        help="Umbral de intensidad para conservar partículas oscuras."
    )

    args = parser.parse_args()

    image_path = Path(args.image)
    checkpoint_path = Path(args.checkpoint)
    output_dir = Path("outputs") / "sam_legacy"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not image_path.exists():
        raise FileNotFoundError(f"No se encontró la imagen: {image_path}")

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"No se encontró el checkpoint: {checkpoint_path}")

    device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"Dispositivo: {device}")
    print(f"Modelo: {args.model_type}")
    print(f"Checkpoint: {checkpoint_path}")
    print(f"Imagen: {image_path}")

    image_bgr = cv2.imread(str(image_path))

    if image_bgr is None:
        raise ValueError(f"No se pudo abrir la imagen: {image_path}")

    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    print("Cargando SAM...")
    mask_generator = load_sam_model(
        checkpoint_path=checkpoint_path,
        model_type=args.model_type,
        device=device
    )

    print("Generando máscaras...")
    masks = mask_generator.generate(image_rgb)

    print(f"Máscaras totales generadas por SAM: {len(masks)}")

    print("Aplicando filtros, bounding boxes y diagonales...")
    analysis_data = analyze_masks(
        masks=masks,
        image_rgb=image_rgb,
        factor=args.factor,
        step_number=args.step_number,
        pixel_threshold=args.pixel_threshold
    )

    stem = image_path.stem

    annotated_path = output_dir / f"{stem}_sam_vit_h_annotated.png"
    summary_path = output_dir / f"{stem}_sam_vit_h_summary.png"
    metrics_path = output_dir / f"{stem}_sam_vit_h_metrics.json"

    annotated_bgr = cv2.cvtColor(analysis_data["annotated_image"], cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(annotated_path), annotated_bgr)

    save_summary_figure(
        annotated_image=analysis_data["annotated_image"],
        area_labels=analysis_data["area_labels"],
        area_counts=analysis_data["area_counts"],
        length_labels=analysis_data["length_labels"],
        length_counts=analysis_data["length_counts"],
        output_path=summary_path
    )

    metrics = {
        "image": str(image_path),
        "model_type": args.model_type,
        "checkpoint": str(checkpoint_path),
        "device": device,
        "total_masks": len(masks),
        "valid_masks": len(analysis_data["valid_masks"]),
        "rejected_masks": len(masks) - len(analysis_data["valid_masks"]),
        "particle_count": len(analysis_data["valid_masks"]),
        "areas_nm2": analysis_data["areas"],
        "diagonals_nm": analysis_data["diagonals"],
        "area_distribution": {
            "labels": analysis_data["area_labels"],
            "counts": analysis_data["area_counts"],
        },
        "length_distribution": {
            "labels": analysis_data["length_labels"],
            "counts": analysis_data["length_counts"],
        },
        "annotated_image_path": str(annotated_path),
        "summary_figure_path": str(summary_path),
    }

    metrics_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Listo.")
    print(f"Imagen anotada: {annotated_path}")
    print(f"Figura resumen: {summary_path}")
    print(f"Métricas JSON: {metrics_path}")
    print(f"Conteo final de partículas: {metrics['particle_count']}")


if __name__ == "__main__":
    main()