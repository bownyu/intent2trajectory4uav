from __future__ import annotations

import math


def envelope_value(name: str, progress: float) -> float:
    progress = max(0.0, min(1.0, progress))
    if name == "constant":
        return 1.0
    if name == "ramp_up":
        return progress
    if name == "ramp_down":
        return 1.0 - progress
    if name == "bell":
        return math.sin(math.pi * progress)
    if name == "triangular":
        return 1.0 - abs(2.0 * progress - 1.0)
    return 1.0
