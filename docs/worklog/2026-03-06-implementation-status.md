# 2026-03-06 Implementation Status

## Current Scope

The repository still implements the kinematic `intent -> trajectory` stage only:

- five intent classes are generated from configuration;
- sample counts are controlled by `class_quota`;
- output remains unified CSV plus `metadata.csv`;
- GUI playback still works on the same CSV schema;
- `act_*` is still reserved for future simulation backfill.

The PX4 / JSBSim closed-loop simulation and `.ulg` backfill stages are not implemented yet.

## Completed in This Change

1. `non_straight_penetration` now supports config-driven weighted variants:
   - `weave_approach`
   - `climb_then_dive`
   - `turn_then_dive`
   - `zigzag_dive`
2. `loiter` now supports config-driven weighted variants:
   - `circle_hold`
   - `ellipse_hold`
   - `figure8_hold`
   - `offset_orbit`
3. Randomized geometry was expanded for key variants:
   - orbit size, axis lengths, phase, direction, and duration are randomized;
   - non-straight maneuver amplitude, period, climb ratio, turn radius, and zigzag segmentation are randomized.
4. Metadata now records:
   - `variant_name`
   - `variant_summary`
5. Validation was strengthened:
   - yaw stability uses unwrapped angles instead of linear std on wrapped angles;
   - non-straight samples are checked for path ratio, lateral deviation, and maneuver strength;
   - loiter samples are checked against a local orbit center, cumulative turning, and tangential motion.

## Configuration Control

Per-intent sample counts are still controlled in `configs/dataset_config.json` through `class_quota`.

Variant mixture inside `non_straight_penetration` and `loiter` is controlled by each variant's `weight` in the same config.

## Remaining Boundaries

- this is still a pure kinematic generator, not a flight-dynamics-validated dataset pipeline;
- some variant parameter ranges should still be visually spot-checked in the GUI to confirm that class differences are obvious enough for downstream training;
- future dataset statistics should include `variant_name` so the realized class mix can be compared against the configured weights.

## Planned WSL Single-CSV Pipeline`r`n`r`nThe approved design and implementation plan for the WSL-only single-CSV PX4 replay pipeline are saved in:`r`n`r`n- `docs/plans/2026-03-06-wsl-px4-single-csv-pipeline-design.md``r`n- `docs/plans/2026-03-06-wsl-px4-single-csv-pipeline.md`

