from __future__ import annotations

from typing import Dict, Mapping


def classify_realized_attack_profile(metrics: Mapping[str, float], cfg: Dict) -> str:
    attack_cfg = cfg.get("attack_diversity") or {}
    distribution = attack_cfg.get("distribution") or {}
    posterior = attack_cfg.get("posterior_metrics") or {}
    early_commit_ratio = float(distribution.get("early_commit_ratio_max", 0.15))
    low_terminal_spike = float(distribution.get("low_terminal_spike_max", 0.35))
    high_terminal_spike = float(distribution.get("high_terminal_spike_min", 0.45))
    continuous_pressure_min = float(posterior.get("continuous_pressure_min", 0.55))
    body_point_min = float(posterior.get("body_point_min", 0.6))
    immediate_dash_cut = min(early_commit_ratio * 0.6, 0.1)
    immediate_duration_max = float(posterior.get("immediate_duration_max", 40.0))
    staged_duration_min = float(posterior.get("staged_duration_min", 60.0))

    abort_count = float(metrics.get("abort_count", 0.0))
    onset_ratio = float(metrics.get("commit_onset_ratio", 1.0))
    terminal_spike_ratio = float(metrics.get("terminal_spike_ratio", 0.0))
    pressure_persistence = float(metrics.get("pressure_persistence", 0.0))
    body_point_persistence = float(metrics.get("body_point_persistence", 0.0))
    duration = float(metrics.get("duration", 0.0))

    if abort_count >= 1.0:
        return "probe_commit"
    if terminal_spike_ratio >= high_terminal_spike or terminal_spike_ratio > low_terminal_spike:
        return "staged_commit"
    if onset_ratio <= immediate_dash_cut and pressure_persistence >= continuous_pressure_min + 0.08 and duration <= immediate_duration_max:
        return "immediate_dash"
    if duration >= staged_duration_min and terminal_spike_ratio >= low_terminal_spike * 0.9:
        return "staged_commit"
    if pressure_persistence >= continuous_pressure_min and terminal_spike_ratio <= low_terminal_spike and body_point_persistence >= body_point_min:
        return "continuous_pressure"
    if pressure_persistence >= continuous_pressure_min:
        return "continuous_pressure"
    return "staged_commit"
