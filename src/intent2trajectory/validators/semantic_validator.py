from __future__ import annotations

from ..models import IntentScores, RiskVector, ValidationResult
from ..semantics.intent_scoring import ambiguity_margin, score_intents
from ..semantics.risk_vector import compute_risk_vector
from ..semantics.station_metrics import compute_station_metrics
from .hard_constraints import validate_hard_constraints


def validate_sample(traj, airframe, target_intent: str, target_style: str, cfg: dict) -> ValidationResult:
    hard_report = validate_hard_constraints(traj, airframe, cfg)
    metrics = compute_station_metrics(traj, cfg["intent_regions"]["bands"], cfg, target_intent)
    risk_vector = compute_risk_vector(metrics, cfg, target_intent)
    scores = score_intents(risk_vector, metrics, cfg)
    margin = ambiguity_margin(scores, target_intent)
    region = cfg["intent_regions"]["intent_regions"][target_intent]

    reasons = []
    category = ""
    if not hard_report["passed"]:
        reasons.extend([f"hard_constraint:{item}" for item in hard_report["violations"]])
        category = "hard_constraint"

    if scores.to_dict()[target_intent] < float(region["score_min"]):
        reasons.append("intent_score_below_threshold")
        category = category or "semantic"
    if margin < float(region["margin_min"]):
        reasons.append("ambiguity_margin_low")
        category = category or "semantic"

    if target_intent == "attack":
        if metrics.get("close_frac") < float(cfg["intent_regions"]["hard_thresholds"]["attack"]["close_frac"]):
            reasons.append("attack_close_frac_low")
        if risk_vector.point_score < float(cfg["intent_regions"]["hard_thresholds"]["attack"]["point_score"]):
            reasons.append("attack_point_low")
    elif target_intent == "retreat":
        if risk_vector.disengage_score < float(cfg["intent_regions"]["hard_thresholds"]["retreat"]["disengage_score"]):
            reasons.append("retreat_disengage_low")
    elif target_intent == "hover":
        if metrics.get("dwell_hold") < float(cfg["intent_regions"]["hard_thresholds"]["hover"]["dwell_hold"]):
            reasons.append("hover_dwell_low")
        if metrics.get("encircle_cycles") > float(cfg["intent_regions"]["hover_limits"]["c_hover_max"]):
            reasons.append("hover_encircle_high")
    elif target_intent == "loiter":
        if metrics.get("dwell_loiter") < float(cfg["intent_regions"]["hard_thresholds"]["loiter"]["dwell_loiter"]):
            reasons.append("loiter_dwell_low")
        if metrics.get("encircle_cycles") < float(cfg["intent_regions"]["hard_thresholds"]["loiter"]["encircle_cycles"]):
            reasons.append("loiter_encircle_low")

    return ValidationResult(
        valid=not reasons,
        reasons=reasons,
        metrics=metrics,
        risk_vector=risk_vector,
        intent_scores=scores,
        ambiguity_margin=margin,
        hard_constraint_report=hard_report,
        failure_category=category,
    )
