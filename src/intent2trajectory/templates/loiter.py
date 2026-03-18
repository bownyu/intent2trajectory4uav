from __future__ import annotations

from .common import build_stage_plan_from_library


def build_stage_plan(style: str, airframe, semantic_target, cfg, rng):
    return build_stage_plan_from_library("loiter", style, airframe, semantic_target, cfg, rng)
