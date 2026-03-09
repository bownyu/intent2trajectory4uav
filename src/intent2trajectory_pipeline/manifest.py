from pathlib import Path
from typing import Any, Dict


def make_run_id(source_csv_name: str, short_hash: str, timestamp: str) -> str:
    return f'{timestamp}__{Path(source_csv_name).stem}__{short_hash}'


def build_manifest(**kwargs: Any) -> Dict[str, Any]:
    payload = dict(kwargs)
    payload['source_csv_name'] = Path(payload['source_csv_original_path']).name
    return payload
