from __future__ import annotations

from ..models import IntentScores, RiskVector, StationMetrics


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def score_intents(risk_vector: RiskVector, metrics: StationMetrics, cfg: dict) -> IntentScores:
    attack = _clip(
        0.35 * risk_vector.close_score
        + 0.25 * risk_vector.point_score
        + 0.15 * (1.0 - risk_vector.disengage_score)
        + 0.15 * metrics.get("intrusion_depth")
        + 0.10 * risk_vector.uncertain_score
    )
    retreat = _clip(
        0.40 * risk_vector.disengage_score
        + 0.25 * metrics.get("outward_monotonic_ratio")
        + 0.20 * (1.0 - risk_vector.close_score)
        + 0.15 * (1.0 - risk_vector.point_score)
    )
    hover = _clip(
        0.35 * metrics.get("dwell_hold")
        + 0.25 * metrics.get("radius_stability")
        + 0.20 * (1.0 - _clip(metrics.get("encircle_cycles") / max(float(cfg["intent_regions"]["hover_limits"].get("c_hover_max", 0.8)), 1e-6)))
        + 0.20 * (1.0 - _clip(metrics.get("radial_drift")))
    )
    loiter = _clip(
        0.30 * metrics.get("dwell_loiter")
        + 0.30 * risk_vector.encircle_score
        + 0.20 * _clip(metrics.get("tangential_dominance_ratio") / max(float(cfg["intent_regions"]["parameters"].get("td_ref", 1.5)), 1e-6))
        + 0.20 * metrics.get("radial_neutrality")
    )
    return IntentScores(attack=attack, retreat=retreat, hover=hover, loiter=loiter)


def ambiguity_margin(scores: IntentScores, target_intent: str) -> float:
    ordered = scores.ordered()
    if not ordered:
        return 0.0
    top_name, top_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0.0
    target_score = scores.to_dict()[target_intent]
    if top_name == target_intent:
        return target_score - second_score
    return target_score - top_score
