from __future__ import annotations

import math
from typing import Dict, List

from ..models import Trajectory


def _clip_metric(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return value


def validate_hard_constraints(traj: Trajectory, airframe, cfg: Dict) -> Dict:
    points = traj.points
    if not points:
        return {"passed": False, "violations": ["empty_trajectory"]}

    space = cfg["constraints"]["space"]
    max_speed = max(point.speed for point in points)
    min_speed = min(point.speed for point in points)
    accelerations: List[tuple[float, float, float]] = []
    jerks: List[float] = []
    yaw_rates: List[float] = []
    turn_rates: List[float] = []
    turn_radii: List[float] = []
    climb_rates = [point.vz for point in points]

    for idx in range(1, len(points)):
        prev = points[idx - 1]
        cur = points[idx]
        dt = max(cur.t - prev.t, 1e-6)
        ax = (cur.vx - prev.vx) / dt
        ay = (cur.vy - prev.vy) / dt
        az = (cur.vz - prev.vz) / dt
        accelerations.append((ax, ay, az))
        yaw_rates.append(abs(cur.yaw - prev.yaw) / dt)
        turn_rate = abs(cur.course - prev.course) / dt
        turn_rates.append(turn_rate)
        turn_radii.append(cur.speed / max(turn_rate, 1e-6))
    for idx in range(1, len(accelerations)):
        prev = accelerations[idx - 1]
        cur = accelerations[idx]
        dt = max(points[idx + 1].t - points[idx].t, 1e-6)
        jerks.append(math.sqrt(sum(((cur_i - prev_i) / dt) ** 2 for cur_i, prev_i in zip(cur, prev))))

    a_long_values = []
    a_lat_values = []
    for point, accel in zip(points[1:], accelerations):
        speed = max(point.speed, 1e-6)
        ux = point.vx / speed
        uy = point.vy / speed
        a_long = accel[0] * ux + accel[1] * uy
        a_lat = math.sqrt(max(accel[0] ** 2 + accel[1] ** 2 - a_long ** 2, 0.0))
        a_long_values.append(abs(a_long))
        a_lat_values.append(a_lat)
    max_a_long = sorted(a_long_values)[int(0.95 * (len(a_long_values) - 1))] if a_long_values else 0.0
    max_a_lat = sorted(a_lat_values)[int(0.95 * (len(a_lat_values) - 1))] if a_lat_values else 0.0

    jerk_metric = sorted(jerks)[int(0.95 * (len(jerks) - 1))] if jerks else 0.0

    violations: List[str] = []
    if max_speed > airframe.v_dash_range[1] + 1e-6:
        violations.append("max_speed")
    if airframe.family == "fixed_wing" and min_speed < airframe.v_min - 1e-6:
        violations.append("min_speed")
    if max_a_long > max(airframe.a_long_max, airframe.a_brake_max) + 1e-6:
        violations.append("a_long")
    if max_a_lat > airframe.a_lat_max + 1e-6:
        violations.append("a_lat")
    if jerks and jerk_metric > airframe.jerk_max + 1e-6:
        violations.append("jerk")
    if climb_rates and max(climb_rates) > airframe.climb_rate_max + 1e-6:
        violations.append("climb_rate")
    if climb_rates and abs(min(climb_rates)) > airframe.descent_rate_max + 1e-6:
        violations.append("descent_rate")
    if yaw_rates and max(yaw_rates) > airframe.yaw_rate_max + 1e-6:
        violations.append("yaw_rate")
    if airframe.family == "fixed_wing" and turn_rates and max(turn_rates) > airframe.turn_rate_max + 1e-6:
        violations.append("turn_rate")
    if airframe.family == "fixed_wing" and turn_radii and min(turn_radii) < airframe.min_turn_radius - 1e-6:
        violations.append("turn_radius")
    if any(point.x < space["x"][0] or point.x > space["x"][1] or point.y < space["y"][0] or point.y > space["y"][1] or point.z < space["z"][0] or point.z > space["z"][1] for point in points):
        violations.append("space")

    return {
        "passed": not violations,
        "violations": violations,
        "max_speed": _clip_metric(max_speed),
        "min_speed": _clip_metric(min_speed),
        "max_a_long": _clip_metric(max_a_long),
        "max_a_lat": _clip_metric(max_a_lat),
        "max_jerk": _clip_metric(jerk_metric),
        "max_yaw_rate": _clip_metric(max(yaw_rates) if yaw_rates else 0.0),
        "max_turn_rate": _clip_metric(max(turn_rates) if turn_rates else 0.0),
        "min_turn_radius": _clip_metric(min(turn_radii) if turn_radii else 0.0),
    }



