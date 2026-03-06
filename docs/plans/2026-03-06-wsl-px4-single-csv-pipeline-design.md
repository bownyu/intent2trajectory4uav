# WSL Single-CSV PX4 Pipeline Design

**Date:** 2026-03-06

## Goal

Build the first-stage simulation pipeline for this project inside WSL so that one trajectory CSV can be replayed end-to-end through CSV preprocessing, ROS 2 Offboard playback, PX4 SITL plus Gazebo simulation, ULog collection, and executed result CSV export.

The target is a single CSV run with full traceability. Batch scheduling is deferred to the next stage.

## Current Project Status

The repository currently implements only the kinematic `intent -> trajectory` generation stage:

- configurable CSV generation
- `ref_*` trajectory export
- reserved `act_*` columns
- metadata export
- GUI playback for inspection

The ROS 2, PX4, Gazebo, Micro XRCE-DDS, and ULog recovery pipeline described in `docs/csv2csv仿真流程.md` is not implemented in code yet.

## Confirmed Constraints

- All runtime scripts execute inside WSL, not on Windows.
- The user will copy project data and scripts into WSL and run there.
- The WSL environment already has ROS 2, Micro XRCE-DDS, PX4, and Gazebo installed.
- QGroundControl remains on Windows and is outside this repository's automation scope.
- Stage one only needs to run a single CSV successfully and collect one result directory.
- All processed files must remain traceable to the original input CSV filename.

## Recommended Architecture

Use a WSL-local Python orchestrator as the top-level controller, with the repository as the control plane and WSL as the execution plane.

### WSL Project Root

Create and use a fixed WSL workspace root:

- `/opt/intent2trajectory_pipeline`

### Main Components

1. **Pipeline orchestrator**: a Python entrypoint that coordinates one full run from input CSV to exported results.
2. **Trajectory preprocessing layer**: converts the source CSV into the local trajectory PX4 expects.
3. **ROS 2 Offboard replay node**: owns the execution state machine and publishes PX4 input topics.
4. **PX4/Gazebo process launcher**: starts the SITL stack and waits until required topics are available.
5. **ULog recovery and export layer**: collects the generated `.ulg`, extracts executed state, and writes result CSVs.

## Data Flow

The run data path is:

`source CSV -> preprocessed local reference CSV -> Offboard playback -> PX4 ULog -> executed local CSV -> executed absolute CSV`

### Input Selection

- Prefer `ref_*` columns if present.
- Fall back to `pos_*` columns if `ref_*` are absent.
- Require the coordinate frame to be configured explicitly as `ENU` or `NED` in stage one.

### Preprocessing

For each run:

1. Read the first frame as absolute start pose `(x0, y0, z0, yaw0)`.
2. Preserve the absolute trajectory semantics in an archived copy.
3. Convert the trajectory to PX4-compatible local NED coordinates.
4. Generate a local replay CSV that PX4 Offboard control can consume.

The preprocessing stage also retains the offset needed to recover absolute executed coordinates after simulation.

### Simulation Initialization

Gazebo model spawning uses the first frame's absolute `x`, `y`, and `yaw`, but does not spawn directly at the first frame altitude when the trajectory starts in the air.

Instead, stage one uses a preparation policy:

- spawn at a safe altitude below the first desired state
- enter a preparation segment
- warm up Offboard control
- arm and transition into the formal replay segment

## Offboard Execution State Machine

The ROS 2 replay node must implement the following explicit states:

- `LOAD_TRAJECTORY`
- `PREPARE_START`
- `WARMUP`
- `ARM_AND_OFFBOARD`
- `PLAYBACK`
- `HOLD_LAST_SETPOINT`
- `FINISH`

### Required Behavior

- `WARMUP` must publish `OffboardControlMode` and valid setpoints continuously for more than one second before arming into Offboard.
- `PLAYBACK` must follow simulation time semantics, not wall-clock semantics.
- If PX4 leaves Offboard unexpectedly during playback, the run must be marked failed.
- `HOLD_LAST_SETPOINT` provides a short stable window before shutdown and log collection.

Stage one only supports position plus yaw replay. It deliberately avoids additional acceleration or jerk control complexity.

## Traceability and File Naming

Every run must preserve a direct mapping back to the original CSV filename.

### Run ID

Use a run identifier of the form:

- `YYYYMMDD_HHMMSS__<source_stem>__<short_hash>`

Example:

- `20260306_183000__loiter_circle_hold_0001_D1450_V10__a1b2c3d4`

### Run Directory Layout

Each run produces:

- `runs/<run_id>/input/<original_filename>.csv`
- `runs/<run_id>/preprocessed/<original_stem>__local_ned.csv`
- `runs/<run_id>/preprocessed/<original_stem>__prepare_segment.csv`
- `runs/<run_id>/logs/orchestrator.log`
- `runs/<run_id>/logs/offboard_node.log`
- `runs/<run_id>/logs/px4_stdout.log`
- `runs/<run_id>/artifacts/<original_stem>__flight.ulg`
- `runs/<run_id>/output/<original_stem>__executed_local.csv`
- `runs/<run_id>/output/<original_stem>__executed_absolute.csv`
- `runs/<run_id>/manifest.json`
- `runs/<run_id>/status.json`

### Manifest Contract

`manifest.json` must include at least:

- `run_id`
- `source_csv_name`
- `source_csv_original_path`
- `source_csv_copied_path`
- `preprocessed_local_csv`
- `prepare_segment_csv`
- `ulog_path`
- `executed_local_csv`
- `executed_absolute_csv`
- `coordinate_frame`
- `initial_pose`
- `simulation_speed_factor`
- `px4_model`
- `world`
- `status`

### Runtime Status Contract

`status.json` must be updated during the run and include at least:

- `state`
- `started_at`
- `updated_at`
- `finished_at`
- `failure_reason`
- `last_completed_stage`

## Result Collection

The primary recorded source of truth is PX4 ULog.

After replay:

1. collect the latest `.ulg` from PX4 SITL log storage
2. parse the executed state
3. export a local-frame executed CSV
4. restore the saved absolute offset
5. export an absolute-frame executed CSV

The executed CSV must include at least:

- `time_relative`
- `act_pos_x`
- `act_pos_y`
- `act_pos_z`
- `act_vel_x`
- `act_vel_y`
- `act_vel_z`
- `act_yaw`

## Failure Handling

Stage one uses a preserve-everything policy:

- no automatic retry
- no cleanup of failed run artifacts
- always persist logs and partial artifacts when possible
- always write failure state to `status.json`

## Acceptance Criteria

Stage one is complete only if all of the following are true:

1. One input CSV can launch the full pipeline from one CLI entrypoint inside WSL.
2. A dedicated run directory is created with traceable filenames and a populated `manifest.json`.
3. The ROS 2 replay node completes the intended state sequence with logged transitions.
4. PX4 SITL plus Gazebo complete one valid simulated flight and produce a `.ulg`.
5. The `.ulg` is parsed into both local and absolute executed CSV outputs.
6. On failure, `status.json` and logs show the failing stage and reason.

## Stage-One Boundaries

The following are out of scope for stage one:

- batch scheduling
- automatic retry
- multi-vehicle model support
- advanced world management
- automatic coordinate-frame inference
- large-scale evaluation metrics

The baseline environment is intentionally narrow:

- one model, recommended `gz_x500`
- one simple world
- one short regression CSV used for repeated validation
