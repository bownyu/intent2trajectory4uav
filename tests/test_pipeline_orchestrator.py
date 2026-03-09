import runpy
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from intent2trajectory_pipeline.orchestrator import create_run_context, run_single_csv_pipeline


def _make_local_tmp(name: str) -> Path:
    root = Path('tests/.tmp_pipeline') / f'{name}_{uuid.uuid4().hex[:8]}'
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_create_run_context_returns_traceable_paths():
    tmp_root = _make_local_tmp('orchestrator_context')
    source_csv = tmp_root / 'hover_case.csv'
    source_csv.write_text('time_relative,ref_pos_x,ref_pos_y,ref_pos_z,ref_yaw\n0.0,1.0,2.0,3.0,0.1\n', encoding='utf-8')

    context = create_run_context(
        source_csv=source_csv,
        runs_root=tmp_root / 'runs',
        coordinate_frame='ENU',
        px4_model='gz_x500',
        world='default',
        simulation_speed_factor=1.0,
    )

    assert context.manifest['source_csv_name'] == 'hover_case.csv'
    assert context.paths.manifest_json.name == 'manifest.json'
    assert context.manifest['world'] == 'default'


def test_run_single_csv_pipeline_creates_traceable_run_artifacts():
    tmp_root = _make_local_tmp('orchestrator_run')
    csv_path = tmp_root / 'hover_case.csv'
    csv_path.write_text(
        'time_relative,ref_pos_x,ref_pos_y,ref_pos_z,ref_yaw\n'
        '0.0,1.0,2.0,3.0,0.1\n'
        '0.1,1.5,2.5,3.5,0.2\n',
        encoding='utf-8',
    )

    result = run_single_csv_pipeline(
        source_csv=csv_path,
        runs_root=tmp_root / 'runs',
        coordinate_frame='NED',
        px4_model='gz_x500',
        world='default',
        simulation_speed_factor=1.0,
        dry_run=True,
    )

    assert result.manifest['source_csv_name'] == 'hover_case.csv'
    assert result.paths.input_csv.exists()
    assert result.paths.preprocessed_local_csv.exists()
    assert result.paths.prepare_segment_csv.exists()
    assert result.paths.manifest_json.exists()
    assert result.paths.status_json.exists()


def test_cli_module_is_loadable():
    namespace = runpy.run_path('scripts/run_single_csv_pipeline.py')
    assert 'build_parser' in namespace


def test_cli_runs_as_standalone_process():
    result = subprocess.run(
        [sys.executable, 'scripts/run_single_csv_pipeline.py', '--help'],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '--input-csv' in result.stdout
