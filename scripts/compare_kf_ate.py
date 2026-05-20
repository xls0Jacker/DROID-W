#!/usr/bin/env python3
"""
Compare per-keyframe ATE between two DROID-W runs to evaluate code changes.

Only keyframes with the same ID (kf_XXX) in both runs are compared.

Usage:
  # Interactive: select dataset, scene, and two runs step by step
  python scripts/compare_kf_ate.py

  # Specify dataset path directly
  python scripts/compare_kf_ate.py --dataset Outputs/DROID-W

  # Specify scene directly (skips scene selection)
  python scripts/compare_kf_ate.py --dataset Outputs/DROID-W --scene downtown1

  # Fully non-interactive: specify both runs directly
  python scripts/compare_kf_ate.py \
      --run-a Outputs/DROID-W/downtown1/20260505_063040 \
      --run-b Outputs/DROID-W/downtown1/20260517_024538
"""

import argparse
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


# ── Data loading & trajectory alignment ───────────────────────────────────

def load_tum_xyz(path):
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
        elif line.startswith("translation:"):
            in_rotation = False
            t = np.array([float(x) for x in line.split(":")[1].strip().strip("[]").split()])
        elif in_rotation:
            row = line.strip().strip("[]")
            if row:
                R_rows.append([float(x) for x in row.split()])
    if s is not None and len(R_rows) == 3 and t is not None:
        return s, np.array(R_rows), t
    return None


def align_and_get_ate(run_dir, est_xyz, gt_xyz):
    """Align est to GT and return per-frame ATE (meters)."""
    n = min(len(est_xyz), len(gt_xyz))

    metrics_path = run_dir / "traj" / "metrics_full_traj.txt"
    precomputed = parse_metrics_full_traj(metrics_path)

    if precomputed is not None:
        s, R, t = precomputed
        est_aligned = s * (est_xyz[:n] @ R.T) + t
        gt = gt_xyz[:n]
        return np.linalg.norm(est_aligned - gt, axis=1)

    from evo.core.trajectory import PoseTrajectory3D
    from evo.core import sync

    timestamps = [float(i) for i in range(n)]
    traj_est = PoseTrajectory3D(positions_xyz=est_xyz[:n], timestamps=timestamps)
    traj_ref = PoseTrajectory3D(positions_xyz=gt_xyz[:n], timestamps=timestamps)

    traj_ref_sync, traj_est_sync = sync.associate_trajectories(traj_ref, traj_est)
    r_a, t_a, s = traj_est_sync.align(traj_ref_sync, correct_scale=True)

    est_pos = traj_est_sync.positions_xyz
    est_aligned = s * (est_pos @ r_a.T) + t_a
    gt_pos = traj_ref_sync.positions_xyz
    return np.linalg.norm(est_aligned - gt_pos, axis=1)


def find_kf_files(run_dir):
    """Find keyframe PNG files and extract (kf_index, frame_ts)."""
    plots_dir = run_dir / "plots_final"
    name_re = re.compile(r"video_kf_(\d+)_ts_(\d+)\.png")

    kf_list = []
    for p in sorted(plots_dir.glob("video_kf_*.png")):
        m = name_re.match(p.name)
        if m:
            kf_list.append((int(m.group(1)), int(m.group(2))))
    return sorted(kf_list)


def load_run(run_dir):
    """Load a single run: return per-frame ATE array and keyframe list."""
    run_dir = Path(run_dir)
    est_file = run_dir / "traj" / "est_poses_full.txt"
    gt_file = run_dir / "gt_poses.txt"

    if not est_file.exists():
        print(f"  ERROR: est_poses_full.txt not found in {run_dir}")
        return None, None
    if not gt_file.exists():
        print(f"  ERROR: gt_poses.txt not found in {run_dir}")
        return None, None

    est_xyz = load_tum_xyz(est_file)
    gt_xyz = load_tum_xyz(gt_file)

    if len(est_xyz) == 0 or len(gt_xyz) == 0:
        print(f"  ERROR: empty trajectory in {run_dir}")
        return None, None

    ate = align_and_get_ate(run_dir, est_xyz, gt_xyz)
    kf_list = find_kf_files(run_dir)
    return ate, kf_list


# ── Comparison ────────────────────────────────────────────────────────────

def compare(ate_a, kf_a, ate_b, kf_b, name_a, name_b):
    """Compare ATE for keyframes present in both runs.

    Keyframes are matched by kf_index (e.g. kf_000, kf_001, ...).
    """
    # Build lookup: kf_index → frame_ts
    ts_a = {kf_idx: frame_ts for kf_idx, frame_ts in kf_a}
    ts_b = {kf_idx: frame_ts for kf_idx, frame_ts in kf_b}

    common_kf = sorted(set(ts_a.keys()) & set(ts_b.keys()))
    if not common_kf:
        print("No common keyframes found between the two runs.")
        return

    # Extract ATE for common keyframes (by their frame timestamp)
    ate_vals_a = []
    ate_vals_b = []
    for kf_idx in common_kf:
        f_a = ts_a[kf_idx]
        f_b = ts_b[kf_idx]
        if f_a < len(ate_a) and f_b < len(ate_b):
            ate_vals_a.append(ate_a[f_a] * 100)  # cm
            ate_vals_b.append(ate_b[f_b] * 100)
        else:
            # Frame out of range — still include what we can
            pass

    ate_a_arr = np.array(ate_vals_a)
    ate_b_arr = np.array(ate_vals_b)
    delta = ate_b_arr - ate_a_arr  # positive = B worse, negative = B better

    # ── Print statistics ──
    n_improved = int(np.sum(delta < 0))
    n_worsened = int(np.sum(delta > 0))
    n_tied = int(np.sum(np.abs(delta) < 1e-6))

    print(f"\n{'='*60}")
    print(f"  Per-keyframe ATE Comparison")
    print(f"{'='*60}")
    print(f"  Common keyframes:  {len(common_kf)}")
    print(f"  Run A:             {name_a}")
    print(f"  Run B:             {name_b}")
    print(f"{'='*60}")
    print(f"  ATE A  mean/median:  {np.mean(ate_a_arr):.2f} / {np.median(ate_a_arr):.2f} cm")
    print(f"  ATE B  mean/median:  {np.mean(ate_b_arr):.2f} / {np.median(ate_b_arr):.2f} cm")
    print(f"  ───────────────────────────────────")
    print(f"  Delta (B - A):")
    print(f"    mean:    {np.mean(delta):+.2f} cm")
    print(f"    median:  {np.median(delta):+.2f} cm")
    print(f"    std:     {np.std(delta):.2f} cm")
    print(f"    min:     {np.min(delta):+.2f} cm")
    print(f"    max:     {np.max(delta):+.2f} cm")
    print(f"  ───────────────────────────────────")
    print(f"  Improved (B < A):  {n_improved} kf  ({100*n_improved/len(delta):.1f}%)")
    print(f"  Worsened (B > A):  {n_worsened} kf  ({100*n_worsened/len(delta):.1f}%)")
    print(f"  Tied:              {n_tied} kf")
    print(f"{'='*60}")

    # ── Plot ──
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. Scatter: ATE A vs ATE B
    ax0 = axes[0, 0]
    ax0.scatter(ate_a_arr, ate_b_arr, c=delta, cmap="coolwarm", s=15,
                edgecolors="black", linewidth=0.2, alpha=0.8)
    lim_max = max(ate_a_arr.max(), ate_b_arr.max()) * 1.1
    ax0.plot([0, lim_max], [0, lim_max], "--", color="gray", alpha=0.5, label="y = x")
    ax0.set_xlabel(f"ATE A ({name_a})  [cm]")
    ax0.set_ylabel(f"ATE B ({name_b})  [cm]")
    ax0.set_title("Per-keyframe ATE: A vs B")
    ax0.legend(fontsize=8)
    ax0.grid(True, alpha=0.3)
    ax0.set_aspect("equal")
    cbar0 = plt.colorbar(ax0.collections[0], ax=ax0)
    cbar0.set_label("Delta (B - A) [cm]", fontsize=8)

    # 2. Histogram of ATE delta
    ax1 = axes[0, 1]
    ax1.hist(delta, bins=30, color="#4a90d9", edgecolor="black", linewidth=0.3)
    ax1.axvline(0, color="red", linestyle="--", linewidth=1.5, label="no change")
    ax1.axvline(np.mean(delta), color="orange", linestyle="-", linewidth=1.5,
                label=f"mean = {np.mean(delta):+.2f} cm")
    ax1.set_xlabel("ATE Delta (B - A) [cm]")
    ax1.set_ylabel("Count")
    ax1.set_title("Distribution of ATE Delta")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # 3. Per-keyframe ATE line plot (sorted by kf index)
    ax2 = axes[1, 0]
    x = np.arange(len(common_kf))
    ax2.plot(x, ate_a_arr, "-", color="#4a90d9", linewidth=1.0, alpha=0.8, label=f"A: {name_a}")
    ax2.plot(x, ate_b_arr, "-", color="#e74c3c", linewidth=1.0, alpha=0.8, label=f"B: {name_b}")
    ax2.set_xlabel("Keyframe (sorted by kf index)")
    ax2.set_ylabel("ATE [cm]")
    ax2.set_title("Per-keyframe ATE")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # 4. Per-keyframe delta (B - A)
    ax3 = axes[1, 1]
    colors = ["#27ae60" if d < 0 else "#e74c3c" for d in delta]
    ax3.bar(x, delta, color=colors, width=1.0, alpha=0.8)
    ax3.axhline(0, color="black", linewidth=0.8)
    ax3.axhline(np.mean(delta), color="orange", linestyle="--", linewidth=1.0,
                label=f"mean = {np.mean(delta):+.2f} cm")
    ax3.set_xlabel("Keyframe (sorted by kf index)")
    ax3.set_ylabel("ATE Delta (B - A) [cm]")
    ax3.set_title("Per-keyframe ATE Delta (green = improved, red = worsened)")
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3)

    fig.suptitle(
        f"ATE Comparison: {name_a}  vs  {name_b}\n"
        f"{n_improved}/{len(delta)} improved, mean delta = {np.mean(delta):+.2f} cm",
        fontsize=12, family="monospace",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    plt.show()

    return ate_a_arr, ate_b_arr, delta


# ── Interactive selection ─────────────────────────────────────────────────

def pick_from_list(items, prompt, display_key="name"):
    """Let user pick one or more items from a list by number."""
    for i, item in enumerate(items):
        label = item if isinstance(item, str) else item.get(display_key, str(item))
        print(f"  [{i}] {label}")
    print()

    while True:
        choice = input(prompt).strip()
        if choice.lower() == "q":
            sys.exit(0)
        try:
            idx = int(choice)
            if 0 <= idx < len(items):
                return items[idx], idx
        except ValueError:
            pass
        print(f"  Invalid choice. Enter 0-{len(items)-1} or 'q' to quit.")


def pick_two_from_list(items, prompt_single, display_key="name"):
    """Let user pick two distinct items by number."""
    print(f"\n{prompt_single}")
    first, i = pick_from_list(items, "  Select first run:  ", display_key)
    print(f"  → Selected: {first if isinstance(first, str) else first[display_key]}\n")

    remaining = [x for j, x in enumerate(items) if j != i]
    print(f"Select second run (comparison target):")
    second, _ = pick_from_list(remaining, "  Select second run: ", display_key)
    print(f"  → Selected: {second if isinstance(second, str) else second[display_key]}\n")
    return first, second


# ── Main ──────────────────────────────────────────────────────────────────

def iter_run_dirs(scene_dir):
    """Yield (name, path) for run directories in a scene, sorted by name."""
    runs = []
    for p in sorted(scene_dir.iterdir()):
        if p.is_dir() and (p / "traj").is_dir():
            runs.append((p.name, p))
    return runs


def main():
    parser = argparse.ArgumentParser(
        description="Compare per-keyframe ATE between two DROID-W runs",
    )
    parser.add_argument("--dataset", help="Path to dataset (e.g. Outputs/DROID-W)")
    parser.add_argument("--scene", help="Scene name (e.g. downtown1)")
    parser.add_argument("--run-a", help="Path to first run directory")
    parser.add_argument("--run-b", help="Path to second run directory")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset) if args.dataset else None
    scene_name = args.scene
    run_a_path = Path(args.run_a) if args.run_a else None
    run_b_path = Path(args.run_b) if args.run_b else None

    # ── Step 1: determine dataset ──
    if dataset_dir is None:
        default = Path("Outputs/DROID-W")
        if default.is_dir():
            dataset_dir = default
        else:
            dataset_dir = Path(input("Dataset path (e.g. Outputs/DROID-W): ").strip())
    if not dataset_dir.is_dir():
        print(f"Dataset directory not found: {dataset_dir}")
        sys.exit(1)

    # ── Step 2: determine scene ──
    if scene_name is None:
        scenes = sorted(
            [d.name for d in dataset_dir.iterdir() if d.is_dir()]
        )
        if not scenes:
            print(f"No scene directories found in {dataset_dir}")
            sys.exit(1)
        print(f"\nScenes in {dataset_dir}:")
        scene_name, _ = pick_from_list(scenes, "Select scene:  ")

    scene_dir = dataset_dir / scene_name
    if not scene_dir.is_dir():
        print(f"Scene directory not found: {scene_dir}")
        sys.exit(1)

    # ── Step 3: determine runs ──
    runs = iter_run_dirs(scene_dir)
    if len(runs) < 2:
        print(f"Need at least 2 runs in {scene_dir}, found {len(runs)}")
        sys.exit(1)

    if run_a_path is not None and run_b_path is not None:
        name_a, name_b = run_a_path.name, run_b_path.name
    elif run_a_path is not None:
        name_a = run_a_path.name
        print(f"\nRun A: {name_a}")
        print(f"Runs in {scene_dir}:")
        remaining = [(n, p) for n, p in runs if p != run_a_path]
        name_b, run_b_path = pick_from_list(
            [{"name": n, "path": p} for n, p in remaining],
            "Select run B:  ",
            display_key="name",
        )
        name_b = name_b["name"]
        run_b_path = name_b["path"]
    elif run_b_path is not None:
        name_b = run_b_path.name
        print(f"\nRun B: {name_b}")
        print(f"Runs in {scene_dir}:")
        remaining = [(n, p) for n, p in runs if p != run_b_path]
        name_a, run_a_path = pick_from_list(
            [{"name": n, "path": p} for n, p in remaining],
            "Select run A:  ",
            display_key="name",
        )
        name_a = name_a["name"]
        run_a_path = name_a["path"]
    else:
        print(f"\nRuns in {scene_dir}:")
        run_names = [n for n, _ in runs]
        name_a, idx_a = pick_from_list(run_names, "Select run A (baseline):  ")
        run_a_path = runs[idx_a][1]
        print(f"  → {name_a}\n")

        remaining = [(runs[j][0], runs[j][1]) for j in range(len(runs)) if j != idx_a]
        print("Select run B (comparison):")
        run_b_info, _ = pick_from_list(
            [{"name": n, "path": p} for n, p in remaining],
            "Select run B:  ",
            display_key="name",
        )
        name_b = run_b_info["name"]
        run_b_path = run_b_info["path"]
        print(f"  → {name_b}\n")

    # ── Step 4: load & compare ──
    print(f"\nLoading runs...")
    print(f"  A: {run_a_path}")
    ate_a, kf_a = load_run(run_a_path)
    if ate_a is None:
        sys.exit(1)
    print(f"     {len(ate_a)} poses, {len(kf_a)} keyframes")

    print(f"  B: {run_b_path}")
    ate_b, kf_b = load_run(run_b_path)
    if ate_b is None:
        sys.exit(1)
    print(f"     {len(ate_b)} poses, {len(kf_b)} keyframes")

    compare(ate_a, kf_a, ate_b, kf_b, name_a, name_b)


if __name__ == "__main__":
    main()
