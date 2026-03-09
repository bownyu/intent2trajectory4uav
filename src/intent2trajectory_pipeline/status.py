import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def write_status(
    path: Path,
    *,
    state: str,
    last_completed_stage: str,
    failure_reason: str,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        'state': state,
        'last_completed_stage': last_completed_stage,
        'failure_reason': failure_reason,
        'started_at': started_at,
        'updated_at': now,
        'finished_at': finished_at,
    }
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
