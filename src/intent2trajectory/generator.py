import csv
import hashlib
import json
import math
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

INTENT_ORDER = [
    "hover",
    "straight_penetration",
    "non_straight_penetration",
    "loiter",
    "retreat",
]


def load_config(config_path: str) -> Dict:
    path = Path(config_path)
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() in {".json"}:
        return json.loads(text)
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("PyYAML is required for YAML config files") from exc
        return yaml.safe_load(text)
    raise ValueError(f"Unsupported config format: {path.suffix}")


def generate_dataset(config_path: str) -> Dict:
    config = load_config(config_path)
    output_root = Path(config["output_root"])
    output_root.mkdir(parents=True, exist_ok=True)

    class_quota = config["class_quota"]
    max_attempts = int(config.get("max_resample_attempts", 10))
    base_seed = int(config.get("seed", 0))
    progress_enabled = bool(config.get("progress", {}).get("enabled", False))
    include_failed_metadata = bool(config.get("failure_logging", {}).get("include_failed_metadata", True))

    intent_dirs = {}
    for idx, intent in enumerate(INTENT_ORDER):
        d = output_root / f"{idx}_{intent}"
        d.mkdir(parents=True, exist_ok=True)
        intent_dirs[intent] = d

    tasks = _build_generation_tasks(config)
    total_samples = len(tasks)
    generated = 0
    failed = 0
    processed = 0
    metadata_rows: List[Dict] = []
    variant_counts: Dict[str, Dict[str, int]] = {}

    for task in tasks:
        intent = task["intent"]
        variant_name = task["variant_name"]
        accepted = None
        failure_reason = ""
        last_sample = None
        attempts_used = 0
        for attempt in range(max_attempts):
            seed = _stable_seed(base_seed, intent, task["intent_sample_index"], attempt, variant_name)
            sample = generate_sample(intent=intent, seed=seed, profile=config, variant_name=variant_name)
            verdict = validate_sample(sample, config)
            last_sample = sample
            attempts_used = attempt + 1
            if verdict["valid"]:
                accepted = sample
                break
            failure_reason = ";".join(verdict["reasons"])

        if accepted is None:
            failed += 1
            md = (last_sample or {}).get("metadata", {})
            metadata_rows.append(
                {
                    "sample_id": f"{intent}_{(variant_name or 'default')}_{task['intent_sample_index']:04d}",
                    "intent": intent,
                    "variant_name": md.get("variant_name", variant_name or "") if include_failed_metadata else "",
                    "variant_summary": json.dumps(md.get("variant_params", {}), ensure_ascii=False, sort_keys=True) if include_failed_metadata else "",
                    "random_seed": md.get("seed", "") if include_failed_metadata else "",
                    "start_x": f"{md['start_xyz'][0]:.6f}" if include_failed_metadata and md.get("start_xyz") else "",
                    "start_y": f"{md['start_xyz'][1]:.6f}" if include_failed_metadata and md.get("start_xyz") else "",
                    "start_z": f"{md['start_xyz'][2]:.6f}" if include_failed_metadata and md.get("start_xyz") else "",
                    "base_speed": f"{md['base_speed']:.6f}" if include_failed_metadata and md.get("base_speed") is not None else "",
                    "simulation_time": f"{md['duration']:.6f}" if include_failed_metadata and md.get("duration") is not None else "",
                    "yaw_policy": md.get("yaw_policy", "") if include_failed_metadata else "",
                    "noise_profile": md.get("noise_profile", "") if include_failed_metadata else "",
                    "constraint_profile": md.get("constraint_profile", "") if include_failed_metadata else "",
                    "target_quota": str(task["target_quota"]),
                    "attempt_count": str(attempts_used),
                    "variant_attempt_count": str(attempts_used),
                    "schema_version": config.get("schema_version", "1.0.0"),
                    "status": "failed",
                    "failure_reason": failure_reason,
                }
            )
        else:
            generated += 1
            md = accepted["metadata"]
            initial_distance = int(round(md["initial_distance"]))
            base_speed = int(round(md["base_speed"]))
            safe_variant_name = _sanitize_token(md.get("variant_name", "default"))
            filename = f"{intent}_{safe_variant_name}_{task['intent_sample_index'] + 1:04d}_D{initial_distance}_V{base_speed}.csv"
            _write_sample_csv(intent_dirs[intent] / filename, accepted["rows"])

            metadata_rows.append(
                {
                    "sample_id": accepted["sample_id"],
                    "intent": intent,
                    "variant_name": md.get("variant_name", "default"),
                    "variant_summary": json.dumps(md.get("variant_params", {}), ensure_ascii=False, sort_keys=True),
                    "random_seed": md["seed"],
                    "start_x": f"{md['start_xyz'][0]:.6f}",
                    "start_y": f"{md['start_xyz'][1]:.6f}",
                    "start_z": f"{md['start_xyz'][2]:.6f}",
                    "base_speed": f"{md['base_speed']:.6f}",
                    "simulation_time": f"{md['duration']:.6f}",
                    "yaw_policy": md["yaw_policy"],
                    "noise_profile": md["noise_profile"],
                    "constraint_profile": md["constraint_profile"],
                    "target_quota": str(task["target_quota"]),
                    "attempt_count": str(attempts_used),
                    "variant_attempt_count": str(attempts_used),
                    "schema_version": config.get("schema_version", "1.0.0"),
                    "status": "generated",
                    "failure_reason": "",
                }
            )

            variant_bucket = variant_counts.setdefault(intent, {})
            key = md.get("variant_name", "default")
            variant_bucket[key] = variant_bucket.get(key, 0) + 1

        processed += 1
        if progress_enabled:
            _print_progress(processed, total_samples, intent, generated, failed, attempts_used)

    if progress_enabled and total_samples:
        sys.stdout.write("\n")
        sys.stdout.flush()

    _write_metadata_csv(output_root / "metadata.csv", metadata_rows)
    return {
        "generated": generated,
        "failed": failed,
        "output_root": str(output_root),
        "variant_counts": variant_counts,
    }


def generate_sample(intent: str, seed: int, profile: Dict, variant_name: Optional[str] = None) -> Dict:
    if intent not in INTENT_ORDER:
        raise ValueError(f"Unsupported intent: {intent}")

    rng = random.Random(seed)
    dt = float(profile.get("dt", 0.1))
    max_time = float(profile.get("max_time", 600.0))
    ip = profile["intent_profiles"][intent]

    if intent == "hover":
        spec = _gen_hover(ip, dt, max_time, rng, variant_name=variant_name)
    elif intent == "straight_penetration":
        spec = _gen_straight(ip, dt, max_time, rng)
    elif intent == "non_straight_penetration":
        spec = _gen_non_straight(ip, dt, max_time, rng, variant_name=variant_name)
    elif intent == "loiter":
        spec = _gen_loiter(ip, dt, max_time, rng, variant_name=variant_name)
    else:
        spec = _gen_retreat(ip, dt, max_time, rng, profile=profile, variant_name=variant_name)

    positions = spec["positions"]
    yaw_policy = spec["yaw_policy"]
    times = [i * dt for i in range(len(positions))]
    velocities = _derivative(positions, dt)
    yaws = _derive_yaw(intent, positions, velocities, yaw_policy, rng, ip)

    rows = []
    variant_name = spec.get("variant_name", "default")
    variant_summary = json.dumps(spec.get("variant_params", {}), ensure_ascii=False, sort_keys=True)
    for t, p, v, yaw in zip(times, positions, velocities, yaws):
        rows.append(
            {
                "time_relative": _r(t),
                "intent": intent,
                "variant_name": variant_name,
                "variant_summary": variant_summary,
                "pos_x": _r(p[0]),
                "pos_y": _r(p[1]),
                "pos_z": _r(p[2]),
                "yaw": _r(yaw),
                "vel_x": _r(v[0]),
                "vel_y": _r(v[1]),
                "vel_z": _r(v[2]),
                "ref_pos_x": _r(p[0]),
                "ref_pos_y": _r(p[1]),
                "ref_pos_z": _r(p[2]),
                "ref_yaw": _r(yaw),
                "act_pos_x": math.nan,
                "act_pos_y": math.nan,
                "act_pos_z": math.nan,
                "act_yaw": math.nan,
                "ref_vel_x": _r(v[0]),
                "ref_vel_y": _r(v[1]),
                "ref_vel_z": _r(v[2]),
                "act_vel_x": math.nan,
                "act_vel_y": math.nan,
                "act_vel_z": math.nan,
            }
        )

    start = positions[0]
    end = positions[-1]
    metadata = {
        "seed": seed,
        "start_xyz": start,
        "end_xyz": end,
        "base_speed": _estimate_base_speed(velocities),
        "duration": times[-1] if times else 0.0,
        "yaw_policy": yaw_policy,
        "noise_profile": spec["noise_profile"],
        "constraint_profile": intent,
        "initial_distance": _norm(start),
        "end_distance": _norm(end),
        "variant_name": spec.get("variant_name", "default"),
        "variant_params": spec.get("variant_params", {}),
    }

    return {
        "sample_id": f"{intent}_{seed}",
        "intent": intent,
        "rows": rows,
        "metadata": metadata,
    }

def validate_sample(sample: Dict, profile: Dict) -> Dict:
    rows = sample["rows"]
    if len(rows) < 3:
        return {"valid": False, "reasons": ["too_short"]}

    intent = sample["intent"]
    dt = float(profile.get("dt", 0.1))
    limits = profile["constraints"]["intent_limits"][intent]
    space = profile["constraints"]["space"]
    metadata = sample.get("metadata", {})
    variant_name = metadata.get("variant_name", "")

    reasons = []
    speed = []
    for row in rows:
        x, y, z = row["pos_x"], row["pos_y"], row["pos_z"]
        if not (space["x"][0] <= x <= space["x"][1]):
            reasons.append("x_out_of_bounds")
            break
        if not (space["y"][0] <= y <= space["y"][1]):
            reasons.append("y_out_of_bounds")
            break
        if not (space["z"][0] <= z <= space["z"][1]):
            reasons.append("z_out_of_bounds")
            break
        speed.append(_norm((row["vel_x"], row["vel_y"], row["vel_z"])))

    if speed and max(speed) > float(limits["max_speed"]) + 1e-6:
        reasons.append("speed_limit")

    acc = []
    yaws = [row["yaw"] for row in rows]
    for i in range(1, len(rows)):
        dv = (
            rows[i]["vel_x"] - rows[i - 1]["vel_x"],
            rows[i]["vel_y"] - rows[i - 1]["vel_y"],
            rows[i]["vel_z"] - rows[i - 1]["vel_z"],
        )
        acc.append(_norm(dv) / dt)
    if acc and max(acc) > float(limits["max_acc"]) + 1e-6:
        reasons.append("acc_limit")

    yaw_rates = []
    for i in range(1, len(yaws)):
        yaw_rates.append(abs(_angle_diff(yaws[i], yaws[i - 1])) / dt)
    if yaw_rates and max(yaw_rates) > float(limits["max_yaw_rate"]) + 1e-6:
        reasons.append("yaw_rate_limit")

    distances = [_norm((row["pos_x"], row["pos_y"], row["pos_z"])) for row in rows]
    yaw_spread = _angle_spread(yaws)
    positions = [(row["pos_x"], row["pos_y"], row["pos_z"]) for row in rows]

    if intent == "straight_penetration":
        if distances[-1] >= distances[0]:
            reasons.append("straight_not_closing")
        if yaw_spread > 0.15:
            reasons.append("straight_yaw_unstable")
    elif intent == "non_straight_penetration":
        if distances[-1] >= distances[0]:
            reasons.append("non_straight_not_closing")
        closing = distances[0] - distances[-1]
        if closing < 200:
            reasons.append("non_straight_closing_too_small")
        displacement = _norm((
            positions[-1][0] - positions[0][0],
            positions[-1][1] - positions[0][1],
            positions[-1][2] - positions[0][2],
        ))
        path_ratio = _path_length(positions) / max(displacement, 1e-6)
        lateral_dev = _max_lateral_deviation(positions)
        z_values = [p[2] for p in positions]
        altitude_range = max(z_values) - min(z_values)
        heading_excursion = _angle_excursion(yaws)
        lateral_sign_changes = _count_sign_changes(_lateral_offsets(positions))

        if variant_name == "weave_approach":
            if path_ratio < 1.02:
                reasons.append("non_straight_path_too_direct")
            if lateral_dev < 30.0:
                reasons.append("non_straight_lateral_small")
            if altitude_range < 10.0 and heading_excursion < 0.3:
                reasons.append("non_straight_maneuver_weak")
        elif variant_name == "climb_then_dive":
            if altitude_range < 35.0:
                reasons.append("non_straight_climb_profile_weak")
        elif variant_name == "turn_then_dive":
            if heading_excursion < 0.3:
                reasons.append("non_straight_turn_profile_weak")
            if lateral_dev < 40.0:
                reasons.append("non_straight_lateral_small")
        elif variant_name == "zigzag_dive":
            if lateral_sign_changes < 2:
                reasons.append("non_straight_zigzag_profile_weak")
            if lateral_dev < 35.0:
                reasons.append("non_straight_lateral_small")
        else:
            if path_ratio < 1.02:
                reasons.append("non_straight_path_too_direct")
            if lateral_dev < 30.0:
                reasons.append("non_straight_lateral_small")
            if altitude_range < 12.0 and heading_excursion < 0.35:
                reasons.append("non_straight_maneuver_weak")
    elif intent == "loiter":
        hints = metadata.get("variant_params", {})
        center_xy = tuple(hints.get("center_xy", [sum(p[0] for p in positions) / len(positions), sum(p[1] for p in positions) / len(positions)]))
        tangential_score = _mean_tangential_score(rows, center_xy)
        cumulative_turn = _cumulative_angle_travel(positions, center_xy)
        radial_spread = _radial_spread(positions, center_xy)
        if tangential_score < 0.45:
            reasons.append("loiter_tangential_weak")
        if cumulative_turn < 5.5:
            reasons.append("loiter_turn_insufficient")
        if variant_name in {"circle_hold", "offset_orbit"} and radial_spread > 160.0:
            reasons.append("loiter_radius_unstable")
        if variant_name == "ellipse_hold":
            bbox_ratio = _bbox_aspect_ratio(positions, center_xy)
            if bbox_ratio < 1.15:
                reasons.append("loiter_ellipse_not_distinct")
        if variant_name == "figure8_hold":
            if _count_sign_changes([p[0] - center_xy[0] for p in positions]) < 2:
                reasons.append("loiter_figure8_crossing_missing")
    elif intent == "retreat":
        mult = float(profile["intent_profiles"]["retreat"].get("distance_multiplier", 1.5))
        if distances[-1] < mult * distances[0]:
            reasons.append("retreat_multiplier_fail")
        outward_steps = sum(1 for i in range(1, len(distances)) if distances[i] >= distances[i - 1] - 5.0)
        if outward_steps / max(1, len(distances) - 1) < 0.8:
            reasons.append("retreat_outward_trend_weak")

        if variant_name == "direct_escape":
            if yaw_spread > 0.25:
                reasons.append("retreat_heading_unstable")
        elif variant_name == "arc_escape":
            heading_excursion = _angle_excursion(yaws)
            lateral_changes = _count_sign_changes(_lateral_offsets(positions))
            if heading_excursion < 0.2:
                reasons.append("retreat_arc_turn_weak")
            if lateral_changes > 1:
                reasons.append("retreat_arc_reversal_excessive")
        elif variant_name == "zigzag_escape":
            lateral_changes = _count_sign_changes(_lateral_offsets(positions))
            if lateral_changes < 2:
                reasons.append("retreat_zigzag_missing")
        elif variant_name == "climb_escape":
            z_gain = positions[-1][2] - positions[0][2]
            if z_gain < 40.0:
                reasons.append("retreat_climb_gain_small")
    elif intent == "hover":
        params = metadata.get("variant_params", {})
        center = tuple(params.get("center_xyz", sample["metadata"].get("start_xyz", (rows[0]["pos_x"], rows[0]["pos_y"], rows[0]["pos_z"]))))
        offsets = []
        planar_points = []
        for row in rows:
            dx = row["pos_x"] - center[0]
            dy = row["pos_y"] - center[1]
            dz = row["pos_z"] - center[2]
            offsets.append(_norm((dx, dy, dz)))
            planar_points.append((row["pos_x"], row["pos_y"], row["pos_z"]))
        max_offset = max(offsets)
        end_offset = offsets[-1]
        avg_speed = sum(speed) / len(speed)
        if max_offset > 20.0:
            reasons.append("hover_drift_large")
        if end_offset > 12.0:
            reasons.append("hover_end_offset_large")
        if avg_speed > 1.5:
            reasons.append("hover_speed_large")

        if variant_name == "steady_hold":
            if max_offset > 6.0:
                reasons.append("hover_steady_spread_large")
        elif variant_name == "micro_orbit_hold":
            center_xy = (center[0], center[1])
            cumulative_turn = _cumulative_angle_travel(planar_points, center_xy)
            radial_spread = _radial_spread(planar_points, center_xy)
            if cumulative_turn < 1.0:
                reasons.append("hover_micro_orbit_turn_weak")
            if radial_spread > 6.0:
                reasons.append("hover_micro_orbit_radius_unstable")
        elif variant_name == "sway_hold":
            axis = tuple(params.get("axis", [1.0, 0.0]))
            primary = []
            secondary = []
            for row in rows:
                dx = row["pos_x"] - center[0]
                dy = row["pos_y"] - center[1]
                primary.append(dx * axis[0] + dy * axis[1])
                secondary.append(-dx * axis[1] + dy * axis[0])
            if _count_sign_changes(primary) < 2:
                reasons.append("hover_sway_reversal_missing")
            if (max(secondary) - min(secondary)) > 6.0:
                reasons.append("hover_sway_cross_axis_large")

    return {"valid": len(reasons) == 0, "reasons": reasons}


def _gen_hover(ip: Dict, dt: float, max_time: float, rng: random.Random, variant_name: Optional[str] = None):
    duration = min(rng.uniform(*ip["duration_range"]), max_time)
    n = max(3, int(duration / dt) + 1)
    center = (
        rng.uniform(*ip["space"]["x"]),
        rng.uniform(*ip["space"]["y"]),
        rng.uniform(*ip["space"]["z"]),
    )
    variants = ip.get("variants")

    if not variants:
        sigma = rng.uniform(*ip["noise_sigma"])
        pos = [center]
        cur = list(center)
        for _ in range(1, n):
            for j in range(3):
                step = rng.gauss(0.0, sigma) * (0.012 if j < 2 else 0.007)
                cur[j] = center[j] + (cur[j] - center[j]) * 0.995 + step
            pos.append(tuple(cur))
        return {
            "positions": pos,
            "yaw_policy": "fixed",
            "noise_profile": f"gaussian_walk_sigma_{sigma:.3f}",
            "variant_name": "default_hover",
            "variant_params": {"center_xyz": [center[0], center[1], center[2]], "noise_sigma": _r(sigma)},
        }

    variant_name, variant_cfg = _select_variant(variants, rng, variant_name)
    yaw_policy = "fixed" if variant_name == "steady_hold" else "velocity_tangent"

    if variant_name == "steady_hold":
        sigma_range = variant_cfg.get("noise_sigma", ip.get("noise_sigma", [0.05, 0.15]))
        sigma = rng.uniform(*sigma_range)
        pos = [center]
        cur = list(center)
        for _ in range(1, n):
            cur[0] = center[0] + (cur[0] - center[0]) * 0.96 + rng.gauss(0.0, sigma) * 0.01
            cur[1] = center[1] + (cur[1] - center[1]) * 0.96 + rng.gauss(0.0, sigma) * 0.01
            cur[2] = center[2] + (cur[2] - center[2]) * 0.97 + rng.gauss(0.0, sigma) * 0.006
            pos.append(tuple(cur))
        params = {"center_xyz": [center[0], center[1], center[2]], "noise_sigma": _r(sigma)}
        noise_profile = f"steady_sigma_{sigma:.3f}"
    elif variant_name == "micro_orbit_hold":
        radius = rng.uniform(*variant_cfg.get("radius", [4.0, 10.0]))
        speed = rng.uniform(*variant_cfg.get("linear_speed", [0.2, 0.5]))
        orbit_duration = min(duration, rng.uniform(*variant_cfg.get("duration_range", [60.0, 90.0])))
        pos = _build_circle_hold(center, radius, speed, orbit_duration, dt, rng, 0.0)
        params = {
            "center_xyz": [center[0], center[1], center[2]],
            "radius": _r(radius),
            "linear_speed": _r(speed),
        }
        noise_profile = f"micro_orbit_r_{radius:.2f}"
    elif variant_name == "sway_hold":
        amplitude = rng.uniform(*variant_cfg.get("amplitude", [3.0, 8.0]))
        period = rng.uniform(*variant_cfg.get("period", [16.0, 28.0]))
        amplitude = min(amplitude, 1.4 * period / (2.0 * math.pi))
        axis_angle = rng.uniform(0.0, 2.0 * math.pi)
        axis = (math.cos(axis_angle), math.sin(axis_angle))
        vertical_amp = min(1.2, amplitude * 0.12)
        pos = []
        phase = rng.uniform(0.0, 2.0 * math.pi)
        for i in range(n):
            t = i * dt
            sway = amplitude * math.sin((2.0 * math.pi * t / max(period, 1e-6)) + phase)
            cross = 0.18 * amplitude * math.sin((4.0 * math.pi * t / max(period, 1e-6)) + phase * 0.5)
            z_shift = vertical_amp * math.sin((2.0 * math.pi * t / max(period, 1e-6)) + phase * 0.25)
            pos.append(
                (
                    center[0] + axis[0] * sway - axis[1] * cross,
                    center[1] + axis[1] * sway + axis[0] * cross,
                    center[2] + z_shift,
                )
            )
        params = {
            "center_xyz": [center[0], center[1], center[2]],
            "amplitude": _r(amplitude),
            "period": _r(period),
            "axis": [round(axis[0], 6), round(axis[1], 6)],
        }
        noise_profile = f"sway_a_{amplitude:.2f}_p_{period:.2f}"
    else:
        raise ValueError(f"Unsupported hover variant: {variant_name}")

    return {
        "positions": pos,
        "yaw_policy": yaw_policy,
        "noise_profile": noise_profile,
        "variant_name": variant_name,
        "variant_params": params,
    }


def _gen_straight(ip: Dict, dt: float, max_time: float, rng: random.Random):
    start = _sample_polar_xyz(rng, ip["start_radius"], ip["start_z"])
    u = _unit((-start[0], -start[1], -start[2]))
    speed = rng.uniform(*ip["base_speed"])
    target_radius = float(ip.get("target_radius", 100.0))

    pos = [start]
    t = dt
    while t < max_time and _norm(pos[-1]) > target_radius:
        jitter = 0.3 * math.sin(0.03 * t)
        v = max(0.0, speed + jitter)
        p = pos[-1]
        nxt = (p[0] + u[0] * v * dt, p[1] + u[1] * v * dt, p[2] + u[2] * v * dt)
        pos.append(nxt)
        t += dt
    return {
        "positions": pos,
        "yaw_policy": "towards_origin",
        "noise_profile": "sin_jitter",
        "variant_name": "direct_closing",
        "variant_params": {},
    }


def _gen_non_straight(ip: Dict, dt: float, max_time: float, rng: random.Random, variant_name: Optional[str] = None):
    start = _sample_polar_xyz(rng, ip["start_radius"], ip["start_z"])
    target_radius = float(ip.get("target_radius", 100.0))
    target = _target_point(start, target_radius)
    variants = ip.get("variants")

    if not variants:
        speed = min(rng.uniform(*ip["base_speed"]), 7.8)
        period = rng.uniform(*ip["lateral_period"])
        amp = min(rng.uniform(*ip["lateral_amplitude"]), 6.0 * period / (2.0 * math.pi))
        vertical_amp = min(0.02 * amp, 10.0)
        positions = _build_weave_path(start, target, speed, dt, amp, period, vertical_amp, 0.0, max_time)
        return {
            "positions": positions,
            "yaw_policy": "velocity_tangent",
            "noise_profile": f"sin_amp_{amp:.2f}_T_{period:.2f}",
            "variant_name": "legacy_weave",
            "variant_params": {"amplitude": _r(amp), "period": _r(period)},
        }

    variant_name, variant_cfg = _select_variant(variants, rng, variant_name)
    horizontal_dir = _unit((target[0] - start[0], target[1] - start[1], 0.0))
    lateral_dir = _unit((-horizontal_dir[1], horizontal_dir[0], 0.0))
    if _norm(lateral_dir) < 1e-6:
        lateral_dir = (1.0, 0.0, 0.0)
    forward = _norm((target[0] - start[0], target[1] - start[1], target[2] - start[2]))

    if variant_name == "weave_approach":
        speed = min(rng.uniform(*variant_cfg["base_speed"]), 8.2)
        period = rng.uniform(*variant_cfg["lateral_period"])
        amp = min(rng.uniform(*variant_cfg["lateral_amplitude"]), 6.0 * period / (2.0 * math.pi))
        vertical_amp = min(rng.uniform(*variant_cfg.get("vertical_amplitude", [8.0, 20.0])), 14.0)
        phase = rng.uniform(0.0, 2.0 * math.pi)
        positions = _build_weave_path(start, target, speed, dt, amp, period, vertical_amp, phase, max_time)
        params = {"amplitude": _r(amp), "period": _r(period), "vertical_amplitude": _r(vertical_amp)}
    else:
        speed = min(rng.uniform(*variant_cfg["base_speed"]), 7.4)
        positions = []

        if variant_name == "climb_then_dive":
            duration = max_time
            n = max(120, int(duration / dt) + 1)
            progress_ratio = min(0.9, (speed * duration / max(forward, 1e-6)) * 0.9)
            final_target = _lerp_point(start, target, progress_ratio)
            climb_ratio = rng.uniform(*variant_cfg["climb_ratio"])
            climb_angle = math.radians(rng.uniform(*variant_cfg["climb_angle_deg"]))
            dive_angle = math.radians(rng.uniform(*variant_cfg.get("dive_angle_deg", [10.0, 18.0])))
            apex_gain = max(45.0, min(140.0, math.tan(climb_angle) * forward * max(climb_ratio, 0.18) * 0.35))
            lateral_bias = rng.uniform(-35.0, 35.0)
            for i in range(n):
                s = i / max(n - 1, 1)
                base = _lerp_point(start, final_target, s)
                climb_arc = apex_gain * math.sin(math.pi * s)
                dive_bias = math.tan(dive_angle) * forward * 0.015 * s
                lateral = lateral_bias * math.sin(math.pi * s)
                positions.append(
                    (
                        base[0] + lateral_dir[0] * lateral,
                        base[1] + lateral_dir[1] * lateral,
                        max(10.0, base[2] + climb_arc - dive_bias),
                    )
                )
            params = {
                "climb_ratio": _r(climb_ratio),
                "apex_gain": _r(apex_gain),
                "dive_angle_deg": _r(math.degrees(dive_angle)),
            }
        elif variant_name == "turn_then_dive":
            duration = max_time
            n = max(120, int(duration / dt) + 1)
            progress_ratio = min(0.88, (speed * duration / max(forward, 1e-6)) * 0.82)
            final_target = _lerp_point(start, target, progress_ratio)
            turn_angle = math.radians(rng.uniform(*variant_cfg["turn_angle_deg"]))
            turn_radius = rng.uniform(*variant_cfg["turn_radius"])
            sign = -1.0 if rng.random() < 0.5 else 1.0
            lateral_amp = turn_radius * max(0.75, math.sin(turn_angle))
            vertical_amp = 18.0 + 12.0 * rng.random()
            for i in range(n):
                s = i / max(n - 1, 1)
                base = _lerp_point(start, final_target, s)
                lateral = sign * lateral_amp * math.sin(math.pi * s)
                z_bias = vertical_amp * math.sin(math.pi * s) * (1.0 - 0.35 * s)
                positions.append(
                    (
                        base[0] + lateral_dir[0] * lateral,
                        base[1] + lateral_dir[1] * lateral,
                        max(10.0, base[2] + z_bias),
                    )
                )
            params = {
                "turn_angle_deg": _r(math.degrees(turn_angle)),
                "turn_radius": _r(turn_radius),
                "turn_direction": int(sign),
            }
        elif variant_name == "zigzag_dive":
            duration = max_time
            n = max(120, int(duration / dt) + 1)
            progress_ratio = min(0.84, (speed * duration / max(forward, 1e-6)) * 0.72)
            final_target = _lerp_point(start, target, progress_ratio)
            seg_min, seg_max = variant_cfg.get("segments", [3, 6])
            segments = int(rng.randint(int(seg_min), int(seg_max)))
            jitter_deg = rng.uniform(*variant_cfg.get("heading_jitter_deg", [15.0, 35.0]))
            cycles = max(2, segments - 1)
            lateral_amp = max(45.0, min(80.0, forward * math.tan(math.radians(jitter_deg)) * 0.06))
            vertical_amp = 14.0 + 8.0 * rng.random()
            for i in range(n):
                s = i / max(n - 1, 1)
                base = _lerp_point(start, final_target, s)
                envelope = math.sin(math.pi * s)
                wave = math.sin(cycles * math.pi * s)
                lateral = lateral_amp * envelope * wave
                z_bias = vertical_amp * envelope - 8.0 * s
                positions.append(
                    (
                        base[0] + lateral_dir[0] * lateral,
                        base[1] + lateral_dir[1] * lateral,
                        max(10.0, base[2] + z_bias),
                    )
                )
            params = {"segments": segments, "heading_jitter_deg": _r(jitter_deg)}
        else:
            raise ValueError(f"Unsupported non-straight variant: {variant_name}")

    positions = positions[: max(3, int(max_time / dt) + 1)]
    return {
        "positions": positions,
        "yaw_policy": "velocity_tangent",
        "noise_profile": variant_name,
        "variant_name": variant_name,
        "variant_params": params,
    }


def _gen_loiter(ip: Dict, dt: float, max_time: float, rng: random.Random, variant_name: Optional[str] = None):
    center = _sample_polar_xyz(rng, ip["center_radius"], ip["center_z"])
    variants = ip.get("variants")
    if not variants:
        speed = rng.uniform(*ip["linear_speed"])
        radius = _feasible_orbit_radius(ip["radius"], speed, min(max_time, ip["duration_range"][1]), rng)
        duration = _sample_loop_duration(radius, speed, ip["duration_range"], max_time, rng)
        positions = _build_circle_hold(center, radius, speed, duration, dt, rng, 0.0)
        return {
            "positions": positions,
            "yaw_policy": ip.get("yaw_policy", "tangent"),
            "noise_profile": "loiter_circle",
            "variant_name": "circle_hold",
            "variant_params": {"center_xy": [center[0], center[1]], "radius": _r(radius)},
        }

    variant_name, variant_cfg = _select_variant(variants, rng, variant_name)
    yaw_policy = ip.get("yaw_policy", "tangent")

    if variant_name == "circle_hold":
        speed = rng.uniform(*variant_cfg["linear_speed"])
        radius = _feasible_orbit_radius(variant_cfg["radius"], speed, min(max_time, variant_cfg["duration_range"][1]), rng)
        duration = _sample_loop_duration(radius, speed, variant_cfg["duration_range"], max_time, rng)
        vertical_wave = rng.uniform(*variant_cfg.get("vertical_wave", [0.0, 6.0]))
        positions = _build_circle_hold(center, radius, speed, duration, dt, rng, vertical_wave)
        params = {"center_xy": [center[0], center[1]], "radius": _r(radius), "vertical_wave": _r(vertical_wave)}
    elif variant_name == "ellipse_hold":
        axis_a = rng.uniform(*variant_cfg["major_axis"])
        axis_b = rng.uniform(*variant_cfg["minor_axis"])
        if axis_a < axis_b:
            axis_a, axis_b = axis_b, axis_a
        speed = rng.uniform(*variant_cfg["linear_speed"])
        duration = _sample_loop_duration(axis_a, speed, variant_cfg["duration_range"], max_time, rng)
        vertical_wave = rng.uniform(*variant_cfg.get("vertical_wave", [0.0, 10.0]))
        positions = _build_ellipse_hold(center, axis_a, axis_b, speed, duration, dt, rng, vertical_wave)
        params = {"center_xy": [center[0], center[1]], "major_axis": _r(axis_a), "minor_axis": _r(axis_b), "vertical_wave": _r(vertical_wave)}
    elif variant_name == "figure8_hold":
        speed = rng.uniform(*variant_cfg["linear_speed"])
        radius = _feasible_orbit_radius(variant_cfg["radius"], speed, min(max_time, variant_cfg["duration_range"][1]), rng)
        duration = _sample_loop_duration(radius, speed, variant_cfg["duration_range"], max_time, rng)
        vertical_wave = rng.uniform(*variant_cfg.get("vertical_wave", [0.0, 8.0]))
        positions = _build_figure8_hold(center, radius, speed, duration, dt, rng, vertical_wave)
        params = {"center_xy": [center[0], center[1]], "radius": _r(radius), "vertical_wave": _r(vertical_wave)}
    elif variant_name == "offset_orbit":
        speed = rng.uniform(*variant_cfg["linear_speed"])
        radius = _feasible_orbit_radius(variant_cfg["radius"], speed, min(max_time, variant_cfg["duration_range"][1]), rng)
        duration = _sample_loop_duration(radius, speed, variant_cfg["duration_range"], max_time, rng)
        offset = rng.uniform(*variant_cfg.get("center_offset", [80.0, 220.0]))
        local_center = _offset_center(center, offset, rng)
        vertical_wave = rng.uniform(*variant_cfg.get("vertical_wave", [0.0, 8.0]))
        positions = _build_circle_hold(local_center, radius, speed, duration, dt, rng, vertical_wave)
        params = {"center_xy": [local_center[0], local_center[1]], "radius": _r(radius), "offset": _r(offset), "vertical_wave": _r(vertical_wave)}
    else:
        raise ValueError(f"Unsupported loiter variant: {variant_name}")

    return {
        "positions": positions,
        "yaw_policy": yaw_policy,
        "noise_profile": f"loiter_{variant_name}",
        "variant_name": variant_name,
        "variant_params": params,
    }


def _gen_retreat(ip: Dict, dt: float, max_time: float, rng: random.Random, profile: Dict, variant_name: Optional[str] = None):
    start = _sample_polar_xyz(rng, ip["start_radius"], ip["start_z"])
    base_dir = _unit((start[0], start[1], 0.0))
    lateral_dir = _unit((-base_dir[1], base_dir[0], 0.0))
    if _norm(lateral_dir) < 1e-6:
        lateral_dir = (1.0, 0.0, 0.0)
    speed = rng.uniform(*ip["base_speed"])
    end_radius = float(ip.get("end_radius", 5000.0))
    variants = ip.get("variants")
    z_max = float(profile["constraints"]["space"]["z"][1])

    if not variants:
        pos = [start]
        t = 0.0
        while t < max_time and _norm(pos[-1]) < end_radius:
            noise = (rng.gauss(0.0, 0.02), rng.gauss(0.0, 0.02), rng.gauss(0.0, 0.01))
            v = (
                base_dir[0] * speed + noise[0],
                base_dir[1] * speed + noise[1],
                noise[2],
            )
            p = pos[-1]
            nxt = (p[0] + v[0] * dt, p[1] + v[1] * dt, max(10.0, p[2] + v[2] * dt))
            pos.append(nxt)
            t += dt
        return {
            "positions": pos,
            "yaw_policy": "velocity_tangent",
            "noise_profile": "biased_walk",
            "variant_name": "biased_retreat",
            "variant_params": {"lateral_axis": [lateral_dir[0], lateral_dir[1]]},
        }

    variant_name, variant_cfg = _select_variant(variants, rng, variant_name)
    duration = max_time
    n = max(3, int(duration / dt) + 1)
    progress_ratio = min(1.0, (speed * duration) / max(end_radius - _norm(start), 1e-6) * 0.9)
    target_radius = min(end_radius, _norm(start) + max(300.0, speed * duration * 0.9))
    target = (base_dir[0] * target_radius, base_dir[1] * target_radius, start[2])
    final_target = _lerp_point(start, target, min(progress_ratio, 1.0))
    positions = []

    if variant_name == "direct_escape":
        for i in range(n):
            s = i / max(n - 1, 1)
            base = _lerp_point(start, final_target, s)
            positions.append((base[0], base[1], start[2]))
        params = {"lateral_axis": [lateral_dir[0], lateral_dir[1]]}
    elif variant_name == "arc_escape":
        lateral_amp = rng.uniform(*variant_cfg.get("lateral_amplitude", [80.0, 180.0]))
        sign = -1.0 if rng.random() < 0.5 else 1.0
        for i in range(n):
            s = i / max(n - 1, 1)
            base = _lerp_point(start, final_target, s)
            lateral = sign * lateral_amp * math.sin(0.5 * math.pi * s)
            positions.append((base[0] + lateral_dir[0] * lateral, base[1] + lateral_dir[1] * lateral, start[2]))
        params = {"lateral_axis": [lateral_dir[0], lateral_dir[1]], "lateral_amplitude": _r(lateral_amp), "turn_direction": int(sign)}
    elif variant_name == "zigzag_escape":
        lateral_amp = rng.uniform(*variant_cfg.get("lateral_amplitude", [60.0, 140.0]))
        lateral_amp = min(lateral_amp, speed * duration / 18.0)
        seg_min, seg_max = variant_cfg.get("segments", [3, 5])
        segments = int(rng.randint(int(seg_min), int(seg_max)))
        cycles = max(2, segments - 1)
        for i in range(n):
            s = i / max(n - 1, 1)
            base = _lerp_point(start, final_target, s)
            lateral = lateral_amp * math.sin(cycles * math.pi * s) * math.sin(math.pi * s)
            positions.append((base[0] + lateral_dir[0] * lateral, base[1] + lateral_dir[1] * lateral, start[2]))
        params = {"lateral_axis": [lateral_dir[0], lateral_dir[1]], "lateral_amplitude": _r(lateral_amp), "segments": segments}
    elif variant_name == "climb_escape":
        requested_gain = rng.uniform(*variant_cfg.get("climb_gain", [80.0, 180.0]))
        max_gain = max(20.0, z_max - start[2] - 5.0)
        climb_gain = min(requested_gain, max_gain)
        for i in range(n):
            s = i / max(n - 1, 1)
            base = _lerp_point(start, final_target, s)
            z = start[2] + climb_gain * math.sin(0.5 * math.pi * s)
            positions.append((base[0], base[1], min(z_max - 2.0, z)))
        params = {"lateral_axis": [lateral_dir[0], lateral_dir[1]], "climb_gain": _r(climb_gain)}
    else:
        raise ValueError(f"Unsupported retreat variant: {variant_name}")

    return {
        "positions": positions,
        "yaw_policy": "velocity_tangent",
        "noise_profile": f"retreat_{variant_name}",
        "variant_name": variant_name,
        "variant_params": params,
    }


def _derive_yaw(intent: str, positions: List[Tuple[float, float, float]], velocities, yaw_policy: str, rng, ip):
    if intent == "straight_penetration":
        p0 = positions[0]
        base = math.atan2(-p0[1], -p0[0])
        return [base] * len(positions)

    if intent == "hover":
        fixed = rng.uniform(-math.pi, math.pi)
        sigma = float(ip.get("yaw_noise_sigma", 0.01))
        return [_wrap_angle(fixed + rng.gauss(0.0, sigma)) for _ in positions]

    yaws = []
    if yaw_policy in {"tangent", "velocity_tangent", "towards_velocity"}:
        for v in velocities:
            yaws.append(math.atan2(v[1], v[0]))
        return yaws

    if yaw_policy == "towards_origin":
        for p in positions:
            yaws.append(math.atan2(-p[1], -p[0]))
        return yaws

    for v in velocities:
        yaws.append(math.atan2(v[1], v[0]))
    return yaws


def _build_weave_path(start, target, speed, dt, amplitude, period, vertical_amp, phase, max_time):
    forward = _norm((target[0] - start[0], target[1] - start[1], target[2] - start[2]))
    duration = min(max_time, forward / max(speed, 1e-6))
    n = max(3, int(duration / dt) + 1)
    uh = _unit((target[0] - start[0], target[1] - start[1], 0.0))
    wh = _unit((-uh[1], uh[0], 0.0))
    if _norm(wh) < 1e-6:
        wh = (1.0, 0.0, 0.0)
    positions = []
    cycles = max(duration / max(period, 1e-6), 1.0)
    progress_ratio = min(1.0, (speed * duration) / max(forward, 1e-6))
    final_target = _lerp_point(start, target, progress_ratio)
    for i in range(n):
        s = i / max(n - 1, 1)
        base = _lerp_point(start, final_target, s)
        wave = math.sin(2.0 * math.pi * cycles * s + phase)
        vert_wave = math.sin(math.pi * s) * math.sin(2.0 * math.pi * cycles * s + phase / 2.0)
        positions.append(
            (
                base[0] + wh[0] * amplitude * wave,
                base[1] + wh[1] * amplitude * wave,
                max(10.0, base[2] + vertical_amp * vert_wave),
            )
        )
    return positions


def _build_circle_hold(center, radius, speed, duration, dt, rng, vertical_wave):
    omega = speed / max(radius, 1e-6)
    direction = -1.0 if rng.random() < 0.5 else 1.0
    omega *= direction
    n = max(3, int(duration / dt) + 1)
    phi0 = rng.uniform(0.0, 2.0 * math.pi)
    phase_z = rng.uniform(0.0, 2.0 * math.pi)
    pos = []
    for i in range(n):
        t = i * dt
        x = center[0] + radius * math.cos(omega * t + phi0)
        y = center[1] + radius * math.sin(omega * t + phi0)
        z = center[2] + vertical_wave * math.sin(0.35 * omega * t + phase_z)
        pos.append((x, y, z))
    return pos


def _build_ellipse_hold(center, axis_a, axis_b, speed, duration, dt, rng, vertical_wave):
    omega = speed / max(axis_a, axis_b, 1e-6)
    direction = -1.0 if rng.random() < 0.5 else 1.0
    omega *= direction
    phi0 = rng.uniform(0.0, 2.0 * math.pi)
    phase_z = rng.uniform(0.0, 2.0 * math.pi)
    n = max(3, int(duration / dt) + 1)
    pos = []
    for i in range(n):
        t = i * dt
        angle = omega * t + phi0
        x = center[0] + axis_a * math.cos(angle)
        y = center[1] + axis_b * math.sin(angle)
        z = center[2] + vertical_wave * math.sin(0.4 * angle + phase_z)
        pos.append((x, y, z))
    return pos


def _build_figure8_hold(center, radius, speed, duration, dt, rng, vertical_wave):
    omega = speed / max(radius, 1e-6)
    direction = -1.0 if rng.random() < 0.5 else 1.0
    omega *= direction
    phi0 = rng.uniform(0.0, 2.0 * math.pi)
    phase_z = rng.uniform(0.0, 2.0 * math.pi)
    n = max(3, int(duration / dt) + 1)
    pos = []
    for i in range(n):
        t = i * dt
        angle = omega * t + phi0
        x = center[0] + radius * math.sin(angle)
        y = center[1] + radius * math.sin(angle) * math.cos(angle)
        z = center[2] + vertical_wave * math.sin(0.5 * angle + phase_z)
        pos.append((x, y, z))
    return pos


def _sample_polyline(waypoints: Sequence[Tuple[float, float, float]], step_distance: float):
    if len(waypoints) < 2:
        return list(waypoints)
    out = [tuple(waypoints[0])]
    for idx in range(1, len(waypoints)):
        a = waypoints[idx - 1]
        b = waypoints[idx]
        seg_len = _norm((b[0] - a[0], b[1] - a[1], b[2] - a[2]))
        steps = max(1, int(math.ceil(seg_len / max(step_distance, 1e-6))))
        for s in range(1, steps + 1):
            t = s / steps
            out.append(_lerp_point(a, b, t))
    return out


def _sample_bezier(control_points: Sequence[Tuple[float, float, float]], step_distance: float):
    est_len = 0.0
    for i in range(1, len(control_points)):
        est_len += _norm((
            control_points[i][0] - control_points[i - 1][0],
            control_points[i][1] - control_points[i - 1][1],
            control_points[i][2] - control_points[i - 1][2],
        ))
    n = max(3, int(math.ceil(est_len / max(step_distance, 1e-6))) + 1)
    out = []
    for i in range(n):
        t = i / max(n - 1, 1)
        out.append(_bezier_point(control_points, t))
    return out

def _bezier_point(points: Sequence[Tuple[float, float, float]], t: float):
    work = [tuple(p) for p in points]
    while len(work) > 1:
        nxt = []
        for i in range(len(work) - 1):
            nxt.append(_lerp_point(work[i], work[i + 1], t))
        work = nxt
    return work[0]


def _smooth_positions(points: Sequence[Tuple[float, float, float]], window: int = 5):
    if len(points) <= 2 or window <= 1:
        return list(points)
    radius = max(1, window // 2)
    out = [points[0]]
    for i in range(1, len(points) - 1):
        lo = max(0, i - radius)
        hi = min(len(points), i + radius + 1)
        chunk = points[lo:hi]
        out.append((
            sum(p[0] for p in chunk) / len(chunk),
            sum(p[1] for p in chunk) / len(chunk),
            sum(p[2] for p in chunk) / len(chunk),
        ))
    out.append(points[-1])
    return out


def _build_zigzag_waypoints(start, target, segments: int, heading_jitter: float, rng: random.Random):
    uh = _unit((target[0] - start[0], target[1] - start[1], 0.0))
    wh = _unit((-uh[1], uh[0], 0.0))
    total_xy = _horizontal_distance(start, target)
    waypoints = [start]
    for idx in range(1, segments):
        s = idx / segments
        base = _lerp_point(start, target, s)
        offset_mag = math.tan(heading_jitter) * total_xy * 0.12 * (1.0 - 0.45 * s)
        sign = -1.0 if idx % 2 == 0 else 1.0
        z_shift = 40.0 * math.sin(math.pi * min(s, 0.65)) - 120.0 * max(0.0, s - 0.5)
        waypoints.append((
            base[0] + wh[0] * offset_mag * sign,
            base[1] + wh[1] * offset_mag * sign,
            max(15.0, base[2] + z_shift),
        ))
    waypoints.append(target)
    return waypoints


def _turn_control_point(start, target, turn_radius, sign, progress, z_gain):
    base = _lerp_point(start, target, progress)
    uh = _unit((target[0] - start[0], target[1] - start[1], 0.0))
    wh = _unit((-uh[1], uh[0], 0.0))
    return (
        base[0] + wh[0] * turn_radius * sign,
        base[1] + wh[1] * turn_radius * sign,
        max(start[2], base[2] + z_gain),
    )


def _target_point(start, target_radius):
    direction = _unit(start)
    return (
        direction[0] * target_radius,
        direction[1] * target_radius,
        max(20.0, direction[2] * target_radius),
    )


def _move_towards_xy(start, target, distance):
    dx = target[0] - start[0]
    dy = target[1] - start[1]
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 1e-6:
        return start
    ratio = min(1.0, distance / dist)
    return (start[0] + dx * ratio, start[1] + dy * ratio, start[2] + (target[2] - start[2]) * ratio)


def _offset_center(center, offset, rng):
    theta = rng.uniform(0.0, 2.0 * math.pi)
    return (
        center[0] + offset * math.cos(theta),
        center[1] + offset * math.sin(theta),
        center[2],
    )


def _sample_loop_duration(radius, speed, duration_range, max_time, rng):
    period = 2.0 * math.pi * max(radius, 1e-6) / max(speed, 1e-6)
    min_loops = max(1, int(math.ceil(duration_range[0] / period)))
    max_loops = max(min_loops, int(math.floor(min(duration_range[1], max_time) / period)))
    loops = rng.randint(min_loops, max_loops)
    return min(max_time, loops * period)


def _feasible_orbit_radius(radius_range, speed, duration_cap, rng):
    max_radius = max(1.0, speed * max(duration_cap, 1e-6) / (2.0 * math.pi))
    low = float(radius_range[0])
    high = min(float(radius_range[1]), max_radius)
    if high <= 0:
        high = low
    if high < low:
        low = max(1.0, high * 0.9)
    return rng.uniform(low, max(low, high))



def compute_variant_quotas(total_quota: int, variants: Dict) -> Dict[str, int]:
    if total_quota <= 0 or not variants:
        return {}

    weighted = []
    total_weight = 0.0
    for name, cfg in variants.items():
        weight = float(cfg.get("weight", 1.0))
        if weight <= 0:
            continue
        total_weight += weight
        weighted.append((name, weight))
    if total_weight <= 0:
        raise ValueError("No positive-weight variants configured")

    quotas = {}
    for name, weight in weighted:
        quotas[name] = max(1, int(round(total_quota * weight / total_weight)))
    return quotas


def _build_generation_tasks(config: Dict) -> List[Dict]:
    class_quota = config["class_quota"]
    intent_profiles = config["intent_profiles"]
    tasks: List[Dict] = []

    for intent in INTENT_ORDER:
        quota = int(class_quota.get(intent, 0))
        if quota <= 0:
            continue
        variants = intent_profiles[intent].get("variants")
        if variants:
            quotas = compute_variant_quotas(quota, variants)
            intent_sample_index = 0
            for variant_name, target_quota in quotas.items():
                for variant_sample_index in range(target_quota):
                    tasks.append(
                        {
                            "intent": intent,
                            "variant_name": variant_name,
                            "target_quota": target_quota,
                            "variant_sample_index": variant_sample_index,
                            "intent_sample_index": intent_sample_index,
                        }
                    )
                    intent_sample_index += 1
        else:
            for intent_sample_index in range(quota):
                tasks.append(
                    {
                        "intent": intent,
                        "variant_name": None,
                        "target_quota": quota,
                        "variant_sample_index": intent_sample_index,
                        "intent_sample_index": intent_sample_index,
                    }
                )
    return tasks


def _select_variant(variants: Dict, rng: random.Random, requested_variant_name: Optional[str]):
    if requested_variant_name is not None:
        if requested_variant_name not in variants:
            raise ValueError(f"Unsupported variant: {requested_variant_name}")
        return requested_variant_name, variants[requested_variant_name]
    return _choose_weighted_variant(rng, variants)


def _lateral_offsets(points: Sequence[Tuple[float, float, float]]):
    if len(points) < 3:
        return []
    start = points[0]
    end = points[-1]
    direction = _unit((end[0] - start[0], end[1] - start[1], 0.0))
    lateral = _unit((-direction[1], direction[0], 0.0))
    offsets = []
    for point in points[1:-1]:
        rel = (point[0] - start[0], point[1] - start[1], 0.0)
        offsets.append(rel[0] * lateral[0] + rel[1] * lateral[1])
    return offsets


def _print_progress(processed: int, total: int, intent: str, generated: int, failed: int, attempts_used: int):
    if total <= 0:
        return
    msg = f"\rprogress {processed}/{total} intent={intent} generated={generated} failed={failed} attempts={attempts_used}"
    sys.stdout.write(msg)
    sys.stdout.flush()


def _sanitize_token(value: str) -> str:
    text = str(value).strip().replace(" ", "_")
    out = []
    for ch in text:
        if ch.isalnum() or ch in {"_", "-"}:
            out.append(ch)
        else:
            out.append("_")
    return "".join(out) or "unknown"


def _choose_weighted_variant(rng: random.Random, variants: Dict):
    items = []
    total = 0.0
    for name, cfg in variants.items():
        weight = float(cfg.get("weight", 1.0))
        if weight <= 0:
            continue
        total += weight
        items.append((name, cfg, total))
    if not items:
        raise ValueError("No positive-weight variants configured")
    pick = rng.uniform(0.0, total)
    for name, cfg, threshold in items:
        if pick <= threshold:
            return name, cfg
    return items[-1][0], items[-1][1]


def _derivative(points, dt):
    out = []
    for i in range(len(points)):
        if i == len(points) - 1:
            p_prev = points[i - 1]
            p_cur = points[i]
            out.append(((p_cur[0] - p_prev[0]) / dt, (p_cur[1] - p_prev[1]) / dt, (p_cur[2] - p_prev[2]) / dt))
        else:
            p_cur = points[i]
            p_nxt = points[i + 1]
            out.append(((p_nxt[0] - p_cur[0]) / dt, (p_nxt[1] - p_cur[1]) / dt, (p_nxt[2] - p_cur[2]) / dt))
    return out


def _sample_polar_xyz(rng, radius_range, z_range):
    theta = rng.uniform(0.0, 2.0 * math.pi)
    r = rng.uniform(*radius_range)
    z = rng.uniform(*z_range)
    return r * math.cos(theta), r * math.sin(theta), z


def _unit(v):
    n = _norm(v)
    if n < 1e-12:
        return (1.0, 0.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def _norm(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _path_length(points: Sequence[Tuple[float, float, float]]):
    total = 0.0
    for i in range(1, len(points)):
        total += _norm((
            points[i][0] - points[i - 1][0],
            points[i][1] - points[i - 1][1],
            points[i][2] - points[i - 1][2],
        ))
    return total


def _max_lateral_deviation(points: Sequence[Tuple[float, float, float]]):
    if len(points) < 3:
        return 0.0
    start = points[0]
    end = points[-1]
    line = (end[0] - start[0], end[1] - start[1], end[2] - start[2])
    line_norm = _norm(line)
    if line_norm < 1e-9:
        return 0.0
    max_dev = 0.0
    for p in points[1:-1]:
        rel = (p[0] - start[0], p[1] - start[1], p[2] - start[2])
        cross = (
            line[1] * rel[2] - line[2] * rel[1],
            line[2] * rel[0] - line[0] * rel[2],
            line[0] * rel[1] - line[1] * rel[0],
        )
        max_dev = max(max_dev, _norm(cross) / line_norm)
    return max_dev


def _estimate_base_speed(velocities):
    if not velocities:
        return 0.0
    mags = [_norm(v) for v in velocities]
    return sum(mags) / len(mags)

def _angle_diff(a, b):
    return math.atan2(math.sin(a - b), math.cos(a - b))


def _unwrap_angles(values: Sequence[float]):
    if not values:
        return []
    out = [values[0]]
    for value in values[1:]:
        out.append(out[-1] + _angle_diff(value, out[-1]))
    return out


def _angle_spread(values: Sequence[float]) -> float:
    return _std(_unwrap_angles(values))


def _angle_excursion(values: Sequence[float]) -> float:
    unwrapped = _unwrap_angles(values)
    if not unwrapped:
        return 0.0
    return max(unwrapped) - min(unwrapped)


def _wrap_angle(a):
    return math.atan2(math.sin(a), math.cos(a))


def _std(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    m = sum(values) / len(values)
    var = sum((x - m) * (x - m) for x in values) / len(values)
    return math.sqrt(var)


def _mean_tangential_score(rows: Sequence[Dict], center_xy: Tuple[float, float]):
    scores = []
    for row in rows:
        rx = row["pos_x"] - center_xy[0]
        ry = row["pos_y"] - center_xy[1]
        vx = row["vel_x"]
        vy = row["vel_y"]
        rn = math.sqrt(rx * rx + ry * ry)
        vn = math.sqrt(vx * vx + vy * vy)
        if rn < 1e-6 or vn < 1e-6:
            continue
        radial_alignment = abs((rx * vx + ry * vy) / (rn * vn))
        scores.append(1.0 - radial_alignment)
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _cumulative_angle_travel(points: Sequence[Tuple[float, float, float]], center_xy: Tuple[float, float]):
    angles = [math.atan2(p[1] - center_xy[1], p[0] - center_xy[0]) for p in points]
    unwrapped = _unwrap_angles(angles)
    total = 0.0
    for i in range(1, len(unwrapped)):
        total += abs(unwrapped[i] - unwrapped[i - 1])
    return total


def _radial_spread(points: Sequence[Tuple[float, float, float]], center_xy: Tuple[float, float]):
    radii = [math.sqrt((p[0] - center_xy[0]) ** 2 + (p[1] - center_xy[1]) ** 2) for p in points]
    if not radii:
        return 0.0
    return max(radii) - min(radii)


def _bbox_aspect_ratio(points: Sequence[Tuple[float, float, float]], center_xy: Tuple[float, float]):
    xs = [abs(p[0] - center_xy[0]) for p in points]
    ys = [abs(p[1] - center_xy[1]) for p in points]
    max_x = max(xs) if xs else 0.0
    max_y = max(ys) if ys else 0.0
    minor = max(min(max_x, max_y), 1e-6)
    return max(max_x, max_y) / minor


def _count_sign_changes(values: Sequence[float]):
    last = 0
    count = 0
    for value in values:
        sign = 0
        if value > 1e-6:
            sign = 1
        elif value < -1e-6:
            sign = -1
        if sign != 0 and last != 0 and sign != last:
            count += 1
        if sign != 0:
            last = sign
    return count


def _horizontal_distance(a, b):
    return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)


def _lerp_point(a, b, t):
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def _r(x):
    return round(float(x), 6)


def _stable_seed(base_seed: int, intent: str, sample_index: int, attempt: int, variant_name: Optional[str] = None) -> int:
    payload = f"{base_seed}|{intent}|{variant_name or ""}|{sample_index}|{attempt}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], byteorder="big") % (2**31)


def _write_sample_csv(path: Path, rows: List[Dict]):
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_metadata_csv(path: Path, rows: List[Dict]):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

