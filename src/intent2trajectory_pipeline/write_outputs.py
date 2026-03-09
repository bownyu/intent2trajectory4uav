import csv
import json
from pathlib import Path
from typing import Iterable, Mapping


def ensure_run_directories(run_root: Path) -> None:
    for name in ['input', 'preprocessed', 'logs', 'artifacts', 'output']:
        (run_root / name).mkdir(parents=True, exist_ok=True)


def write_manifest(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(json.dumps(dict(payload), indent=2), encoding='utf-8')


def write_csv_rows(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    rows = list(rows)
    if not rows:
        raise ValueError('rows must not be empty')
    fieldnames = list(rows[0].keys())
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
