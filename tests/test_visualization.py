import csv
import math
import shutil
from pathlib import Path

from intent2trajectory.visualization import (
    compute_intervals_ms,
    list_csv_files,
    load_trajectory_csv,
    select_path_points,
)


def _write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_load_trajectory_prefers_actual_columns_when_valid():
    root = Path("tests/.tmp_vis_1")
    if root.exists():
        shutil.rmtree(root)

    csv_path = root / "a.csv"
    fields = ["time_relative", "act_pos_x", "act_pos_y", "act_pos_z", "ref_pos_x", "ref_pos_y", "ref_pos_z"]
    rows = [
        {"time_relative": "0.0", "act_pos_x": "1", "act_pos_y": "2", "act_pos_z": "3", "ref_pos_x": "9", "ref_pos_y": "9", "ref_pos_z": "9"},
        {"time_relative": "0.1", "act_pos_x": "2", "act_pos_y": "3", "act_pos_z": "4", "ref_pos_x": "9", "ref_pos_y": "9", "ref_pos_z": "9"},
    ]
    _write_csv(csv_path, fields, rows)

    data = load_trajectory_csv(str(csv_path))
    assert data["position_columns"] == ("act_pos_x", "act_pos_y", "act_pos_z")
    assert data["xs"] == [1.0, 2.0]


def test_load_trajectory_falls_back_to_ref_when_actual_nan():
    root = Path("tests/.tmp_vis_2")
    if root.exists():
        shutil.rmtree(root)

    csv_path = root / "b.csv"
    fields = ["time_relative", "act_pos_x", "act_pos_y", "act_pos_z", "ref_pos_x", "ref_pos_y", "ref_pos_z"]
    rows = [
        {"time_relative": "0.0", "act_pos_x": "NaN", "act_pos_y": "NaN", "act_pos_z": "NaN", "ref_pos_x": "1", "ref_pos_y": "2", "ref_pos_z": "3"},
        {"time_relative": "0.2", "act_pos_x": "", "act_pos_y": "", "act_pos_z": "", "ref_pos_x": "2", "ref_pos_y": "3", "ref_pos_z": "4"},
    ]
    _write_csv(csv_path, fields, rows)

    data = load_trajectory_csv(str(csv_path))
    assert data["position_columns"] == ("ref_pos_x", "ref_pos_y", "ref_pos_z")
    assert data["times"] == [0.0, 0.2]


def test_intervals_and_file_listing():
    root = Path("tests/.tmp_vis_3")
    if root.exists():
        shutil.rmtree(root)
    (root / "x").mkdir(parents=True, exist_ok=True)
    (root / "x" / "c.csv").write_text("time_relative,pos_x,pos_y,pos_z\n0,0,0,0\n", encoding="utf-8")

    files = list_csv_files(str(root))
    assert len(files) == 1
    assert files[0].name == "c.csv"

    intervals = compute_intervals_ms([0.0, 0.1, 0.3], speed=1.0)
    assert intervals == [100, 200, 200]

    fast = compute_intervals_ms([0.0, 0.1], speed=2.0)
    assert fast[0] == 50
    assert math.isfinite(fast[0])


def test_select_path_points_progressive_mode_returns_points_up_to_frame():
    xs = [0.0, 1.0, 2.0]
    ys = [10.0, 11.0, 12.0]
    zs = [20.0, 21.0, 22.0]

    line_xs, line_ys, line_zs = select_path_points(xs, ys, zs, idx=1, show_full_path=False)

    assert line_xs == [0.0, 1.0]
    assert line_ys == [10.0, 11.0]
    assert line_zs == [20.0, 21.0]


def test_select_path_points_full_mode_returns_entire_path():
    xs = [0.0, 1.0, 2.0]
    ys = [10.0, 11.0, 12.0]
    zs = [20.0, 21.0, 22.0]

    line_xs, line_ys, line_zs = select_path_points(xs, ys, zs, idx=1, show_full_path=True)

    assert line_xs == xs
    assert line_ys == ys
    assert line_zs == zs
