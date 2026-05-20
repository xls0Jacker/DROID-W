# Scripts

## `visualize_kf_traj.py`

交互式关键帧-轨迹联合浏览器，用于 DROID-W 输出结果的可视化分析。

### 布局

```
┌────────────────────────────────────┐
│        关键帧可视化图像             │  ← plots_final 面板图
├────────────────────────────────────┤
│   轨迹图 (全帧估计 + 对齐GT)       │  ← 细蓝线=全帧估计, 绿虚线=Umeyama对齐GT
│  关键帧按 ATE 热力图着色            │     红=误差大, 黄=误差小, 色条标注 ATE(cm)
├────────────────────────────────────┤
│  [═══════o═══════]   N / M        │  ← 滑块
└────────────────────────────────────┘
```

`--traj-only` 模式下隐藏图像面板，轨迹图占满窗口。

- GT 通过 SE(3) Umeyama 对齐（与 `eval_traj.py` 相同，优先读取 `traj/metrics_full_traj.txt` 预计算参数，无此文件时通过 `evo` 实时计算）
- 关键帧在轨迹图上按 ATE (Absolute Trajectory Error) 着色，红色越深误差越大，单位 cm
- 默认模式：标题栏显示当前关键帧的 ATE 值 (cm)；`--traj-only` 模式：信息显示在窗口顶部 suptitle
- 轨迹线加粗（width=1.2）：蓝色实线=全帧估计, 绿色虚线=对齐 GT

### 用法

```bash
# 默认：查看 plots_final 主面板图
python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown1/20260505_063040 --traj-only # 空旷场景初始化？
> python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown1/20260517_024538 --traj-only

> python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown2/20260505_033625 --traj-only # 大面积不确定性移动？（人群）
> python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown2/20260517_030303 --traj-only

> python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown3/20260505_035805 --traj-only # 大面积不确定性移动（个人）
> python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown3/20260517_032606 --traj-only

> python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown4/20260505_041306 --traj-only # 大面积不确定性移动？（近距离人群）
> python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown4/20260517_034207 --traj-only

> python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown5/20260505_042850 --traj-only # 大面积不确定性移动（车辆）
> python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown5/20260517_035842 --traj-only

> python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown6/20260505_044745 --traj-only # 关键帧不够密集，初始移速快
> python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown6/20260517_041833 --traj-only

> python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown7/20260505_060725 --traj-only # 大面积不确定性移动（脚）
> python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown7/20260517_044215 --traj-only

# 仅显示轨迹图（更大的观察面积）
python scripts/visualize_kf_traj.py Outputs/DROID-W/downtown1/20260505_063040 --traj-only

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
| `--traj-only` | 仅显示轨迹图，隐藏关键帧图像以获得更大的轨迹观察面积 |

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


## `compare_kf_ate.py`

对比两个运行结果的逐关键帧 ATE 误差分布，用于判断代码修改前后 ATE 是否改善。

仅对比两个运行中编号相同的关键帧（`kf_XXX`），输出统计信息和四幅对比图。

### 用法

```bash
# 完全交互式：逐步选择数据集 → 场景 → 两个运行
python scripts/compare_kf_ate.py

# 指定数据集
python scripts/compare_kf_ate.py --dataset Outputs/DROID-W

# 指定场景（跳过场景选择）
python scripts/compare_kf_ate.py --dataset Outputs/DROID-W --scene downtown1

# 完全非交互：直接指定两个运行目录
python scripts/compare_kf_ate.py \
    --run-a Outputs/DROID-W/downtown1/20260505_063040 \
    --run-b Outputs/DROID-W/downtown1/20260517_024538
```

### 参数

| 参数 | 说明 |
|---|---|
| `--dataset` | 数据集路径 (e.g. `Outputs/DROID-W`) |
| `--scene` | 场景名 (e.g. `downtown1`) |
| `--run-a` | 第一个运行目录（基线） |
| `--run-b` | 第二个运行目录（对比） |

### 输出

- **控制台统计**：共同关键帧数、ATE A vs B 的 mean/median、Delta 分布、改善/恶化比例
- **四幅图**：ATE 散点图 (A vs B)、Delta 分布直方图、逐帧 ATE 折线、逐帧 Delta 柱状图（绿色=改善，红色=恶化）

### 依赖

`matplotlib`, `numpy`, `evo`
