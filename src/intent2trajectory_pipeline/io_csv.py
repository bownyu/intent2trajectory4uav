import csv
from pathlib import Path
from typing import Dict, List


Row = Dict[str, float]


def load_reference_rows(path: Path) -> List[Row]:
    rows: List[Row] = []
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            use_ref = bool(row.get('ref_pos_x'))
            x_key = 'ref_pos_x' if use_ref else 'pos_x'
            y_key = 'ref_pos_y' if use_ref else 'pos_y'
            z_key = 'ref_pos_z' if use_ref else 'pos_z'
            yaw_value = row.get('ref_yaw') or row.get('yaw') or '0'
            rows.append(
                {
                    'time_relative': float(row.get('time_relative') or row.get('time') or 0.0),
                    'x': float(row[x_key]),
                    'y': float(row[y_key]),
                    'z': float(row[z_key]),
                    'yaw': float(yaw_value),
                }
            )
    return rows
