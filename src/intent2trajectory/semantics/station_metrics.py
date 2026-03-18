from __future__ import annotations

import math
from typing import Dict, Iterable, List, Sequence, Tuple

from ..models import StationMetrics, Trajectory

EPS = 1e-6


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _unwrap(angles: Sequence[float]) -> List[float]:
    if not angles:
        return []
    out = [angles[0]]
    for angle in angles[1:]:
        delta = angle - out[-1]
        while delta > math.pi:
            angle -= 2.0 * math.pi
            delta = angle - out[-1]
        while delta < -math.pi:
            angle += 2.0 * math.pi
            delta = angle - out[-1]
        out.append(angle)
    return out


def _count_sign_changes(values: Sequence[float], deadband: float) -> int:
    last = 0
    changes = 0
    for value in values:
        sign = 0
        if value > deadband:
            sign = 1
        elif value < -deadband:
            sign = -1
        if sign == 0:
            continue
        if last and sign != last:
            changes += 1
        last = sign
    return changes


def _count_abort_events(ranges: Sequence[float], dt: float, probe: float, abort: float, recommit: float, window_sec: float) -> int:
    if len(ranges) < 5:
        return 0
    window = max(int(window_sec / max(dt, EPS)), 3)
    count = 0
    for center in range(1, len(ranges) - window - 1):
        before = max(ranges[max(0, center - window):center])
        minimum = ranges[center]
        after_window = ranges[center + 1:center + window]
        if not after_window:
            continue
        after = max(after_window)
        if before - minimum < probe:
            continue
        if after - minimum < abort:
            continue
        remainder = ranges[center + window:]
        if not remainder:
            continue
        recommit_min = min(remainder)
        if after - recommit_min >= recommit:
            count += 1
    return count


def _linear_slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    x_mean = _mean(xs)
    y_mean = _mean(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom <= EPS:
        return 0.0
    numer = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    return numer / denom


def compute_station_metrics(traj: Trajectory, bands: Dict[str, Sequence[float]], cfg: Dict, intent: str) -> StationMetrics:
    points = traj.points
    if len(points) < 2:
        return StationMetrics(values={"range_mean": 0.0}, active_band_name="")

    xs = [point.x for point in points]
    ys = [point.y for point in points]
    zs = [point.z for point in points]
    times = [point.t for point in points]
    speeds = [point.speed for point in points]
    ranges = [math.hypot(x, y) for x, y in zip(xs, ys)]
    bearings = _unwrap([math.atan2(y, x) for x, y in zip(xs, ys)])
    radial_speeds: List[float] = []
    tangential_speeds: List[float] = []
    course_alignments: List[float] = []
    yaw_alignments: List[float] = []
    for point, radius in zip(points, ranges):
        erx = point.x / (radius + EPS)
        ery = point.y / (radius + EPS)
        etx = -ery
        ety = erx
        radial_speeds.append(point.vx * erx + point.vy * ery)
        tangential_speeds.append(point.vx * etx + point.vy * ety)
        station_angle = math.atan2(-point.y, -point.x)
        course_alignments.append(math.cos(point.course - station_angle))
        yaw_alignments.append(math.cos(point.yaw - station_angle))

    bearing_cumulative_change = sum(abs(bearings[idx] - bearings[idx - 1]) for idx in range(1, len(bearings)))
    encircle_cycles = bearing_cumulative_change / (2.0 * math.pi)
    path_length = 0.0
    altitude_excursion = (max(zs) - min(zs)) if zs else 0.0
    for idx in range(1, len(points)):
        dx = xs[idx] - xs[idx - 1]
        dy = ys[idx] - ys[idx - 1]
        dz = zs[idx] - zs[idx - 1]
        path_length += math.sqrt(dx * dx + dy * dy + dz * dz)
    displacement = math.sqrt((xs[-1] - xs[0]) ** 2 + (ys[-1] - ys[0]) ** 2 + (zs[-1] - zs[0]) ** 2)
    path_ratio = path_length / max(displacement, EPS)

    active_band_name = "hold" if intent == "hover" else "loiter" if intent == "loiter" else "terminal" if intent == "attack" else "escape"
    active_band = bands.get(active_band_name, bands.get("hold", [0.0, 1.0]))
    dwell_ratio_in_band = sum(1.0 for radius in ranges if active_band[0] <= radius <= active_band[1]) / len(ranges)
    dwell_hold = sum(1.0 for radius in ranges if bands["hold"][0] <= radius <= bands["hold"][1]) / len(ranges)
    dwell_loiter = sum(1.0 for radius in ranges if bands["loiter"][0] <= radius <= bands["loiter"][1]) / len(ranges)

    range_width = max(active_band[1] - active_band[0], EPS)
    radius_stability = 1.0 - _clip(_std(ranges) / max(0.5 * range_width, EPS), 0.0, 1.0)
    radial_drift = abs(ranges[-1] - ranges[0]) / range_width
    radial_neutrality = 1.0 - _clip(abs(ranges[-1] - ranges[0]) / range_width, 0.0, 1.0)

    r_core = float(cfg["intent_regions"]["risk_bands"]["core"])
    r_sensitive = float(cfg["intent_regions"]["risk_bands"]["sensitive"])
    close_thr = float(cfg["intent_regions"]["parameters"].get("v_close_thr", 0.5))
    open_thr = float(cfg["intent_regions"]["parameters"].get("v_open_thr", 0.5))
    close_frac = sum(1.0 for value in radial_speeds if value < -close_thr) / len(radial_speeds)
    open_frac = sum(1.0 for value in radial_speeds if value > open_thr) / len(radial_speeds)
    net_close = _clip((ranges[0] - ranges[-1]) / max(ranges[0] - r_core, EPS), 0.0, 1.0)
    intrusion_depth = _clip((r_sensitive - min(ranges)) / max(r_sensitive - r_core, EPS), 0.0, 1.0)
    net_open = _clip((ranges[-1] - ranges[0]) / max(cfg["intent_regions"]["risk_bands"]["exit"] - ranges[0], EPS), 0.0, 1.0)
    tangential_abs = [abs(value) for value in tangential_speeds]
    radial_abs = [abs(value) for value in radial_speeds]
    tangential_dominance_ratio = _mean(tangential_abs) / max(_mean(radial_abs), EPS)
    outward_monotonic_ratio = sum(1.0 for idx in range(1, len(ranges)) if ranges[idx] - ranges[idx - 1] >= -float(cfg["intent_regions"]["parameters"].get("dr_tol", 5.0))) / max(len(ranges) - 1, 1)
    sign_changes = _count_sign_changes(radial_speeds, float(cfg["intent_regions"]["parameters"].get("v_r_eps", 0.2)))
    abort_count = _count_abort_events(
        ranges,
        traj.dt,
        float(cfg["intent_regions"]["parameters"].get("delta_r_probe", 80.0)),
        float(cfg["intent_regions"]["parameters"].get("delta_r_abort", 60.0)),
        float(cfg["intent_regions"]["parameters"].get("delta_r_recommit", 60.0)),
        float(cfg["intent_regions"]["parameters"].get("w_abort", 8.0)),
    )

    values = {
        "duration": times[-1] - times[0],
        "start_range": ranges[0],
        "end_range": ranges[-1],
        "range_mean": _mean(ranges),
        "range_std": _std(ranges),
        "range_slope": _linear_slope(times, ranges),
        "min_range": min(ranges),
        "max_range": max(ranges),
        "bearing_cumulative_change": bearing_cumulative_change,
        "encircle_cycles": encircle_cycles,
        "radial_speed_mean": _mean(radial_speeds),
        "radial_speed_std": _std(radial_speeds),
        "tangential_speed_mean": _mean(tangential_abs),
        "tangential_dominance_ratio": tangential_dominance_ratio,
        "dwell_ratio_in_band": dwell_ratio_in_band,
        "dwell_hold": dwell_hold,
        "dwell_loiter": dwell_loiter,
        "course_point_ratio": sum(1.0 for value in course_alignments if value > math.cos(math.radians(cfg["intent_regions"]["parameters"].get("alpha_course_deg", 30.0)))) / len(course_alignments),
        "yaw_point_ratio": sum(1.0 for value in yaw_alignments if value > math.cos(math.radians(cfg["intent_regions"]["parameters"].get("alpha_yaw_deg", 35.0)))) / len(yaw_alignments),
        "close_frac": close_frac,
        "net_close": net_close,
        "intrusion_depth": intrusion_depth,
        "open_frac": open_frac,
        "net_open": net_open,
        "path_length": path_length,
        "path_ratio": path_ratio,
        "sign_changes": float(sign_changes),
        "abort_count": float(abort_count),
        "outward_monotonic_ratio": outward_monotonic_ratio,
        "radius_stability": radius_stability,
        "radial_drift": radial_drift,
        "radial_neutrality": radial_neutrality,
        "mean_speed": _mean(speeds),
        "max_speed": max(speeds),
        "altitude_excursion": altitude_excursion,
    }
    return StationMetrics(values=values, active_band_name=active_band_name)
