from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


@dataclass(slots=True)
class CommandProfile:
    base: float
    amplitude: float = 0.0
    period: float = 1.0
    phase: float = 0.0
    envelope: str = "constant"
    bias: float = 0.0

    def to_dict(self) -> Dict[str, float | str]:
        return asdict(self)


@dataclass(slots=True)
class StageSpec:
    name: str
    duration_range: Tuple[float, float]
    terminate_rule: str
    vr_cmd: CommandProfile
    vt_cmd: CommandProfile
    vz_cmd: CommandProfile
    yaw_mode: str
    noise_profile: str
    semantic_effects: Dict[str, float] = field(default_factory=dict)
    flight_mode: str = "auto"
    dynamics_model: str = "auto"

    def sampled_duration(self) -> float:
        return 0.5 * (self.duration_range[0] + self.duration_range[1])

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["duration_range"] = list(self.duration_range)
        return payload


@dataclass(slots=True)
class AirframeProfile:
    name: str
    family: str
    hover_capable: bool
    v_min: float
    v_cruise_range: Tuple[float, float]
    v_dash_range: Tuple[float, float]
    a_long_max: float
    a_brake_max: float
    a_lat_max: float
    climb_rate_max: float
    descent_rate_max: float
    jerk_max: float
    yaw_rate_max: float
    turn_rate_max: float
    min_turn_radius: float
    control_tau: float
    preferred_altitude: Tuple[float, float]
    allowed_styles: Dict[str, List[str]]
    validator_overrides: Dict[str, float] = field(default_factory=dict)
    selection_weight: float = 1.0
    enabled: bool = True
    attack_capability: Dict[str, Any] = field(default_factory=dict)

    def cruise_speed(self) -> float:
        return 0.5 * (self.v_cruise_range[0] + self.v_cruise_range[1])

    def dash_speed(self) -> float:
        return 0.5 * (self.v_dash_range[0] + self.v_dash_range[1])

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["v_cruise_range"] = list(self.v_cruise_range)
        payload["v_dash_range"] = list(self.v_dash_range)
        payload["preferred_altitude"] = list(self.preferred_altitude)
        return payload


@dataclass(slots=True)
class SemanticTarget:
    intent: str
    target_values: Dict[str, float]
    active_band_name: str
    risk_bands: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "target_values": dict(self.target_values),
            "active_band_name": self.active_band_name,
            "risk_bands": dict(self.risk_bands),
        }


@dataclass(slots=True)
class TrajectoryPoint:
    t: float
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    yaw: float
    course: float
    speed: float
    stage_name: str
    flight_mode: str

    def to_dict(self) -> Dict[str, float | str]:
        return asdict(self)


@dataclass(slots=True)
class Trajectory:
    points: List[TrajectoryPoint]
    dt: float
    stage_plan: List[StageSpec]
    flight_mode_sequence: List[str]
    dynamics_model_sequence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dt": self.dt,
            "flight_mode_sequence": list(self.flight_mode_sequence),
            "dynamics_model_sequence": list(self.dynamics_model_sequence),
            "stage_plan": [stage.to_dict() for stage in self.stage_plan],
            "points": [point.to_dict() for point in self.points],
        }


@dataclass(slots=True)
class StationMetrics:
    values: Dict[str, float]
    active_band_name: str

    def __getitem__(self, key: str) -> float:
        return self.values[key]

    def get(self, key: str, default: float = 0.0) -> float:
        return self.values.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        payload = dict(self.values)
        payload["active_band_name"] = self.active_band_name
        return payload


@dataclass(slots=True)
class RiskVector:
    close_score: float
    dwell_score: float
    encircle_score: float
    point_score: float
    uncertain_score: float
    disengage_score: float

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass(slots=True)
class IntentScores:
    attack: float
    retreat: float
    hover: float
    loiter: float

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    def ordered(self) -> List[Tuple[str, float]]:
        return sorted(self.to_dict().items(), key=lambda item: item[1], reverse=True)


@dataclass(slots=True)
class ValidationResult:
    valid: bool
    reasons: List[str]
    metrics: StationMetrics
    risk_vector: RiskVector
    intent_scores: IntentScores
    ambiguity_margin: float
    hard_constraint_report: Dict[str, Any]
    failure_category: str = ""
    posterior_metrics: Dict[str, Any] = field(default_factory=dict)
    realized_attack_profile: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "reasons": list(self.reasons),
            "metrics": self.metrics.to_dict(),
            "risk_vector": self.risk_vector.to_dict(),
            "intent_scores": self.intent_scores.to_dict(),
            "ambiguity_margin": self.ambiguity_margin,
            "hard_constraint_report": dict(self.hard_constraint_report),
            "failure_category": self.failure_category,
            "posterior_metrics": dict(self.posterior_metrics),
            "realized_attack_profile": self.realized_attack_profile,
        }


def ensure_tuple(values: Sequence[float]) -> Tuple[float, float]:
    return float(values[0]), float(values[1])


def ensure_float_dict(values: Mapping[str, Any]) -> Dict[str, float]:
    return {str(key): float(value) for key, value in values.items()}
