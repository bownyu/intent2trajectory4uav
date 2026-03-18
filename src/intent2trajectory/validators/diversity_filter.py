from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple


class DiversityFilter:
    def __init__(self, config: Dict):
        self.distance_threshold = float(config.get("distance_threshold", 0.18))
        self.bucket_bins = dict(config.get("bucket_bins") or {})
        self._features: Dict[Tuple[str, str, str], List[List[float]]] = defaultdict(list)
        self._bucket_counts: Dict[str, Dict[Tuple[int, ...], int]] = defaultdict(lambda: defaultdict(int))

    def _digitize(self, value: float, bins: Iterable[float]) -> int:
        ordered = list(bins)
        for idx in range(len(ordered) - 1):
            if ordered[idx] <= value < ordered[idx + 1]:
                return idx
        return max(len(ordered) - 2, 0)

    def feature_vector(self, sample: Dict) -> List[float]:
        metrics = sample["metadata"]["station_metrics"]
        risk = sample["metadata"]["risk_vector"]
        airframe = sample["metadata"]["airframe"]
        return [
            float(sample["metadata"]["duration"] / max(sample["metadata"].get("duration_cap", sample["metadata"]["duration"]), 1.0)),
            float(metrics["start_range"] / max(sample["metadata"].get("range_norm", metrics["start_range"]), 1.0)),
            float(metrics["min_range"] / max(sample["metadata"].get("range_norm", metrics["min_range"]), 1.0)),
            float(metrics["mean_speed"] / max(airframe["v_dash_range"][1], 1.0)),
            float(metrics["max_speed"] / max(airframe["v_dash_range"][1], 1.0)),
            float(metrics["altitude_excursion"] / max(airframe["preferred_altitude"][1] - airframe["preferred_altitude"][0], 1.0)),
            float(metrics["path_ratio"]),
            float(metrics["encircle_cycles"]),
            float(risk["close_score"]),
            float(risk["dwell_score"]),
            float(risk["encircle_score"]),
            float(risk["point_score"]),
            float(risk["uncertain_score"]),
            float(risk["disengage_score"]),
            float(metrics["abort_count"]),
        ]

    def _bucket_signature(self, sample: Dict) -> Dict[str, Tuple[int, ...]]:
        metrics = sample["metadata"]["station_metrics"]
        risk = sample["metadata"]["risk_vector"]
        return {
            "min_range": (self._digitize(metrics["min_range"], self.bucket_bins["min_range"]),),
            "mean_speed_norm": (self._digitize(metrics["mean_speed"] / max(sample["metadata"]["airframe"]["v_dash_range"][1], 1.0), self.bucket_bins["mean_speed_norm"]),),
            "uncertain_score": (self._digitize(risk["uncertain_score"], self.bucket_bins["uncertain_score"]),),
            "duration": (self._digitize(sample["metadata"]["duration"], self.bucket_bins["duration"]),),
            "encircle_cycles": (self._digitize(metrics["encircle_cycles"], self.bucket_bins["encircle_cycles"]),),
        }

    def accept(self, sample: Dict) -> tuple[bool, str]:
        key = (sample["metadata"]["primary_intent"], sample["metadata"]["airframe_name"], sample["metadata"]["motion_style"])
        vector = self.feature_vector(sample)
        existing = self._features[key]
        for prior in existing:
            distance = math.sqrt(sum((left - right) ** 2 for left, right in zip(vector, prior)))
            if distance < self.distance_threshold:
                return False, "diversity_duplicate"
        existing.append(vector)
        for bucket_name, signature in self._bucket_signature(sample).items():
            self._bucket_counts[bucket_name][signature] += 1
        return True, ""
