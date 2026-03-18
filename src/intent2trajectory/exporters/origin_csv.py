from __future__ import annotations

import json
from typing import Dict, List


def build_origin_rows(sample: Dict) -> List[Dict]:
    rows: List[Dict] = []
    for point in sample["trajectory"]["points"]:
        rows.append(
            {
                "time_relative": f"{point['t']:.3f}",
                "primary_intent": sample["metadata"]["primary_intent"],
                "motion_style": sample["metadata"]["motion_style"],
                "airframe_name": sample["metadata"]["airframe_name"],
                "stage_name": point["stage_name"],
                "flight_mode": point["flight_mode"],
                "pos_x": f"{point['x']:.6f}",
                "pos_y": f"{point['y']:.6f}",
                "pos_z": f"{point['z']:.6f}",
                "yaw": f"{point['yaw']:.6f}",
                "vel_x": f"{point['vx']:.6f}",
                "vel_y": f"{point['vy']:.6f}",
                "vel_z": f"{point['vz']:.6f}",
                "risk_vector_json": json.dumps(sample["metadata"]["risk_vector"], ensure_ascii=False, sort_keys=True),
            }
        )
    return rows
