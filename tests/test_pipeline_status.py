import json
import shutil
import uuid
from pathlib import Path

from intent2trajectory_pipeline.status import write_status


def _make_local_tmp(name: str) -> Path:
    root = Path('tests/.tmp_pipeline') / f'{name}_{uuid.uuid4().hex[:8]}'
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_write_status_persists_state_and_failure_reason():
    tmp_root = _make_local_tmp('status')
    out = tmp_root / 'status.json'
    write_status(
        out,
        state='PLAYBACK',
        last_completed_stage='ARM_AND_OFFBOARD',
        failure_reason='',
        started_at='2026-03-06T18:30:00Z',
    )

    payload = json.loads(out.read_text(encoding='utf-8'))
    assert payload['state'] == 'PLAYBACK'
    assert payload['last_completed_stage'] == 'ARM_AND_OFFBOARD'
    assert payload['failure_reason'] == ''
    assert payload['started_at'] == '2026-03-06T18:30:00Z'
    assert payload['updated_at']
