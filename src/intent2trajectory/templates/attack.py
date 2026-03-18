from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from ..stages.primitives import sample_stage_spec


def _attack_library(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return cfg["style_library"]["intents"]["attack"]


def _weighted_choice(options: Iterable[str], weights: Dict[str, float], rng) -> str:
    choices = list(options)
    if not choices:
        raise ValueError("No choices available for attack profile selection")
    total = sum(max(float(weights.get(choice, 1.0)), 0.0) for choice in choices)
    if total <= 0.0:
        return choices[0]
    draw = rng.uniform(0.0, total)
    upto = 0.0
    for choice in choices:
        upto += max(float(weights.get(choice, 1.0)), 0.0)
        if draw <= upto:
            return choice
    return choices[-1]


def _find_style_mapping(library: Dict[str, Any], requested_style: str) -> Optional[Dict[str, str]]:
    legacy = library.get("legacy_styles") or {}
    if requested_style in legacy:
        mapping = dict(legacy[requested_style])
        mapping.setdefault("requested_style", requested_style)
        return mapping
    for pressure_profile, profile_def in (library.get("profiles") or {}).items():
        for maneuver_profile, maneuver_def in (profile_def.get("maneuvers") or {}).items():
            if maneuver_def.get("style_name") == requested_style:
                return {
                    "pressure_profile": pressure_profile,
                    "maneuver_profile": maneuver_profile,
                    "style_name": requested_style,
                    "requested_style": requested_style,
                }
    return None


def _resolve_dynamics_model(airframe, pressure_profile: str, maneuver_profile: str) -> str:
    capability = airframe.attack_capability or {}
    policy = capability.get("attack_dynamics_policy") or {}
    overrides = policy.get("overrides") or {}
    key = f"{pressure_profile}:{maneuver_profile}"
    default_model = policy.get("default")
    if key in overrides:
        return str(overrides[key])
    if default_model:
        return str(default_model)
    return "course_speed" if airframe.family == "fixed_wing" else "velocity_tracking"


def _select_start_context(airframe, library: Dict[str, Any], pressure_profile: str, rng) -> str:
    capability = airframe.attack_capability or {}
    start_contexts = list(capability.get("allowed_start_contexts") or ["outer_direct"])
    default_weights = {str(key): float(value) for key, value in (capability.get("start_context_weights") or {}).items()}
    profile_weights = {str(key): float(value) for key, value in (((library.get("profiles") or {}).get(pressure_profile) or {}).get("start_context_weights") or {}).items()}
    if profile_weights:
        filtered = [context for context in start_contexts if context in profile_weights]
        if filtered:
            return _weighted_choice(filtered, profile_weights, rng)
    return _weighted_choice(start_contexts, default_weights, rng)


def select_attack_profile(airframe, cfg: Dict[str, Any], rng, requested_style: Optional[str] = None) -> Dict[str, str]:
    library = _attack_library(cfg)
    capability = airframe.attack_capability or {}
    pressure_profiles = list(capability.get("allowed_pressure_profiles") or list((library.get("profiles") or {}).keys()))
    allowed_maneuvers = set(capability.get("allowed_maneuvers") or [])

    if requested_style:
        mapping = _find_style_mapping(library, requested_style)
        if mapping is None:
            raise ValueError(f"Unknown attack style '{requested_style}'")
        pressure_profile = mapping["pressure_profile"]
        maneuver_profile = mapping["maneuver_profile"]
        if pressure_profile not in pressure_profiles:
            raise ValueError(f"Attack pressure profile '{pressure_profile}' is not allowed on airframe '{airframe.name}'")
        if allowed_maneuvers and maneuver_profile not in allowed_maneuvers:
            raise ValueError(f"Attack maneuver profile '{maneuver_profile}' is not allowed on airframe '{airframe.name}'")
        style_name = mapping["style_name"]
    else:
        profile_weights = {
            name: float(((library.get("profiles") or {}).get(name) or {}).get("weight", 1.0))
            for name in pressure_profiles
            if name in (library.get("profiles") or {})
        }
        pressure_profile = _weighted_choice(profile_weights.keys(), profile_weights, rng)
        maneuvers = (library["profiles"][pressure_profile].get("maneuvers") or {})
        compatible = {
            name: definition
            for name, definition in maneuvers.items()
            if not allowed_maneuvers or name in allowed_maneuvers
        }
        if not compatible:
            raise ValueError(f"No compatible maneuver profiles for attack pressure profile '{pressure_profile}' on airframe '{airframe.name}'")
        maneuver_weights = {name: float(definition.get("weight", 1.0)) for name, definition in compatible.items()}
        maneuver_profile = _weighted_choice(maneuver_weights.keys(), maneuver_weights, rng)
        style_name = str(compatible[maneuver_profile]["style_name"])

    start_context = _select_start_context(airframe, library, pressure_profile, rng)
    return {
        "start_context": start_context,
        "pressure_profile": pressure_profile,
        "maneuver_profile": maneuver_profile,
        "motion_style": style_name,
        "dynamics_model": _resolve_dynamics_model(airframe, pressure_profile, maneuver_profile),
    }


def build_stage_plan(style: str, airframe, semantic_target, cfg, rng, attack_profile: Optional[Dict[str, str]] = None):
    if attack_profile is None:
        attack_profile = select_attack_profile(airframe, cfg, rng, requested_style=style)
    library = _attack_library(cfg)
    profile_def = library["profiles"][attack_profile["pressure_profile"]]
    maneuver_def = profile_def["maneuvers"][attack_profile["maneuver_profile"]]
    prefix_defs = list((library.get("start_context_primitives") or {}).get(attack_profile["start_context"], []))
    stage_defs = prefix_defs + list(maneuver_def.get("stages") or [])
    context = {
        "airframe": airframe,
        "bands": cfg["intent_regions"]["bands"],
        "semantic_target": semantic_target.to_dict(),
    }
    plan = [sample_stage_spec(stage_def, rng, context) for stage_def in stage_defs]
    duration_scale = float(maneuver_def.get("duration_scale", profile_def.get("duration_scale", 1.0)))
    vr_scale = float(maneuver_def.get("vr_scale", profile_def.get("vr_scale", 1.0)))
    for stage in plan:
        stage.duration_range = (stage.duration_range[0] * duration_scale, stage.duration_range[1] * duration_scale)
        stage.vr_cmd.base *= vr_scale
        if stage.dynamics_model == "auto":
            stage.dynamics_model = attack_profile["dynamics_model"]
    return plan
