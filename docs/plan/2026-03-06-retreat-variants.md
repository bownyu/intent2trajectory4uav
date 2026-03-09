# Retreat Variants Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the single retreat path with multiple retreat variants and make the generator altitude-aware and duration-aware so retreat samples remain feasible and semantically distinct.

**Architecture:** Add retreat variants to the intent profile and route retreat generation through the same explicit-variant path used by other multi-variant intents. Generate each retreat path from reachable outward progress within `max_time`, then validate both shared retreat semantics and variant-specific geometry.

**Tech Stack:** Python, pytest, JSON config

---

### Task 1: Add failing tests for retreat variants

**Files:**
- Modify: `tests/test_generator.py`
- Test: `tests/test_generator.py`

**Step 1: Write the failing tests**

Add tests that:
- request each retreat variant explicitly
- verify variant names propagate into metadata
- verify dataset generation distributes quota across retreat variants

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_generator.py -k "retreat_variant" -v`
Expected: FAIL because retreat only supports a single default path today.

**Step 3: Write minimal implementation**

Introduce retreat variant config support and generator routing.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_generator.py -k "retreat_variant" -v`
Expected: PASS

### Task 2: Implement structured retreat generators

**Files:**
- Modify: `src/intent2trajectory/generator.py`
- Modify: `tests/test_generator.py`

**Step 1: Write the failing tests**

Add tests that lock intended retreat geometry:
- `direct_escape` has the smallest heading variation
- `arc_escape` has one-sided turning
- `zigzag_escape` has reversal structure
- `climb_escape` has clear altitude gain without leaving bounds

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_generator.py -k "direct_escape or arc_escape or zigzag_escape or climb_escape" -v`
Expected: FAIL because retreat is currently still a single outward line.

**Step 3: Write minimal implementation**

Implement four retreat path builders that use reachable progress rather than fixed duration targets.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_generator.py -k "direct_escape or arc_escape or zigzag_escape or climb_escape" -v`
Expected: PASS

### Task 3: Add retreat validation rules

**Files:**
- Modify: `src/intent2trajectory/generator.py`
- Modify: `tests/test_generator.py`

**Step 1: Write the failing tests**

Add tests that verify retreat stays outward-moving and that `climb_escape` remains inside altitude bounds.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_generator.py -k "retreat and altitude" -v`
Expected: FAIL until retreat validation checks shared semantics and variant morphology.

**Step 3: Write minimal implementation**

Add shared retreat checks plus variant-specific rules for heading variation, turn structure, zigzag changes, and climb gain.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_generator.py -k "retreat and altitude" -v`
Expected: PASS

### Task 4: Final verification

**Files:**
- Modify: none
- Test: `tests/test_generator.py`, `tests/test_visualization.py`

**Step 1: Run full generator tests**

Run: `pytest tests/test_generator.py -v`
Expected: PASS with 0 failures.

**Step 2: Run visualization regressions**

Run: `pytest tests/test_visualization.py -v`
Expected: PASS with 0 failures.

**Step 3: Review diff**

Run: `git diff -- src/intent2trajectory/generator.py tests/test_generator.py docs/plan/2026-03-06-retreat-variants-design.md docs/plan/2026-03-06-retreat-variants.md`
Expected: Only intended retreat generator, validation, tests, and docs changes.
