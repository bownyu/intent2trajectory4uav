# Hover Variants Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current noisy single-mode hover generator with three structured hover variants that better represent controlled position holding.

**Architecture:** Add hover variants in the intent profile and allow `generate_sample()` / dataset generation to request them explicitly, consistent with the new variant-quota flow already used elsewhere. Keep a shared hover envelope in validation, then add variant-specific morphology checks for `steady_hold`, `micro_orbit_hold`, and `sway_hold`.

**Tech Stack:** Python, pytest, JSON config

---

### Task 1: Add failing tests for hover variants

**Files:**
- Modify: `tests/test_generator.py`
- Test: `tests/test_generator.py`

**Step 1: Write the failing tests**

Add tests that:
- request each hover variant explicitly
- assert each variant name is preserved in metadata
- assert each hover variant passes validation
- assert hover dataset generation distributes quota across hover variants

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_generator.py -k "hover_variant" -v`
Expected: FAIL because hover only supports `default_hover` today.

**Step 3: Write minimal implementation**

Introduce the hover variant config and generator hooks needed for explicit hover variant generation.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_generator.py -k "hover_variant" -v`
Expected: PASS

### Task 2: Implement structured hover generators

**Files:**
- Modify: `src/intent2trajectory/generator.py`
- Modify: `tests/test_generator.py`

**Step 1: Write the failing test**

Add tests that lock the intended geometry:
- `steady_hold` has the smallest spread
- `micro_orbit_hold` shows bounded angular travel around a center
- `sway_hold` shows repeated reversals on a dominant axis

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_generator.py -k "steady_hold or micro_orbit_hold or sway_hold" -v`
Expected: FAIL because current hover is an undirected random walk.

**Step 3: Write minimal implementation**

Implement three small-scale hover path builders and metadata capture for each variant.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_generator.py -k "steady_hold or micro_orbit_hold or sway_hold" -v`
Expected: PASS

### Task 3: Add hover validation rules

**Files:**
- Modify: `src/intent2trajectory/generator.py`
- Modify: `tests/test_generator.py`

**Step 1: Write the failing test**

Add tests that verify hover remains separable from loiter by scale and correction semantics.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_generator.py -k "hover and loiter" -v`
Expected: FAIL until validation distinguishes hover variants properly.

**Step 3: Write minimal implementation**

Add shared hover limits plus variant-specific checks for spread, angular travel, and reversal structure.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_generator.py -k "hover and loiter" -v`
Expected: PASS

### Task 4: Final verification

**Files:**
- Modify: none
- Test: `tests/test_generator.py`, `tests/test_visualization.py`

**Step 1: Run the full generator test suite**

Run: `pytest tests/test_generator.py -v`
Expected: PASS with 0 failures.

**Step 2: Run visualization regression tests**

Run: `pytest tests/test_visualization.py -v`
Expected: PASS with 0 failures.

**Step 3: Review diff**

Run: `git diff -- src/intent2trajectory/generator.py tests/test_generator.py docs/plan/2026-03-06-hover-variants-design.md docs/plan/2026-03-06-hover-variants.md`
Expected: Only intended hover variant generator, validation, tests, and docs changes.
