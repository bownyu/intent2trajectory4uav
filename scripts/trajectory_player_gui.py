#!/usr/bin/env python
"""GUI player for 3D trajectory CSV files.

Usage:
    python scripts/trajectory_player_gui.py --input-dir dataset_workspace
"""

from __future__ import annotations

import argparse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
except Exception as exc:  # pragma: no cover
    raise SystemExit("matplotlib is required. Install it with: pip install matplotlib") from exc

import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from intent2trajectory.visualization import (
    compute_intervals_ms,
    list_csv_files,
    load_trajectory_csv,
    select_path_points,
)


class TrajectoryPlayerApp:
    def __init__(self, root: tk.Tk, input_dir: str):
        self.root = root
        self.root.title("CSV 3D Trajectory Player")
        self.root.geometry("1300x800")

        self.dir_var = tk.StringVar(value=input_dir)
        self.speed_var = tk.DoubleVar(value=1.0)
        self.show_full_path_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")

        self.file_paths: list[Path] = []
        self.data = None
        self.frame_index = 0
        self.intervals_ms: list[int] = [100]
        self.timer_id = None
        self.playing = False

        self._build_ui()
        self.refresh_file_list()

    def _build_ui(self):
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(top, text="Input Dir:").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.dir_var, width=80).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Browse", command=self.browse_dir).pack(side=tk.LEFT)
        ttk.Button(top, text="Refresh", command=self.refresh_file_list).pack(side=tk.LEFT, padx=6)

        body = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        left = ttk.Frame(body, width=340)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=4)

        ttk.Label(left, text="CSV Files").pack(anchor=tk.W)
        list_frame = ttk.Frame(left)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(list_frame, exportselection=False)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)

        control = ttk.Frame(left)
        control.pack(fill=tk.X, pady=8)
        ttk.Button(control, text="Load", command=self.load_selected).pack(side=tk.LEFT)
        ttk.Button(control, text="Play", command=self.play).pack(side=tk.LEFT, padx=4)
        ttk.Button(control, text="Pause", command=self.pause).pack(side=tk.LEFT)
        ttk.Button(control, text="Reset", command=self.reset).pack(side=tk.LEFT, padx=4)

        visibility = ttk.Frame(left)
        visibility.pack(fill=tk.X)
        ttk.Checkbutton(
            visibility,
            text="Show Full Path",
            variable=self.show_full_path_var,
            command=self._redraw_current_frame,
        ).pack(side=tk.LEFT)

        speed_box = ttk.Frame(left)
        speed_box.pack(fill=tk.X)
        ttk.Label(speed_box, text="Speed x").pack(side=tk.LEFT)
        self.speed_scale = ttk.Scale(speed_box, from_=0.1, to=5.0, variable=self.speed_var, orient=tk.HORIZONTAL)
        self.speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(speed_box, text="Apply", command=self._recompute_intervals).pack(side=tk.LEFT)

        self.info_label = ttk.Label(left, text="No file loaded", wraplength=300, justify=tk.LEFT)
        self.info_label.pack(fill=tk.X, pady=8)

        fig = Figure(figsize=(8, 6), dpi=100)
        self.ax = fig.add_subplot(111, projection="3d")
        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Y")
        self.ax.set_zlabel("Z")
        self.ax.grid(True)
        self.line, = self.ax.plot([], [], [], lw=2, color="tab:blue", label="trajectory")
        self.point, = self.ax.plot([], [], [], marker="o", color="tab:red", markersize=5, label="uav")
        self.ax.legend(loc="upper right")

        self.canvas = FigureCanvasTkAgg(fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas.draw_idle()

        bottom = ttk.Frame(self.root)
        bottom.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(bottom, textvariable=self.status_var).pack(side=tk.LEFT)

    def browse_dir(self):
        selected = filedialog.askdirectory(initialdir=self.dir_var.get() or str(ROOT))
        if selected:
            self.dir_var.set(selected)
            self.refresh_file_list()

    def refresh_file_list(self):
        self.file_paths = list_csv_files(self.dir_var.get())
        self.listbox.delete(0, tk.END)
        for p in self.file_paths:
            try:
                rel = p.relative_to(Path(self.dir_var.get()))
                label = str(rel)
            except Exception:
                label = str(p)
            self.listbox.insert(tk.END, label)

        self.status_var.set(f"Found {len(self.file_paths)} CSV files")

    def on_select(self, _event=None):
        idx = self._selected_index()
        if idx is not None:
            self.status_var.set(f"Selected: {self.file_paths[idx]}")

    def _selected_index(self):
        sel = self.listbox.curselection()
        if not sel:
            return None
        return int(sel[0])

    def load_selected(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showwarning("No selection", "Please select a CSV file first.")
            return

        path = self.file_paths[idx]
        try:
            self.data = load_trajectory_csv(str(path))
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc))
            return

        self.frame_index = 0
        self._recompute_intervals()
        self._draw_frame(0)

        cols = self.data["position_columns"]
        self.info_label.config(
            text=(
                f"File: {path}\n"
                f"Samples: {len(self.data['times'])}\n"
                f"Time column: {self.data['time_column']}\n"
                f"Position columns: {cols[0]}, {cols[1]}, {cols[2]}"
            )
        )
        self.status_var.set("Loaded")

    def _recompute_intervals(self):
        if not self.data:
            return
        self.intervals_ms = compute_intervals_ms(self.data["times"], speed=float(self.speed_var.get()))

    def play(self):
        if not self.data:
            messagebox.showwarning("No data", "Please load a CSV file first.")
            return
        if self.playing:
            return
        self.playing = True
        self._schedule_next()

    def pause(self):
        self.playing = False
        if self.timer_id is not None:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
        self.status_var.set("Paused")

    def reset(self):
        self.pause()
        if self.data:
            self.frame_index = 0
            self._draw_frame(0)
            self.status_var.set("Reset to start")

    def _schedule_next(self):
        if not self.playing or not self.data:
            return
        self._draw_frame(self.frame_index)
        self.frame_index += 1
        if self.frame_index >= len(self.data["times"]):
            self.playing = False
            self.timer_id = None
            self.status_var.set("Playback finished")
            return

        interval = self.intervals_ms[min(self.frame_index - 1, len(self.intervals_ms) - 1)]
        self.timer_id = self.root.after(interval, self._schedule_next)

    def _redraw_current_frame(self):
        if not self.data:
            return
        current_idx = self.frame_index - 1 if self.playing and self.frame_index > 0 else self.frame_index
        self._draw_frame(current_idx)

    def _draw_frame(self, idx: int):
        if not self.data:
            return
        xs = self.data["xs"]
        ys = self.data["ys"]
        zs = self.data["zs"]
        times = self.data["times"]

        idx = max(0, min(idx, len(times) - 1))
        line_xs, line_ys, line_zs = select_path_points(
            xs,
            ys,
            zs,
            idx=idx,
            show_full_path=self.show_full_path_var.get(),
        )
        self.line.set_data(line_xs, line_ys)
        self.line.set_3d_properties(line_zs)

        self.point.set_data([xs[idx]], [ys[idx]])
        self.point.set_3d_properties([zs[idx]])

        self._set_axes_equal(xs, ys, zs)
        self.canvas.draw_idle()

        self.status_var.set(
            f"t={times[idx]:.2f}s  frame={idx + 1}/{len(times)}  speed={float(self.speed_var.get()):.2f}x"
        )

    def _set_axes_equal(self, xs, ys, zs):
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        z_min, z_max = min(zs), max(zs)

        cx = 0.5 * (x_min + x_max)
        cy = 0.5 * (y_min + y_max)
        cz = 0.5 * (z_min + z_max)

        span = max(x_max - x_min, y_max - y_min, z_max - z_min)
        if span <= 0:
            span = 1.0
        half = 0.55 * span

        self.ax.set_xlim(cx - half, cx + half)
        self.ax.set_ylim(cy - half, cy + half)
        self.ax.set_zlim(max(0.0, cz - half), cz + half)


def parse_args():
    parser = argparse.ArgumentParser(description="3D CSV trajectory GUI player")
    parser.add_argument("--input-dir", default="dataset_workspace", help="Directory containing CSV files")
    return parser.parse_args()


def main():
    args = parse_args()
    root = tk.Tk()
    app = TrajectoryPlayerApp(root, input_dir=args.input_dir)
    root.mainloop()


if __name__ == "__main__":
    main()
