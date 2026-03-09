# Retreat Variants Design

**Date:** 2026-03-06

**Goal:** Replace the single straight-line retreat generator with several semantically distinct retreat variants that all preserve a strong outward-escape trend while staying physically feasible within time and altitude limits.

## Problem

The current `retreat` generator only produces a noisy outward line. This is too narrow semantically, and many failures are caused by generated trajectories exceeding altitude constraints instead of being shaped around feasibility from the start.

## Decision

Split `retreat` into four moderate-intensity variants:

- `direct_escape`
- `arc_escape`
- `zigzag_escape`
- `climb_escape`

All variants must keep the core retreat meaning: distance from the origin grows substantially over time.

## Shared generation principles

- do not force a fixed total duration
- derive sample length from the chosen speed, `dt`, `max_time`, and reachable progress
- shape trajectories within feasible travel distance rather than forcing an unreachable endpoint
- constrain altitude during generation, especially for `climb_escape`, instead of relying on validation failure

## Variant semantics

### direct_escape

A clean outward departure.

- fastest to understand
- smallest heading variation
- acts as the baseline retreat pattern

### arc_escape

A one-sided curved departure.

- continuous lateral bias while moving outward
- no repeated switching like zigzag
- reads as evasive but still controlled

### zigzag_escape

A limited evasive withdrawal.

- multiple lateral direction changes
- outward trend remains dominant
- lower maneuver intensity than attack-side zigzag trajectories

### climb_escape

An outward withdrawal with meaningful altitude gain.

- distance increases substantially
- altitude rises clearly but remains within `space.z`
- reads as disengagement from a threat envelope rather than an attack dive/climb profile

## Boundary with other intents

- unlike penetration intents, retreat cannot end closer to the origin than it began
- unlike loiter, retreat cannot circle around a center for repeated area holding
- unlike hover, retreat must show sustained translational escape

## Validation strategy

Shared checks:
- final distance exceeds initial distance by a configured factor
- overall distance trend is increasing, allowing only small local fluctuations
- speed, acceleration, yaw-rate, and space bounds all remain valid

Variant-specific checks:
- `direct_escape`: heading variation upper bound
- `arc_escape`: cumulative turn lower bound, reversal count upper bound
- `zigzag_escape`: lateral sign-change lower bound
- `climb_escape`: altitude gain lower bound

## Risks

- `arc_escape` and `zigzag_escape` can drift toward attack-like motion if lateral amplitude is too large
- `climb_escape` can still fail if altitude planning ignores remaining headroom
- overly strict monotonic-distance rules may reject realistic small oscillations during evasive withdrawal

## Test strategy

- add tests for explicit retreat variant generation
- verify all retreat variants pass validation under a balanced profile
- verify dataset generation distributes quota across retreat variants
- verify `climb_escape` respects altitude limits under constrained `space.z`
