# Hover Variants Design

**Date:** 2026-03-06

**Goal:** Redesign the `hover` intent so it represents controlled position-holding behavior instead of a noisy random walk, using multiple small-scale correction variants with clear boundaries from `loiter`.

## Problem

The current `hover` generator is a Gaussian random walk around a center point. It satisfies low-speed constraints, but visually it looks disorderly and semantically weak. The resulting trajectories do not clearly express deliberate hovering behavior.

## Decision

Split `hover` into three flight-control-style variants:

- `steady_hold`: near-stationary hold with only very small perturbations
- `micro_orbit_hold`: tiny-radius circular or elliptical correction around a center point
- `sway_hold`: small back-and-forth correction along a short principal axis

## Boundary with other intents

`hover` must always remain a position-holding intent.

- small spatial envelope
- low speed
- end position remains close to hold center
- motion is correction-scale, not area-patrol scale

`loiter` remains the intent for active orbiting over a larger region. `hover` variants can contain structured motion, but only at a much smaller radius and speed.

## Variant semantics

### steady_hold

Represents the cleanest hovering case.

- center stays effectively fixed
- smallest displacement envelope
- lowest speed among hover variants
- heading can remain nearly fixed with only tiny noise

### micro_orbit_hold

Represents continuous fine correction around the hold point.

- circular or slightly elliptical motion around center
- very small orbit radius
- smooth continuous angular travel
- clearly smaller radius and duration signature than `loiter`

### sway_hold

Represents repeated short-axis correction.

- motion concentrated along one short axis
- visible direction reversals
- narrow secondary-axis spread
- total drift remains small

## Validation strategy

Use a shared hover envelope plus variant-specific checks.

Shared checks:
- low average speed
- bounded max displacement from hold center
- final position remains close to center

Variant-specific checks:
- `steady_hold`: very low spread and low radial variance
- `micro_orbit_hold`: cumulative angle travel lower bound and radius upper bound
- `sway_hold`: aspect-ratio threshold plus minimum reversal count

## Metadata

Each hover sample should record:
- `variant_name`
- key geometric parameters such as hold radius, sway amplitude, axis direction, or noise level

## Risks

- `micro_orbit_hold` can overlap with `loiter` if radius or angular travel are too large
- `sway_hold` can look too noisy if axis persistence is weak
- over-regularized trajectories may look synthetic if all variants are too perfect

## Test strategy

- add explicit tests for all three hover variants
- verify all hover variants pass validation
- verify hover remains separable from loiter by scale and turn behavior
- verify dataset generation can allocate quota across hover variants
