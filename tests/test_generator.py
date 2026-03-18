import csv
import json
import shutil
from pathlib import Path

from intent2trajectory.generator import generate_dataset, generate_sample, load_config, validate_sample
from intent2trajectory.validators.diversity_filter import DiversityFilter


def _base_config(tmp_root: Path | None = None):
    cfg = load_config("configs/dataset_config.json")
    cfg["progress"] = {"enabled": False}
    if tmp_root is not None:
        cfg["output_root"] = str(tmp_root / "dataset_workspace")
    return cfg


def test_load_config_reads_split_semantic_files():
    cfg = load_config("configs/dataset_config.json")

    assert cfg["schema_version"] == "2.0.0"
    assert set(cfg["intent_order"]) == {"attack", "retreat", "hover", "loiter"}
    assert "profiles" in cfg["airframes"]
    assert "intent_regions" in cfg["intent_regions"]
    assert "intents" in cfg["style_library"]
    assert cfg["class_quota"]["attack"] > 0


def test_generate_sample_emits_new_semantic_metadata_for_all_intents():
    cfg = _base_config()

    for idx, intent in enumerate(("attack", "retreat", "hover", "loiter"), start=1):
        sample = generate_sample(intent, seed=100 + idx, profile=cfg)
        result = validate_sample(sample, cfg)
        scores = sample["metadata"]["intent_scores"]

        assert result["valid"] is True, result["reasons"]
        assert sample["metadata"]["primary_intent"] == intent
        assert sample["metadata"]["motion_style"]
        assert sample["metadata"]["airframe_name"]
        assert sample["metadata"]["airframe_family"] in {"multirotor", "fixed_wing", "vtol"}
        assert set(sample["metadata"]["risk_vector"]) == {
            "close_score",
            "dwell_score",
            "encircle_score",
            "point_score",
            "uncertain_score",
            "disengage_score",
        }
        assert set(scores) == {"attack", "retreat", "hover", "loiter"}
        assert scores[intent] == max(scores.values())
        assert sample["metadata"]["stage_plan"]
        assert sample["metadata"]["flight_mode_sequence"]


def test_legacy_penetration_alias_maps_to_attack_direct_commit():
    cfg = _base_config()
    sample = generate_sample("straight_penetration", seed=321, profile=cfg, variant_name="direct_closing")
    result = validate_sample(sample, cfg)

    assert result["valid"] is True, result["reasons"]
    assert sample["metadata"]["primary_intent"] == "attack"
    assert sample["metadata"]["motion_style"] == "direct_commit"
    assert "legacy intent 'straight_penetration' mapped to 'attack'" == sample["metadata"]["legacy_hint"]


def test_fixed_wing_hover_and_loiter_use_supported_styles_and_validate():
    cfg = _base_config()

    hover = generate_sample("hover", seed=401, profile=cfg, variant_name="corridor_hold", airframe_name="fixed_wing_patrol")
    loiter = generate_sample("loiter", seed=402, profile=cfg, variant_name="ellipse_loiter", airframe_name="fixed_wing_patrol")

    hover_result = validate_sample(hover, cfg)
    loiter_result = validate_sample(loiter, cfg)

    assert hover_result["valid"] is True, hover_result["reasons"]
    assert loiter_result["valid"] is True, loiter_result["reasons"]
    assert hover["metadata"]["motion_style"] in {"corridor_hold", "pseudo_hover_racetrack"}
    assert loiter["metadata"]["motion_style"] in {"circle_loiter", "ellipse_loiter", "racetrack_loiter", "probe_loiter"}
    assert hover["metadata"]["flight_mode_sequence"] == ["cruise"]
    assert loiter["metadata"]["flight_mode_sequence"] == ["cruise"]


def test_vtol_attack_validates_and_keeps_airframe_context():
    cfg = _base_config()
    sample = generate_sample("attack", seed=510, profile=cfg, variant_name="direct_commit", airframe_name="vtol_hybrid")
    result = validate_sample(sample, cfg)

    assert result["valid"] is True, result["reasons"]
    assert sample["metadata"]["airframe_name"] == "vtol_hybrid"
    assert sample["metadata"]["airframe_family"] == "vtol"
    assert sample["metadata"]["motion_style"] in cfg["airframes"]["profiles"]["vtol_hybrid"]["allowed_styles"]["attack"]


def test_diversity_filter_rejects_duplicate_candidate():
    cfg = _base_config()
    first = generate_sample("hover", seed=901, profile=cfg, airframe_name="quad_small")
    second = generate_sample("hover", seed=901, profile=cfg, airframe_name="quad_small")
    validate_sample(first, cfg)
    validate_sample(second, cfg)

    diversity = DiversityFilter(cfg["diversity"])
    assert diversity.accept(first) == (True, "")
    accepted, reason = diversity.accept(second)
    assert accepted is False
    assert reason == "diversity_duplicate"


def test_generate_dataset_writes_semantic_exports():
    root = Path("tests/.tmp_semantic_dataset")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    cfg = _base_config(root)
    cfg["class_quota"] = {"attack": 1, "retreat": 1, "hover": 1, "loiter": 1}
    cfg_path = root / "dataset_config.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = generate_dataset(str(cfg_path))
    output_root = Path(summary["output_root"])

    assert summary["generated"] == 4
    assert summary["failed"] == 0
    assert set(summary["style_counts"]) == {"attack", "retreat", "hover", "loiter"}

    metadata_rows = list(csv.DictReader((output_root / "metadata.csv").read_text(encoding="utf-8").splitlines()))
    assert len(metadata_rows) == 4
    assert {row["primary_intent"] for row in metadata_rows} == {"attack", "retreat", "hover", "loiter"}
    assert all(row["motion_style"] for row in metadata_rows)
    assert all(row["airframe_name"] for row in metadata_rows)
    assert all(row["intent_scores_json"] for row in metadata_rows)
    assert all(row["risk_vector_json"] for row in metadata_rows)
    assert all(row["stage_plan_json"] for row in metadata_rows)

    meta_files = list((output_root / "meta").rglob("*.json"))
    origin_files = list((output_root / "origin").rglob("*.csv"))
    threat_files = list((output_root / "threat").rglob("*.csv"))

    assert len(meta_files) == 4
    assert len(origin_files) == 4
    assert len(threat_files) == 4

    sample_meta = json.loads(meta_files[0].read_text(encoding="utf-8"))
    assert {"sample_id", "primary_intent", "motion_style", "airframe", "risk_vector", "intent_scores", "stage_plan"}.issubset(sample_meta)

