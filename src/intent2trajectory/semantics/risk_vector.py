from __future__ import annotations

from ..models import RiskVector, StationMetrics


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def compute_risk_vector(metrics: StationMetrics, cfg: dict, intent: str) -> RiskVector:
    params = cfg["intent_regions"]["parameters"]
    close_score = _clip(0.45 * metrics.get("close_frac") + 0.35 * metrics.get("net_close") + 0.20 * metrics.get("intrusion_depth"))
    dwell_score = _clip(metrics.get("dwell_ratio_in_band"))
    encircle_score = _clip(metrics.get("encircle_cycles") / max(float(params.get("c_ref", 1.0)), 1e-6))

    weights = cfg["intent_regions"]["point_weights"].get(intent, cfg["intent_regions"]["point_weights"]["hover"])
    point_score = _clip(weights["course"] * metrics.get("course_point_ratio") + weights["yaw"] * metrics.get("yaw_point_ratio"))

    uncertain_score = _clip(
        0.40 * min(metrics.get("sign_changes") / max(float(params.get("n_sign_ref", 4.0)), 1e-6), 1.0)
        + 0.40 * min(metrics.get("abort_count") / max(float(params.get("n_abort_ref", 2.0)), 1e-6), 1.0)
        + 0.20 * _clip((metrics.get("path_ratio") - 1.0) / max(float(params.get("rho_ref", 1.8)) - 1.0, 1e-6))
    )
    disengage_score = _clip(0.55 * metrics.get("open_frac") + 0.45 * metrics.get("net_open"))
    return RiskVector(
        close_score=close_score,
        dwell_score=dwell_score,
        encircle_score=encircle_score,
        point_score=point_score,
        uncertain_score=uncertain_score,
        disengage_score=disengage_score,
    )
