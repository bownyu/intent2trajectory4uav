from __future__ import annotations

from typing import List

from ..models import AirframeProfile


def list_allowed_styles(airframe: AirframeProfile, intent: str) -> List[str]:
    return list(airframe.allowed_styles.get(intent, []))


def supports_style(airframe: AirframeProfile, intent: str, style: str) -> bool:
    return style in airframe.allowed_styles.get(intent, [])
