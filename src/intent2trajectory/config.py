from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


INTENT_ORDER = ["attack", "retreat", "hover", "loiter"]
LEGACY_INTENT_ALIASES = {
    "straight_penetration": ("attack", "direct_commit"),
    "non_straight_penetration": ("attack", None),
    "hover": ("hover", None),
    "loiter": ("loiter", None),
    "retreat": ("retreat", None),
}
LEGACY_STYLE_ALIASES = {
    "attack": {
        "direct_closing": "direct_commit",
        "weave_approach": "weave_commit",
        "climb_then_dive": "climb_dive_commit",
        "turn_then_dive": "turn_dive_commit",
        "zigzag_dive": "zigzag_commit",
        "probe_recommit": "probe_recommit",
    },
    "hover": {
        "standoff_hover": "drift_hold",
    },
    "loiter": {
        "surveillance_loiter": "circle_loiter",
        "circle_hold": "circle_loiter",
        "ellipse_hold": "ellipse_loiter",
        "figure8_hold": "petal_loiter",
    },
    "retreat": {
        "direct_escape": "direct_breakaway",
        "arc_escape": "arc_breakaway",
        "zigzag_escape": "zigzag_breakaway",
        "climb_escape": "climb_breakaway",
    },
}
DEFAULT_RELATIVE_FILES = {
    "airframes_path": "airframes.json",
    "intent_regions_path": "intent_regions.json",
    "style_library_path": "style_library.json",
}


def read_config_file(config_path: str | Path) -> Dict[str, Any]:
    path = Path(config_path)
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("PyYAML is required for YAML config files") from exc
        return yaml.safe_load(text)
    raise ValueError(f"Unsupported config format: {path.suffix}")


def load_config(config_path: str | Path) -> Dict[str, Any]:
    path = Path(config_path).resolve()
    raw = read_config_file(path)
    return normalize_config(raw, path)


def normalize_config(raw: Dict[str, Any], source_path: Optional[Path] = None) -> Dict[str, Any]:
    config_dir = source_path.parent if source_path else Path.cwd()
    normalized = dict(raw)
    normalized.setdefault("schema_version", "2.0.0")
    normalized.setdefault("seed", 0)
    normalized.setdefault("dt", 0.2)
    normalized.setdefault("max_time", 240.0)
    normalized.setdefault("max_resample_attempts", 8)
    normalized.setdefault("progress", {"enabled": False})
    normalized.setdefault("failure_logging", {"include_failed_metadata": True})
    normalized.setdefault("output_formats", ["origin"])
    normalized.setdefault("output_root", "dataset_workspace")
    normalized.setdefault("diversity", {
        "distance_threshold": 0.18,
        "bucket_bins": {
            "min_range": [0.0, 250.0, 600.0, 1200.0, 2400.0],
            "mean_speed_norm": [0.0, 0.25, 0.5, 0.75, 1.01],
            "uncertain_score": [0.0, 0.25, 0.5, 0.75, 1.01],
            "duration": [0.0, 40.0, 90.0, 150.0, 400.0],
            "encircle_cycles": [0.0, 0.25, 0.75, 1.5, 4.0],
        },
    })
    normalized.setdefault("constraints", {})
    normalized["constraints"].setdefault("space", {"x": [-6000.0, 6000.0], "y": [-6000.0, 6000.0], "z": [20.0, 800.0]})

    quota = dict(normalized.get("class_quota") or {})
    if any(key in quota for key in ("straight_penetration", "non_straight_penetration")):
        quota["attack"] = int(quota.get("attack", 0)) + int(quota.get("straight_penetration", 0)) + int(quota.get("non_straight_penetration", 0))
        quota.pop("straight_penetration", None)
        quota.pop("non_straight_penetration", None)
    normalized["class_quota"] = {intent: int(quota.get(intent, 0)) for intent in INTENT_ORDER}

    normalized["legacy_aliases"] = {
        "intent": dict(LEGACY_INTENT_ALIASES),
        "style": {intent: dict(values) for intent, values in LEGACY_STYLE_ALIASES.items()},
    }

    for key, default_name in DEFAULT_RELATIVE_FILES.items():
        inline_key = key.replace("_path", "")
        if inline_key in normalized and normalized[inline_key]:
            continue
        path_value = normalized.get(key)
        resolved_path = (config_dir / (path_value or default_name)).resolve()
        normalized[key] = str(resolved_path)
        normalized[inline_key] = read_config_file(resolved_path)

    normalized.setdefault("threat_export", {})
    normalized["intent_order"] = list(INTENT_ORDER)
    return normalized


def map_legacy_intent(intent: str) -> Tuple[str, Optional[str]]:
    if intent in INTENT_ORDER:
        return intent, None
    if intent not in LEGACY_INTENT_ALIASES:
        supported = ", ".join(INTENT_ORDER + sorted(LEGACY_INTENT_ALIASES))
        raise ValueError(f"Unsupported intent '{intent}'. Supported intents: {supported}")
    return LEGACY_INTENT_ALIASES[intent]


def map_legacy_style(intent: str, style: Optional[str]) -> Optional[str]:
    if style is None:
        return None
    aliases = LEGACY_STYLE_ALIASES.get(intent, {})
    return aliases.get(style, style)


def normalize_requested_labels(intent: str, motion_style: Optional[str] = None) -> Tuple[str, Optional[str], Optional[str]]:
    normalized_intent, default_style = map_legacy_intent(intent)
    effective_style = motion_style or default_style
    effective_style = map_legacy_style(normalized_intent, effective_style)
    legacy_hint = None
    if intent != normalized_intent:
        legacy_hint = f"legacy intent '{intent}' mapped to '{normalized_intent}'"
    return normalized_intent, effective_style, legacy_hint
