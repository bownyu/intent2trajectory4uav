import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from intent2trajectory.generator import generate_dataset, load_config


def _parse_formats(raw_values: Optional[Iterable[str]]) -> Optional[List[str]]:
    if raw_values is None:
        return None

    formats: List[str] = []
    for value in raw_values:
        for item in value.split(","):
            name = item.strip().lower()
            if name and name not in formats:
                formats.append(name)
    return formats


def _build_override_config(args: argparse.Namespace) -> dict:
    config = load_config(args.config)

    if args.output_root:
        config["output_root"] = args.output_root

    formats = _parse_formats(args.formats)
    if formats is not None:
        config["output_formats"] = formats

    if args.station_lat is not None or args.station_lon is not None:
        threat_export = dict(config.get("threat_export") or {})
        station = dict(threat_export.get("station") or {})
        if args.station_lat is not None:
            station["latitude"] = args.station_lat
        if args.station_lon is not None:
            station["longitude"] = args.station_lon
        threat_export["station"] = station
        config["threat_export"] = threat_export

    return config


def _write_temp_config(config: dict) -> Path:
    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        prefix="export_dual_format_",
        dir=str(PROJECT_ROOT),
        delete=False,
    )
    try:
        with temp_file:
            json.dump(config, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
    except Exception:
        Path(temp_file.name).unlink(missing_ok=True)
        raise
    return Path(temp_file.name)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export dataset in origin/threat formats with CLI overrides.")
    parser.add_argument("--config", default="configs/dataset_config.json", help="Path to the base JSON/YAML config.")
    parser.add_argument(
        "--formats",
        nargs="+",
        help="Output formats to export, for example: --formats origin threat or --formats origin,threat",
    )
    parser.add_argument("--station-lat", type=float, help="Override threat_export.station.latitude")
    parser.add_argument("--station-lon", type=float, help="Override threat_export.station.longitude")
    parser.add_argument("--output-root", help="Override output_root")
    args = parser.parse_args(argv)

    temp_config_path = _write_temp_config(_build_override_config(args))
    try:
        summary = generate_dataset(str(temp_config_path))
    finally:
        temp_config_path.unlink(missing_ok=True)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
