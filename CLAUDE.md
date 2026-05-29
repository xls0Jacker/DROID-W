# DROID-W Project

DROID-W (DROID-SLAM in the Wild) — CVPR 2026. Estimates camera trajectory, scene structure, and dynamic uncertainty from casually captured in-the-wild video. Built on DROID-SLAM with Metric3D depth priors, DINOv2 features, dynamic uncertainty modeling, and optional 3D Gaussian Splatting online mapping.

## Tech Stack

- **Python 3.10**, **CUDA 11.8**, **PyTorch 2.1.0** (cu118)
- Custom CUDA extensions: `droid_backends` (built via `setup.py`)
- Third-party submodules: `lietorch`, `diff-gaussian-rasterization-w-pose`, `gaussian_splatting`, `simple-knn`, `eigen`, `fit3d`
- Multiprocessing with `spawn` start method (CUDA requirement)
- Offline mode: torch.hub calls are monkey-patched to avoid network access

## Architecture

```
run.py → SLAM.run()
           ├─ tracking() subprocess  → Tracker → MotionFilter → Frontend → Backend
           └─ mapping() subprocess   → Mapper (3DGS online mapping)
```

- **`src/slam.py`** — Top-level orchestrator: loads DROID pretrained weights, creates subprocesses, coordinates lifecycle
- **`src/tracker.py`** — Tracking process entry: manages MotionFilter (keyframe selection), Frontend (local BA), Backend (global BA)
- **`src/mapper.py`** — Mapping process entry (~1550 lines): 3DGS initialization, incremental optimization, uncertainty-aware weighting, final refinement
- **`src/depth_video.py`** — Core data structure: the keyframe graph (poses, depths, covariances, uncertainties)
- **`src/factor_graph.py`** — Factor graph for BA optimization
- **`src/trajectory_filler.py`** — Interpolates poses for non-keyframe frames after tracking completes
- **`src/config.py`** — YAML config loading with recursive inheritance (`inherit_from` chain)
- **`src/modules/droid_net/`** — DROID network (feature extractors, correlation pyramid, GRU update operator)
- **`src/geom/`** — CUDA-accelerated geometric ops (projection, BA solver, Cholesky)
- **`src/utils/dyn_uncertainty/`** — Dynamic uncertainty MLP and mapping utilities

## Configuration System

Configs use a recursive inheritance chain: child YAML specifies `inherit_from` pointing to a parent, which may also inherit. The base config is `configs/droid_w.yaml`. Dataset-specific configs live under `configs/Dynamic/`.

Key base config fields:
- `mapping.enable: False` — 3DGS mapping is off by default; enable per-dataset
- `fast_mode: True` — caps `final_refine_iters` to 3000
- `device: "cuda:0"`, `setup_seed: 43`
- Dataset type selected via `dataset` field (maps to `dataset_dict` in `datasets.py`)

## Key Conventions

- **Multiprocessing always uses `spawn`** — CUDA contexts don't survive `fork`
- **Mixed CN/EN comments** — docstrings are primarily Chinese, inline comments mixed
- **Outputs go to `cfg['data']['output']/{scene}/{timestamp}/`** — each run gets a unique directory
- **Keyframe graph stored in `DepthVideo`** — all poses, depths, covariances, and uncertainties live here
- **Pretrained weights** — DROID checkpoint at `./pretrained/droid.pth`; mono priors loaded from torch hub cache
- **Dataset factory** — `dataset_dict` in `src/utils/datasets.py` maps config name to class
- **No network access at runtime** — everything is pre-downloaded, torch.hub is monkey-patched

## Running

```bash
python run.py --config configs/Dynamic/TUM_RGBD/freiburg3_walking_xyz.yaml
```

## Editing Guidelines

1. **Surgical changes only** — don't refactor adjacent code, don't clean up unrelated formatting
2. **Simplicity first** — minimum code to solve the problem, no speculative abstractions
3. **Match existing style** — even if you'd do it differently
4. **Before implementing** — state assumptions, surface tradeoffs, ask if unclear
5. **Verify through execution** — define success criteria before coding
