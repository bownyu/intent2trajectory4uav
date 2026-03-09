import csv
import json
import math
import shutil
from pathlib import Path

from intent2trajectory.generator import compute_variant_quotas, generate_dataset, generate_sample, validate_sample


BASE_PROFILE = {
    "dt": 0.1,
    "max_time": 120.0,
    "intent_profiles": {
        "hover": {
            "duration_range": [60.0, 80.0],
            "space": {"x": [-2000, 2000], "y": [-2000, 2000], "z": [50, 300]},
            "base_speed": [0.1, 1.0],
            "noise_sigma": [0.1, 0.3],
            "yaw_noise_sigma": 0.01,
        },
        "straight_penetration": {
            "start_radius": [3000, 3500],
            "start_z": [120, 200],
            "base_speed": [10.0, 12.0],
            "target_radius": 100,
        },
        "non_straight_penetration": {
            "start_radius": [3000, 3500],
            "start_z": [120, 200],
            "target_radius": 100,
            "variants": {
                "weave_approach": {
                    "weight": 0.35,
                    "base_speed": [7.2, 8.2],
                    "lateral_amplitude": [70, 120],
                    "lateral_period": [20, 32],
                    "vertical_amplitude": [10, 20],
                },
                "climb_then_dive": {
                    "weight": 0.25,
                    "base_speed": [6.8, 7.8],
                    "climb_ratio": [0.18, 0.32],
                    "climb_angle_deg": [7, 14],
                    "dive_angle_deg": [10, 20],
                },
                "turn_then_dive": {
                    "weight": 0.20,
                    "base_speed": [6.8, 7.8],
                    "turn_angle_deg": [35, 65],
                    "turn_radius": [180, 320],
                },
                "zigzag_dive": {
                    "weight": 0.20,
                    "base_speed": [6.2, 7.2],
                    "segments": [4, 6],
                    "heading_jitter_deg": [18, 30],
                },
            },
        },
        "loiter": {
            "center_radius": [1000, 1500],
            "center_z": [120, 200],
            "variants": {
                "circle_hold": {
                    "weight": 1.0,
                    "radius": [200, 300],
                    "linear_speed": [8.0, 12.0],
                    "duration_range": [90, 120],
                    "vertical_wave": [0.0, 8.0],
                }
            },
        },
        "retreat": {
            "start_radius": [120, 250],
            "start_z": [80, 160],
            "base_speed": [10.0, 12.0],
            "end_radius": 800,
            "distance_multiplier": 1.5,
        },
    },
    "constraints": {
        "intent_limits": {
            "hover": {"max_speed": 2.0, "max_acc": 2.0, "max_yaw_rate": 1.5},
            "straight_penetration": {"max_speed": 13.0, "max_acc": 5.0, "max_yaw_rate": 0.2},
            "non_straight_penetration": {"max_speed": 13.0, "max_acc": 8.0, "max_yaw_rate": 2.5},
            "loiter": {"max_speed": 13.0, "max_acc": 7.0, "max_yaw_rate": 2.5},
            "retreat": {"max_speed": 13.0, "max_acc": 5.0, "max_yaw_rate": 2.0},
        },
        "space": {"x": [-6000, 6000], "y": [-6000, 6000], "z": [10, 600]},
    },
}


NON_STRAIGHT_VARIANTS = tuple(BASE_PROFILE["intent_profiles"]["non_straight_penetration"]["variants"].keys())

HOVER_VARIANTS = ("steady_hold", "micro_orbit_hold", "sway_hold")

RETREAT_VARIANTS = ("direct_escape", "arc_escape", "zigzag_escape", "climb_escape")


def _distance(row):
    return math.sqrt(row["pos_x"] ** 2 + row["pos_y"] ** 2 + row["pos_z"] ** 2)


def _rows_equal_with_nan(a_rows, b_rows):
    assert len(a_rows) == len(b_rows)
    for a, b in zip(a_rows, b_rows):
        assert a.keys() == b.keys()
        for k in a.keys():
            av, bv = a[k], b[k]
            if isinstance(av, float) and isinstance(bv, float) and math.isnan(av) and math.isnan(bv):
                continue
            assert av == bv


def _path_length(rows):
    total = 0.0
    for i in range(1, len(rows)):
        dx = rows[i]["pos_x"] - rows[i - 1]["pos_x"]
        dy = rows[i]["pos_y"] - rows[i - 1]["pos_y"]
        dz = rows[i]["pos_z"] - rows[i - 1]["pos_z"]
        total += math.sqrt(dx * dx + dy * dy + dz * dz)
    return total


def _lateral_deviation(rows):
    start = rows[0]
    end = rows[-1]
    sx, sy, sz = start["pos_x"], start["pos_y"], start["pos_z"]
    ex, ey, ez = end["pos_x"], end["pos_y"], end["pos_z"]
    vx, vy, vz = ex - sx, ey - sy, ez - sz
    norm = math.sqrt(vx * vx + vy * vy + vz * vz)
    assert norm > 1e-6
    max_dev = 0.0
    for row in rows[1:-1]:
        wx, wy, wz = row["pos_x"] - sx, row["pos_y"] - sy, row["pos_z"] - sz
        cx = vy * wz - vz * wy
        cy = vz * wx - vx * wz
        cz = vx * wy - vy * wx
        dev = math.sqrt(cx * cx + cy * cy + cz * cz) / norm
        max_dev = max(max_dev, dev)
    return max_dev


def test_generate_sample_has_expected_schema_and_placeholders():
    sample = generate_sample("straight_penetration", seed=7, profile=BASE_PROFILE)
    assert sample["intent"] == "straight_penetration"
    assert sample["rows"], "rows should not be empty"

    first = sample["rows"][0]
    required = {
        "time_relative",
        "intent",
        "variant_name",
        "variant_summary",
        "pos_x",
        "pos_y",
        "pos_z",
        "yaw",
        "vel_x",
        "vel_y",
        "vel_z",
        "ref_pos_x",
        "ref_pos_y",
        "ref_pos_z",
        "ref_yaw",
        "act_pos_x",
        "act_pos_y",
        "act_pos_z",
        "act_yaw",
    }
    assert required.issubset(first.keys())
    assert first["intent"] == "straight_penetration"
    assert first["variant_name"] == "direct_closing"
    assert math.isnan(first["act_pos_x"])
    assert math.isnan(first["act_yaw"])


def test_reproducible_given_same_seed_and_profile():
    a = generate_sample("non_straight_penetration", seed=1234, profile=BASE_PROFILE)
    b = generate_sample("non_straight_penetration", seed=1234, profile=BASE_PROFILE)
    assert a["metadata"] == b["metadata"]
    _rows_equal_with_nan(a["rows"], b["rows"])


def test_compute_variant_quotas_rounds_and_preserves_minimum_one_slot():
    quotas = compute_variant_quotas(100, BASE_PROFILE["intent_profiles"]["non_straight_penetration"]["variants"])
    assert quotas == {
        "weave_approach": 35,
        "climb_then_dive": 25,
        "turn_then_dive": 20,
        "zigzag_dive": 20,
    }

    tiny = compute_variant_quotas(1, BASE_PROFILE["intent_profiles"]["non_straight_penetration"]["variants"])
    assert set(tiny) == set(NON_STRAIGHT_VARIANTS)
    assert all(value >= 1 for value in tiny.values())


def test_generate_sample_supports_requested_variant():
    for index, variant_name in enumerate(NON_STRAIGHT_VARIANTS):
        sample = generate_sample("non_straight_penetration", seed=300 + index, profile=BASE_PROFILE, variant_name=variant_name)
        assert sample["metadata"]["variant_name"] == variant_name
        assert sample["rows"][0]["variant_name"] == variant_name




def test_hover_variant_quotas_round_and_preserve_minimum_slots():
    variants = {
        "steady_hold": {"weight": 0.5},
        "micro_orbit_hold": {"weight": 0.3},
        "sway_hold": {"weight": 0.2},
    }
    quotas = compute_variant_quotas(100, variants)
    assert quotas == {
        "steady_hold": 50,
        "micro_orbit_hold": 30,
        "sway_hold": 20,
    }

    tiny = compute_variant_quotas(1, variants)
    assert tiny == {
        "steady_hold": 1,
        "micro_orbit_hold": 1,
        "sway_hold": 1,
    }


def test_generate_sample_supports_requested_hover_variant():
    profile = json.loads(json.dumps(BASE_PROFILE))
    profile["intent_profiles"]["hover"]["variants"] = {
        "steady_hold": {"weight": 0.5},
        "micro_orbit_hold": {
            "weight": 0.3,
            "radius": [4.0, 10.0],
            "linear_speed": [0.2, 0.5],
        },
        "sway_hold": {
            "weight": 0.2,
            "amplitude": [3.0, 8.0],
            "period": [16.0, 28.0],
        },
    }

    for idx, variant_name in enumerate(HOVER_VARIANTS):
        sample = generate_sample("hover", seed=900 + idx, profile=profile, variant_name=variant_name)
        assert sample["metadata"]["variant_name"] == variant_name
        assert sample["rows"][0]["variant_name"] == variant_name


def test_hover_variants_can_validate_when_requested():
    profile = json.loads(json.dumps(BASE_PROFILE))
    profile["intent_profiles"]["hover"]["variants"] = {
        "steady_hold": {
            "weight": 0.5,
            "noise_sigma": [0.05, 0.15],
        },
        "micro_orbit_hold": {
            "weight": 0.3,
            "radius": [4.0, 10.0],
            "linear_speed": [0.2, 0.5],
            "duration_range": [60.0, 90.0],
        },
        "sway_hold": {
            "weight": 0.2,
            "amplitude": [3.0, 8.0],
            "period": [16.0, 28.0],
            "duration_range": [60.0, 90.0],
        },
    }

    for idx, variant_name in enumerate(HOVER_VARIANTS):
        sample = generate_sample("hover", seed=950 + idx, profile=profile, variant_name=variant_name)
        result = validate_sample(sample, profile)
        assert result["valid"] is True, f"{variant_name} failed with {result['reasons']}"


def test_hover_variants_show_distinct_geometry():
    profile = json.loads(json.dumps(BASE_PROFILE))
    profile["intent_profiles"]["hover"]["variants"] = {
        "steady_hold": {
            "weight": 0.5,
            "noise_sigma": [0.05, 0.15],
        },
        "micro_orbit_hold": {
            "weight": 0.3,
            "radius": [4.0, 10.0],
            "linear_speed": [0.2, 0.5],
            "duration_range": [60.0, 90.0],
        },
        "sway_hold": {
            "weight": 0.2,
            "amplitude": [3.0, 8.0],
            "period": [16.0, 28.0],
            "duration_range": [60.0, 90.0],
        },
    }

    steady = generate_sample("hover", seed=1001, profile=profile, variant_name="steady_hold")
    orbit = generate_sample("hover", seed=1002, profile=profile, variant_name="micro_orbit_hold")
    sway = generate_sample("hover", seed=1003, profile=profile, variant_name="sway_hold")

    def max_offset(sample):
        center = sample["metadata"]["variant_params"]["center_xyz"]
        return max(math.sqrt((row["pos_x"] - center[0]) ** 2 + (row["pos_y"] - center[1]) ** 2 + (row["pos_z"] - center[2]) ** 2) for row in sample["rows"])

    def cumulative_angle(sample):
        center_x, center_y = sample["metadata"]["variant_params"]["center_xyz"][:2]
        points = [(row["pos_x"], row["pos_y"], row["pos_z"]) for row in sample["rows"]]
        from intent2trajectory.generator import _cumulative_angle_travel
        return _cumulative_angle_travel(points, (center_x, center_y))

    def sign_changes(sample):
        axis = sample["metadata"]["variant_params"]["axis"]
        center = sample["metadata"]["variant_params"]["center_xyz"]
        values = []
        for row in sample["rows"]:
            dx = row["pos_x"] - center[0]
            dy = row["pos_y"] - center[1]
            values.append(dx * axis[0] + dy * axis[1])
        from intent2trajectory.generator import _count_sign_changes
        return _count_sign_changes(values)

    assert max_offset(steady) < max_offset(sway)
    assert cumulative_angle(orbit) > 2.5
    assert sign_changes(sway) >= 2


def test_hover_dataset_generation_uses_variant_quotas():
    root = Path("tests/.tmp_hover_dataset")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    cfg = {
        "schema_version": "1.0.0",
        "output_root": str(root / "dataset_workspace"),
        "seed": 303,
        "max_resample_attempts": 6,
        "progress": {"enabled": False},
        "failure_logging": {"include_failed_metadata": True},
        "class_quota": {
            "hover": 10,
            "straight_penetration": 0,
            "non_straight_penetration": 0,
            "loiter": 0,
            "retreat": 0,
        },
        **json.loads(json.dumps(BASE_PROFILE)),
    }
    cfg["intent_profiles"]["hover"]["variants"] = {
        "steady_hold": {
            "weight": 0.5,
            "noise_sigma": [0.05, 0.15],
        },
        "micro_orbit_hold": {
            "weight": 0.3,
            "radius": [4.0, 10.0],
            "linear_speed": [0.2, 0.5],
            "duration_range": [60.0, 90.0],
        },
        "sway_hold": {
            "weight": 0.2,
            "amplitude": [3.0, 8.0],
            "period": [16.0, 28.0],
            "duration_range": [60.0, 90.0],
        },
    }

    cfg_path = root / "dataset_config.json"
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    summary = generate_dataset(str(cfg_path))
    assert summary["generated"] == 10
    assert summary["failed"] == 0
    assert summary["variant_counts"]["hover"] == {
        "steady_hold": 5,
        "micro_orbit_hold": 3,
        "sway_hold": 2,
    }

    rows = list(csv.DictReader((Path(cfg["output_root"]) / "metadata.csv").read_text(encoding="utf-8").splitlines()))
    counts = {}
    for row in rows:
        counts[row["variant_name"]] = counts.get(row["variant_name"], 0) + 1
    assert counts == {
        "steady_hold": 5,
        "micro_orbit_hold": 3,
        "sway_hold": 2,
    }



def test_retreat_variant_quotas_round_and_preserve_minimum_slots():
    variants = {
        "direct_escape": {"weight": 0.4},
        "arc_escape": {"weight": 0.25},
        "zigzag_escape": {"weight": 0.2},
        "climb_escape": {"weight": 0.15},
    }
    quotas = compute_variant_quotas(100, variants)
    assert quotas == {
        "direct_escape": 40,
        "arc_escape": 25,
        "zigzag_escape": 20,
        "climb_escape": 15,
    }

    tiny = compute_variant_quotas(1, variants)
    assert tiny == {name: 1 for name in RETREAT_VARIANTS}


def test_generate_sample_supports_requested_retreat_variant():
    profile = json.loads(json.dumps(BASE_PROFILE))
    profile["intent_profiles"]["retreat"]["variants"] = {
        "direct_escape": {"weight": 0.4},
        "arc_escape": {"weight": 0.25, "lateral_amplitude": [80.0, 180.0]},
        "zigzag_escape": {"weight": 0.2, "lateral_amplitude": [60.0, 140.0], "segments": [3, 5]},
        "climb_escape": {"weight": 0.15, "climb_gain": [80.0, 180.0]},
    }

    for idx, variant_name in enumerate(RETREAT_VARIANTS):
        sample = generate_sample("retreat", seed=1100 + idx, profile=profile, variant_name=variant_name)
        assert sample["metadata"]["variant_name"] == variant_name
        assert sample["rows"][0]["variant_name"] == variant_name


def test_retreat_variants_can_validate_when_requested():
    profile = json.loads(json.dumps(BASE_PROFILE))
    profile["intent_profiles"]["retreat"]["variants"] = {
        "direct_escape": {"weight": 0.4},
        "arc_escape": {"weight": 0.25, "lateral_amplitude": [80.0, 180.0]},
        "zigzag_escape": {"weight": 0.2, "lateral_amplitude": [60.0, 140.0], "segments": [3, 5]},
        "climb_escape": {"weight": 0.15, "climb_gain": [80.0, 180.0]},
    }

    for idx, variant_name in enumerate(RETREAT_VARIANTS):
        sample = generate_sample("retreat", seed=1150 + idx, profile=profile, variant_name=variant_name)
        result = validate_sample(sample, profile)
        assert result["valid"] is True, f"{variant_name} failed with {result['reasons']}"


def test_retreat_variants_show_distinct_geometry_and_climb_respects_altitude():
    profile = json.loads(json.dumps(BASE_PROFILE))
    profile["constraints"]["space"]["z"] = [10, 260]
    profile["intent_profiles"]["retreat"]["start_z"] = [80, 120]
    profile["intent_profiles"]["retreat"]["variants"] = {
        "direct_escape": {"weight": 0.4},
        "arc_escape": {"weight": 0.25, "lateral_amplitude": [80.0, 180.0]},
        "zigzag_escape": {"weight": 0.2, "lateral_amplitude": [60.0, 140.0], "segments": [3, 5]},
        "climb_escape": {"weight": 0.15, "climb_gain": [120.0, 220.0]},
    }

    direct = generate_sample("retreat", seed=1201, profile=profile, variant_name="direct_escape")
    arc = generate_sample("retreat", seed=1202, profile=profile, variant_name="arc_escape")
    zigzag = generate_sample("retreat", seed=1203, profile=profile, variant_name="zigzag_escape")
    climb = generate_sample("retreat", seed=1204, profile=profile, variant_name="climb_escape")

    def heading_excursion(sample):
        from intent2trajectory.generator import _angle_excursion
        return _angle_excursion([row["yaw"] for row in sample["rows"]])

    def lateral_changes(sample):
        from intent2trajectory.generator import _count_sign_changes
        axis = sample["metadata"]["variant_params"].get("lateral_axis", [1.0, 0.0])
        start = sample["metadata"]["start_xyz"]
        values = []
        for row in sample["rows"]:
            dx = row["pos_x"] - start[0]
            dy = row["pos_y"] - start[1]
            values.append(dx * axis[0] + dy * axis[1])
        return _count_sign_changes(values)

    assert heading_excursion(direct) < heading_excursion(arc)
    assert lateral_changes(zigzag) >= 2
    assert max(row["pos_z"] for row in climb["rows"]) <= 260.0
    assert climb["rows"][-1]["pos_z"] > climb["rows"][0]["pos_z"]


def test_retreat_dataset_generation_uses_variant_quotas():
    root = Path("tests/.tmp_retreat_dataset")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    cfg = {
        "schema_version": "1.0.0",
        "output_root": str(root / "dataset_workspace"),
        "seed": 404,
        "max_resample_attempts": 8,
        "progress": {"enabled": False},
        "failure_logging": {"include_failed_metadata": True},
        "class_quota": {
            "hover": 0,
            "straight_penetration": 0,
            "non_straight_penetration": 0,
            "loiter": 0,
            "retreat": 20,
        },
        **json.loads(json.dumps(BASE_PROFILE)),
    }
    cfg["intent_profiles"]["retreat"]["variants"] = {
        "direct_escape": {"weight": 0.4},
        "arc_escape": {"weight": 0.25, "lateral_amplitude": [80.0, 180.0]},
        "zigzag_escape": {"weight": 0.2, "lateral_amplitude": [60.0, 140.0], "segments": [3, 5]},
        "climb_escape": {"weight": 0.15, "climb_gain": [80.0, 180.0]},
    }

    cfg_path = root / "dataset_config.json"
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    summary = generate_dataset(str(cfg_path))
    assert summary["generated"] == 20
    assert summary["failed"] == 0
    assert summary["variant_counts"]["retreat"] == {
        "direct_escape": 8,
        "arc_escape": 5,
        "zigzag_escape": 4,
        "climb_escape": 3,
    }

def test_validate_sample_passes_for_generated_trajectory():
    sample = generate_sample("hover", seed=5, profile=BASE_PROFILE)
    result = validate_sample(sample, BASE_PROFILE)
    assert result["valid"] is True
    assert result["reasons"] == []


def test_non_straight_variants_can_validate_when_requested():
    for index, variant_name in enumerate(NON_STRAIGHT_VARIANTS):
        sample = generate_sample("non_straight_penetration", seed=500 + index, profile=BASE_PROFILE, variant_name=variant_name)
        result = validate_sample(sample, BASE_PROFILE)
        assert result["valid"] is True, f"{variant_name} failed with {result['reasons']}"


def test_intent_behavior_rules_hold_for_straight_and_retreat():
    straight = generate_sample("straight_penetration", seed=9, profile=BASE_PROFILE)
    sdist = [_distance(r) for r in straight["rows"]]
    assert sdist[-1] < sdist[0]

    retreat = generate_sample("retreat", seed=17, profile=BASE_PROFILE)
    rdist = [_distance(r) for r in retreat["rows"]]
    assert rdist[-1] >= 1.5 * rdist[0]


def test_loiter_yaw_is_tangent_to_velocity():
    sample = generate_sample("loiter", seed=22, profile=BASE_PROFILE)
    rows = sample["rows"]
    for row in rows[5:30]:
        if abs(row["vel_x"]) + abs(row["vel_y"]) < 1e-6:
            continue
        yaw_from_vel = math.atan2(row["vel_y"], row["vel_x"])
        err = math.atan2(math.sin(row["yaw"] - yaw_from_vel), math.cos(row["yaw"] - yaw_from_vel))
        assert abs(err) < 0.2


def test_class_separability_non_straight_vs_loiter_not_overlapping():
    non_straight = generate_sample("non_straight_penetration", seed=41, profile=BASE_PROFILE, variant_name="weave_approach")
    loiter = generate_sample("loiter", seed=42, profile=BASE_PROFILE)

    ns_dist_delta = _distance(non_straight["rows"][0]) - _distance(non_straight["rows"][-1])
    loiter_dist_delta = abs(_distance(loiter["rows"][0]) - _distance(loiter["rows"][-1]))

    assert ns_dist_delta > 500
    assert loiter_dist_delta < 200


def test_straight_yaw_wraparound_is_not_flagged_as_unstable():
    rows = []
    yaws = [-3.1410, 3.1412, -3.1408, 3.1411, -3.1411]
    for idx, yaw in enumerate(yaws):
        rows.append(
            {
                "time_relative": idx * 0.1,
                "intent": "straight_penetration",
                "variant_name": "direct_closing",
                "variant_summary": "{}",
                "pos_x": 3000.0 - idx * 10.0,
                "pos_y": 0.0,
                "pos_z": 100.0,
                "yaw": yaw,
                "vel_x": -10.0,
                "vel_y": 0.0,
                "vel_z": 0.0,
            }
        )
    sample = {
        "intent": "straight_penetration",
        "rows": rows,
        "metadata": {"start_xyz": (3000.0, 0.0, 100.0)},
    }
    result = validate_sample(sample, BASE_PROFILE)
    assert "straight_yaw_unstable" not in result["reasons"]


def test_non_straight_records_variant_and_shows_geometric_nonlinearity():
    sample = generate_sample("non_straight_penetration", seed=123, profile=BASE_PROFILE, variant_name="weave_approach")
    rows = sample["rows"]
    displacement = math.sqrt(
        (rows[-1]["pos_x"] - rows[0]["pos_x"]) ** 2
        + (rows[-1]["pos_y"] - rows[0]["pos_y"]) ** 2
        + (rows[-1]["pos_z"] - rows[0]["pos_z"]) ** 2
    )

    assert sample["metadata"]["variant_name"] == "weave_approach"
    assert _path_length(rows) > displacement * 1.02
    assert _lateral_deviation(rows) > 30.0
    assert rows[0]["variant_name"] == "weave_approach"


def test_loiter_records_variant_and_has_orbit_structure():
    sample = generate_sample("loiter", seed=321, profile=BASE_PROFILE)
    rows = sample["rows"]
    xs = [row["pos_x"] for row in rows]
    ys = [row["pos_y"] for row in rows]
    zs = [row["pos_z"] for row in rows]
    center_x, center_y = sample["metadata"]["variant_params"]["center_xy"]
    radii = [math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2) for x, y in zip(xs, ys)]

    assert sample["metadata"]["variant_name"] == "circle_hold"
    assert rows[0]["variant_name"] == "circle_hold"
    assert max(radii) - min(radii) < 120.0
    assert max(zs) - min(zs) <= 12.0


def test_generate_dataset_uses_variant_quotas_and_records_metadata(capsys):
    root = Path("tests/.tmp_dataset")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    cfg = {
        "schema_version": "1.0.0",
        "output_root": str(root / "dataset_workspace"),
        "seed": 100,
        "max_resample_attempts": 10,
        "progress": {"enabled": True},
        "failure_logging": {"include_failed_metadata": True},
        "class_quota": {
            "hover": 0,
            "straight_penetration": 0,
            "non_straight_penetration": 20,
            "loiter": 0,
            "retreat": 0,
        },
        **BASE_PROFILE,
    }

    cfg_path = root / "dataset_config.json"
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    summary = generate_dataset(str(cfg_path))
    assert summary["generated"] == 20
    assert summary["failed"] == 0
    assert summary["variant_counts"]["non_straight_penetration"] == {
        "weave_approach": 7,
        "climb_then_dive": 5,
        "turn_then_dive": 4,
        "zigzag_dive": 4,
    }

    captured = capsys.readouterr().out
    assert "progress" in captured.lower()
    assert "20/20" in captured

    out_root = Path(cfg["output_root"])
    files = list((out_root / "2_non_straight_penetration").glob("*.csv"))
    assert len(files) == 20
    assert any("climb_then_dive" in path.name for path in files)
    assert any("turn_then_dive" in path.name for path in files)
    assert any("zigzag_dive" in path.name for path in files)

    metadata_path = out_root / "metadata.csv"
    rows = list(csv.DictReader(metadata_path.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 20
    assert {r["status"] for r in rows} == {"generated"}
    assert {r["schema_version"] for r in rows} == {"1.0.0"}
    assert {r["target_quota"] for r in rows if r["variant_name"] == "weave_approach"} == {"7"}
    assert all(int(r["variant_attempt_count"]) >= 1 for r in rows)

    counts = {}
    for row in rows:
        counts[row["variant_name"]] = counts.get(row["variant_name"], 0) + 1
    assert counts == {
        "weave_approach": 7,
        "climb_then_dive": 5,
        "turn_then_dive": 4,
        "zigzag_dive": 4,
    }


def test_generate_dataset_records_failed_metadata_with_reason_and_seed():
    root = Path("tests/.tmp_dataset_fail")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    cfg = {
        "schema_version": "1.0.0",
        "output_root": str(root / "dataset_workspace"),
        "seed": 200,
        "max_resample_attempts": 2,
        "progress": {"enabled": False},
        "failure_logging": {"include_failed_metadata": True},
        "class_quota": {
            "hover": 0,
            "straight_penetration": 0,
            "non_straight_penetration": 1,
            "loiter": 0,
            "retreat": 0,
        },
        **BASE_PROFILE,
    }
    cfg["constraints"] = {
        **BASE_PROFILE["constraints"],
        "intent_limits": {
            **BASE_PROFILE["constraints"]["intent_limits"],
            "non_straight_penetration": {"max_speed": 1.0, "max_acc": 1.0, "max_yaw_rate": 0.1},
        },
    }

    cfg_path = root / "dataset_config_fail.json"
    cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    summary = generate_dataset(str(cfg_path))
    assert summary["generated"] == 0
    assert summary["failed"] == 4

    rows = list(csv.DictReader((Path(cfg["output_root"]) / "metadata.csv").read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 4
    assert {row["status"] for row in rows} == {"failed"}
    assert {row["variant_name"] for row in rows} == set(NON_STRAIGHT_VARIANTS)
    assert all(row["failure_reason"] for row in rows)
    assert all(row["random_seed"] for row in rows)
    assert all(row["variant_summary"] for row in rows)
    assert all(row["attempt_count"] == "2" for row in rows)
    assert all(row["target_quota"] == "1" for row in rows)
    assert all(row["variant_attempt_count"] == "2" for row in rows)


def test_generate_dataset_accepts_utf8_bom_config():
    root = Path("tests/.tmp_dataset_bom")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    cfg = {
        "schema_version": "1.0.0",
        "output_root": str(root / "dataset_workspace"),
        "seed": 101,
        "max_resample_attempts": 3,
        "progress": {"enabled": False},
        "failure_logging": {"include_failed_metadata": True},
        "class_quota": {
            "hover": 1,
            "straight_penetration": 1,
            "non_straight_penetration": 1,
            "loiter": 1,
            "retreat": 1,
        },
        **BASE_PROFILE,
    }

    cfg_path = root / "dataset_config_bom.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8-sig")

    summary = generate_dataset(str(cfg_path))
    assert summary["generated"] == 8
    assert summary["failed"] == 0
