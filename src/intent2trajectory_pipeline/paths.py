from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    run_root: Path
    input_csv: Path
    preprocessed_local_csv: Path
    prepare_segment_csv: Path
    orchestrator_log: Path
    offboard_log: Path
    px4_stdout_log: Path
    ulog_path: Path
    executed_local_csv: Path
    executed_absolute_csv: Path
    manifest_json: Path
    status_json: Path


def build_run_paths(runs_root: Path, source_csv: Path, run_id: str) -> RunPaths:
    stem = source_csv.stem
    run_root = runs_root / run_id
    return RunPaths(
        run_root=run_root,
        input_csv=run_root / 'input' / source_csv.name,
        preprocessed_local_csv=run_root / 'preprocessed' / f'{stem}__local_ned.csv',
        prepare_segment_csv=run_root / 'preprocessed' / f'{stem}__prepare_segment.csv',
        orchestrator_log=run_root / 'logs' / 'orchestrator.log',
        offboard_log=run_root / 'logs' / 'offboard_node.log',
        px4_stdout_log=run_root / 'logs' / 'px4_stdout.log',
        ulog_path=run_root / 'artifacts' / f'{stem}__flight.ulg',
        executed_local_csv=run_root / 'output' / f'{stem}__executed_local.csv',
        executed_absolute_csv=run_root / 'output' / f'{stem}__executed_absolute.csv',
        manifest_json=run_root / 'manifest.json',
        status_json=run_root / 'status.json',
    )
