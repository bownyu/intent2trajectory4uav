from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple


class DiversityFilter:
    def __init__(self, config: Dict):
        if "diversity" in config:
            diversity_cfg = dict(config.get("diversity") or {})
            self.attack_cfg = dict(config.get("attack_diversity") or {})
            self.attack_target_quota = int((config.get("class_quota") or {}).get("attack", 0))
        else:
            diversity_cfg = dict(config or {})
            self.attack_cfg = {}
            self.attack_target_quota = 0
        self.distance_threshold = float(diversity_cfg.get("distance_threshold", 0.18))
        self.bucket_bins = dict(diversity_cfg.get("bucket_bins") or {})
        self._features: Dict[Tuple[str, str, str], List[List[float]]] = defaultdict(list)
        self._bucket_counts: Dict[str, Dict[Tuple[int, ...], int]] = defaultdict(lambda: defaultdict(int))
        self._category_ids: Dict[str, Dict[str, int]] = defaultdict(dict)
        self._accepted_attack = 0
        self._attack_profile_counts: Dict[str, int] = defaultdict(int)
        self._attack_early_commit = 0
        self._attack_low_terminal = 0
        self._attack_high_terminal = 0

    def _digitize(self, value: float, bins: Iterable[float]) -> int:
        ordered = list(bins)
        for idx in range(len(ordered) - 1):
            if ordered[idx] <= value < ordered[idx + 1]:
                return idx
        return max(len(ordered) - 2, 0)

    def _category_id(self, group: str, value: str) -> float:
        if not value:
            return 0.0
        mapping = self._category_ids[group]
        if value not in mapping:
            mapping[value] = len(mapping) + 1
        return float(mapping[value])

    def feature_vector(self, sample: Dict) -> List[float]:
        md = sample["metadata"]
        metrics = md["station_metrics"]
        risk = md["risk_vector"]
        airframe = md["airframe"]
        initial_state = md.get("initial_state") or {}
        start_speed = math.hypot(float(initial_state.get("vx", 0.0)), float(initial_state.get("vy", 0.0)))
        return [
            float(metrics["start_range"] / max(md.get("range_norm", metrics["start_range"]), 1.0)),
            float(start_speed / max(airframe["v_dash_range"][1], 1.0)),
            float(metrics["min_range"] / max(md.get("range_norm", metrics["min_range"]), 1.0)),
            float(metrics["mean_speed"] / max(airframe["v_dash_range"][1], 1.0)),
            float(metrics["max_speed"] / max(airframe["v_dash_range"][1], 1.0)),
            float(metrics["path_ratio"]),
            float(metrics["bearing_cumulative_change"] / max(8.0 * math.pi, 1.0)),
            float(metrics.get("pressure_persistence", 0.0)),
            float(metrics.get("commit_onset_ratio", 0.0)),
            float(metrics.get("terminal_spike_ratio", 0.0)),
            float(metrics.get("body_point_persistence", 0.0)),
            float(metrics.get("lateral_pressure_ratio", 0.0)),
            float(metrics.get("abort_count", 0.0)),
            self._category_id("start_context", str(md.get("start_context", ""))),
            self._category_id("pressure_profile", str(md.get("pressure_profile_realized") or md.get("pressure_profile_target", ""))),
            self._category_id("maneuver_profile", str(md.get("maneuver_profile", ""))),
            float(risk["close_score"]),
            float(risk["point_score"]),
            float(risk["uncertain_score"]),
        ]

    def _bucket_signature(self, sample: Dict) -> Dict[str, Tuple[int, ...]]:
        metrics = sample["metadata"]["station_metrics"]
        risk = sample["metadata"]["risk_vector"]
        signatures: Dict[str, Tuple[int, ...]] = {
            "min_range": (self._digitize(metrics["min_range"], self.bucket_bins["min_range"]),),
            "mean_speed_norm": (self._digitize(metrics["mean_speed"] / max(sample["metadata"]["airframe"]["v_dash_range"][1], 1.0), self.bucket_bins["mean_speed_norm"]),),
            "uncertain_score": (self._digitize(risk["uncertain_score"], self.bucket_bins["uncertain_score"]),),
            "duration": (self._digitize(sample["metadata"]["duration"], self.bucket_bins["duration"]),),
            "encircle_cycles": (self._digitize(metrics["encircle_cycles"], self.bucket_bins["encircle_cycles"]),),
        }
        if "commit_onset_ratio" in self.bucket_bins:
            signatures["commit_onset_ratio"] = (self._digitize(metrics.get("commit_onset_ratio", 0.0), self.bucket_bins["commit_onset_ratio"]),)
        if "terminal_spike_ratio" in self.bucket_bins:
            signatures["terminal_spike_ratio"] = (self._digitize(metrics.get("terminal_spike_ratio", 0.0), self.bucket_bins["terminal_spike_ratio"]),)
        return signatures

    def _attack_distribution_reason(self, sample: Dict) -> str:
        if sample["metadata"]["primary_intent"] != "attack" or self.attack_target_quota <= 0:
            return ""
        md = sample["metadata"]
        distribution = self.attack_cfg.get("distribution") or {}
        profile_quota = self.attack_cfg.get("profile_quota") or {}
        onset = float(md.get("commit_onset_ratio", 1.0))
        terminal_spike = float(md.get("terminal_spike_ratio", 0.0))
        early_cut = float(distribution.get("early_commit_ratio_max", 0.15))
        low_terminal_cut = float(distribution.get("low_terminal_spike_max", 0.35))
        high_terminal_cut = float(distribution.get("high_terminal_spike_min", 0.55))
        min_early_fraction = float(distribution.get("minimum_early_commit_fraction", 0.0))
        min_low_fraction = float(distribution.get("minimum_low_terminal_fraction", 0.0))
        max_high_fraction = float(distribution.get("maximum_high_terminal_fraction", 1.0))

        is_early = onset <= early_cut
        is_low_terminal = terminal_spike <= low_terminal_cut
        is_high_terminal = terminal_spike >= high_terminal_cut
        realized_profile = str(md.get("pressure_profile_realized") or md.get("pressure_profile_target") or "")
        remaining_after_accept = max(self.attack_target_quota - self._accepted_attack - 1, 0)

        if is_high_terminal and self._attack_high_terminal + 1 > math.ceil(self.attack_target_quota * max_high_fraction):
            return "attack_distribution_high_terminal_ceiling"
        if not is_early and self._attack_early_commit + remaining_after_accept < math.ceil(self.attack_target_quota * min_early_fraction):
            return "attack_distribution_early_commit_reserve"
        if not is_low_terminal and self._attack_low_terminal + remaining_after_accept < math.ceil(self.attack_target_quota * min_low_fraction):
            return "attack_distribution_low_terminal_reserve"
        if realized_profile and realized_profile in profile_quota:
            max_count = max(1, math.ceil(self.attack_target_quota * float(profile_quota[realized_profile])))
            if self._attack_profile_counts[realized_profile] + 1 > max_count:
                return f"attack_profile_quota:{realized_profile}"
        return ""

    def _record_attack_distribution(self, sample: Dict) -> None:
        if sample["metadata"]["primary_intent"] != "attack":
            return
        md = sample["metadata"]
        distribution = self.attack_cfg.get("distribution") or {}
        onset = float(md.get("commit_onset_ratio", 1.0))
        terminal_spike = float(md.get("terminal_spike_ratio", 0.0))
        early_cut = float(distribution.get("early_commit_ratio_max", 0.15))
        low_terminal_cut = float(distribution.get("low_terminal_spike_max", 0.35))
        high_terminal_cut = float(distribution.get("high_terminal_spike_min", 0.55))
        realized_profile = str(md.get("pressure_profile_realized") or md.get("pressure_profile_target") or "")

        self._accepted_attack += 1
        if onset <= early_cut:
            self._attack_early_commit += 1
        if terminal_spike <= low_terminal_cut:
            self._attack_low_terminal += 1
        if terminal_spike >= high_terminal_cut:
            self._attack_high_terminal += 1
        if realized_profile:
            self._attack_profile_counts[realized_profile] += 1

    def accept(self, sample: Dict) -> tuple[bool, str]:
        distribution_reason = self._attack_distribution_reason(sample)
        if distribution_reason:
            return False, distribution_reason
        key = (
            sample["metadata"]["primary_intent"],
            sample["metadata"]["airframe_name"],
            str(sample["metadata"].get("pressure_profile_realized") or sample["metadata"]["motion_style"]),
        )
        vector = self.feature_vector(sample)
        existing = self._features[key]
        for prior in existing:
            distance = math.sqrt(sum((left - right) ** 2 for left, right in zip(vector, prior)))
            if distance < self.distance_threshold:
                return False, "diversity_duplicate"
        existing.append(vector)
        for bucket_name, signature in self._bucket_signature(sample).items():
            self._bucket_counts[bucket_name][signature] += 1
        self._record_attack_distribution(sample)
        return True, ""
