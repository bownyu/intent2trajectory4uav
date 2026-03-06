# WSL Single-CSV PX4 Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a WSL-only single-CSV experiment pipeline that preprocesses one trajectory, replays it through ROS 2 Offboard into PX4 SITL plus Gazebo, collects ULog, and exports executed CSV results with full run traceability.

**Architecture:** A Python orchestrator owns one run directory and invokes three layers in sequence: preprocessing, simulation and replay, and result export. The ROS 2 Offboard node encapsulates the replay state machine, while manifest and status files make every artifact traceable back to the original CSV.

**Tech Stack:** Python 3, ROS 2, PX4 SITL, Gazebo, Micro XRCE-DDS Agent, pytest, JSON, CSV

---

### Task 1: Create the pipeline module skeleton

**Files:**
- Create: `src/intent2trajectory_pipeline/__init__.py`
- Create: `src/intent2trajectory_pipeline/paths.py`
- Create: `src/intent2trajectory_pipeline/models.py`
- Test: `tests/test_pipeline_paths.py`

**Step 1: Write the failing test**

```python
from pathlib import Path

from intent2trajectory_pipeline.paths import build_run_paths


def test_build_run_paths_preserves_source_name(tmp_path: Path):
    paths = build_run_paths(
        runs_root=tmp_path / "runs",
        source_csv=Path("/data/input/hover_case.csv"),
        run_id="20260306_183000__hover_case__deadbeef",
    )

    assert paths.input_csv.name == "hover_case.csv"
    assert paths.preprocessed_local_csv.name == "hover_case__local_ned.csv"
    assert paths.executed_absolute_csv.name == "hover_case__executed_absolute.csv"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_paths.py::test_build_run_paths_preserves_source_name -v`
Expected: FAIL with missing module or function

**Step 3: Write minimal implementation**

Implement the run path dataclass and deterministic naming contract described in the design doc.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_paths.py::test_build_run_paths_preserves_source_name -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_paths.py src/intent2trajectory_pipeline/__init__.py src/intent2trajectory_pipeline/paths.py src/intent2trajectory_pipeline/models.py
git commit -m "feat: add pipeline path contracts"
```

### Task 2: Add run-id and manifest generation

**Files:**
- Modify: `src/intent2trajectory_pipeline/models.py`
- Create: `src/intent2trajectory_pipeline/manifest.py`
- Modify: `tests/test_pipeline_paths.py`

**Step 1: Write the failing test**

Write tests for `make_run_id(...)` and `build_manifest(...)` so that the source filename and all derived artifact paths remain traceable.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_paths.py -v`
Expected: FAIL with missing manifest utilities

**Step 3: Write minimal implementation**

Implement:

```python
def make_run_id(source_csv_name: str, short_hash: str, timestamp: str) -> str:
    ...


def build_manifest(...):
    ...
```

The manifest must include the stage-one required keys from the design doc.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_paths.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_paths.py src/intent2trajectory_pipeline/models.py src/intent2trajectory_pipeline/manifest.py
git commit -m "feat: add run manifest contracts"
```

### Task 3: Add runtime status persistence

**Files:**
- Create: `src/intent2trajectory_pipeline/status.py`
- Test: `tests/test_pipeline_status.py`

**Step 1: Write the failing test**

Write a test that persists `status.json` and asserts `state`, `last_completed_stage`, `failure_reason`, and `updated_at` are written.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_status.py::test_write_status_persists_state_and_failure_reason -v`
Expected: FAIL with missing module or function

**Step 3: Write minimal implementation**

Implement a status writer that updates the JSON payload on every stage transition.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_status.py::test_write_status_persists_state_and_failure_reason -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_status.py src/intent2trajectory_pipeline/status.py
git commit -m "feat: add runtime status tracking"
```

### Task 4: Implement CSV loading and frame selection

**Files:**
- Create: `src/intent2trajectory_pipeline/io_csv.py`
- Test: `tests/test_pipeline_io_csv.py`

**Step 1: Write the failing test**

Write tests for:

- preferring `ref_pos_*` over `pos_*`
- falling back to `pos_*` when `ref_*` is absent
- reading `ref_yaw` first, then `yaw`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_io_csv.py -v`
Expected: FAIL with missing loader implementation

**Step 3: Write minimal implementation**

Implement the CSV loader that returns normalized rows with `time_relative`, `x`, `y`, `z`, and `yaw`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_io_csv.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_io_csv.py src/intent2trajectory_pipeline/io_csv.py
git commit -m "feat: add reference csv loader"
```

### Task 5: Implement local-frame preprocessing

**Files:**
- Create: `src/intent2trajectory_pipeline/preprocess.py`
- Test: `tests/test_pipeline_preprocess.py`

**Step 1: Write the failing test**

Write tests that verify:

- the first row becomes the saved `initial_pose`
- the first local row is zeroed in the local frame
- `ENU` and `NED` are treated explicitly rather than guessed

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_preprocess.py -v`
Expected: FAIL with missing preprocessing implementation

**Step 3: Write minimal implementation**

Implement preprocessing that stores the first frame as `initial_pose`, converts rows to the local replay frame, and saves the offset needed for absolute result restoration.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_preprocess.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_preprocess.py src/intent2trajectory_pipeline/preprocess.py
git commit -m "feat: add local trajectory preprocessing"
```

### Task 6: Implement prepare-segment generation

**Files:**
- Modify: `src/intent2trajectory_pipeline/preprocess.py`
- Modify: `tests/test_pipeline_preprocess.py`

**Step 1: Write the failing test**

Write a test asserting the prepare segment starts at the configured safe spawn altitude, ends at the desired initial altitude, and preserves the initial `x`, `y`, and `yaw`.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_preprocess.py::test_build_prepare_segment_creates_safe_start_before_playback -v`
Expected: FAIL with missing function

**Step 3: Write minimal implementation**

Implement `build_prepare_segment(...)` to create a deterministic interpolation segment for stage-one startup.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_preprocess.py::test_build_prepare_segment_creates_safe_start_before_playback -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_preprocess.py src/intent2trajectory_pipeline/preprocess.py
git commit -m "feat: add prepare segment generation"
```

### Task 7: Implement filesystem writers for run artifacts

**Files:**
- Create: `src/intent2trajectory_pipeline/write_outputs.py`
- Test: `tests/test_pipeline_write_outputs.py`

**Step 1: Write the failing test**

Write tests for run directory creation, manifest JSON writing, and CSV writing for preprocessed artifacts.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_write_outputs.py -v`
Expected: FAIL with missing file writer utilities

**Step 3: Write minimal implementation**

Implement run directory creation, JSON writers, and CSV writers for replay and export files.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_write_outputs.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_write_outputs.py src/intent2trajectory_pipeline/write_outputs.py
git commit -m "feat: add pipeline artifact writers"
```

### Task 8: Add process-launch contract for external tools

**Files:**
- Create: `src/intent2trajectory_pipeline/processes.py`
- Test: `tests/test_pipeline_processes.py`

**Step 1: Write the failing test**

Write tests for command builders that produce:

- a valid `MicroXRCEAgent` command
- a PX4 command containing the selected model and world
- a contract for simulation speed factor

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_processes.py -v`
Expected: FAIL with missing command builders

**Step 3: Write minimal implementation**

Implement deterministic command builders for the external processes without launching them in tests.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_processes.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_processes.py src/intent2trajectory_pipeline/processes.py
git commit -m "feat: add external process command builders"
```

### Task 9: Add replay state-machine contract

**Files:**
- Create: `src/intent2trajectory_pipeline/replay_state.py`
- Test: `tests/test_pipeline_replay_state.py`

**Step 1: Write the failing test**

Write tests that walk through:

- `LOAD_TRAJECTORY`
- `PREPARE_START`
- `WARMUP`
- `ARM_AND_OFFBOARD`
- `PLAYBACK`
- `HOLD_LAST_SETPOINT`
- `FINISH`

and reject invalid transitions.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_replay_state.py -v`
Expected: FAIL with missing state-machine implementation

**Step 3: Write minimal implementation**

Implement a small explicit state machine independent from ROS 2 so its transition rules can be tested directly.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_replay_state.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_replay_state.py src/intent2trajectory_pipeline/replay_state.py
git commit -m "feat: add replay state machine contract"
```

### Task 10: Implement the single-run orchestrator contract

**Files:**
- Create: `src/intent2trajectory_pipeline/orchestrator.py`
- Test: `tests/test_pipeline_orchestrator.py`

**Step 1: Write the failing test**

Write a test that constructs one run context and asserts the source filename is preserved in the manifest, traceable path objects are returned, and the selected coordinate frame, model, and world are recorded.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_orchestrator.py -v`
Expected: FAIL with missing orchestrator implementation

**Step 3: Write minimal implementation**

Implement `create_run_context(...)` and the basic orchestration data model without process launching yet.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_orchestrator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_orchestrator.py src/intent2trajectory_pipeline/orchestrator.py
git commit -m "feat: add single-run orchestrator contract"
```

### Task 11: Add the CLI entrypoint for one CSV run

**Files:**
- Create: `scripts/run_single_csv_pipeline.py`
- Modify: `tests/test_pipeline_orchestrator.py`

**Step 1: Write the failing test**

Write a test that loads the CLI module and asserts the parser accepts:

- `--input-csv`
- `--runs-root`
- `--coordinate-frame`
- `--px4-model`
- `--world`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_orchestrator.py::test_cli_module_is_loadable -v`
Expected: FAIL because the script does not exist

**Step 3: Write minimal implementation**

Implement the parser and a thin `main()` entrypoint for one run.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_orchestrator.py::test_cli_module_is_loadable -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_orchestrator.py scripts/run_single_csv_pipeline.py
git commit -m "feat: add single csv pipeline entrypoint"
```

### Task 12: Add ULog export contract

**Files:**
- Create: `src/intent2trajectory_pipeline/ulog_export.py`
- Test: `tests/test_pipeline_ulog_export.py`

**Step 1: Write the failing test**

Write tests that verify executed export rows include:

- `time_relative`
- `act_pos_x`
- `act_pos_y`
- `act_pos_z`
- `act_vel_x`
- `act_vel_y`
- `act_vel_z`
- `act_yaw`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_ulog_export.py -v`
Expected: FAIL with missing export implementation

**Step 3: Write minimal implementation**

Implement a transformation layer from parsed ULog samples to executed CSV rows.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_ulog_export.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_pipeline_ulog_export.py src/intent2trajectory_pipeline/ulog_export.py
git commit -m "feat: add executed csv export contract"
```

### Task 13: Add planning references to current docs

**Files:**
- Modify: `README.md`
- Modify: `docs/worklog/2026-03-06-implementation-status.md`

**Step 1: Write the documentation change**

Add a concise note that the WSL single-CSV PX4 pipeline is now planned but not yet implemented.

**Step 2: Run verification**

Run: `rg "2026-03-06-wsl-px4-single-csv-pipeline" README.md docs/worklog/2026-03-06-implementation-status.md`
Expected: both docs reference the new planning files

**Step 3: Commit**

```bash
git add README.md docs/worklog/2026-03-06-implementation-status.md
git commit -m "docs: add single csv pipeline planning references"
```

### Task 14: End-to-end stage-one dry-run verification

**Files:**
- Modify: `scripts/run_single_csv_pipeline.py`
- Modify: `src/intent2trajectory_pipeline/orchestrator.py`
- Modify: `src/intent2trajectory_pipeline/preprocess.py`
- Modify: `src/intent2trajectory_pipeline/processes.py`
- Modify: `src/intent2trajectory_pipeline/ulog_export.py`
- Modify: `tests/test_pipeline_orchestrator.py`
- Modify: `tests/test_pipeline_preprocess.py`
- Modify: `tests/test_pipeline_processes.py`
- Modify: `tests/test_pipeline_ulog_export.py`

**Step 1: Write the failing integration test**

Write a dry-run integration test that creates a temporary CSV, runs the orchestrator in `dry_run=True`, and asserts the run directory, copied input, preprocessed CSV, manifest, and status files exist.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_orchestrator.py::test_run_single_csv_pipeline_creates_traceable_run_artifacts -v`
Expected: FAIL because the dry-run orchestration path is incomplete

**Step 3: Write minimal implementation**

Implement a dry-run path that:

- creates the run directory
- copies the source CSV
- writes manifest and status files
- writes the local replay CSV and prepare segment CSV
- skips launching PX4, Gazebo, Agent, and ROS 2 when `dry_run=True`

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pipeline_paths.py tests/test_pipeline_status.py tests/test_pipeline_io_csv.py tests/test_pipeline_preprocess.py tests/test_pipeline_write_outputs.py tests/test_pipeline_processes.py tests/test_pipeline_replay_state.py tests/test_pipeline_orchestrator.py tests/test_pipeline_ulog_export.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/run_single_csv_pipeline.py src/intent2trajectory_pipeline tests
git commit -m "feat: add dry-run single csv pipeline"
```
