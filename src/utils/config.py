import os
import yaml
from typing import Any, Dict

def deep_merge(base: Dict[Any, Any], override: Dict[Any, Any]) -> Dict[Any, Any]:
    """Recursively merges override dict into base."""
    for key, value in override.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base

def load_config(config_path: str | None = None) -> Dict[str, Any]:
    """
    Loads and merges config layers (lowest → highest priority):
    1. config/config_default.yaml   (committed defaults)
    2. config/config_local.yaml     (gitignored user overrides)
    3. --config / MOWBOT_GUI_CONFIG (external file override)
    4. MOWBOT_* environment variables
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    default_path = os.path.join(base_dir, "config", "config_default.yaml")
    local_path = os.path.join(base_dir, "config", "config_local.yaml")

    # 1. Load Defaults
    if not os.path.exists(default_path):
        config = {
            "general": {"manufacturer": "MowbotTech", "serial_number": "mowbot_001"},
            "broker": {"host": "localhost", "port": 1883, "use_tls": False}
        }
    else:
        with open(default_path, "r") as f:
            config = yaml.safe_load(f) or {}

    # 2. Merge Local Overrides
    if os.path.exists(local_path):
        with open(local_path, "r") as f:
            local_config = yaml.safe_load(f) or {}
            config = deep_merge(config, local_config)

    # 3. External config file (--config flag > MOWBOT_GUI_CONFIG env var)
    ext_path = config_path or os.getenv("MOWBOT_GUI_CONFIG")
    if ext_path:
        ext_path = os.path.expanduser(ext_path)
        if not os.path.isfile(ext_path):
            raise FileNotFoundError(f"Config file not found: {ext_path}")
        with open(ext_path, "r") as f:
            ext_config = yaml.safe_load(f) or {}
            config = deep_merge(config, ext_config)

    # 4. Environment Variable Overrides (highest priority)
    env_override = {
        "general": {
            "manufacturer": os.getenv("MOWBOT_MANUFACTURER"),
            "serial_number": os.getenv("MOWBOT_SERIAL_NUMBER"),
            "map_id": os.getenv("MOWBOT_MAP_ID"),
        },
        "broker": {
            "host": os.getenv("MOWBOT_MQTT_HOST"),
            "port": _to_int_or_none(os.getenv("MOWBOT_MQTT_PORT")),
            "use_tls": _to_bool_or_none(os.getenv("MOWBOT_MQTT_USE_TLS")),
            "user": os.getenv("MOWBOT_MQTT_USER"),
            "password": os.getenv("MOWBOT_MQTT_PASSWORD"),
        },
        "teach_in": {
            "poly_max_close_gap_m": _to_float_or_none(
                os.getenv("MOWBOT_TEACH_POLY_MAX_CLOSE_GAP_M")
            ),
            "poly_min_area_m2": _to_float_or_none(
                os.getenv("MOWBOT_TEACH_POLY_MIN_AREA_M2")
            ),
            "poly_reject_self_intersection": _to_bool_or_none(
                os.getenv("MOWBOT_TEACH_POLY_REJECT_SELF_INTERSECTION")
            ),
        },
        "coverage": {
            "mow_width_m": _to_float_or_none(os.getenv("MOWBOT_COVERAGE_MOW_WIDTH_M")),
            "overlap_pct": _to_float_or_none(os.getenv("MOWBOT_COVERAGE_OVERLAP_PCT")),
            "sweep_angle_deg": _to_float_or_none(
                os.getenv("MOWBOT_COVERAGE_SWEEP_ANGLE_DEG")
            ),
            "max_waypoints": _to_int_or_none(os.getenv("MOWBOT_COVERAGE_MAX_WAYPOINTS")),
            "min_turn_radius_m": _to_float_or_none(
                os.getenv("MOWBOT_COVERAGE_MIN_TURN_RADIUS_M")
            ),
        },
        "docker_reset_on_startup": _to_bool_or_none(
            os.getenv("MOWBOT_DOCKER_RESET_ON_STARTUP")
        ),
    }
    config = deep_merge(config, _drop_nones_recursive(env_override))

    return config


def _to_float_or_none(value: Any) -> Any:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int_or_none(value: Any) -> Any:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_bool_or_none(value: Any) -> Any:
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    return None


def _drop_nones_recursive(obj: Any) -> Any:
    if isinstance(obj, dict):
        cleaned = {}
        for key, value in obj.items():
            value = _drop_nones_recursive(value)
            if value is not None:
                cleaned[key] = value
        return cleaned
    return obj