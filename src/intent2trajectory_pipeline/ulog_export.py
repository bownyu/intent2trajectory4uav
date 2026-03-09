from typing import Dict, Iterable, List


ExecutedRow = Dict[str, float]


def build_executed_rows(*, samples: Iterable[Dict[str, float]]) -> List[ExecutedRow]:
    rows: List[ExecutedRow] = []
    for sample in samples:
        rows.append(
            {
                'time_relative': sample['time_relative'],
                'act_pos_x': sample['x'],
                'act_pos_y': sample['y'],
                'act_pos_z': sample['z'],
                'act_vel_x': sample['vx'],
                'act_vel_y': sample['vy'],
                'act_vel_z': sample['vz'],
                'act_yaw': sample['yaw'],
            }
        )
    return rows


def restore_absolute_rows(rows: Iterable[ExecutedRow], *, origin_ned: Dict[str, float]) -> List[ExecutedRow]:
    restored: List[ExecutedRow] = []
    for row in rows:
        item = dict(row)
        item['act_pos_x'] = row['act_pos_x'] + origin_ned['x']
        item['act_pos_y'] = row['act_pos_y'] + origin_ned['y']
        item['act_pos_z'] = row['act_pos_z'] + origin_ned['z']
        restored.append(item)
    return restored
