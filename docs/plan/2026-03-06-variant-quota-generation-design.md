# Variant Quota Generation Design

**Date:** 2026-03-06

**Goal:** Replace weighted random variant sampling with quota-driven generation, and tune generation plus validation so each configured variant can produce accepted samples.

## Problem

The current dataset generator treats `variants.weight` as a random sampling weight inside an intent. That means:

- weights do not guarantee output proportions
- fixed seeds can produce heavily skewed outputs
- validation can reject some variants systematically, collapsing the final dataset to one surviving variant

This is currently happening for `non_straight_penetration`, where the output is entirely `weave_approach`.

## Decisions

### Generation strategy

For intents that define `variants`, generation will be quota-driven instead of random:

- compute `target_quota = round(class_quota[intent] * weight / total_weight)` for each variant
- guarantee at least one quota slot for each positive-weight variant when the intent itself is requested
- accept small differences from the intent-level quota caused by rounding and minimum-slot protection
- expand generation work into `(intent, variant_name, target_quota)` tasks
- generate each variant directly until its target quota is satisfied or attempts are exhausted

If an intent has no `variants`, keep the current intent-level generation behavior.

### Generator interface

`generate_sample()` accepts an optional `variant_name`.

- when omitted, behavior stays backward compatible and may still use weighted random selection
- when provided, generation is forced to that variant

### Validation strategy

Keep shared intent-level physical checks:

- bounds
- speed
- acceleration
- yaw-rate
- closing/retreat intent semantics

Add variant-specific morphology checks for intents with multiple variants, especially `non_straight_penetration`, so variants are judged against their intended shape rather than a single shared profile.

### Metadata

Each metadata row exposes:

- `target_quota`
- `variant_attempt_count`

The dataset summary also exposes per-intent and per-variant generation counts.
