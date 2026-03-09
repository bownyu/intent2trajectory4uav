# Trajectory Full Path Visibility Design

**Date:** 2026-03-06

**Goal:** Add an option in the visualization GUI so users can switch between progressive trajectory drawing and always showing the full path while the UAV marker continues to move frame by frame.

## Context

The current GUI player in `scripts/trajectory_player_gui.py` always draws the trajectory line from the first sample to the current frame. This makes it impossible to inspect the complete route before playback reaches later segments.

## Decision

Add a checkbox control labeled `Show Full Path` in the left-side control area.

- Default state: off
- Off behavior: keep the existing progressive trajectory rendering
- On behavior: render the full trajectory line immediately
- UAV position marker: always stays tied to the current frame index
- Toggle behavior: redraw immediately without requiring file reload

## Scope

Included:
- GUI state for the new option
- Immediate redraw when the option changes
- Test coverage for line data selection behavior

Excluded:
- New playback modes beyond this boolean toggle
- Changes to timing, playback controls, file loading, or axis scaling

## Risks

- Tkinter variable callbacks can trigger before data is loaded; the redraw path must no-op safely when there is no active dataset.
- The current drawing logic is tightly coupled to matplotlib artist updates, so tests should isolate the path-selection behavior instead of depending on a live GUI.

## Test Strategy

- Add a focused unit test around the logic that chooses line coordinates for the current frame.
- Verify the existing default behavior remains progressive.
- Verify the new enabled mode returns the full trajectory.
