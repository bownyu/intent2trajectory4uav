import hashlib
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict

from .io_csv import load_reference_rows
from .manifest import build_manifest, make_run_id
from .paths import RunPaths, build_run_paths
from .preprocess import build_prepare_segment, preprocess_rows
from .status import write_status
from .write_outputs import ensure_run_directories, write_csv_rows, write_manifest


@dataclass(frozen=True)
class RunContext:
    paths: RunPaths
    manifest: Dict[str, object]


@dataclass(frozen=True)
class PipelineRunResult:
    paths: RunPaths
    manifest: Dict[str, object]


def _timestamp_now() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def _short_hash(source_csv: Path) -> str:
    digest = hashlib.sha1(str(source_csv).encode('utf-8')).hexdigest()
    return digest[:8]


def create_run_context(
    *,
    source_csv: Path,
    runs_root: Path,
    coordinate_frame: str,
    px4_model: str,
    world: str,
    simulation_speed_factor: float,
) -> RunContext:
    run_id = make_run_id(source_csv.name, _short_hash(source_csv), _timestamp_now())
    paths = build_run_paths(runs_root=runs_root, source_csv=source_csv, run_id=run_id)
    manifest = build_manifest(
        run_id=run_id,
        source_csv_original_path=str(source_csv),
        source_csv_copied_path=str(paths.input_csv),
        preprocessed_local_csv=str(paths.preprocessed_local_csv),
        prepare_segment_csv=str(paths.prepare_segment_csv),
        ulog_path=str(paths.ulog_path),
        executed_local_csv=str(paths.executed_local_csv),
        executed_absolute_csv=str(paths.executed_absolute_csv),
        coordinate_frame=coordinate_frame,
        initial_pose={},
        simulation_speed_factor=simulation_speed_factor,
        px4_model=px4_model,
        world=world,
        status='created',
    )
    return RunContext(paths=paths, manifest=manifest)


def run_single_csv_pipeline(
    *,
    source_csv: Path,
    runs_root: Path,
    coordinate_frame: str,
    px4_model: str,
    world: str,
    simulation_speed_factor: float,
    dry_run: bool,
    safe_spawn_z: float = 5.0,
    prepare_duration: float = 2.0,
) -> PipelineRunResult:
    context = create_run_context(
        source_csv=source_csv,
        runs_root=runs_root,
        coordinate_frame=coordinate_frame,
        px4_model=px4_model,
        world=world,
        simulation_speed_factor=simulation_speed_factor,
    )
    ensure_run_directories(context.paths.run_root)
    shutil.copy2(source_csv, context.paths.input_csv)

    rows = load_reference_rows(source_csv)
    processed = preprocess_rows(rows, coordinate_frame=coordinate_frame)
    local_rows = processed.local_rows
    dt = local_rows[1]['time_relative'] - local_rows[0]['time_relative'] if len(local_rows) > 1 else 0.1
    prepare_rows = build_prepare_segment(
        initial_local_pose=local_rows[0],
        safe_spawn_z=safe_spawn_z,
        prepare_duration=prepare_duration,
        dt=dt,
    )

    manifest = dict(context.manifest)
    manifest['initial_pose'] = processed.initial_pose
    manifest['status'] = 'dry_run_complete' if dry_run else 'prepared'
    write_csv_rows(context.paths.preprocessed_local_csv, local_rows)
    write_csv_rows(context.paths.prepare_segment_csv, prepare_rows)
    write_manifest(context.paths.manifest_json, manifest)
    write_status(
        context.paths.status_json,
        state='DRY_RUN_COMPLETE' if dry_run else 'PREPARED',
        last_completed_stage='PREPROCESS',
        failure_reason='',
        started_at=_timestamp_now(),
        finished_at=_timestamp_now() if dry_run else None,
    )

    if not dry_run:
        raise NotImplementedError('Live PX4/Gazebo execution is not implemented yet')

    return PipelineRunResult(paths=context.paths, manifest=manifest)
