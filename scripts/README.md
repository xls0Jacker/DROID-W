# Scripts

## `visualize_kf_traj.py`

交互式关键帧-轨迹联合浏览器，用于 DROID-W 输出结果的可视化分析。

### 布局

```
┌────────────────────────────────────┐
│        关键帧可视化图像             │  ← plots_final 面板图
├────────────────────────────────────┤
│   轨迹图 (全帧估计 + 对齐GT)       │  ← 细蓝线=全帧估计, 绿虚线=Umeyama对齐GT
│  关键帧按 ATE 热力图着色            │     红=误差大, 黄=误差小, 色条标注 ATE(m)
├────────────────────────────────────┤
│  [═══════o═══════]   N / M        │  ← 滑块
└────────────────────────────────────┘
```

- GT 通过 SE(3) Umeyama 对齐（与 `eval_traj.py` 相同，优先读取 `traj/metrics_full_traj.txt` 预计算参数，无此文件时通过 `evo` 实时计算）
- 关键帧在轨迹图上按 ATE (Absolute Trajectory Error) 着色，红色越深误差越大，单位 cm
- 标题栏显示当前关键帧的 ATE 值 (cm)
- 轨迹线加粗（width=1.2）：蓝色实线=全帧估计, 绿色虚线=对齐 GT

### 用法

```bash
# 默认：查看 plots_final 主面板图
python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown1/20260505_063040

# 指定可视化子类型
python scripts/visualize_kf_traj.py <run_dir> --mode input_images
python scripts/visualize_kf_traj.py <run_dir> --mode scaled_uncertainty
python scripts/visualize_kf_traj.py <run_dir> --mode uncertainty_contours
python scripts/visualize_kf_traj.py <run_dir> --mode high_res_uncertainty
```

### 参数

| 参数 | 说明 |
|---|---|
| `run_dir` | 运行输出目录，需包含 `plots_final/`、`traj/est_poses_full.txt`，可选 `gt_poses.txt` 和 `traj/metrics_full_traj.txt`（用于对齐与 ATE 着色） |
| `--mode` | 查看 `plots_final/` 下的子目录：`main`(默认), `input_images`, `scaled_uncertainty`, `uncertainty_contours`, `high_res_uncertainty` |

### 操作

| 操作 | 快捷键 |
|---|---|
| 上一帧 | `←` |
| 下一帧 | `→` |
| 跳到首帧 | `Home` |
| 跳到末帧 | `End` |
| 点击关键帧圆点跳转 | 鼠标 |
| 拖拽滑块 | 鼠标 |

### 依赖

`matplotlib`, `numpy`, `Pillow`, `evo`, `scipy`
