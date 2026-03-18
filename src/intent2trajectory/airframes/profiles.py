from __future__ import annotations

from typing import Dict, List

from ..models import AirframeProfile, ensure_tuple


def build_airframe_profiles(config: Dict) -> Dict[str, AirframeProfile]:
    raw_profiles = config["airframes"]["profiles"]
    profiles: Dict[str, AirframeProfile] = {}
    for name, raw in raw_profiles.items():
        profiles[name] = AirframeProfile(
            name=name,
            family=str(raw["family"]),
            hover_capable=bool(raw["hover_capable"]),
            v_min=float(raw.get("v_min", 0.0)),
            v_cruise_range=ensure_tuple(raw["v_cruise_range"]),
            v_dash_range=ensure_tuple(raw["v_dash_range"]),
            a_long_max=float(raw["a_long_max"]),
            a_brake_max=float(raw["a_brake_max"]),
            a_lat_max=float(raw["a_lat_max"]),
            climb_rate_max=float(raw["climb_rate_max"]),
            descent_rate_max=float(raw["descent_rate_max"]),
            jerk_max=float(raw["jerk_max"]),
            yaw_rate_max=float(raw["yaw_rate_max"]),
            turn_rate_max=float(raw["turn_rate_max"]),
            min_turn_radius=float(raw["min_turn_radius"]),
            control_tau=float(raw["control_tau"]),
            preferred_altitude=ensure_tuple(raw["preferred_altitude"]),
            allowed_styles={intent: list(styles) for intent, styles in raw["allowed_styles"].items()},
            validator_overrides={str(k): float(v) for k, v in (raw.get("validator_overrides") or {}).items()},
            selection_weight=float(raw.get("selection_weight", 1.0)),
        )
    return profiles


def get_airframe(config: Dict, name: str) -> AirframeProfile:
    profiles = config.get("_airframe_profiles")
    if profiles is None:
        profiles = build_airframe_profiles(config)
        config["_airframe_profiles"] = profiles
    if name not in profiles:
        raise ValueError(f"Unknown airframe '{name}'")
    return profiles[name]


def sample_airframe(intent: str, config: Dict, rng) -> AirframeProfile:
    profiles = config.get("_airframe_profiles")
    if profiles is None:
        profiles = build_airframe_profiles(config)
        config["_airframe_profiles"] = profiles

    candidates: List[AirframeProfile] = [profile for profile in profiles.values() if profile.allowed_styles.get(intent)]
    if not candidates:
        raise ValueError(f"No airframes configured for intent '{intent}'")

    total = sum(max(profile.selection_weight, 0.0) for profile in candidates)
    if total <= 0:
        return candidates[0]
    draw = rng.uniform(0.0, total)
    upto = 0.0
    for profile in candidates:
        upto += max(profile.selection_weight, 0.0)
        if draw <= upto:
            return profile
    return candidates[-1]
