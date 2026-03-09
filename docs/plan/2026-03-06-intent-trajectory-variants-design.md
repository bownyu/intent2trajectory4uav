# Intent Trajectory Variants Design

**Date:** 2026-03-06

## Goal

Upgrade the kinematic intent-to-trajectory generator so that:

- `non_straight_penetration` produces clearly different maneuver families instead of a single spiral-like approach.
- `loiter` represents broader holding and circling behavior with stronger spatial diversity.
- validation rules check semantic intent quality rather than only coarse start/end distance conditions.
- sample counts remain explicitly controlled from configuration.

## Current Project Status

The current repository implements the kinematic generation stage only:

- five intent classes are generated from configuration;
- output is written as CSV plus `metadata.csv`;
- `act_*` columns are placeholders for future simulation backfill;
- GUI playback exists for trajectory inspection.

The PX4/JSBSim closed-loop simulation stage described in the original target document is not implemented yet. This design only upgrades the current kinematic generator.

## Confirmed Constraints

- generation count per intent remains controlled by `class_quota` in `configs/dataset_config.json`;
- diversity must be configuration-driven, not hidden entirely inside code;
- circular, elliptical, figure-8, and similar fixed-shape trajectories still need randomized size, phase, direction, and duration;
- new behavior must remain reproducible under the same seed and config;
- validation must become stricter for key intents.

## Variant Strategy

### Non-Straight Penetration

Use weighted subtypes under `intent_profiles.non_straight_penetration.variants`:

1. `weave_approach`
   Horizontal weaving while closing on the target.
2. `climb_then_dive`
   Initial climb segment followed by a committed dive toward the target.
3. `turn_then_dive`
   A visible turning arc before diving toward the target.
4. `zigzag_dive`
   Multi-segment heading changes followed by continued closing behavior.

Each subtype will carry its own parameter ranges and weight. Shared spawn settings such as `start_radius`, `start_z`, and `target_radius` remain at the intent level.

### Loiter

Use weighted subtypes under `intent_profiles.loiter.variants`:

1. `circle_hold`
   Randomized circular orbit.
2. `ellipse_hold`
   Randomized ellipse with different major/minor axes.
3. `figure8_hold`
   Figure-8 hold pattern.
4. `offset_orbit`
   Orbit around an offset local center with controlled radial variation relative to the origin.

Each subtype will randomize its geometry:

- orbit size or axes;
- phase offset;
- clockwise/counterclockwise direction;
- duration or loop count;
- optional mild altitude undulation where appropriate.

## Configuration Design

Keep per-intent generation count in `class_quota`.

Add weighted variants like:

```json
"non_straight_penetration": {
  "start_radius": [3000, 5000],
  "start_z": [100, 500],
  "target_radius": 100,
  "variants": {
    "weave_approach": {
      "weight": 0.35,
      "base_speed": [10, 13],
      "lateral_amplitude": [80, 260],
      "lateral_period": [15, 45],
      "vertical_amplitude": [10, 80]
    },
    "climb_then_dive": {
      "weight": 0.25,
      "base_speed": [10, 13],
      "climb_ratio": [0.2, 0.4],
      "climb_angle_deg": [8, 20],
      "dive_angle_deg": [15, 35]
    }
  }
}
```

Equivalent structure applies to `loiter`.

## Validation Design

### Yaw Statistics

Replace plain standard deviation of wrapped yaw values with angle unwrapping before dispersion checks. This avoids false instability around the `-pi/pi` boundary.

### Non-Straight Penetration

The sample must still close on the target, but also satisfy semantic nonlinearity checks such as:

- minimum path-length to displacement ratio;
- minimum lateral deviation from the straight start-to-end line;
- either meaningful altitude excursion or heading excursion depending on subtype.

Validation will treat subtype-specific maneuvers as first-class signals rather than relying only on yaw variance.

### Loiter

Validation will check:

- estimated local center stability;
- radius or axis stability around that center;
- sufficient cumulative angular travel or loop completion;
- sustained tangential movement.

This prevents short arcs or drift paths from being accepted as loiter.

## Metadata Changes

Add variant information to sample metadata:

- `variant_name`
- key randomized maneuver parameters summary

This improves inspection and later debugging.

## Testing Plan

Add tests for:

- weighted variant selection reproducibility;
- non-straight samples showing geometric deviation beyond straight-line behavior;
- loiter variants satisfying orbit-like properties;
- yaw dispersion checks remaining stable across the angle wrap boundary;
- dataset generation preserving configurable class counts.

## Implementation Notes

- Keep generator changes localized to `src/intent2trajectory/generator.py`.
- Expand tests in `tests/test_generator.py`.
- Update `configs/dataset_config.json` to demonstrate the new config shape.
- Write an updated engineering status document in `docs`.
