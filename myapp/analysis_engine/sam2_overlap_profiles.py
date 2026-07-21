from copy import deepcopy


SAM2_MODEL_CONFIG = {
    "model_cfg": "configs/sam2.1/sam2.1_hiera_l.yaml",
    "checkpoint_filename": "sam2.1_hiera_large.pt",
    "model_name": "sam2.1_hiera_large",
}


SAM2_FILTER_DEFAULTS = {
    "mode": "filtered",
    "max_area_factor": 8.0,
    "min_circularity": 0.72,
    "max_aspect_ratio": 1.30,
    "min_solidity": 0.90,
    "iou_threshold": 0.65,
}


SAM2_SHARED_GENERATOR_PARAMS = {
    "points_per_batch": 64,
    "stability_score_offset": 0.5,
    "crop_n_layers": 0,
    "crop_n_points_downscale_factor": 2,
    "use_m2m": True,
}


SAM2_MASK_GENERATOR_DEFAULT = {
    **SAM2_SHARED_GENERATOR_PARAMS,
    "points_per_side": 32,
    "pred_iou_thresh": 0.88,
    "stability_score_thresh": 0.95,
    "min_mask_region_area": 88,
    "box_nms_thresh": 0.7,
}


SAM2_OVERLAP_PROFILES = {
    "default": {
        "description": "SAM 2 default baseline profile.",
        "overlap_level": None,
        "mask_generator": SAM2_MASK_GENERATOR_DEFAULT,
        "filter": SAM2_FILTER_DEFAULTS,
    },
    "0": {
        "description": (
            "Optimal SAM 2 hyperparameter profile obtained by PSO "
            "for 0% particle overlap."
        ),
        "overlap_level": 0,
        "mask_generator": {
            **SAM2_SHARED_GENERATOR_PARAMS,
            "points_per_side": 60,
            "pred_iou_thresh": 0.824,
            "stability_score_thresh": 0.915,
            "min_mask_region_area": 88,
            "box_nms_thresh": 0.594,
        },
        "filter": SAM2_FILTER_DEFAULTS,
    },
    "15": {
        "description": (
            "Optimal SAM 2 hyperparameter profile obtained by PSO "
            "for 15% particle overlap."
        ),
        "overlap_level": 15,
        "mask_generator": {
            **SAM2_SHARED_GENERATOR_PARAMS,
            "points_per_side": 63,
            "pred_iou_thresh": 0.801,
            "stability_score_thresh": 0.951,
            "min_mask_region_area": 149,
            "box_nms_thresh": 0.543,
        },
        "filter": SAM2_FILTER_DEFAULTS,
    },
    "30": {
        "description": (
            "Optimal SAM 2 hyperparameter profile obtained by PSO "
            "for 30% particle overlap."
        ),
        "overlap_level": 30,
        "mask_generator": {
            **SAM2_SHARED_GENERATOR_PARAMS,
            "points_per_side": 53,
            "pred_iou_thresh": 0.818,
            "stability_score_thresh": 0.923,
            "min_mask_region_area": 121,
            "box_nms_thresh": 0.467,
        },
        "filter": SAM2_FILTER_DEFAULTS,
    },
    "45": {
        "description": (
            "Optimal SAM 2 hyperparameter profile obtained by PSO "
            "for 45% particle overlap."
        ),
        "overlap_level": 45,
        "mask_generator": {
            **SAM2_SHARED_GENERATOR_PARAMS,
            "points_per_side": 61,
            "pred_iou_thresh": 0.813,
            "stability_score_thresh": 0.928,
            "min_mask_region_area": 131,
            "box_nms_thresh": 0.684,
        },
        "filter": SAM2_FILTER_DEFAULTS,
    },
    "60": {
        "description": (
            "Optimal SAM 2 hyperparameter profile obtained by PSO "
            "for 60% particle overlap."
        ),
        "overlap_level": 60,
        "mask_generator": {
            **SAM2_SHARED_GENERATOR_PARAMS,
            "points_per_side": 51,
            "pred_iou_thresh": 0.815,
            "stability_score_thresh": 0.917,
            "min_mask_region_area": 135,
            "box_nms_thresh": 0.602,
        },
        "filter": SAM2_FILTER_DEFAULTS,
    },
}


def normalize_profile_name(profile_name=None, overlap_level=None):
    """
    Normaliza el nombre del perfil solicitado.

    Perfiles disponibles:
    - default
    - 0
    - 15
    - 30
    - 45
    - 60

    También acepta valores como:
    - "0%"
    - "15%"
    - "30%"
    - "45%"
    - "60%"
    """
    selected_value = profile_name

    if selected_value is None or str(selected_value).strip() == "":
        selected_value = overlap_level

    if selected_value is None or str(selected_value).strip() == "":
        return "60"

    normalized_name = str(selected_value).strip().lower()
    normalized_name = normalized_name.replace("%", "")
    normalized_name = normalized_name.replace("overlap_", "")
    normalized_name = normalized_name.replace("overlap-", "")
    normalized_name = normalized_name.replace("overlap", "")
    normalized_name = normalized_name.strip()

    return normalized_name


def get_available_sam2_profiles():
    """
    Retorna los perfiles disponibles para SAM 2.
    """
    return sorted(SAM2_OVERLAP_PROFILES.keys())


def get_sam2_profile(profile_name=None, overlap_level=None):
    """
    Obtiene un perfil de configuración SAM 2.

    Retorna una copia para evitar modificar los perfiles globales.
    """
    normalized_name = normalize_profile_name(
        profile_name=profile_name,
        overlap_level=overlap_level,
    )

    if normalized_name not in SAM2_OVERLAP_PROFILES:
        available_profiles = ", ".join(get_available_sam2_profiles())
        raise ValueError(
            f"SAM 2 profile '{normalized_name}' is not available. "
            f"Available profiles: {available_profiles}"
        )

    profile = deepcopy(SAM2_OVERLAP_PROFILES[normalized_name])
    profile["profile_name"] = normalized_name

    return profile


def get_sam2_mask_generator_params(profile_name=None, overlap_level=None):
    """
    Obtiene únicamente los parámetros para SAM2AutomaticMaskGenerator.
    """
    profile = get_sam2_profile(
        profile_name=profile_name,
        overlap_level=overlap_level,
    )

    return deepcopy(profile["mask_generator"])


def get_sam2_filter_params(profile_name=None, overlap_level=None):
    """
    Obtiene únicamente los parámetros del filtro morfológico.
    """
    profile = get_sam2_profile(
        profile_name=profile_name,
        overlap_level=overlap_level,
    )

    return deepcopy(profile["filter"])