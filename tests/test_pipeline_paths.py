import shutil
import uuid
from pathlib import Path

from intent2trajectory_pipeline.manifest import build_manifest, make_run_id
from intent2trajectory_pipeline.paths import build_run_paths


def _make_local_tmp(name: str) -> Path:
    root = Path('tests/.tmp_pipeline') / f'{name}_{uuid.uuid4().hex[:8]}'
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_build_run_paths_preserves_source_name():
    tmp_root = _make_local_tmp('paths')
    paths = build_run_paths(
        runs_root=tmp_root / 'runs',
        source_csv=Path('/data/input/hover_case.csv'),
        run_id='20260306_183000__hover_case__deadbeef',
    )

    assert paths.input_csv.name == 'hover_case.csv'
    assert paths.preprocessed_local_csv.name == 'hover_case__local_ned.csv'
    assert paths.prepare_segment_csv.name == 'hover_case__prepare_segment.csv'
    assert paths.executed_absolute_csv.name == 'hover_case__executed_absolute.csv'


def test_make_run_id_includes_source_stem():
    run_id = make_run_id('hover_case.csv', 'abc12345', '20260306_183000')
    assert run_id == '20260306_183000__hover_case__abc12345'


def test_build_manifest_records_traceable_artifacts():
    tmp_root = _make_local_tmp('manifest')
    manifest = build_manifest(
        run_id='20260306_183000__hover_case__abc12345',
        source_csv_original_path='/data/input/hover_case.csv',
        source_csv_copied_path=str(tmp_root / 'runs' / 'x' / 'input' / 'hover_case.csv'),
        preprocessed_local_csv='local.csv',
        prepare_segment_csv='prepare.csv',
        ulog_path='flight.ulg',
        executed_local_csv='exec_local.csv',
        executed_absolute_csv='exec_abs.csv',
        coordinate_frame='ENU',
        initial_pose={'x': 1.0, 'y': 2.0, 'z': 3.0, 'yaw': 0.5},
        simulation_speed_factor=1.0,
        px4_model='gz_x500',
        world='default',
        status='created',
    )

    assert manifest['source_csv_name'] == 'hover_case.csv'
    assert manifest['executed_absolute_csv'] == 'exec_abs.csv'
    assert manifest['coordinate_frame'] == 'ENU'
