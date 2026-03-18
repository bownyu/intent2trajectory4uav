from __future__ import annotations

import math
from typing import Dict, List, Sequence

from ..models import Trajectory, TrajectoryPoint
from ..stages.primitives import evaluate_command
from ..stages.yaw_modes import desired_yaw
from .course_speed import step_course_speed
from .velocity_tracking import step_velocity_tracking


def _polar_basis(x: float, y: float) -> tuple[tuple[float, float], tuple[float, float]]:
    radius = math.hypot(x, y)
    erx = x / max(radius, 1e-6)
    ery = y / max(radius, 1e-6)
    return (erx, ery), (-ery, erx)


def _desired_velocity_from_commands(state: Dict, vr_cmd: float, vt_cmd: float, vz_cmd: float) -> tuple[float, float, float]:
    e_r, e_t = _polar_basis(state["x"], state["y"])
    vx = vr_cmd * e_r[0] + vt_cmd * e_t[0]
    vy = vr_cmd * e_r[1] + vt_cmd * e_t[1]
    return vx, vy, vz_cmd


def rollout(plan, airframe, dt: float, cfg: Dict, initial_state: Dict) -> Trajectory:
    state = dict(initial_state)
    points: List[TrajectoryPoint] = []
    flight_modes: List[str] = []
    elapsed_global = 0.0

    for stage in plan:
        duration = stage.sampled_duration()
        steps = max(int(duration / dt), 1)
        flight_mode = stage.flight_mode if stage.flight_mode != "auto" else ("hover" if airframe.family == "multirotor" or (airframe.family == "vtol" and airframe.hover_capable and stage.yaw_mode in {"station_facing", "station_scan"}) else "cruise")
        if not flight_modes or flight_modes[-1] != flight_mode:
            flight_modes.append(flight_mode)
        for step_idx in range(steps):
            elapsed = step_idx * dt
            vr_cmd = evaluate_command(stage.vr_cmd, elapsed, duration)
            vt_cmd = evaluate_command(stage.vt_cmd, elapsed, duration)
            vz_cmd = evaluate_command(stage.vz_cmd, elapsed, duration)
            desired_velocity = _desired_velocity_from_commands(state, vr_cmd, vt_cmd, vz_cmd)
            yaw_cmd = desired_yaw(stage.yaw_mode, (state["x"], state["y"], state["z"]), desired_velocity, elapsed_global)
            if flight_mode == "cruise" or airframe.family == "fixed_wing":
                state = step_course_speed(state, desired_velocity, yaw_cmd, airframe, dt)
            else:
                state = step_velocity_tracking(state, desired_velocity, yaw_cmd, airframe, dt)
            elapsed_global += dt
            points.append(
                TrajectoryPoint(
                    t=elapsed_global,
                    x=state["x"],
                    y=state["y"],
                    z=state["z"],
                    vx=state["vx"],
                    vy=state["vy"],
                    vz=state["vz"],
                    yaw=state["yaw"],
                    course=state["course"],
                    speed=state["speed"],
                    stage_name=stage.name,
                    flight_mode=flight_mode,
                )
            )
    return Trajectory(points=points, dt=dt, stage_plan=list(plan), flight_mode_sequence=flight_modes)
