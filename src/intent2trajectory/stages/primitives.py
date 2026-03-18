from __future__ import annotations

import math
import random
from typing import Any, Dict

from ..models import CommandProfile, StageSpec
from .envelopes import envelope_value


def _sample_range(raw, rng: random.Random, default: float = 0.0) -> float:
    if raw is None:
        return float(default)
    if isinstance(raw, (int, float)):
        return float(raw)
    return rng.uniform(float(raw[0]), float(raw[1]))


def resolve_reference(reference: str | None, value: float, context: Dict[str, Any]) -> float:
    if not reference or reference == "absolute":
        return value
    if reference == "v_cruise":
        return value * float(context["airframe"].cruise_speed())
    if reference == "v_dash":
        return value * float(context["airframe"].dash_speed())
    if reference == "hold_width":
        width = float(context["bands"]["hold"][1] - context["bands"]["hold"][0])
        return value * width * 0.01
    if reference == "loiter_width":
        width = float(context["bands"]["loiter"][1] - context["bands"]["loiter"][0])
        return value * width * 0.01
    if reference == "preferred_altitude":
        low, high = context["airframe"].preferred_altitude
        return value * (high - low)
    return value


def sample_command_profile(definition: Dict[str, Any], rng: random.Random, context: Dict[str, Any]) -> CommandProfile:
    reference = definition.get("reference")
    base = resolve_reference(reference, _sample_range(definition.get("base_range"), rng, definition.get("base", 0.0)), context)
    amplitude = resolve_reference(reference, _sample_range(definition.get("amplitude_range"), rng, definition.get("amplitude", 0.0)), context)
    period = _sample_range(definition.get("period_range"), rng, definition.get("period", 20.0))
    phase = _sample_range(definition.get("phase_range"), rng, definition.get("phase", 0.0))
    bias = resolve_reference(reference, _sample_range(definition.get("bias_range"), rng, definition.get("bias", 0.0)), context)
    envelope = str(definition.get("envelope", "constant"))
    return CommandProfile(base=base, amplitude=amplitude, period=max(period, 1e-3), phase=phase, envelope=envelope, bias=bias)


def sample_stage_spec(definition: Dict[str, Any], rng: random.Random, context: Dict[str, Any]) -> StageSpec:
    duration = definition.get("duration_range") or definition.get("duration") or [10.0, 20.0]
    sampled = _sample_range(duration, rng, 10.0)
    return StageSpec(
        name=str(definition["name"]),
        duration_range=(float(sampled), float(sampled)),
        terminate_rule=str(definition.get("terminate_rule", "duration")),
        vr_cmd=sample_command_profile(definition.get("vr_cmd", {}), rng, context),
        vt_cmd=sample_command_profile(definition.get("vt_cmd", {}), rng, context),
        vz_cmd=sample_command_profile(definition.get("vz_cmd", {}), rng, context),
        yaw_mode=str(definition.get("yaw_mode", "course_locked")),
        noise_profile=str(definition.get("noise_profile", "none")),
        semantic_effects={str(key): float(value) for key, value in (definition.get("semantic_effects") or {}).items()},
        flight_mode=str(definition.get("flight_mode", "auto")),
    )


def evaluate_command(profile: CommandProfile, elapsed: float, duration: float) -> float:
    progress = 0.0 if duration <= 0 else max(0.0, min(1.0, elapsed / duration))
    wave = math.sin(2.0 * math.pi * elapsed / max(profile.period, 1e-6) + profile.phase)
    return profile.base + profile.bias + profile.amplitude * wave * envelope_value(profile.envelope, progress)

