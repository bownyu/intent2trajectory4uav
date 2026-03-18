from __future__ import annotations

import math
from typing import Dict, Tuple


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def step_course_speed(state: Dict, desired_velocity: Tuple[float, float, float], desired_yaw: float, airframe, dt: float) -> Dict:
    desired_speed = math.hypot(desired_velocity[0], desired_velocity[1])
    desired_speed = _clip(desired_speed, airframe.v_min, airframe.v_dash_range[1])
    desired_course = math.atan2(desired_velocity[1], desired_velocity[0]) if desired_speed > 1e-6 else state["course"]

    course_delta = desired_course - state["course"]
    while course_delta > math.pi:
        course_delta -= 2.0 * math.pi
    while course_delta < -math.pi:
        course_delta += 2.0 * math.pi
    course_step = _clip(course_delta, -airframe.turn_rate_max * dt, airframe.turn_rate_max * dt)
    course_next = state["course"] + course_step

    speed_delta = desired_speed - state["speed"]
    accel_limit = airframe.a_long_max if speed_delta >= 0 else airframe.a_brake_max
    speed_next = _clip(state["speed"] + _clip(speed_delta, -accel_limit * dt, accel_limit * dt), airframe.v_min, airframe.v_dash_range[1])
    vx_next = speed_next * math.cos(course_next)
    vy_next = speed_next * math.sin(course_next)

    vz_delta = desired_velocity[2] - state["vz"]
    vz_next = _clip(state["vz"] + _clip(vz_delta, -airframe.descent_rate_max * dt, airframe.climb_rate_max * dt), -airframe.descent_rate_max, airframe.climb_rate_max)

    yaw_delta = desired_yaw - state["yaw"]
    while yaw_delta > math.pi:
        yaw_delta -= 2.0 * math.pi
    while yaw_delta < -math.pi:
        yaw_delta += 2.0 * math.pi
    yaw_next = state["yaw"] + _clip(yaw_delta, -airframe.yaw_rate_max * dt, airframe.yaw_rate_max * dt)

    return {
        "x": state["x"] + vx_next * dt,
        "y": state["y"] + vy_next * dt,
        "z": state["z"] + vz_next * dt,
        "vx": vx_next,
        "vy": vy_next,
        "vz": vz_next,
        "yaw": yaw_next,
        "course": course_next,
        "speed": speed_next,
    }
