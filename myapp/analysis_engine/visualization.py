import cv2


def draw_measurements(image_rgb, measurements):
    """
    Dibuja sobre la micrografía:
    - bounding boxes
    - diagonal máxima de cada nanopartícula

    Mantiene el estilo visual del prototipo de Diego.
    """
    annotated_image = image_rgb.copy()

    for measurement in measurements:
        bbox = measurement["bbox"]
        diagonal_pair = measurement["diagonal_pair"]

        if diagonal_pair:
            point_a, point_b = diagonal_pair
            cv2.line(
                annotated_image,
                point_a,
                point_b,
                (0, 255, 0),
                2
            )

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

    return annotated_image