# Intent Trajectory Variants Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add config-driven maneuver variants for `non_straight_penetration` and `loiter`, strengthen intent validation, and preserve config-controlled class counts.

**Architecture:** Keep the public generator entrypoints unchanged while extending the intent profile schema to support weighted variants. Implement subtype-specific trajectory builders inside `src/intent2trajectory/generator.py`, record variant metadata, and validate generated paths using geometric and angle-aware measures instead of only coarse endpoint checks.

**Tech Stack:** Python, pytest, JSON configuration, CSV output

---

### Task 1: Document approved design and current project state

**Files:**
- Create: `docs/plan/2026-03-06-intent-trajectory-variants-design.md`
- Create: `docs/worklog/2026-03-06-工程现状与轨迹增强计划.md`

**Step 1: Write the design and status docs**

Capture the approved subtype strategy, config layout, validation goals, and current repository scope.

**Step 2: Verify docs exist**

Run: `Get-ChildItem docs/plan,docs/worklog`
Expected: both new markdown files are listed.

### Task 2: Add failing tests for yaw handling and variant-driven behavior

**Files:**
- Modify: `tests/test_generator.py`
- Test: `tests/test_generator.py`

**Step 1: Write the failing tests**

Add tests for:

- yaw dispersion handling across `-pi/pi`;
- non-straight metadata reporting a selected variant;
- non-straight variants producing stronger nonlinearity than a straight closing path;
- loiter variants reporting a selected subtype and maintaining orbit-like geometry.

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_generator.py -q`
Expected: FAIL because new metadata fields and validation logic do not exist yet.

### Task 3: Implement weighted variant selection and metadata

**Files:**
- Modify: `src/intent2trajectory/generator.py`
- Modify: `configs/dataset_config.json`

**Step 1: Add weighted variant selection helpers**

Implement helper functions to:

- choose a variant by weight;
- keep selection deterministic under the sample RNG;
- expose the chosen variant name and parameters in metadata.

**Step 2: Update non-straight and loiter generators**

Implement subtype-specific generation logic while preserving reproducibility and config-driven ranges.

**Step 3: Run focused tests**

Run: `pytest tests/test_generator.py -q`
Expected: some tests still fail until validation is upgraded.

### Task 4: Strengthen semantic validation

**Files:**
- Modify: `src/intent2trajectory/generator.py`
- Test: `tests/test_generator.py`

**Step 1: Replace linear yaw dispersion**

Add angle unwrapping or equivalent circular handling before computing yaw spread.

**Step 2: Add geometric validation for non-straight**

Check path-length ratio and lateral deviation, plus subtype-appropriate vertical or heading excursion.

**Step 3: Add orbit validation for loiter**

Check center stability, angular travel, tangential motion, and bounded radial variation.

**Step 4: Run focused tests**

Run: `pytest tests/test_generator.py -q`
Expected: PASS.

### Task 5: Update engineering status after implementation

**Files:**
- Modify: `docs/worklog/2026-03-06-工程现状与轨迹增强计划.md`

**Step 1: Record completed implementation scope**

Document what changed in generator behavior, config shape, tests, and remaining gaps.

### Task 6: Full verification

**Files:**
- Test: `tests/test_generator.py`
- Test: `tests/test_visualization.py`

**Step 1: Run generator tests**

Run: `pytest tests/test_generator.py -q`
Expected: PASS.

**Step 2: Run visualization tests**

Run: `pytest tests/test_visualization.py -q`
Expected: PASS.

**Step 3: Run full test suite**

Run: `pytest -q`
Expected: PASS.
