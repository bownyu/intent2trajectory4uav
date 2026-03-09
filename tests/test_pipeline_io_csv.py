import shutil
import uuid
from pathlib import Path

from intent2trajectory_pipeline.io_csv import load_reference_rows


def _make_local_tmp(name: str) -> Path:
    root = Path('tests/.tmp_pipeline') / f'{name}_{uuid.uuid4().hex[:8]}'
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_load_reference_rows_prefers_ref_columns():
    tmp_root = _make_local_tmp('io_csv_ref')
    path = tmp_root / 'sample.csv'
    path.write_text(
        'time_relative,ref_pos_x,ref_pos_y,ref_pos_z,pos_x,pos_y,pos_z,ref_yaw,yaw\n'
        '0.0,1,2,3,9,9,9,0.1,1.5\n',
        encoding='utf-8',
    )

    rows = load_reference_rows(path)
    assert rows[0]['x'] == 1.0
    assert rows[0]['y'] == 2.0
    assert rows[0]['z'] == 3.0
    assert rows[0]['yaw'] == 0.1


def test_load_reference_rows_falls_back_to_pos_columns():
    tmp_root = _make_local_tmp('io_csv_pos')
    path = tmp_root / 'sample.csv'
    path.write_text(
        'time_relative,pos_x,pos_y,pos_z,yaw\n'
        '0.0,4,5,6,0.3\n',
        encoding='utf-8',
    )

    rows = load_reference_rows(path)
    assert rows[0]['x'] == 4.0
    assert rows[0]['y'] == 5.0
    assert rows[0]['z'] == 6.0
    assert rows[0]['yaw'] == 0.3
