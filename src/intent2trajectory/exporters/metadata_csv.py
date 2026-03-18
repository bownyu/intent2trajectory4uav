from __future__ import annotations

import json
from typing import Dict


def build_metadata_row(sample: Dict, output_formats: str, attempts_used: int, target_quota: int, status: str = "generated", failure_reason: str = "") -> Dict[str, str]:
    md = sample["metadata"]
    return {
        "sample_id": md["sample_id"],
        "primary_intent": md["primary_intent"],
        "motion_style": md["motion_style"],
        "airframe_name": md["airframe_name"],
        "airframe_family": md["airframe_family"],
        "start_context": md.get("start_context", ""),
        "pressure_profile_target": md.get("pressure_profile_target", ""),
        "pressure_profile_realized": md.get("pressure_profile_realized", ""),
        "maneuver_profile": md.get("maneuver_profile", ""),
        "dynamics_model": md.get("dynamics_model", ""),
        "yaw_mode_sequence_json": json.dumps(md.get("yaw_mode_sequence", []), ensure_ascii=False, sort_keys=False),
        "commit_onset_ratio": f"{float(md.get('commit_onset_ratio', 0.0)):.6f}",
        "terminal_spike_ratio": f"{float(md.get('terminal_spike_ratio', 0.0)):.6f}",
        "pressure_persistence": f"{float(md.get('pressure_persistence', 0.0)):.6f}",
        "body_point_persistence": f"{float(md.get('body_point_persistence', 0.0)):.6f}",
        "output_formats": output_formats,
        "random_seed": str(md["seed"]),
        "duration": f"{md['duration']:.6f}",
        "repair_count": str(md["repair_count"]),
        "ambiguity_margin": f"{md['ambiguity_margin']:.6f}",
        "intent_scores_json": json.dumps(md["intent_scores"], ensure_ascii=False, sort_keys=True),
        "risk_vector_json": json.dumps(md["risk_vector"], ensure_ascii=False, sort_keys=True),
        "stage_plan_json": json.dumps(md["stage_plan"], ensure_ascii=False, sort_keys=True),
        "hard_constraint_report": json.dumps(md["hard_constraint_report"], ensure_ascii=False, sort_keys=True),
        "target_quota": str(target_quota),
        "attempt_count": str(attempts_used),
        "status": status,
        "failure_reason": failure_reason,
    }


def build_failure_row(seed: int, primary_intent: str, motion_style: str, airframe_name: str, category: str, reasons: str) -> Dict[str, str]:
    return {
        "seed": str(seed),
        "primary_intent": primary_intent,
        "motion_style": motion_style,
        "airframe_name": airframe_name,
        "failure_category": category,
        "reasons": reasons,
    }
