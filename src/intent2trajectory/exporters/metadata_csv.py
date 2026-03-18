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
