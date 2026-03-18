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
        "airframe_family": sample["metadata"]["airframe_family"],
        "start_context": sample["metadata"].get("start_context", ""),
        "pressure_profile_target": sample["metadata"].get("pressure_profile_target", ""),
        "pressure_profile_realized": sample["metadata"].get("pressure_profile_realized", ""),
        "maneuver_profile": sample["metadata"].get("maneuver_profile", ""),
        "dynamics_model": sample["metadata"].get("dynamics_model", ""),
        "yaw_mode_sequence": sample["metadata"].get("yaw_mode_sequence", []),
        "commit_onset_ratio": sample["metadata"].get("commit_onset_ratio", 0.0),
        "terminal_spike_ratio": sample["metadata"].get("terminal_spike_ratio", 0.0),
        "pressure_persistence": sample["metadata"].get("pressure_persistence", 0.0),
        "body_point_persistence": sample["metadata"].get("body_point_persistence", 0.0),
        "risk_vector": sample["metadata"]["risk_vector"],
        "intent_scores": sample["metadata"]["intent_scores"],
        "station_metrics": sample["metadata"].get("station_metrics", {}),
        "stage_plan": sample["metadata"]["stage_plan"],
        "flight_mode_sequence": sample["metadata"]["flight_mode_sequence"],
        "dynamics_model_sequence": sample["metadata"].get("dynamics_model_sequence", []),
        "hard_constraint_report": sample["metadata"]["hard_constraint_report"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
