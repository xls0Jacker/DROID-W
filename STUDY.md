# DROID-W 学习路径

> **论文**: DROID-SLAM in the Wild (CVPR 2026)
> **一句话概览**: 在 DROID-SLAM 基础上，融合 Metric3D 深度先验、DINOv2 特征、动态不确定性建模、3D Gaussian Splatting 在线建图，实现对 in-the-wild 视频的鲁棒 SLAM。

---

## 1. 项目总览

### 1.1 系统做了什么

```
输入: 一段随意拍摄的视频 (无相机参数、无先验)
  │
  ├─ Tracking (DROID-SLAM 核心)
  │    ├─ MotionFilter: 判断帧间运动是否足够 → 选关键帧
  │    ├─ Frontend: Dense Bundle Adjustment → 估计位姿 + 深度
  │    ├─ Backend: 全局 BA + 回环检测
  │    └─ Uncertainty: 动态/不确定区域建模
  │
  ├─ Mapping (3D Gaussian Splatting) [可选]
  │    ├─ 在线: 每来一帧关键帧，增量建图
  │    └─ 离线: Final BA 后精化
  │
  └─ 输出: 相机轨迹 + 深度图 + 3DGS 点云
```

### 1.2 核心创新点

| 创新 | 说明 | 对应代码 |
|------|------|----------|
| Metric Depth Prior | 用 Metric3D 提供绝对尺度深度，解决单目 SLAM 的尺度漂移 | `motion_filter.py:72` |
| DINOv2 Features | 语义特征用于回环检测和不确定性预测 | `motion_filter.py:74` |
| Dynamic Uncertainty | 用 MLP 预测每个像素的"动态/不确定"权重，降低动态物体干扰 | `src/utils/dyn_uncertainty/` |
| Affine Feature Transform | 学习特征空间的仿射变换，适应光照/场景变化 | `depth_video.py` |
| 3DGS Mapping | 在线 Gaussian Splatting 建图（可选） | `mapper.py` |

### 1.3 项目目录结构

```
DROID-W/
├── run.py                    # 入口
├── configs/                  # 配置文件（YAML, 可继承）
│   ├── droid_w.yaml          #   基础配置
│   ├── Dynamic/              #   各数据集配置
│   │   ├── DROIDW/           #   DROID-W 数据集
│   │   ├── Bonn/             #   Bonn Dynamic
│   │   ├── TUM_RGBD/         #   TUM RGB-D
│   │   ├── DyCheck/          #   DyCheck
│   │   └── YouTube/          #   YouTube 视频
│   └── ...
├── src/
│   ├── slam.py               # 主控制器: 进程调度, 生命周期
│   ├── tracker.py            # Tracking 进程入口
│   ├── motion_filter.py      # 运动过滤 + 首帧初始化
│   ├── frontend.py           # 局部 BA（前端里程计）
│   ├── backend.py            # 全局 BA + 回环
│   ├── depth_video.py        # 核心数据结构: 关键帧图
│   ├── factor_graph.py       # 因子图: BA 优化后端
│   ├── mapper.py             # 3DGS Mapping 进程 (1547 行, 最复杂)
│   ├── trajectory_filler.py  # 非关键帧位姿插值
│   ├── config.py             # 配置加载（YAML 继承）
│   ├── modules/droid_net/    # DROID-SLAM 网络
│   │   ├── droid_net.py      #   网络主体 (DroidNet)
│   │   ├── extractor.py      #   特征提取器 (context + feature)
│   │   ├── corr.py           #   相关性金字塔 (CorrBlock)
│   │   └── gru.py            #   GRU 更新算子
│   ├── geom/                 # 几何运算 (CUDA 加速)
│   │   ├── projective_ops.py #   投影/反投影
│   │   ├── ba.py             #   BA 求解器
│   │   └── chol.py           #   Cholesky 分解
│   └── utils/
│       ├── datasets.py       # 数据加载器
│       ├── mono_priors/      #   单目先验模型
│       │   ├── metric_depth_estimators.py  # Metric3D / DepthAnything
│       │   └── img_feature_extractors.py   # DINOv2 / FiT3D
│       ├── dyn_uncertainty/  #   动态不确定性模块
│       ├── slam_utils.py     #   SLAM 工具函数
│       ├── eval_traj.py      #   轨迹评估
│       ├── plot_utils.py     #   可视化
│       └── ...
├── thirdparty/               # 第三方依赖
│   ├── lietorch/             #   SE3 李代数库
│   ├── gaussian_splatting/   #   3DGS 渲染器
│   ├── diff-gaussian-rasterization-w-pose/  # 可微光栅化
│   └── simple-knn/           #   快速 KNN
├── pretrained/
│   └── droid.pth             # DROID-SLAM 预训练权重
└── scripts_eval/             # 评估脚本
```

---

## 2. 学习路线图

### 阶段 0: 前置知识 (1-2 天)

开始阅读源码前建议先了解：

- **DROID-SLAM** (CVPR 2021) — RAFT 光流在 SLAM 中的应用，本项目的 tracking 核心
  - 论文: *DROID-SLAM: Deep Visual SLAM for Monocular, Stereo, and RGB-D Cameras*
  - 理解概念: dense correlation volume, iterative update operator, differentiable BA
- **3D Gaussian Splatting** (SIGGRAPH 2023) — mapping 模块的理论基础
  - 理解概念: 2D/3D Gaussian, alpha blending, tile-based rasterization
- **GO-SLAM** (CVPR 2023) — 全局 BA + 回环检测的来源
- **Metric3D** — 度量深度估计

### 阶段 1: 入口与配置 (1 小时)

**目标**: 理解程序如何启动和配置

1. **`run.py`** (70 行) — 入口文件
   - 第 26 行: `set_start_method('spawn')` — CUDA 多进程必须用 spawn
   - 第 54 行: 加载数据集
   - 第 56 行: 创建 SLAM 对象, 调用 `slam.run()`

2. **`src/config.py`** (71 行) — 配置加载
   - YAML `inherit_from` 机制: `downtown1.yaml` → `droidw.yaml` → `droid_w.yaml`
   - 配置合并规则

3. **`configs/droid_w.yaml`** — 主配置文件
   - `tracking`: 跟踪参数 (motion_filter, frontend, backend, uncertainty)
   - `mapping`: 建图参数 (Gaussian 参数, 训练配置)
   - `mono_prior`: 单目先验模型 (depth: metric3d_vit_large, feature: dinov2)
   - `cam`: 相机参数

思考题: 为什么要用 `spawn` 而不是 `fork`？

### 阶段 2: 主控制流 (2 小时)

**目标**: 理解 SLAM 系统的整体生命周期

1. **`src/slam.py`** (354 行) — 系统的"大脑"
   - `__init__` (27-69): 加载 DROID net, 初始化 DepthVideo, Backend
   - `run()` (278-347): 
     - 创建 tracking/mapping 两个子进程
     - 通过 `mp.Pipe()` 和 `mp.Queue()` 做进程间通信
     - 双进程屏障同步: `all_trigered` 计数器
   - `tracking()` (89-110): tracking 进程入口
   - `mapping()` (112-125): mapping 进程入口
   - `terminate()` (145-231): 
     - 先做 Final Global BA
     - 再精化 Gaussian
     - 填充非关键帧位姿 → 轨迹评估 → 保存 PLY

2. **关键执行顺序**:
   ```
   Tracking 进程                        Mapping 进程
   ─────────────                        ────────────
   Tracker.__init__                     Mapper.__init__
   ├─ MotionFilter.__init__             ├─ GaussianModel
   │  ├─ get_metric_depth_estimator     ├─ get_dataset
   │  └─ get_feature_extractor          └─ 等待同步
   ├─ Frontend.__init__
   │  └─ FactorGraph.__init__
   └─ 等待同步
        ↓ 同步完成                    ↓
   Tracker.run (逐帧)                  Mapper.run (逐关键帧)
   ```

### 阶段 3: Tracking 核心 (4-5 小时)

**目标**: 深入理解视觉里程计和 BA 优化

#### 3.1 DepthVideo — 核心数据结构 (`depth_video.py`, 885 行)

整个 tracking 系统围绕 `DepthVideo` 展开，它是关键帧图的数据存储：

```
DepthVideo:
├─ images:       [N, 3, H, W]        关键帧图像
├─ disps:        [N, H, W]           逆深度图 (disparity)
├─ poses:        [N, 7]              相机位姿 (SE3, 四元数+平移)
├─ intrinsics:   [N, 4]              相机内参
├─ fmaps:        [N, 128, H/8, W/8]  特征图
├─ nets:         [N, 128, H/8, W/8]  上下文特征
├─ inps:         [N, 128, H/8, W/8]  上下文特征 2
├─ dino_features:[N, *, 384]         DINOv2 特征
├─ uncertainties:[N, ...]            逐像素不确定性
├─ affine_weights:[N, ...]           仿射变换权重
├─ ii, jj:       [M]                 因子图的边 (帧对)
├─ target, weight: [M]               每条边的优化目标 & 权重
└─ counter: int                      当前关键帧数
```

关键方法:
- `append()`: 添加新关键帧到图中
- `update_edges()`: 更新因子图的边
- `save_video()`: 保存为 `.npz`

#### 3.2 MotionFilter (`motion_filter.py`, 120 行)

**是程序卡住的高发区**（之前我们 debug 的那个问题）。

```python
def track(tstamp, image, intrinsics):
    # 1. 提取特征图 (fnet)
    gmap = feature_encoder(image)
    
    # 2. 如果是第一帧
    if counter == 0:
        extract context features
        predict metric depth (Metric3D)
        extract DINO features
        add to video
    
    # 3. 否则: 计算与上一关键帧的光流
    else:
        corr = CorrBlock(fmap, gmap)
        _, delta, weight = update(net, inp, corr)
        if delta.norm > threshold:
            add as new keyframe
```

涉及的关键概念:
- **Context features** vs **Feature features**: DROID-SLAM 双流架构
- **Metric depth prior**: 从 Metric3D 获得绝对尺度深度

#### 3.3 Frontend — 前端里程计 (`frontend.py`, 226 行)

```
Frontend.__call__(force_to_add_keyframe):
  1. 更新因子图的边 (update edges)
  2. 运行 BA 优化 (iters1 次)
  3. 移除"离得太近"的关键帧
  4. 对新关键帧运行额外优化 (iters2 次)
  5. 可选: 回环检测 → 全局 BA
```

#### 3.4 FactorGraph (`factor_graph.py`, 565 行)

从 GO-SLAM 继承的因子图优化：

```
FactorGraph:
├─ 边选择: 在局部窗口内根据光流大小建立帧间约束
├─ Cholesky 消元: 用 Schur Complement 加速 BA
├─ Dense BA: 同时优化所有帧的位姿和深度
└─ 与 DROID-SLAM 的 GRU update 算子对接
```

#### 3.5 Backend (`backend.py`, 121 行)

全局 BA + 回环检测，周期性运行：
- `dense_ba(7)`: 7 次迭代全局优化
- `dense_ba(12)`: 12 次迭代精化

### 阶段 4: 不确定性建模 (2 小时)

**目标**: 理解如何让 SLAM 对动态物体鲁棒

`src/utils/dyn_uncertainty/` — DROID-W 的核心贡献之一：

1. **逐像素不确定性预测**: 每个 3D 点有一个"不确定度"
2. **Affine Feature Transform**: 特征空间学习仿射变换，适应环境变化
3. **损失加权**: 高不确定性区域在 BA 中降权
4. **动态 mask**: 可选的动态物体分割

关键配置：
```yaml
tracking:
  uncertainty_params:
    activate: True
    gamma_data: 0.1
    gamma_depth: 0.001
    enable_affine_transform: True
```

### 阶段 5: 3DGS Mapping (3-4 小时)

**目标**: 理解高斯建图模块

#### 5.1 Mapper (`mapper.py`, 1547 行)

最复杂的模块，主要流程：

```python
class Mapper:
    def run():
        while True:
            # 1. 从 pipe 接收 tracker 发来的关键帧
            # 2. 初始化: 首帧深度图 → 3D 点云 → 高斯初始化
            # 3. 增量建图:
            #    - Tracking loss (位姿优化)
            #    - Mapping loss (RGB + Depth + SSIM + Normal)
            #    - 动态 densification/pruning
            # 4. 保存和可视化
```

关键概念:
- **2D Gaussian Splatting**: DROID-W 使用 surfel 渲染
- **Uncertainty-aware loss**: 不确定性加权损失函数
- **Deform Gaussians**: BA 后变形高斯以适应位姿修正

#### 5.2 渲染管线

```
3D Gaussian → Rasterizer (diff-gaussian-rasterization-w-pose) → RGB + Depth
```

---

## 3. 推荐阅读顺序（按文件）

| 优先级 | 文件 | 行数 | 阅读时间 | 关键内容 |
|--------|------|------|----------|----------|
| ★★★ | `run.py` | 70 | 10 min | 入口, spawn |
| ★★★ | `src/config.py` | 71 | 15 min | YAML 继承 |
| ★★★ | `configs/droid_w.yaml` | 163 | 20 min | 所有参数含义 |
| ★★★ | `src/slam.py` | 354 | 1 h | 主控制流, 进程调度 |
| ★★★ | `src/tracker.py` | ~200 | 30 min | Tracking 入口 |
| ★★★ | `src/motion_filter.py` | 120 | 30 min | DROID-SLAM 核心 loop |
| ★★★ | `src/depth_video.py` | 885 | 1.5 h | 核心数据结构 |
| ★★☆ | `src/frontend.py` | 226 | 1 h | 局部 BA |
| ★★☆ | `src/factor_graph.py` | 565 | 1.5 h | 因子图 |
| ★★☆ | `src/backend.py` | 121 | 30 min | 全局 BA |
| ★★☆ | `src/mapper.py` | 1547 | 2 h | 3DGS 建图 |
| ★☆☆ | `src/modules/droid_net/` | 551 | 1 h | 网络结构 |
| ★☆☆ | `src/geom/` | 439 | 45 min | 几何运算 |
| ★☆☆ | `src/trajectory_filler.py` | 141 | 20 min | 轨迹插值 |
| ★☆☆ | `src/utils/mono_priors/` | ~300 | 30 min | 深度/特征提取 |
| ★☆☆ | `src/utils/dyn_uncertainty/` | ~500 | 1 h | 不确定性模块 |

---

## 4. 实践练习

### 练习 1: 调试追踪

从 motion filter 开始，在 `motion_filter.py:52` 的 `track()` 入口打断点，逐步跟踪一帧的处理流程，理解：
- 特征提取做了什么
- 光流如何计算
- 关键帧如何确定

### 练习 2: 关闭模块观察影响

```bash
# 关闭不确定性建模
# 修改 configs/droid_w.yaml:
#   tracking.uncertainty_params.activate: False

# 关闭 mapping
#   mapping.enable: False

# 关闭 metric depth
#   修改代码跳过 predict_metric_depth
```

### 练习 3: 理解 BA 优化

在 `frontend.py` 的 `__update()` 方法中，跟踪因子图的构建和 Cholesky 消元过程。打印优化前后的位姿变化。

### 练习 4: 轨迹评估

运行完成后，检查输出:
```bash
ls Outputs/DROID-W/downtown1/
# traj/         ← 轨迹文件
# final_gs.ply  ← 3DGS 点云
# plots_final/  ← 渲染图像
```

---

## 5. 常见踩坑

| 问题 | 原因 | 解决 |
|------|------|------|
| 程序卡在 Mapping Triggered | 网络阻断 `torch.hub.load` | `export TORCH_HUB_OFFLINE=1` |
| CUDA OOM | Metric3D + FiT3D + 3DGS 同时占显存 | 降低分辨率或关闭 mapping |
| spawn 子进程报 CUDA 错误 | spawn 后需要重新初始化 CUDA | 确保 `set_start_method('spawn')` 在最前面 |
| 数据集路径报错 | config 中 `input_folder` 未设置 | 检查 `ROOT_FOLDER_PLACEHOLDER` 是否替换为实际路径 |

---

## 6. 论文与参考资料

1. **DROID-W**: [DROID-SLAM in the Wild](https://arxiv.org/abs/2603.19076) (CVPR 2026)
2. **DROID-SLAM**: [Deep Visual SLAM for Monocular, Stereo, and RGB-D Cameras](https://arxiv.org/abs/2111.12711) (NeurIPS 2021)
3. **GO-SLAM**: [Global Optimization for Consistent 3D Instant Reconstruction](https://arxiv.org/abs/2309.02436) (ICCV 2023)
4. **3D Gaussian Splatting**: [3D Gaussian Splatting for Real-Time Radiance Field Rendering](https://arxiv.org/abs/2308.04079) (SIGGRAPH 2023)
5. **Metric3D V2**: [Metric3D v2: A Versatile Monocular Geometric Foundation Model](https://arxiv.org/abs/2404.15506) (ECCV 2024)
6. **WildGS-SLAM**: [Wild-GS: Real-Time Novel View Synthesis from In-the-Wild Monocular Videos](https://arxiv.org/abs/2406.10357) (3DV 2025)
