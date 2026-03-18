from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def write_meta_json(path: Path, sample: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sample_id": sample["metadata"]["sample_id"],
        "primary_intent": sample["metadata"]["primary_intent"],
        "motion_style": sample["metadata"]["motion_style"],
        "airframe": sample["metadata"]["airframe_name"],
        "risk_vector": sample["metadata"]["risk_vector"],
        "intent_scores": sample["metadata"]["intent_scores"],
        "stage_plan": sample["metadata"]["stage_plan"],
        "flight_mode_sequence": sample["metadata"]["flight_mode_sequence"],
        "hard_constraint_report": sample["metadata"]["hard_constraint_report"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
