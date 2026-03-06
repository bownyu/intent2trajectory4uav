# intent2trajectory (Kinematic Generator)

This repository implements the current `intent -> trajectory` kinematic generation stage for five UAV intent classes:

- `hover`
- `straight_penetration`
- `non_straight_penetration`
- `loiter`
- `retreat`

It is a configurable, reproducible trajectory generator with sample validation, metadata export, and a GUI trajectory player.

## Current Scope

Implemented in the current stage:

- config-driven batch generation
- per-intent sample count control via `class_quota`
- weighted maneuver variants for `non_straight_penetration` and `loiter`
- unified CSV export with `ref_*` and reserved `act_*` columns
- `metadata.csv` export including `variant_name`, `variant_summary`, and failure attempt information
- terminal progress output during dataset generation
- semantic validation for key intent classes
- GUI playback for generated trajectories

Not implemented yet:

- PX4 / JSBSim closed-loop simulation
- `.ulg` parsing and actual trajectory backfill
- simulation-corrected `act_*` data export

## Public APIs

- `generate_dataset(config_path)`
- `generate_sample(intent, seed, profile)`
- `validate_sample(sample, profile)`

Implemented in [src/intent2trajectory/generator.py](E:/CodeProject/UAV_Releated/intent2trajectory/src/intent2trajectory/generator.py).

## Config Overview

Primary config file:

- `configs/dataset_config.json`

Key top-level fields:

- `output_root`: dataset output directory
- `seed`: base seed for reproducible generation
- `max_resample_attempts`: retry limit when validation fails
- `dt`: sampling interval in seconds
- `max_time`: hard cap for one sample duration
- `class_quota`: per-intent sample count control
- `intent_profiles`: per-intent generation rules
- `constraints`: validation thresholds and space bounds
- `progress.enabled`: terminal progress visibility
- `failure_logging.include_failed_metadata`: preserve failed-sample metadata for later analysis

### Sample Count Control

You control how many samples are generated for each intent through `class_quota`:

```json
"class_quota": {
  "hover": 100,
  "straight_penetration": 100,
  "non_straight_penetration": 100,
  "loiter": 100,
  "retreat": 100
}
```

### Variant Control

`non_straight_penetration` and `loiter` use weighted variants.

`non_straight_penetration` variants:

- `weave_approach`
- `climb_then_dive`
- `turn_then_dive`
- `zigzag_dive`

`loiter` variants:

- `circle_hold`
- `ellipse_hold`
- `figure8_hold`
- `offset_orbit`

Each variant has a `weight` field that controls its relative sampling probability.

## Execution Route

Current complete execution route for the kinematic stage:

1. Edit `configs/dataset_config.json`
2. Run `generate_dataset(...)`
3. Generator samples trajectories by intent and variant
4. `validate_sample(...)` checks kinematic and semantic constraints
5. Accepted samples are written as CSV files under intent-specific folders
6. Each CSV row includes `intent`, `variant_name`, and `variant_summary`
7. Output filenames include the maneuver subtype for direct terminal browsing
8. `metadata.csv` records seed, variant, timing, attempt count, and failure reasons
9. Use the GUI player to inspect generated trajectories

For the original full project vision, the route is still incomplete because simulation and `.ulg` backfill are not implemented.

## Quick Start

Generate a dataset:

```powershell
python -c "import sys; sys.path.insert(0, 'src'); from intent2trajectory.generator import generate_dataset; print(generate_dataset('configs/dataset_config.json'))"
```

Outputs:

- class directories under `output_root` such as `0_hover`, `1_straight_penetration`, `2_non_straight_penetration`, `3_loiter`, `4_retreat`
- per-sample CSV with `intent`, `variant_name`, `variant_summary`, `ref_*`, and reserved `act_*` fields
- subtype-labeled filenames such as `loiter_circle_hold_0001_D1450_V10.csv`
- `metadata.csv` ledger with generated and failed sample records

## Metadata

`metadata.csv` includes sample-level fields such as:

- `sample_id`
- `intent`
- `variant_name`
- `variant_summary`
- `random_seed`
- `attempt_count`
- `start_x`, `start_y`, `start_z`
- `base_speed`
- `simulation_time`
- `yaw_policy`
- `noise_profile`
- `status`
- `failure_reason`

## Tests

Generator tests:

```powershell
pytest tests/test_generator.py -q
```

Visualization tests:

```powershell
pytest tests/test_visualization.py -q
```

Recommended full project test command for the current codebase:

```powershell
pytest tests -q
```

## GUI Trajectory Player

```powershell
python scripts/trajectory_player_gui.py --input-dir dataset_workspace
```

Features:

- choose input directory and refresh CSV list
- select one CSV and render a 3D trajectory
- real-time playback based on `time_relative` or `time`
- play / pause / reset and speed multiplier control
- position column priority: `act_pos_*` -> `ref_pos_*` -> `pos_*`

## Related Docs

- `docs/轨迹生成规则（intent2trajectory）.md`
- `docs/worklog/代码实现整理.md`
- `docs/worklog/2026-03-06-implementation-status.md`
- `docs/plan/2026-03-06-intent-trajectory-variants-design.md`

## Planned WSL Pipeline`r`n`r`n- `docs/plans/2026-03-06-wsl-px4-single-csv-pipeline-design.md``r`n- `docs/plans/2026-03-06-wsl-px4-single-csv-pipeline.md`

