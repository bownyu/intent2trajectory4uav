from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .airframes.capability_matrix import list_allowed_styles, supports_style
from .airframes.profiles import get_airframe, sample_airframe as _sample_airframe
from .config import INTENT_ORDER, load_config as _load_config, normalize_config, normalize_requested_labels
from .dynamics.rollout import rollout as _rollout
from .exporters.meta_json import write_meta_json
from .exporters.metadata_csv import build_failure_row, build_metadata_row
from .exporters.origin_csv import build_origin_rows
from .exporters.threat_csv import build_threat_rows
from .models import AirframeProfile, RiskVector, SemanticTarget, StageSpec, Trajectory, ValidationResult
from .semantics.intent_scoring import score_intents
from .semantics.risk_vector import compute_risk_vector
from .semantics.station_metrics import compute_station_metrics
from .templates import attack as attack_templates
from .templates import hover as hover_templates
from .templates import loiter as loiter_templates
from .templates import retreat as retreat_templates
from .validators.diversity_filter import DiversityFilter
from .validators.semantic_validator import validate_sample as _validate_trajectory_sample


def load_config(config_path: str) -> Dict:
    return _load_config(config_path)


def sample_airframe(intent: str, cfg: Dict, rng: random.Random) -> AirframeProfile:
    return _sample_airframe(intent, cfg, rng)


def sample_semantic_target(intent: str, cfg: Dict, rng: random.Random) -> SemanticTarget:
    region = cfg["intent_regions"]["intent_regions"][intent]
    target_values = {}
    for key in ("close", "dwell", "encircle", "point", "uncertain", "disengage"):
        low, high = region[key]
        target_values[key] = rng.uniform(float(low), float(high))
    active_band_name = "terminal" if intent == "attack" else "escape" if intent == "retreat" else "hold" if intent == "hover" else "loiter"
    return SemanticTarget(intent=intent, target_values=target_values, active_band_name=active_band_name, risk_bands=cfg["intent_regions"]["bands"])


def select_style(intent: str, airframe: AirframeProfile, semantic_target: SemanticTarget, cfg: Dict, rng: random.Random, requested_style: Optional[str] = None) -> str:
    allowed = list_allowed_styles(airframe, intent)
    if not allowed:
        raise ValueError(f"Airframe '{airframe.name}' has no styles for intent '{intent}'")
    if requested_style:
        if not supports_style(airframe, intent, requested_style):
            raise ValueError(f"Style '{requested_style}' is not allowed for intent '{intent}' on airframe '{airframe.name}'")
        return requested_style
    library = cfg["style_library"]["intents"][intent]
    weights = [(style, float(library[style].get("weight", 1.0))) for style in allowed]
    total = sum(weight for _, weight in weights)
    draw = rng.uniform(0.0, total)
    upto = 0.0
    for style, weight in weights:
        upto += weight
        if draw <= upto:
            return style
    return allowed[-1]


def build_stage_plan(intent: str, style: str, airframe: AirframeProfile, semantic_target: SemanticTarget, cfg: Dict, rng: random.Random) -> List[StageSpec]:
    if intent == "attack":
        plan = attack_templates.build_stage_plan(style, airframe, semantic_target, cfg, rng)
    elif intent == "retreat":
        plan = retreat_templates.build_stage_plan(style, airframe, semantic_target, cfg, rng)
    elif intent == "hover":
        plan = hover_templates.build_stage_plan(style, airframe, semantic_target, cfg, rng)
    elif intent == "loiter":
        plan = loiter_templates.build_stage_plan(style, airframe, semantic_target, cfg, rng)
    else:
        raise ValueError(f"Unsupported intent '{intent}'")

    duration_scale = {"attack": 1.6, "retreat": 1.35, "hover": 1.2, "loiter": 2.4}[intent]
    for stage in plan:
        stage.duration_range = (stage.duration_range[0] * duration_scale, stage.duration_range[1] * duration_scale)
        if intent == "loiter":
            stage.vt_cmd.base *= 1.1
        if intent == "attack":
            stage.vr_cmd.base *= 1.08
    return plan


def rollout(plan: List[StageSpec], airframe: AirframeProfile, dt: float, cfg: Dict, initial_state: Dict) -> Trajectory:
    return _rollout(plan, airframe, dt, cfg, initial_state)


def compute_risk_vector_for_sample(traj: Trajectory, intent: str, cfg: Dict) -> Tuple[Dict, Dict, Dict]:
    metrics = compute_station_metrics(traj, cfg["intent_regions"]["bands"], cfg, intent)
    risk_vector = compute_risk_vector(metrics, cfg, intent)
    scores = score_intents(risk_vector, metrics, cfg)
    return metrics.to_dict(), risk_vector.to_dict(), scores.to_dict()


def _normalize_profile(profile) -> Dict:
    if isinstance(profile, (str, Path)):
        return load_config(str(profile))
    return normalize_config(dict(profile))


def _sample_angle(rng: random.Random) -> float:
    return rng.uniform(-math.pi, math.pi)


def _sample_initial_state(intent: str, airframe: AirframeProfile, style: str, semantic_target: SemanticTarget, cfg: Dict, rng: random.Random, dt: float) -> Dict:
    bands = cfg["intent_regions"]["bands"]
    angle = _sample_angle(rng)
    if intent == "attack":
        radius = rng.uniform(max(bands["hold"][1] * 1.1, cfg["intent_regions"]["risk_bands"]["sensitive"] * 3.0), cfg["intent_regions"]["risk_bands"]["outer_start"] * 0.6)
    elif intent == "retreat":
        radius = rng.uniform(cfg["intent_regions"]["risk_bands"]["sensitive"] * 1.2, bands["hold"][0] * 0.8)
    elif intent == "hover":
        radius = rng.uniform(bands["hold"][0] * 1.02, bands["hold"][1] * 0.98)
    else:
        radius = rng.uniform(bands["loiter"][0] * 1.02, bands["loiter"][1] * 0.98)
    altitude = rng.uniform(*airframe.preferred_altitude)
    x = radius * math.cos(angle)
    y = radius * math.sin(angle)

    if intent == "attack":
        speed = max(airframe.cruise_speed() * 0.8, airframe.v_min)
        course = math.atan2(-y, -x)
    elif intent == "retreat":
        speed = max(airframe.cruise_speed() * 0.75, airframe.v_min)
        course = math.atan2(y, x)
    elif intent == "loiter":
        speed = max(airframe.cruise_speed() * 0.55, airframe.v_min)
        tangent = math.atan2(y, x) + math.pi / 2.0
        course = tangent
    else:
        speed = 0.4 if airframe.family == "multirotor" else max(airframe.v_min, airframe.cruise_speed() * 0.45)
        course = math.atan2(y, x) + math.pi / 2.0

    vx = speed * math.cos(course)
    vy = speed * math.sin(course)
    yaw = course if intent in {"attack", "retreat"} else math.atan2(-y, -x)
    return {
        "x": x,
        "y": y,
        "z": altitude,
        "vx": vx,
        "vy": vy,
        "vz": 0.0,
        "yaw": yaw,
        "course": course,
        "speed": max(speed, airframe.v_min),
    }


def _repair_stage_plan(plan: List[StageSpec]) -> List[StageSpec]:
    repaired: List[StageSpec] = []
    for stage in plan:
        clone = StageSpec(
            name=stage.name,
            duration_range=(stage.duration_range[0] * 1.25, stage.duration_range[1] * 1.25),
            terminate_rule=stage.terminate_rule,
            vr_cmd=stage.vr_cmd.__class__(**stage.vr_cmd.to_dict()),
            vt_cmd=stage.vt_cmd.__class__(**stage.vt_cmd.to_dict()),
            vz_cmd=stage.vz_cmd.__class__(**stage.vz_cmd.to_dict()),
            yaw_mode=stage.yaw_mode,
            noise_profile=stage.noise_profile,
            semantic_effects=dict(stage.semantic_effects),
            flight_mode=stage.flight_mode,
        )
        clone.vr_cmd.amplitude *= 0.8
        clone.vt_cmd.amplitude *= 0.8
        clone.vz_cmd.amplitude *= 0.8
        clone.vr_cmd.base *= 0.95
        repaired.append(clone)
    return repaired


def generate_sample(intent: str, seed: int, profile: Dict, variant_name: Optional[str] = None, airframe_name: Optional[str] = None) -> Dict:
    cfg = _normalize_profile(profile)
    normalized_intent, requested_style, legacy_hint = normalize_requested_labels(intent, variant_name)
    rng = random.Random(seed)
    dt = float(cfg.get("dt", 0.2))
    airframe = get_airframe(cfg, airframe_name) if airframe_name else sample_airframe(normalized_intent, cfg, rng)
    semantic_target = sample_semantic_target(normalized_intent, cfg, rng)
    style = select_style(normalized_intent, airframe, semantic_target, cfg, rng, requested_style=requested_style)
    stage_plan = build_stage_plan(normalized_intent, style, airframe, semantic_target, cfg, rng)
    initial_state = _sample_initial_state(normalized_intent, airframe, style, semantic_target, cfg, rng, dt)

    repair_count = 0
    trajectory = rollout(stage_plan, airframe, dt, cfg, initial_state)
    validation = _validate_trajectory_sample(trajectory, airframe, normalized_intent, style, cfg)
    if not validation.valid:
        repaired_plan = _repair_stage_plan(stage_plan)
        repaired_trajectory = rollout(repaired_plan, airframe, dt, cfg, initial_state)
        repaired_validation = _validate_trajectory_sample(repaired_trajectory, airframe, normalized_intent, style, cfg)
        if repaired_validation.valid or len(repaired_validation.reasons) < len(validation.reasons):
            repair_count = 1
            stage_plan = repaired_plan
            trajectory = repaired_trajectory
            validation = repaired_validation

    trajectory_dict = trajectory.to_dict()
    rows = build_origin_rows({
        "trajectory": trajectory_dict,
        "metadata": {
            "primary_intent": normalized_intent,
            "motion_style": style,
            "airframe_name": airframe.name,
            "risk_vector": validation.risk_vector.to_dict(),
        },
    })
    metadata = {
        "sample_id": f"{normalized_intent}_{style}_{airframe.name}_{seed}",
        "seed": seed,
        "primary_intent": normalized_intent,
        "motion_style": style,
        "airframe_name": airframe.name,
        "airframe_family": airframe.family,
        "airframe": airframe.to_dict(),
        "semantic_target": semantic_target.to_dict(),
        "risk_bands": cfg["intent_regions"]["bands"],
        "active_band_name": semantic_target.active_band_name,
        "risk_vector": validation.risk_vector.to_dict(),
        "intent_scores": validation.intent_scores.to_dict(),
        "station_metrics": validation.metrics.to_dict(),
        "stage_plan": [stage.to_dict() for stage in stage_plan],
        "flight_mode_sequence": list(trajectory.flight_mode_sequence),
        "hard_constraint_report": dict(validation.hard_constraint_report),
        "ambiguity_margin": validation.ambiguity_margin,
        "repair_count": repair_count,
        "duration": trajectory.points[-1].t if trajectory.points else 0.0,
        "duration_cap": float(cfg.get("max_time", 240.0)),
        "range_norm": float(cfg["intent_regions"]["risk_bands"]["exit"]),
        "legacy_hint": legacy_hint,
        "valid": validation.valid,
        "reasons": list(validation.reasons),
        "failure_category": validation.failure_category,
    }
    sample = {
        "sample_id": metadata["sample_id"],
        "intent": normalized_intent,
        "rows": rows,
        "metadata": metadata,
        "trajectory": trajectory_dict,
        "validation": validation.to_dict(),
        "_trajectory_obj": trajectory,
        "_airframe_obj": airframe,
        "_config": cfg,
    }
    return sample


def validate_sample(sample: Dict, profile: Dict) -> Dict:
    cfg = _normalize_profile(profile)
    trajectory = sample.get("_trajectory_obj")
    airframe = sample.get("_airframe_obj")
    if trajectory is None or airframe is None:
        regenerated = generate_sample(sample.get("intent", sample["metadata"]["primary_intent"]), sample["metadata"]["seed"], cfg, variant_name=sample["metadata"].get("motion_style"), airframe_name=sample["metadata"].get("airframe_name"))
        trajectory = regenerated["_trajectory_obj"]
        airframe = regenerated["_airframe_obj"]
        sample.update(regenerated)
    result = _validate_trajectory_sample(trajectory, airframe, sample["metadata"]["primary_intent"], sample["metadata"]["motion_style"], cfg)
    sample["validation"] = result.to_dict()
    sample["metadata"]["station_metrics"] = result.metrics.to_dict()
    sample["metadata"]["risk_vector"] = result.risk_vector.to_dict()
    sample["metadata"]["intent_scores"] = result.intent_scores.to_dict()
    sample["metadata"]["ambiguity_margin"] = result.ambiguity_margin
    sample["metadata"]["hard_constraint_report"] = dict(result.hard_constraint_report)
    sample["metadata"]["valid"] = result.valid
    sample["metadata"]["reasons"] = list(result.reasons)
    sample["metadata"]["failure_category"] = result.failure_category
    return result.to_dict()


def compute_variant_quotas(total_quota: int, variants: Dict) -> Dict[str, int]:
    if total_quota <= 0 or not variants:
        return {}
    weights = {name: float(cfg.get("weight", 1.0)) for name, cfg in variants.items()}
    total_weight = sum(max(weight, 0.0) for weight in weights.values())
    if total_weight <= 0:
        raise ValueError("No positive-weight variants configured")
    raw = {name: total_quota * weight / total_weight for name, weight in weights.items()}
    quotas = {name: int(value) for name, value in raw.items()}
    remainder = total_quota - sum(quotas.values())
    if remainder > 0:
        ranking = sorted(raw.items(), key=lambda item: item[1] - int(item[1]), reverse=True)
        for idx in range(remainder):
            quotas[ranking[idx % len(ranking)][0]] += 1
    return quotas


def _build_generation_tasks(cfg: Dict) -> List[Dict]:
    tasks: List[Dict] = []
    for intent in INTENT_ORDER:
        quota = int(cfg["class_quota"].get(intent, 0))
        for idx in range(quota):
            tasks.append({"intent": intent, "target_quota": quota, "intent_sample_index": idx})
    return tasks


def _stable_seed(base_seed: int, intent: str, sample_index: int, attempt: int) -> int:
    return abs(hash((base_seed, intent, sample_index, attempt))) % (2 ** 31)


def _sanitize_token(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)


def _write_csv(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _normalize_output_formats(raw_formats) -> List[str]:
    if not raw_formats:
        return ["origin"]
    formats = []
    for value in raw_formats:
        name = str(value).strip().lower()
        if name and name not in formats:
            formats.append(name)
    return formats


def generate_dataset(config_path: str) -> Dict:
    cfg = load_config(config_path)
    output_root = Path(cfg["output_root"])
    output_root.mkdir(parents=True, exist_ok=True)
    output_formats = _normalize_output_formats(cfg.get("output_formats"))
    if "threat" in output_formats and not cfg.get("threat_export", {}).get("station"):
        raise ValueError("threat export requires threat_export.station")

    diversity_filter = DiversityFilter(cfg.get("diversity") or {})
    metadata_rows: List[Dict[str, str]] = []
    failure_rows: List[Dict[str, str]] = []
    style_counts: Dict[str, Dict[str, int]] = {}
    generated = 0
    failed = 0
    base_seed = int(cfg.get("seed", 0))
    max_attempts = int(cfg.get("max_resample_attempts", 8))
    target_id = int(cfg.get("threat_export", {}).get("target_id_start", 100000))

    for task in _build_generation_tasks(cfg):
        accepted = None
        last_failure = None
        attempts_used = 0
        for attempt in range(max_attempts):
            seed = _stable_seed(base_seed, task["intent"], task["intent_sample_index"], attempt)
            sample = generate_sample(task["intent"], seed, cfg)
            result = validate_sample(sample, cfg)
            attempts_used = attempt + 1
            if result["valid"]:
                ok, reason = diversity_filter.accept(sample)
                if ok:
                    accepted = sample
                    break
                sample["metadata"]["failure_category"] = "diversity"
                sample["metadata"]["reasons"] = [reason]
                last_failure = sample
            else:
                last_failure = sample
        if accepted is None:
            failed += 1
            failure_sample = last_failure
            if failure_sample:
                failure_rows.append(build_failure_row(
                    seed=failure_sample["metadata"]["seed"],
                    primary_intent=failure_sample["metadata"]["primary_intent"],
                    motion_style=failure_sample["metadata"]["motion_style"],
                    airframe_name=failure_sample["metadata"]["airframe_name"],
                    category=failure_sample["metadata"].get("failure_category", "semantic"),
                    reasons=";".join(failure_sample["metadata"].get("reasons", [])),
                ))
            continue

        generated += 1
        md = accepted["metadata"]
        style_counts.setdefault(md["primary_intent"], {})
        style_counts[md["primary_intent"]][md["motion_style"]] = style_counts[md["primary_intent"]].get(md["motion_style"], 0) + 1
        safe_name = _sanitize_token(md["sample_id"])

        if "origin" in output_formats:
            origin_path = output_root / "origin" / md["primary_intent"] / f"{safe_name}.csv"
            _write_csv(origin_path, accepted["rows"])
        if "threat" in output_formats:
            threat_path = output_root / "threat" / md["primary_intent"] / f"{safe_name}.csv"
            _write_csv(threat_path, build_threat_rows(accepted, target_id, cfg.get("threat_export") or {}))
        meta_path = output_root / "meta" / md["primary_intent"] / f"{safe_name}.json"
        write_meta_json(meta_path, accepted)
        metadata_rows.append(build_metadata_row(accepted, ",".join(output_formats), attempts_used, task["target_quota"]))
        target_id += 1

    if metadata_rows:
        _write_csv(output_root / "metadata.csv", metadata_rows)
    if failure_rows:
        _write_csv(output_root / "failures.csv", failure_rows)
    return {
        "generated": generated,
        "failed": failed,
        "output_root": str(output_root),
        "style_counts": style_counts,
        "variant_counts": style_counts,
    }


