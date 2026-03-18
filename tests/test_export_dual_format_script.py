import csv
import json
import runpy
import shutil
import sys
from pathlib import Path

from intent2trajectory.generator import load_config


def test_export_dual_format_script_supports_cli_overrides(capsys):
    root = Path("tests/.tmp_export_dual_format_script")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    cfg = load_config("configs/dataset_config.json")
    cfg["progress"] = {"enabled": False}
    cfg["output_root"] = str(root / "config_output")
    cfg["class_quota"] = {"attack": 1, "retreat": 0, "hover": 0, "loiter": 0}
    config_path = root / "dataset_config.json"
    config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    argv = [
        "scripts/export_dual_format.py",
        "--config",
        str(config_path),
        "--formats",
        "origin",
        "threat",
        "--station-lat",
        "31.2304",
        "--station-lon",
        "121.4737",
        "--output-root",
        str(root / "cli_output"),
    ]

    old_argv = sys.argv[:]
    try:
        sys.argv = argv
        try:
            runpy.run_path(str(Path("scripts/export_dual_format.py")), run_name="__main__")
        except SystemExit as exc:
            assert exc.code == 0
    finally:
        sys.argv = old_argv

    summary = json.loads(capsys.readouterr().out)
    output_root = Path(summary["output_root"])

    assert summary["generated"] == 1
    assert summary["failed"] == 0
    assert output_root == root / "cli_output"
    assert not (root / "config_output").exists()

    metadata_rows = list(csv.DictReader((output_root / "metadata.csv").read_text(encoding="utf-8").splitlines()))
    assert len(metadata_rows) == 1
    assert metadata_rows[0]["output_formats"] == "origin,threat"
    assert metadata_rows[0]["primary_intent"] == "attack"
    assert metadata_rows[0]["motion_style"]

    origin_files = list((output_root / "origin").rglob("*.csv"))
    threat_files = list((output_root / "threat").rglob("*.csv"))
    meta_files = list((output_root / "meta").rglob("*.json"))
    assert len(origin_files) == 1
    assert len(threat_files) == 1
    assert len(meta_files) == 1
