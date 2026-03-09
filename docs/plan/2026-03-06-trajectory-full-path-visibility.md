# Trajectory Full Path Visibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a GUI toggle that lets the trajectory player show the full path immediately while keeping the UAV marker synchronized to the current playback frame.

**Architecture:** Keep the change local to `scripts/trajectory_player_gui.py`. Extract a small helper that computes the line segment to render for a given frame and mode, then use that helper from `_draw_frame()` and cover it with targeted unit tests.

**Tech Stack:** Python, Tkinter, matplotlib, pytest

---

### Task 1: Add regression tests for trajectory line selection

**Files:**
- Modify: `tests/test_visualization.py`
- Test: `tests/test_visualization.py`

**Step 1: Write the failing test**

```python
def test_select_path_points_progressive_mode_returns_points_up_to_frame():
    xs = [0.0, 1.0, 2.0]
    ys = [10.0, 11.0, 12.0]
    zs = [20.0, 21.0, 22.0]

    line_xs, line_ys, line_zs = select_path_points(xs, ys, zs, idx=1, show_full_path=False)

    assert line_xs == [0.0, 1.0]
    assert line_ys == [10.0, 11.0]
    assert line_zs == [20.0, 21.0]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_visualization.py -k path_points -v`
Expected: FAIL because `select_path_points` does not exist yet.

**Step 3: Write the second failing test for full-path mode**

```python
def test_select_path_points_full_mode_returns_entire_path():
    xs = [0.0, 1.0, 2.0]
    ys = [10.0, 11.0, 12.0]
    zs = [20.0, 21.0, 22.0]

    line_xs, line_ys, line_zs = select_path_points(xs, ys, zs, idx=1, show_full_path=True)

    assert line_xs == xs
    assert line_ys == ys
    assert line_zs == zs
```

**Step 4: Run test to verify it fails**

Run: `pytest tests/test_visualization.py -k path_points -v`
Expected: FAIL because the helper is still missing.

**Step 5: Commit**

```bash
git add tests/test_visualization.py
git commit -m "test: add path visibility regression coverage"
```

### Task 2: Implement the path-selection helper and export it

**Files:**
- Modify: `scripts/trajectory_player_gui.py`
- Modify: `src/intent2trajectory/__init__.py` only if export becomes useful elsewhere
- Test: `tests/test_visualization.py`

**Step 1: Write the minimal implementation**

```python
def select_path_points(xs, ys, zs, idx, show_full_path):
    end = len(xs) if show_full_path else idx + 1
    return xs[:end], ys[:end], zs[:end]
```

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_visualization.py -k path_points -v`
Expected: PASS

**Step 3: Refine helper placement if needed**

Keep the helper near the GUI code unless a cleaner shared module is obviously better. Do not generalize beyond this use case.

**Step 4: Run focused tests again**

Run: `pytest tests/test_visualization.py -k path_points -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/trajectory_player_gui.py tests/test_visualization.py
git commit -m "feat: add selectable full-path rendering"
```

### Task 3: Wire the GUI toggle into rendering

**Files:**
- Modify: `scripts/trajectory_player_gui.py`
- Test: `tests/test_visualization.py`

**Step 1: Add a failing UI-behavior test if practical**

Prefer a small method-level test instead of a Tk root integration test. If GUI-level testing is too brittle in this repo, keep coverage at the helper level and document that choice in the final summary.

**Step 2: Add the checkbox state**

```python
self.show_full_path_var = tk.BooleanVar(value=False)
```

**Step 3: Add the checkbox widget and redraw callback**

```python
ttk.Checkbutton(
    control,
    text="Show Full Path",
    variable=self.show_full_path_var,
    command=self._redraw_current_frame,
)
```

**Step 4: Update `_draw_frame()` to use the helper**

```python
line_xs, line_ys, line_zs = select_path_points(
    xs, ys, zs, idx=idx, show_full_path=self.show_full_path_var.get()
)
self.line.set_data(line_xs, line_ys)
self.line.set_3d_properties(line_zs)
```

**Step 5: Add `_redraw_current_frame()`**

```python
def _redraw_current_frame(self):
    if self.data:
        self._draw_frame(self.frame_index if self.playing else max(self.frame_index, 0))
```
```

Adjust the exact frame selection so it redraws the currently visible state, especially after load/reset.

**Step 6: Run focused tests**

Run: `pytest tests/test_visualization.py -k path_points -v`
Expected: PASS

**Step 7: Run broader verification**

Run: `pytest tests/test_visualization.py -v`
Expected: PASS

**Step 8: Commit**

```bash
git add scripts/trajectory_player_gui.py tests/test_visualization.py
git commit -m "feat: add GUI full-path visibility toggle"
```

### Task 4: Final verification

**Files:**
- Modify: none
- Test: `tests/test_visualization.py`

**Step 1: Run the complete relevant test file**

Run: `pytest tests/test_visualization.py -v`
Expected: PASS with 0 failures.

**Step 2: Smoke-check the script help output**

Run: `python scripts/trajectory_player_gui.py --help`
Expected: Exit 0 and show CLI usage.

**Step 3: Review diff before reporting completion**

Run: `git diff -- scripts/trajectory_player_gui.py tests/test_visualization.py docs/plan/2026-03-06-trajectory-full-path-visibility-design.md docs/plan/2026-03-06-trajectory-full-path-visibility.md`
Expected: Only the intended GUI toggle, helper, tests, and docs changes appear.
