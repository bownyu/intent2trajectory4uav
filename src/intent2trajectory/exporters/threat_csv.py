from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List


def _select_rows_1hz(points: List[Dict]) -> List[Dict]:
    selected: List[Dict] = []
    next_second = 0
    for point in points:
        second = int(point["t"])
        if second >= next_second:
            selected.append(point)
            next_second = second + 1
    if points and selected[-1] is not points[-1]:
        selected.append(points[-1])
    return selected


def _format_time(base: datetime, offset: float) -> str:
    return (base + timedelta(seconds=offset)).strftime("%Y-%m-%d %H:%M:%S")


def build_threat_rows(sample: Dict, target_id: int, threat_cfg: Dict) -> List[Dict]:
    start_time = datetime.fromisoformat(threat_cfg.get("start_time", "2026-03-13T10:00:00"))
    points = _select_rows_1hz(sample["trajectory"]["points"])
    station = threat_cfg.get("station", {"latitude": 31.2304, "longitude": 121.4737})
    rows: List[Dict] = []
    for point in points:
        lat = station["latitude"] + point["y"] / 111111.0
        lon = station["longitude"] + point["x"] / max(111111.0, 1e-6)
        rows.append(
            {
                "target_id": str(target_id),
                "occur_time": _format_time(start_time, point["t"]),
                "uav_height": f"{point['z']:.3f}",
                "uav_speed": f"{point['speed']:.3f}",
                "uav_latitude": f"{lat:.7f}",
                "uav_longitude": f"{lon:.7f}",
                "uav_azimuth_angle": f"{point['yaw']:.6f}",
                "uav_direction": f"{point['course']:.6f}",
                "intention": sample["metadata"]["primary_intent"],
            }
        )
    return rows
