import csv
import math
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


def list_csv_files(input_dir: str) -> List[Path]:
    root = Path(input_dir)
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.csv") if p.is_file())


def _to_float(value: str) -> float:
    if value is None:
        return math.nan
    text = str(value).strip()
    if text == "":
        return math.nan
    try:
        return float(text)
    except ValueError:
        return math.nan


def choose_position_columns(fieldnames: Sequence[str], rows: Sequence[Dict[str, str]]) -> Tuple[str, str, str]:
    candidates = [
        ("act_pos_x", "act_pos_y", "act_pos_z"),
        ("ref_pos_x", "ref_pos_y", "ref_pos_z"),
        ("pos_x", "pos_y", "pos_z"),
    ]
    names = set(fieldnames)
    for xk, yk, zk in candidates:
        if {xk, yk, zk}.issubset(names):
            has_valid = False
            for row in rows:
                x = _to_float(row.get(xk, ""))
                y = _to_float(row.get(yk, ""))
                z = _to_float(row.get(zk, ""))
                if math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
                    has_valid = True
                    break
            if has_valid:
                return xk, yk, zk
    raise ValueError("No usable position columns found in CSV")


def _choose_time_column(fieldnames: Sequence[str]) -> str:
    if "time_relative" in fieldnames:
        return "time_relative"
    if "time" in fieldnames:
        return "time"
    raise ValueError("CSV missing time column: expected 'time_relative' or 'time'")


def load_trajectory_csv(csv_path: str) -> Dict:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if not rows:
            raise ValueError("CSV is empty")
        fieldnames = reader.fieldnames or []

    time_key = _choose_time_column(fieldnames)
    xk, yk, zk = choose_position_columns(fieldnames, rows)

    tuples = []
    for r in rows:
        t = _to_float(r.get(time_key, ""))
        x = _to_float(r.get(xk, ""))
        y = _to_float(r.get(yk, ""))
        z = _to_float(r.get(zk, ""))
        if math.isfinite(t) and math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
            tuples.append((t, x, y, z))

    if not tuples:
        raise ValueError("CSV has no valid time-position samples")

    tuples.sort(key=lambda v: v[0])
    times = [v[0] for v in tuples]
    xs = [v[1] for v in tuples]
    ys = [v[2] for v in tuples]
    zs = [v[3] for v in tuples]
    return {
        "file": str(path),
        "time_column": time_key,
        "position_columns": (xk, yk, zk),
        "times": times,
        "xs": xs,
        "ys": ys,
        "zs": zs,
    }


def select_path_points(
    xs: Sequence[float],
    ys: Sequence[float],
    zs: Sequence[float],
    idx: int,
    show_full_path: bool,
) -> Tuple[List[float], List[float], List[float]]:
    if not xs or not ys or not zs:
        return [], [], []

    idx = max(0, min(idx, len(xs) - 1, len(ys) - 1, len(zs) - 1))
    end = len(xs) if show_full_path else idx + 1
    return list(xs[:end]), list(ys[:end]), list(zs[:end])


def compute_intervals_ms(times: Sequence[float], speed: float = 1.0, min_ms: int = 10, max_ms: int = 1000) -> List[int]:
    if speed <= 0:
        speed = 1.0
    if len(times) < 2:
        return [max(min_ms, 100)]

    intervals: List[int] = []
    for i in range(1, len(times)):
        dt = times[i] - times[i - 1]
        if dt <= 0:
            dt = 0.1
        ms = int(round((dt * 1000.0) / speed))
        ms = max(min_ms, min(max_ms, ms))
        intervals.append(ms)

    intervals.append(intervals[-1])
    return intervals
