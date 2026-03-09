import csv
import json
import shutil
import uuid
from pathlib import Path

from intent2trajectory_pipeline.write_outputs import ensure_run_directories, write_csv_rows, write_manifest


def _make_local_tmp(name: str) -> Path:
    root = Path('tests/.tmp_pipeline') / f'{name}_{uuid.uuid4().hex[:8]}'
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_write_manifest_creates_json_file():
    tmp_root = _make_local_tmp('write_manifest')
    run_root = tmp_root / 'run'
    manifest_path = run_root / 'manifest.json'
    payload = {'run_id': 'x', 'status': 'created'}

    ensure_run_directories(run_root)
    write_manifest(manifest_path, payload)

    stored = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert stored['run_id'] == 'x'


def test_write_csv_rows_creates_header_and_values():
    tmp_root = _make_local_tmp('write_csv')
    path = tmp_root / 'rows.csv'
    rows = [
        {'time_relative': 0.0, 'x': 1.0, 'y': 2.0},
        {'time_relative': 0.1, 'x': 1.5, 'y': 2.5},
    ]

    write_csv_rows(path, rows)

    with path.open('r', encoding='utf-8', newline='') as handle:
        reader = list(csv.DictReader(handle))
    assert reader[0]['x'] == '1.0'
    assert reader[1]['y'] == '2.5'
