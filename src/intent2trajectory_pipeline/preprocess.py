import math
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class PreprocessResult:
    initial_pose: Dict[str, float]
    local_rows: List[Dict[str, float]]
    coordinate_frame: str


def _wrap_pi(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def _enu_to_ned(row: Dict[str, float]) -> Dict[str, float]:
    return {
        'time_relative': row['time_relative'],
        'x': row['y'],
        'y': row['x'],
        'z': -row['z'],
        'yaw': _wrap_pi((math.pi / 2) - row['yaw']),
    }


def preprocess_rows(rows: List[Dict[str, float]], *, coordinate_frame: str) -> PreprocessResult:
    if coordinate_frame not in {'ENU', 'NED'}:
        raise ValueError(f'Unsupported coordinate_frame: {coordinate_frame}')
    if not rows:
        raise ValueError('rows must not be empty')

    initial_pose = {
        'x': rows[0]['x'],
        'y': rows[0]['y'],
        'z': rows[0]['z'],
        'yaw': rows[0]['yaw'],
    }

    ned_rows = [_enu_to_ned(row) for row in rows] if coordinate_frame == 'ENU' else [dict(row) for row in rows]
    origin = ned_rows[0]
    local_rows: List[Dict[str, float]] = []
    for row in ned_rows:
        local_rows.append(
            {
                'time_relative': row['time_relative'],
                'x': row['x'] - origin['x'],
                'y': row['y'] - origin['y'],
                'z': row['z'] - origin['z'],
                'yaw': row['yaw'],
            }
        )

    return PreprocessResult(initial_pose=initial_pose, local_rows=local_rows, coordinate_frame=coordinate_frame)


def build_prepare_segment(
    *,
    initial_local_pose: Dict[str, float],
    safe_spawn_z: float,
    prepare_duration: float,
    dt: float,
) -> List[Dict[str, float]]:
    if dt <= 0:
        raise ValueError('dt must be positive')
    steps = max(2, int(round(prepare_duration / dt)) + 1)
    result: List[Dict[str, float]] = []
    for idx in range(steps):
        ratio = idx / (steps - 1)
        result.append(
            {
                'time_relative': idx * dt,
                'x': initial_local_pose['x'],
                'y': initial_local_pose['y'],
                'z': safe_spawn_z + (initial_local_pose['z'] - safe_spawn_z) * ratio,
                'yaw': initial_local_pose['yaw'],
            }
        )
    return result
