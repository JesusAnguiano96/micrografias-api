import cv2
import numpy as np


def mask_to_contour(segmentation):
    """
    Obtiene el contorno principal de una máscara binaria.

    La máscara puede venir como bool, uint8 o cualquier arreglo compatible.
    """
    segmentation_u8 = segmentation.astype(np.uint8)

    contours, _ = cv2.findContours(
        segmentation_u8,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if len(contours) == 0:
        return None

    return max(contours, key=cv2.contourArea)


def shape_features(segmentation):
    """
    Calcula características morfológicas de una máscara.

    Características:
    - área
    - circularidad
    - relación de aspecto
    - solidez
    - bounding box
    """
    contour = mask_to_contour(segmentation)

    if contour is None:
        return None

    area = float(cv2.contourArea(contour))

    if area <= 0:
        return None

    perimeter = float(cv2.arcLength(contour, True))

    if perimeter <= 0:
        return None

    circularity = (4.0 * np.pi * area) / ((perimeter * perimeter) + 1e-9)

    x, y, width, height = cv2.boundingRect(contour)

    aspect_ratio_raw = float(width) / float(height + 1e-9)
    aspect_ratio = max(aspect_ratio_raw, 1.0 / aspect_ratio_raw)

    hull = cv2.convexHull(contour)
    hull_area = float(cv2.contourArea(hull)) + 1e-9
    solidity = area / hull_area

    return {
        "area": area,
        "circularity": circularity,
        "aspect_ratio": aspect_ratio,
        "solidity": solidity,
        "bbox": [int(x), int(y), int(width), int(height)],
    }


def mask_iou(mask_a, mask_b):
    """
    Calcula el IoU entre dos máscaras SAM/SAM 2.

    Las máscaras deben tener la llave:
    - segmentation
    """
    segmentation_a = mask_a["segmentation"].astype(bool)
    segmentation_b = mask_b["segmentation"].astype(bool)

    intersection = np.logical_and(segmentation_a, segmentation_b).sum()
    union = np.logical_or(segmentation_a, segmentation_b).sum()

    if union == 0:
        return 0.0

    return float(intersection) / float(union)


def deduplicate_masks(masks, iou_threshold=0.65):
    """
    Elimina máscaras duplicadas o muy solapadas.

    Conserva primero las máscaras con mejor:
    - predicted_iou
    - stability_score
    - menor área cuando hay empate
    """
    if len(masks) <= 1:
        return masks

    sorted_masks = sorted(
        masks,
        key=lambda mask: (
            float(mask.get("predicted_iou", 0.0)),
            float(mask.get("stability_score", 0.0)),
            -float(mask.get("area", 0.0)),
        ),
        reverse=True,
    )

    kept_masks = []

    for mask in sorted_masks:
        is_duplicate = False

        for kept_mask in kept_masks:
            if mask_iou(mask, kept_mask) > iou_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            kept_masks.append(mask)

    return kept_masks


def is_valid_particle_mask(
    mask,
    min_area_px,
    max_area_px=None,
    min_circularity=0.72,
    max_aspect_ratio=1.30,
    min_solidity=0.90,
):
    """
    Determina si una máscara corresponde a una partícula esférica válida.

    Este filtro proviene del prototipo SAM 2 con filtrado morfológico.
    """
    if max_area_px is None:
        max_area_px = 1e18

    segmentation = mask["segmentation"].astype(bool)
    features = shape_features(segmentation)

    if features is None:
        return False, None

    if not (min_area_px <= features["area"] <= max_area_px):
        return False, features

    if features["circularity"] < min_circularity:
        return False, features

    if features["aspect_ratio"] > max_aspect_ratio:
        return False, features

    if features["solidity"] < min_solidity:
        return False, features

    return True, features


def filter_sam2_particle_masks(
    masks,
    min_area_px,
    max_area_px=None,
    max_area_factor=8.0,
    min_circularity=0.72,
    max_aspect_ratio=1.30,
    min_solidity=0.90,
    iou_threshold=0.65,
    mode="filtered",
):
    """
    Filtra las máscaras generadas por SAM 2.

    Modos:
    - pure: filtra solo por área.
    - filtered: filtra por área, circularidad, aspect ratio y solidez.

    Retorna:
    - valid_masks
    - rejected_masks
    """
    if max_area_px is None:
        max_area_px = float(min_area_px) * float(max_area_factor)

    valid_masks = []
    rejected_masks = []

    for mask in masks:
        mask_copy = dict(mask)

        if "segmentation" not in mask_copy:
            rejected_masks.append(mask_copy)
            continue

        segmentation = mask_copy["segmentation"].astype(bool)

        features = shape_features(segmentation)

        if features:
            mask_copy["shape_features"] = features
            mask_copy["bbox"] = features["bbox"]

        if mode == "pure":
            area = float(mask_copy.get("area", 0.0))

            if min_area_px <= area <= max_area_px:
                valid_masks.append(mask_copy)
            else:
                rejected_masks.append(mask_copy)

            continue

        is_valid, features = is_valid_particle_mask(
            mask_copy,
            min_area_px=min_area_px,
            max_area_px=max_area_px,
            min_circularity=min_circularity,
            max_aspect_ratio=max_aspect_ratio,
            min_solidity=min_solidity,
        )

        if features:
            mask_copy["shape_features"] = features
            mask_copy["bbox"] = features["bbox"]

        if is_valid:
            valid_masks.append(mask_copy)
        else:
            rejected_masks.append(mask_copy)

    valid_masks = deduplicate_masks(
        valid_masks,
        iou_threshold=iou_threshold
    )

    return valid_masks, rejected_masks


def count_valid_sam2_particles(
    masks,
    min_area_px,
    max_area_px=None,
    max_area_factor=8.0,
    min_circularity=0.72,
    max_aspect_ratio=1.30,
    min_solidity=0.90,
    iou_threshold=0.65,
    mode="filtered",
):
    """
    Cuenta partículas válidas después del filtrado morfológico.
    """
    valid_masks, _ = filter_sam2_particle_masks(
        masks=masks,
        min_area_px=min_area_px,
        max_area_px=max_area_px,
        max_area_factor=max_area_factor,
        min_circularity=min_circularity,
        max_aspect_ratio=max_aspect_ratio,
        min_solidity=min_solidity,
        iou_threshold=iou_threshold,
        mode=mode,
    )

    return len(valid_masks)