from __future__ import annotations

from typing import Dict, List

from ..airframes.capability_matrix import supports_style
from ..stages.primitives import sample_stage_spec


def _style_definition(intent: str, style: str, cfg: Dict) -> Dict:
    styles = cfg["style_library"]["intents"][intent]
    if style not in styles:
        raise ValueError(f"Unknown style '{style}' for intent '{intent}'")
    return styles[style]


def build_stage_plan_from_library(intent: str, style: str, airframe, semantic_target, cfg: Dict, rng) -> List:
    if not supports_style(airframe, intent, style):
        raise ValueError(f"Airframe '{airframe.name}' does not support style '{style}' for intent '{intent}'")
    definition = _style_definition(intent, style, cfg)
    context = {
        "airframe": airframe,
        "bands": cfg["intent_regions"]["bands"],
        "semantic_target": semantic_target.to_dict(),
    }
    return [sample_stage_spec(stage_def, rng, context) for stage_def in definition["stages"]]
