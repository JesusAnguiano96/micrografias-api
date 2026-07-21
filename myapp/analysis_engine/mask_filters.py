def detect_bottom_metadata_bar(sorted_anns, image_rgb):
    """
    Detecta la franja inferior de metadatos de la micrografía.

    Esta franja suele contener texto como:
    JEOL 1010, Mag, escala, barra de referencia, etc.

    La función busca una región grande, ancha y ubicada en la parte inferior.
    """
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


def remove_containers(anns, min_height):
    """
    Elimina máscaras contenedoras.

    Primero descarta las máscaras que están por debajo de la franja útil
    de la imagen. Después elimina regiones grandes que contienen otras
    máscaras internas.
    """
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
    """
    Conserva principalmente regiones oscuras.

    En micrografías TEM/SEM, las nanopartículas suelen aparecer oscuras
    sobre un fondo más claro. Este filtro calcula un promedio de intensidad
    en el centro horizontal y vertical del bounding box.
    """
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


def filter_masks(masks, image_rgb, pixel_threshold=140):
    """
    Aplica el flujo de filtrado heredado del prototipo SAM clásico.

    Flujo:
    1. Ordenar máscaras por área.
    2. Detectar barra inferior de texto/escala.
    3. Eliminar regiones debajo de esa barra.
    4. Eliminar máscaras contenedoras.
    5. Filtrar por intensidad de píxel.
    """
    if not masks:
        return []

    sorted_anns = sorted(masks, key=lambda item: item["area"], reverse=True)
    min_height = detect_bottom_metadata_bar(sorted_anns, image_rgb)

    filtered_anns = remove_containers(sorted_anns, min_height)
    filtered_anns = remove_by_pixel_value(
        filtered_anns,
        image_rgb,
        threshold=pixel_threshold
    )

    return filtered_anns