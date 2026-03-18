from __future__ import annotations

import math
from typing import Tuple


def desired_yaw(mode: str, position: Tuple[float, float, float], velocity: Tuple[float, float, float], elapsed: float = 0.0) -> float:
    x, y, _ = position
    vx, vy, _ = velocity
    course = math.atan2(vy, vx) if abs(vx) + abs(vy) > 1e-6 else 0.0
    station_angle = math.atan2(-y, -x)
    if mode == "course_locked":
        return course
    if mode == "station_facing":
        return station_angle
    if mode == "station_scan":
        return station_angle + 0.35 * math.sin(0.2 * elapsed)
    if mode == "decoupled":
        return course + 0.45 * math.sin(0.1 * elapsed)
    return course
