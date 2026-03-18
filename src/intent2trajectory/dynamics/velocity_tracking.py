from __future__ import annotations

import math
from typing import Dict, Tuple


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def step_velocity_tracking(state: Dict, desired_velocity: Tuple[float, float, float], desired_yaw: float, airframe, dt: float) -> Dict:
    vx, vy, vz = state["vx"], state["vy"], state["vz"]
    dvx = (desired_velocity[0] - vx) / max(airframe.control_tau, 1e-6)
    dvy = (desired_velocity[1] - vy) / max(airframe.control_tau, 1e-6)
    ax_norm = math.hypot(dvx, dvy)
    if ax_norm > airframe.a_lat_max:
        scale = airframe.a_lat_max / max(ax_norm, 1e-6)
        dvx *= scale
        dvy *= scale
    dvz = _clip((desired_velocity[2] - vz) / max(airframe.control_tau, 1e-6), -airframe.descent_rate_max, airframe.climb_rate_max)

    vx_next = vx + dvx * dt
    vy_next = vy + dvy * dt
    vz_next = _clip(vz + dvz * dt, -airframe.descent_rate_max, airframe.climb_rate_max)
    speed = math.hypot(vx_next, vy_next)
    max_speed = airframe.v_dash_range[1]
    if speed > max_speed:
        scale = max_speed / max(speed, 1e-6)
        vx_next *= scale
        vy_next *= scale
        speed = max_speed

    yaw_delta = desired_yaw - state["yaw"]
    while yaw_delta > math.pi:
        yaw_delta -= 2.0 * math.pi
    while yaw_delta < -math.pi:
        yaw_delta += 2.0 * math.pi
    yaw_step = _clip(yaw_delta, -airframe.yaw_rate_max * dt, airframe.yaw_rate_max * dt)
    yaw_next = state["yaw"] + yaw_step
    course_next = math.atan2(vy_next, vx_next) if speed > 1e-6 else state["course"]

    return {
        "x": state["x"] + vx_next * dt,
        "y": state["y"] + vy_next * dt,
        "z": state["z"] + vz_next * dt,
        "vx": vx_next,
        "vy": vy_next,
        "vz": vz_next,
        "yaw": yaw_next,
        "course": course_next,
        "speed": speed,
    }
