#!/usr/bin/env python3
"""
Interactive keyframe-trajectory viewer for DROID-W outputs.

Layout:
  ┌─────────────────────────────────┐
  │     Keyframe Visualization      │  ← top (plots_final/video_kf_*.png)
  ├─────────────────────────────────┤
  │     Trajectory Plot             │  ← middle (full est + aligned GT, kf colored by ATE)
  ├─────────────────────────────────┤
  │  [═══════o═══════]  N / M      │  ← bottom (slider)

Alignment follows the same SE(3) Umeyama approach as eval_traj.py (evo library).

Usage:
  python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown1/20260505_063040
  python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown1/20260505_063040 --mode input_images
  python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown1/20260505_063040 --traj-only

Keyboard:
  ← →  navigate frames
  Home/End  jump to first/last
"""

import argparse
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Slider
from PIL import Image


# ── Data loading & trajectory alignment ───────────────────────────────────

def load_tum_xyz(path):
    """Load TUM-format trajectory as (N, 3) XYZ array (skipping rotation)."""
    xyz = []
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 8:
                continue
            xyz.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return np.array(xyz)


def parse_metrics_full_traj(metrics_path):
    """Parse metrics_full_traj.txt → (s, R, t) or None."""
    if not metrics_path.exists():
        return None
    lines = metrics_path.read_text().splitlines()
    s = None
    R_rows = []
    t = None
    in_rotation = False
    for line in lines:
        if line.startswith("scale:"):
            s = float(line.split(":")[1].strip())
        elif line.startswith("rotation:"):
            in_rotation = True
            continue
        elif line.startswith("translation:"):
            in_rotation = False
            t = np.array([float(x) for x in line.split(":")[1].strip().strip("[]").split()])
        elif in_rotation:
            # Matrix row line like " [ 0.05  0.05 -0.99]"
            row = line.strip().strip("[]")
            if row:
                R_rows.append([float(x) for x in row.split()])
    if s is not None and len(R_rows) == 3 and t is not None:
        return s, np.array(R_rows), t
    return None


def align_trajectories(run_dir, est_xyz, gt_xyz):
    """Align estimated trajectory to GT using evo (same approach as eval_traj.py).

    Prefers precomputed alignment from metrics_full_traj.txt; falls back to
    computing it directly with evo.

    Returns:
        est_aligned_xy: (N, 2) aligned estimated 2D positions
        gt_xy: (N, 2) GT 2D positions
        ate_per_frame: (N,) per-frame ATE values (meters)
    """
    n = min(len(est_xyz), len(gt_xyz))

    # ── Try precomputed alignment first ──
    metrics_path = run_dir / "traj" / "metrics_full_traj.txt"
    precomputed = parse_metrics_full_traj(metrics_path)

    if precomputed is not None:
        s, R, t = precomputed
        est_aligned = s * (est_xyz[:n] @ R.T) + t
        gt = gt_xyz[:n]
        ate = np.linalg.norm(est_aligned - gt, axis=1)
        return est_aligned[:, :2], gt[:, :2], ate

    # ── Fallback: compute alignment via evo ──
    from evo.core.trajectory import PoseTrajectory3D
    from evo.core import sync
    from evo.core import lie_algebra as lie

    timestamps = [float(i) for i in range(n)]
    traj_est = PoseTrajectory3D(positions_xyz=est_xyz[:n], timestamps=timestamps)
    traj_ref = PoseTrajectory3D(positions_xyz=gt_xyz[:n], timestamps=timestamps)

    traj_ref_sync, traj_est_sync = sync.associate_trajectories(traj_ref, traj_est)
    r_a, t_a, s = traj_est_sync.align(traj_ref_sync, correct_scale=True)

    # Apply manually (avoid evo scale/transform internal quirks)
    est_pos = traj_est_sync.positions_xyz
    est_aligned = s * (est_pos @ r_a.T) + t_a
    gt_pos = traj_ref_sync.positions_xyz
    ate = np.linalg.norm(est_aligned - gt_pos, axis=1)

    return est_aligned[:, :2], gt_pos[:, :2], ate


# ── File discovery ────────────────────────────────────────────────────────

def find_keyframe_files(plots_dir, mode="main"):
    mode_map = {
        "main": ("", "video_kf_{kf:03d}_ts_{ts:05d}.png"),
        "input_images": ("input_images", "input_kf_{kf:03d}_ts_{ts:05d}.png"),
        "high_res_uncertainty": (
            "high_res_uncertainty",
            "high_res_uncertainty_kf_{kf:03d}_ts_{ts:05d}.png",
        ),
        "scaled_uncertainty": (
            "scaled_uncertainty",
            "uncertainty_kf_{kf:03d}_ts_{ts:05d}.png",
        ),
        "uncertainty_contours": (
            "uncertainty_contours",
            "uncertainty_contour_kf_{kf:03d}_ts_{ts:05d}.png",
        ),
    }

    subdir, pattern = mode_map.get(mode, mode_map["main"])
    search_dir = Path(plots_dir) / subdir if subdir else Path(plots_dir)

    files = []
    name_re = re.compile(
        pattern.replace("{kf:03d}", r"(\d+)").replace("{ts:05d}", r"(\d+)")
    )

    for p in sorted(search_dir.glob("*.png")):
        m = name_re.match(p.name)
        if m:
            files.append((int(m.group(1)), int(m.group(2)), p))

    files.sort(key=lambda x: x[0])
    return files


# ── UI ────────────────────────────────────────────────────────────────────

def build_ui(kf_files, est_2d, gt_2d, ate_per_frame, mode_name, traj_only=False):
    n_kf = len(kf_files)
    if n_kf == 0:
        print("No keyframe files found.")
        sys.exit(1)

    n_est = len(est_2d)
    has_gt = gt_2d is not None

    # Per-keyframe ATE in cm: lookup by ts (frame index)
    kf_ate = np.array([
        ate_per_frame[f[1]] * 100 if f[1] < len(ate_per_frame) else 0.0
        for f in kf_files
    ])

    # ── figure layout ──
    if traj_only:
        fig = plt.figure(figsize=(14, 14))
        gs = fig.add_gridspec(
            2, 1,
            height_ratios=[20, 0.7],
            hspace=0.08,
            top=0.98, bottom=0.04, left=0.07, right=0.96,
        )
        ax_traj = fig.add_subplot(gs[0])
        ax_slider = fig.add_subplot(gs[1])
        ax_img = None
        im_handle = None
        title = None
    else:
        fig = plt.figure(figsize=(18, 12))
        gs = fig.add_gridspec(
            3, 1,
            height_ratios=[4, 3, 0.3],
            hspace=0.35,
            top=0.97, bottom=0.06, left=0.05, right=0.98,
        )
        ax_img = fig.add_subplot(gs[0])
        ax_traj = fig.add_subplot(gs[1])
        ax_slider = fig.add_subplot(gs[2])

    # ── top: keyframe image ──
    kf_idx_init, ts_init, path_init = kf_files[0]
    if ax_img is not None:
        pil_img = Image.open(path_init)
        im_handle = ax_img.imshow(pil_img)
        ax_img.axis("off")
        title = ax_img.set_title(
            f"[{mode_name}]  Keyframe {kf_idx_init} / {n_kf - 1}  |  ts = {ts_init}",
            fontsize=11, family="monospace",
        )
    else:
        im_handle = None
        title = None

    # ── middle: trajectory ──
    # Full estimated trajectory
    ax_traj.plot(est_2d[:, 0], est_2d[:, 1], "-", color="#4a90d9",
                 linewidth=1.2, alpha=0.85, label="Est (all frames)")

    # Aligned GT
    if has_gt:
        ax_traj.plot(gt_2d[:, 0], gt_2d[:, 1], "--", color="#2ca02c",
                     linewidth=1.2, alpha=0.85, label="GT")

    # Keyframe positions color-coded by ATE
    kf_xy = np.array([
        (est_2d[f[1], 0], est_2d[f[1], 1]) if f[1] < n_est else (np.nan, np.nan)
        for f in kf_files
    ])
    valid_kf = np.all(np.isfinite(kf_xy), axis=1)

    # Map scatter index → kf_files index (valid_kf drops NaN positions)
    scatter_to_kf = np.where(valid_kf)[0]

    if has_gt:
        sc = ax_traj.scatter(
            kf_xy[valid_kf, 0], kf_xy[valid_kf, 1],
            c=kf_ate[valid_kf], s=28, cmap="hot_r",
            edgecolors="black", linewidth=0.3,
            zorder=3, label="Keyframes", picker=True, pickradius=5,
        )
        cbar = plt.colorbar(sc, ax=ax_traj, shrink=0.85, pad=0.02)
        cbar.set_label("ATE (cm)", fontsize=8)
    else:
        sc = ax_traj.scatter(
            kf_xy[valid_kf, 0], kf_xy[valid_kf, 1],
            c="gray", s=24, edgecolors="black", linewidth=0.3,
            zorder=3, label="Keyframes", picker=True, pickradius=5,
        )

    # Current position marker
    first_pos = kf_xy[0]
    (marker,) = ax_traj.plot(
        first_pos[0], first_pos[1], "o", color="cyan", markersize=12,
        markeredgecolor="black", markeredgewidth=1.5, zorder=5,
    )
    marker_label = ax_traj.annotate(
        f"kf {kf_idx_init}", xy=first_pos, xytext=(10, 10),
        textcoords="offset points", fontsize=8,
        color="#0077b6", fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.85),
    )

    ax_traj.legend(loc="upper right", fontsize=8, markerscale=1.5)
    ax_traj.set_aspect("equal")
    ax_traj.set_title("Trajectory  (← → keys / click keyframes to navigate)", fontsize=10, family="monospace")
    ax_traj.set_xlabel("x (m)")
    ax_traj.set_ylabel("y (m)")
    ax_traj.grid(True, alpha=0.3)

    # ── bottom: slider ──
    slider = Slider(
        ax_slider, "Keyframe",
        valmin=0, valmax=n_kf - 1,
        valinit=0, valstep=1,
        color="#4a90d9",
    )
    slider.valtext.set_text(f"0 / {n_kf - 1}")

    # ── callbacks ──
    def update(val):
        idx = int(slider.val)
        kf_i, t_s, p = kf_files[idx]

        if traj_only:
            slider.valtext.set_text(f"{idx} / {n_kf - 1}")
            ate_str = f"  ATE={kf_ate[idx]:.1f}cm" if has_gt else ""
            fig.suptitle(
                f"[{mode_name}]  Keyframe {kf_i} / {n_kf - 1}  |  ts = {t_s}{ate_str}",
                fontsize=11, family="monospace",
            )
        else:
            img = Image.open(p)
            im_handle.set_data(img)
            ate_str = f"  |  ATE = {kf_ate[idx]:.1f} cm" if has_gt else ""
            title.set_text(
                f"[{mode_name}]  Keyframe {kf_i} / {n_kf - 1}  |  ts = {t_s}{ate_str}"
            )
            slider.valtext.set_text(f"{idx} / {n_kf - 1}")

        if t_s < n_est:
            pos = est_2d[t_s]
            marker.set_data([pos[0]], [pos[1]])
            marker_label.set_position(pos)
            label_text = f"kf {kf_i}\nATE={kf_ate[idx]:.1f}cm" if has_gt else f"kf {kf_i}"
            marker_label.set_text(label_text)

        fig.canvas.draw_idle()

    slider.on_changed(update)

    def on_key(event):
        if event.key in ("right", "up"):
            slider.set_val(min(slider.val + 1, n_kf - 1))
        elif event.key in ("left", "down"):
            slider.set_val(max(slider.val - 1, 0))
        elif event.key == "home":
            slider.set_val(0)
        elif event.key == "end":
            slider.set_val(n_kf - 1)

    fig.canvas.mpl_connect("key_press_event", on_key)

    def on_pick(event):
        ind = event.ind[0]  # first picked point index
        kf_idx = scatter_to_kf[ind]  # map to kf_files index
        slider.set_val(kf_idx)

    fig.canvas.mpl_connect("pick_event", on_pick)

    return fig, slider


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Interactive keyframe + trajectory viewer for DROID-W outputs",
    )
    parser.add_argument(
        "run_dir",
        nargs="?",
        default="Outputs/DROID-W/downtown1/20260505_063040",
        help="Path to run directory (e.g. Outputs/DROID-W/downtown1/20260505_063040)",
    )
    parser.add_argument(
        "--mode",
        default="main",
        choices=[
            "main", "input_images", "high_res_uncertainty",
            "scaled_uncertainty", "uncertainty_contours",
        ],
        help="Which plots_final subdirectory to display (default: main)",
    )
    parser.add_argument(
        "--traj-only", action="store_true",
        help="Show only the trajectory plot (hide keyframe image for more plot area)",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"Run directory not found: {run_dir}")
        sys.exit(1)

    plots_dir = run_dir / "plots_final"
    est_poses_file = run_dir / "traj" / "est_poses_full.txt"
    gt_poses_file = run_dir / "gt_poses.txt"

    # ── load data ──
    kf_files = find_keyframe_files(plots_dir, args.mode)
    if not kf_files:
        print(f"No keyframe files found in {plots_dir} (mode={args.mode})")
        sys.exit(1)

    est_xyz = load_tum_xyz(est_poses_file) if est_poses_file.exists() else np.empty((0, 3))
    gt_xyz = load_tum_xyz(gt_poses_file) if gt_poses_file.exists() else np.empty((0, 3))

    print(f"Run dir:       {run_dir}")
    print(f"Mode:          {args.mode}")
    print(f"Keyframes:     {len(kf_files)}")
    print(f"Est poses:     {len(est_xyz)} frames")
    print(f"GT poses:      {len(gt_xyz)} frames")
    print(f"First kf:      idx={kf_files[0][0]}, ts={kf_files[0][1]}")
    print(f"Last kf:       idx={kf_files[-1][0]}, ts={kf_files[-1][1]}")

    # ── align trajectories ──
    if len(est_xyz) > 0 and len(gt_xyz) > 0:
        est_2d, gt_2d, ate = align_trajectories(run_dir, est_xyz, gt_xyz)
        print(f"ATE (aligned): mean={np.mean(ate):.3f}m, "
              f"median={np.median(ate):.3f}m, "
              f"max={np.max(ate):.3f}m, "
              f"rmse={np.sqrt(np.mean(ate**2)):.3f}m")
    else:
        est_2d = est_xyz[:, :2]
        gt_2d = None
        ate = np.zeros(len(est_2d))

    mode_names = {
        "main": "plots_final",
        "input_images": "input_images",
        "high_res_uncertainty": "high_res_uncertainty",
        "scaled_uncertainty": "scaled_uncertainty",
        "uncertainty_contours": "uncertainty_contours",
    }

    fig, slider = build_ui(kf_files, est_2d, gt_2d, ate, mode_names[args.mode],
                            traj_only=args.traj_only)

    print("\nControls:")
    print("  ← →        navigate frames")
    print("  Home/End   jump to first/last frame")
    print("  Mouse      drag slider / click keyframe dot")
    print("  Close window to exit")

    plt.show()


if __name__ == "__main__":
    main()
