import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from intent2trajectory_pipeline.orchestrator import run_single_csv_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-csv', required=True)
    parser.add_argument('--runs-root', default='/opt/intent2trajectory_pipeline/runs')
    parser.add_argument('--coordinate-frame', required=True, choices=['ENU', 'NED'])
    parser.add_argument('--px4-model', default='gz_x500')
    parser.add_argument('--world', default='default')
    parser.add_argument('--simulation-speed-factor', type=float, default=1.0)
    parser.add_argument('--dry-run', action='store_true')
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_single_csv_pipeline(
        source_csv=Path(args.input_csv),
        runs_root=Path(args.runs_root),
        coordinate_frame=args.coordinate_frame,
        px4_model=args.px4_model,
        world=args.world,
        simulation_speed_factor=args.simulation_speed_factor,
        dry_run=args.dry_run,
    )


if __name__ == '__main__':
    main()
