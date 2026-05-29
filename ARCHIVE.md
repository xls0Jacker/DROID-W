# DROID-W 项目归档笔记

> 归档日期：2026-05-26
> 决策：放弃继续投入，原因见 §6

---

## 1. 项目概述

**DROID-W** (DROID-SLAM in the Wild)，CVPR 2026，ETH Zurich。
- 论文：[arXiv 2603.19076](https://arxiv.org/abs/2603.19076)
- 代码：[github.com/MoyangLi00/DROID-W](https://github.com/MoyangLi00/DROID-W)
- 作者：Moyang Li, Zihan Zhu, Marc Pollefeys, Dániel Béla Baráth

**核心思路**：在 DROID-SLAM 的可微分 BA 层中引入逐像素动态不确定性，通过多视角 DINOv2 特征相似度在线估计每个像素的动态概率，对动态区域在 BA 中降权。与 WildGS-SLAM/UP-SLAM 的关键区别是：不确定性估计与 3DGS 建图解耦，不依赖渲染质量。

**技术栈**：Python 3.10, CUDA 11.8, PyTorch 2.1.0, DROID-SLAM + Metric3D + DINOv2/FiT3D + 3DGS (可选)

---

## 2. 已完成的工作

### 2.1 文档产出

| 文件 | 内容 |
|------|------|
| `RESEARCH.md` | 系统分析：架构、不确定性链路、7 个根本性缺陷、4 个改进方案（P0-P3）、7 个研究方向 |
| `formula_RESEARCH.md` | 论文公式→代码的逐行映射（Eq 1-11），含完整数据流图 |
| `Table4_RESEARCH.md` | Table 4 深度分析：DROID-W vs DROID-SLAM/Splat-SLAM/WildGS-SLAM，13 个改进方案（I1-I13） |
| `tmp.md` | PlanA 几何纠偏方案对比：方案一（乘法下拉）vs 方案二（插值融合）vs 推荐方案 |
| `STUDY.md` | 项目学习路径：目录结构、5 阶段阅读计划、实践练习 |
| `XXYJ DROID-SLAM in the Wild.md` | 论文全文精读笔记（219行），含公式+参考文献注释 |
| `docs/PlanA/PlanA_1.{1,2,3}.md` | P2 几何纠偏的三版迭代文档 |

### 2.2 代码改动

**main 分支**（相比上游 `9e05273`）：
- `run.py`：添加 torch.hub 离线模式 monkey-patch（绕过 GitHub API 调用）
- `src/utils/datasets.py`：新增 `DROIDW` 数据集类（GT 位姿加载+时间戳对齐）；修复 `RGB_NoPose` 的路径问题
- `src/utils/eval_traj.py`：修复 GT 位姿为 None 时的评估崩溃
- 新增 `configs/Dynamic/StereoMIS/` 和 `configs/Dynamic/endonerf/` 自定义数据集配置

**PlanA 分支**（相比 main，已验证后放弃）：
- `src/depth_video.py`：新增 `apply_geometric_correction()` 方法（~80 行），在 BA 后用几何重投影残差纠偏语义不确定性
- `src/frontend.py`、`src/factor_graph.py`：BA 调用后插入几何纠偏
- `configs/`：添加 `p2_geo_correction` 配置开关
- 大量注释和 docstring 翻译（中英文混合）

### 2.3 实验结论

**PlanA 几何纠偏效果**：
- 可视化上解决了部分"语义假阳性"问题（静态物体被 DINO 误判为动态→不确定性被几何信号拉低）
- **ATE 基本无变化**：per-sequence ATE 趋势与 baseline 几乎一致
- 根本原因：`w_uncer = clamp(1/clamp(45u-35, 0.1), 0, 1)` 的极度非线性映射使得中等程度的不确定性改善不转化为 BA 权重变化，也就不转化为 ATE 改善（详见 RESEARCH.md §4.1 因果链分析）

---

## 3. 已识别的核心问题

### 3.1 论文复现失败（致命）

**Table 4 的 DROID-W 数据集 ATE 无法复现**，实测值比论文报告值大数倍。联系作者未获回复。

DROID-W 在 Table 4 报告的平均 ATE 为 0.230m，在 Downtown 2 达到 0.25m（超出其他方法一个数量级）。这个数字在自建 pipeline 上跑不出来。

### 3.2 理论基础缺陷

1. **范畴错误**（最根本）：DINOv2 编码身份（"是什么"），不编码运动（"是否在动"）。用语义特征推断运动在原理上存在不可逾越的 gap。
2. **全局共享仿射变换**：384 维→1 维，信息丢弃率 > 99.7%，所有帧/所有空间位置共享同一组参数，无法区分同语义不同运动。
3. **`cos_sim > 0.5` 硬阈值**：将连续相似度二值化，丢失了"中等相似度"这个最重要的判别信号。
4. **梯度不对称性**：不确定性"易升难降"（上升单帧完成，下降需 50-100 帧）。
5. **循环依赖**：位姿不准→不确定性质量差→BA 约束丢失→位姿更差。
6. **DINOv2 不变性反噬**：光照/视角不变性对运动检测起反作用。

详见 `RESEARCH.md` §3.1-3.8。

### 3.3 工程局限

- `w_uncer` 映射在 u≈0.78 处存在陡峭"悬崖"，微小不确定性差异决定 BA 约束的有无
- `mapper.py` 中 `uncer > 0.7 → depth = 0` 硬阈值导致不可逆建图信息删除
- 初始化 12 帧内位姿不准导致不确定性全图误判
- CUDA 内核在 `thirdparty/` 中以子模块方式引入，修改和调试困难

---

## 4. 放弃原因总结

1. **Table 4 数据无法复现**：ATE 差数倍，无法作为后续研究的可靠 baseline
2. **作者不回复**：无法获得复现所需的缺失信息（预训练权重版本、数据预处理细节等）
3. **PlanA 纠偏验证确认了瓶颈不在实现细节**：修复已知问题后 ATE 无显著变化，说明问题在方法设计层面
4. **理论基础存在范畴错误**：用 DINOv2 语义特征推断运动状态，在原理上无法区分同语义不同运动（静止车 vs 行驶车）
5. **投入产出比不划算**：继续投入需要重写 CUDA 内核、替换不确定性模型架构，工作量相当于重做一半系统，且无把握达到论文声称性能

---

## 5. 可迁移的知识/经验

### 5.1 技术理解

- DROID-SLAM 的完整 pipeline：RAFT 光流 + 可微分 BA + GRU 更新算子
- 3DGS SLAM 的架构模式：tracking/mapping 双进程，因子图管理，高斯管理
- Metric3D 深度先验的集成方式（尺度/偏移对齐、深度正则化）
- DINOv2 特征在 SLAM 中的应用方式与局限
- CUDA 多进程 spawn 模式的约束

### 5.2 研究方法

- "公式→代码"逐行映射的研究方法（见 `formula_RESEARCH.md`）
- 以 ATE 为目标的因果链分析法（从不确定性到 BA 权重到 Hessian 到位姿到 ATE）
- "可视化改善 ≠ 指标改善"的教训（见 `RESEARCH.md` §6.1）
- 几何信号的质量在 SLAM 不同阶段差异巨大，融合策略必须考虑可靠性门控

### 5.3 代码资产

- `DROIDW` 数据集类（GT 位姿加载+时间戳对齐）可直接复用到其他 SLAM 项目
- torch.hub 离线模式 monkey-patch 可用于其他需要离线运行的深度学习项目
- 可视化/评估脚本（`scripts/` 目录下）

---

## 6. 项目文件索引

| 路径 | 说明 |
|------|------|
| `RESEARCH.md` | 系统分析+改进方案（400行） |
| `Table4_RESEARCH.md` | Table 4 深度对比分析（133行） |
| `formula_RESEARCH.md` | 公式→代码映射（594行） |
| `tmp.md` | PlanA 几何纠偏方案对比+推荐实现（360行） |
| `STUDY.md` | 学习路径指南（384行） |
| `XXYJ DROID-SLAM in the Wild.md` | 论文全文精读笔记（219行） |
| `ARCHIVE.md` | 本文档 |
| `docs/PlanA/` | P2 几何纠偏迭代文档（v1.1→v1.3） |
| `run.py` | 入口（含 torch.hub 离线 patch） |
| `src/utils/datasets.py` | 数据集加载（含 DROIDW 类） |
| `src/utils/eval_traj.py` | 轨迹评估（含 None GT 修复） |
| `src/depth_video.py` | 核心数据结构（PlanA 分支有 `apply_geometric_correction`） |

**Git 分支**：
- `main`：工作分支（含 DROIDW 数据集类+离线 patch），基于上游 `9e05273`
- `PlanA`：几何纠偏方案（已验证，ATE 无显著改善），基于 `489ab18`
- `study`：学习笔记分支
- `remotes/origin/main`：上游主分支

---

## 7. 未来可能的复现条件

如果将来考虑重新尝试，以下条件需要满足：

1. 作者回复并提供复现所需的完整信息（预训练权重、数据预处理、评估脚本细节）
2. 有其他独立团队成功复现 Table 4 并公开确认
3. 有足够时间进行超参数搜索（不同 seed、不同 gamma_data/gamma_prior/lr 组合）

在没有上述条件的情况下，不建议重新投入。
