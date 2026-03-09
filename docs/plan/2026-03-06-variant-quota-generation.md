# Variant Quota Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make dataset generation quota-driven per variant, and tune generation plus validation so each configured trajectory variant can be generated and accepted.

**Architecture:** Move variant distribution logic to a deterministic planning step in `generate_dataset()`, then pass explicit variant targets into `generate_sample()`. Keep intent-level validation, but add variant-specific morphology checks so non-straight and loiter trajectories are judged against their actual geometric family.

**Tech Stack:** Python, pytest, JSON config

---

### Task 1: Lock quota behavior with failing tests

**Files:**
- Modify: `tests/test_generator.py`
- Test: `tests/test_generator.py`

**Step 1: Write the failing tests**

Add tests for:
- quota calculation from weights
- explicit variant generation
- multi-variant dataset generation by target quota

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_generator.py -k "quota or requested_variant or non_straight_variants_can_validate or uses_variant_quotas" -v`
Expected: FAIL because quota helpers and variant-directed generation do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- `compute_variant_quotas()`
- task expansion per variant
- optional `variant_name` input to `generate_sample()`

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_generator.py -k "quota or requested_variant or non_straight_variants_can_validate or uses_variant_quotas" -v`
Expected: PASS

### Task 2: Tune generation and validation

**Files:**
- Modify: `src/intent2trajectory/generator.py`
- Modify: `tests/test_generator.py`

**Step 1: Write the failing test**

Add a test showing each configured non-straight variant can generate a valid sample.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_generator.py -k "non_straight_variants_can_validate" -v`
Expected: FAIL because some variants are rejected by current generation or validation rules.

**Step 3: Write minimal implementation**

Tune the affected non-straight generators so they do not try to traverse impossible full distances within `max_time`, and make validation branch by `variant_name`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_generator.py -k "non_straight_variants_can_validate" -v`
Expected: PASS

### Task 3: Final verification

**Files:**
- Modify: none
- Test: `tests/test_generator.py`, `tests/test_visualization.py`

**Step 1: Run the full generator test suite**

Run: `pytest tests/test_generator.py -v`
Expected: PASS with 0 failures.

**Step 2: Run the visualization regression suite**

Run: `pytest tests/test_visualization.py -v`
Expected: PASS with 0 failures.

**Step 3: Review diff**

Run: `git diff -- src/intent2trajectory/generator.py tests/test_generator.py docs/plan/2026-03-06-variant-quota-generation-design.md docs/plan/2026-03-06-variant-quota-generation.md`
Expected: Only intended generator, validation, tests, and docs changes.
