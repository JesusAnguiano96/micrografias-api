import math

import cv2
import numpy as np


def longest_diagonal_from_mask(mask):
    """
    Calcula la diagonal más larga de una máscara.

    Usa el contorno externo de la máscara y busca los dos puntos más lejanos.
    Esto aproxima el diámetro máximo de la nanopartícula.
    """
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
    """
    Construye intervalos para graficar distribuciones.

    Se usa para:
    - áreas
    - longitudes/diámetros
    """
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

    filtered_labels = []
    filtered_counts = []

    for label, count in zip(labels, counts):
        if count > 0:
            filtered_labels.append(label)
            filtered_counts.append(count)

    return filtered_labels, filtered_counts


def measure_masks(masks, factor=5.95):
    """
    Calcula métricas geométricas para cada máscara válida.

    Retorna una lista de mediciones con:
    - área convertida
    - diagonal convertida
    - par de puntos de la diagonal
    - bounding box
    """
    measurements = []

    for ann in masks:
        bbox = ann["bbox"]
        area_px = ann["area"]
        area_nm2 = int(area_px * factor)

        distance_px, diagonal_pair = longest_diagonal_from_mask(
            ann["segmentation"]
        )

        diagonal_nm = None

        if diagonal_pair:
            diagonal_nm = round(distance_px * factor)

        measurements.append({
            "mask": ann,
            "bbox": bbox,
            "area_nm2": area_nm2,
            "diagonal_nm": diagonal_nm,
            "diagonal_pair": diagonal_pair,
        })

    return measurements