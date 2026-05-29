# PlanA_1: P2 几何残差作为不确定性纠偏信号
> 基于 RESEARCH_E.md §4.4 实现。将几何重投影残差作为语义不确定性的**纠偏信号**（非主导信号），在 BA 优化后自适应融合。
>

---

## 一、问题定位
DROID-W 的不确定性估计完全依赖 DINOv2 语义特征（仿射变换 → softplus）。语义特征对"外观相似但运动状态不同"的物体（如停放的汽车 vs 行驶的汽车）缺乏分辨力。

几何重投影残差携带了运动状态的直接信息——静态像素的 BA 残差小，动态/误匹配像素的残差大。但几何信号在 SLAM 不同阶段质量差异巨大：

+ **初始化阶段**：位姿不准 → 几何残差噪声 > 信号 → 直接融合会恶化 ATE
+ **稳定运行阶段**：位姿收敛 → 几何残差可靠 → 可提供有效纠偏
+ **快速运动/回环后**：位姿突变 → 几何残差暂时不可靠

## 二、设计原则
与 RESEARCH_A 方向一（多源不确定性融合）的**本质区别**：

| 维度 | RESEARCH_A 方向一 | P2（本方案） |
| --- | --- | --- |
| 几何信号角色 | 与语义"平权"融合 | 仅做"纠偏"（权重上限 0.25） |
| 外点处理 | 未明确 | 外点几何信号自动归零 |
| 初始化安全 | 时间常数调度 `w_geo(t)` | 基于内点率自适应（零风险） |
| 可学习性 | 融合权重可学习 | 固定规则（可验证、可解释） |
| ATE 安全性 | 初始化阶段可能恶化 | 初始化自动退化为纯语义模式 |


## 三、实现细节
### 3.1 核心公式
```python
# 重投影残差（BA 优化后）
u_geo = 1 - exp(-λ · ||target - reproject(pose, depth)||)

# 内点判定（3σ 中位数门控）
inlier_mask = (residual_norm < 3 · median(residual_norm)) & valid_mask

# 自适应几何权重
w_geo = 0.25 · inlier_ratio

# 融合
u_fused = (1 - w_geo) · u_sem + w_geo · u_geo
```

### 3.2 安全性机制
1. **外点自动归零**：`u_geo *= inlier_mask`，大残差像素不参与纠偏
2. **帧级可靠性门控**：`w_geo = 0.25 × inlier_ratio`，位姿不准时内点率低 → 自动退化
3. **像素级有效性**：`torch.where(valid_fusion, ...)` 仅在至少一条边提供有效几何信号的像素处融合
4. **初始化零风险**：初始化阶段位姿/深度误差大 → 内点率极低 → `w_geo ≈ 0` → 等价于纯语义模式

## 四、代码变更
### 4.1 `src/depth_video.py` — 新增 `apply_geometric_correction()` 方法
**修改前：** `ba()` 方法结束后直接进入 `visualize_uncertainty()` 方法。

```python
# === 修改前 (study 分支, 原行 378-381) ===
            self.disps.clamp_(min=1e-5)

    @torch.no_grad()
    def visualize_uncertainty(self, target, weight, ii, jj, frame_choice="nearest", mode="Before"):
```

**修改后：** 在 `ba()` 与 `visualize_uncertainty()` 之间插入新方法。

```python
# === 修改后 (PlanA 分支) ===
            # 确保逆深度为正数（数值稳定）
            self.disps.clamp_(min=1e-5)

    @torch.no_grad()
    def apply_geometric_correction(self, target, ii, jj, lambda_geo=5.0, max_geo_weight=0.25):
        """P2: 使用几何重投影残差纠正语义不确定性的系统性偏差。

        核心设计（RESEARCH_E §4.4）：
          - 几何信号仅做"纠偏"不做"主导"：w_geo 上限 max_geo_weight (0.25)
          - 几何信号有效性门控：外点（大残差）处几何信号自动失效
          - 帧级别自适应：基于内点率判断几何信号可靠性
          - 初始化阶段零风险：位姿不准时内点率低 → w_geo ≈ 0 → 自动退化为纯语义模式

        参数:
            target: 光流目标坐标 [1, N, H, W, 2] 或 [N, H, W, 2]
            ii, jj: 边索引 [N]
            lambda_geo: 几何残差→不确定性的衰减系数
            max_geo_weight: 几何信号的最大权重上限
        """
        if not self.uncertainty_aware:
            return

        # 统一 target 形状为 [N, H, W, 2]
        if target.dim() == 5:
            target = target.squeeze(0)

        # 用优化后的位姿/深度计算重投影坐标
        coords, valid_mask = self.reproject(ii, jj)  # [N, H, W, 2], [N, H, W, 1]

        # 重投影残差范数
        residual = target - coords  # [N, H, W, 2]
        residual_norm = torch.norm(residual, dim=-1)  # [N, H, W]

        # 内点掩码：残差 < 3 * 每条边的中位数残差
        N, H, W = residual_norm.shape
        flat_res = residual_norm.reshape(N, -1)  # [N, H*W]
        median_res = flat_res.median(dim=1).values  # [N]
        inlier_mask = residual_norm < (3.0 * median_res[:, None, None])  # [N, H, W]
        inlier_mask = inlier_mask & valid_mask.squeeze(-1)

        # 几何不确定性：u_geo = 1 - exp(-λ||r||)，外点处归零
        u_geo = 1.0 - torch.exp(-lambda_geo * residual_norm)
        u_geo = u_geo * inlier_mask.float()

        # 自适应几何权重：内点率越高 → 几何信号越可靠 → 权重越高
        inlier_ratio = inlier_mask.float().mean()
        w_geo = max_geo_weight * inlier_ratio

        # 逐帧融合
        unique_ii = torch.unique(ii)
        for idx in unique_ii:
            edge_mask = (ii == idx)
            n_edges = edge_mask.sum()
            if n_edges == 0:
                continue

            # 聚合该帧作为源帧的所有边的几何不确定性
            u_geo_frame = u_geo[edge_mask].mean(dim=0)  # [H, W]
            u_sem_frame = self.uncertainties[idx]

            # 仅在有有效几何信号的像素处融合
            valid_fusion = inlier_mask[edge_mask].any(dim=0)
            u_fused = (1.0 - w_geo) * u_sem_frame + w_geo * u_geo_frame
            self.uncertainties[idx] = torch.where(valid_fusion, u_fused, u_sem_frame)

    @torch.no_grad()
    def visualize_uncertainty(self, target, weight, ii, jj, ...):
```

---

### 4.2 `src/factor_graph.py` — `update()` 中调用几何纠偏
**修改前：**

```python
# === 修改前 (study 分支, 原行 274-283) ===
            self.video.ba(target, weight, damping, ii, jj, t0, t1, 
                iters=itrs, lm=1e-4, ep=0.1, lr=self.video.cfg['tracking']['uncertainty_params']['lr'], 
                weight_decay=self.video.cfg['tracking']['uncertainty_params']['weight_decay'],
                motion_only=motion_only, 
                enable_update_uncer=enable_update_uncer, 
                enable_udba=enable_udba, 
                visualization_stage=visualization_stage)
        
            self.video.upsample(torch.unique(self.ii), upmask)
```

**修改后：**

```python
# === 修改后 (PlanA 分支) ===
            self.video.ba(
                target, weight, damping, ii, jj, t0, t1,
                iters=itrs, lm=1e-4, ep=0.1,
                lr=self.video.cfg['tracking']['uncertainty_params']['lr'],
                weight_decay=self.video.cfg['tracking']['uncertainty_params']['weight_decay'],
                motion_only=motion_only,
                enable_update_uncer=enable_update_uncer,
                enable_udba=enable_udba,
                visualization_stage=visualization_stage
            )

            # P2：几何残差纠偏
            if self.video.cfg['tracking']['uncertainty_params'].get('p2_geo_correction', False):
                self.video.apply_geometric_correction(target, ii, jj)

            # 第六步：对优化后的逆深度图上采样到原始分辨率
            self.video.upsample(torch.unique(self.ii), upmask)
```

---

### 4.3 `src/factor_graph.py` — `update_lowmem()` 中调用几何纠偏
**修改前：**

```python
# === 修改前 (study 分支, 原行 331-338) ===
            self.video.ba(target, weight, damping, self.ii, self.jj, t0, t1, 
                iters=itrs, lm=1e-5, ep=1e-2, lr=self.video.cfg['tracking']['uncertainty_params']['gba_lr'],
                weight_decay=self.video.cfg['tracking']['uncertainty_params']['gba_weight_decay'],
                motion_only=False, 
                enable_update_uncer=enable_update_uncer,
                enable_udba=enable_udba, 
                visualization_stage=visualization_stage)
        # print all edges with the format of (i, j)
```

**修改后：**

```python
# === 修改后 (PlanA 分支) ===
            self.video.ba(
                target, weight, damping, self.ii, self.jj, t0, t1,
                iters=itrs, lm=1e-5, ep=1e-2,
                lr=self.video.cfg['tracking']['uncertainty_params']['gba_lr'],
                weight_decay=self.video.cfg['tracking']['uncertainty_params']['gba_weight_decay'],
                motion_only=False,
                enable_update_uncer=enable_update_uncer,
                enable_udba=enable_udba,
                visualization_stage=visualization_stage
            )

            # P2：几何残差纠偏（低内存模式）
            if self.video.cfg['tracking']['uncertainty_params'].get('p2_geo_correction', False):
                self.video.apply_geometric_correction(target, self.ii, self.jj)

        # 如果启用调试，打印所有边并保存权重到文件
```

---

### 4.4 `configs/droid_w.yaml` — 基配置新增开关（默认关闭）
**修改前：**

```yaml
# === 修改前 (study 分支) ===
    enable_affine_transform: True
    enable_bidirectional_uncer: False
    
  force_keyframe_every_n_frames: 9
```

**修改后：**

```yaml
# === 修改后 (PlanA 分支) ===
    enable_affine_transform: True
    enable_bidirectional_uncer: False
    p2_geo_correction: False

  force_keyframe_every_n_frames: 9
```

---

### 4.5 `configs/Dynamic/DROIDW/droidw.yaml` — DROID-W 数据集启用
**修改前：**

```yaml
# === 修改前 (study 分支) ===
tracking:
  buffer: 560
  force_keyframe_every_n_frames: -1
  uncertainty_params:
    gamma_depth: 0.01
```

**修改后：**

```yaml
# === 修改后 (PlanA 分支) ===
tracking:
  buffer: 560
  force_keyframe_every_n_frames: -1
  uncertainty_params:
    gamma_depth: 0.01
    p2_geo_correction: True
```

## 五、使用方法
在数据集配置中启用：

```yaml
tracking:
  uncertainty_params:
    p2_geo_correction: True   # 启用 P2 几何纠偏
```

可调参数（在 `apply_geometric_correction` 方法签名中）：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `lambda_geo` | 5.0 | 残差→不确定性的衰减速率 |
| `max_geo_weight` | 0.25 | 几何信号最大权重 |


## 六、预期效果
+ **稳定运行阶段**：5-15% ATE 改善（几何残差有效纠偏语义不确定性）
+ **初始化阶段**：零退化（自动降级为纯语义模式）
+ **高动态场景**：改善显著（语义信号系统偏差大，几何纠偏价值高）
+ **低动态/静态场景**：改善有限（语义信号已足够准确）

## 七、与后续方案的关系
+ **P0（数值修复）**：修复 CUDA 内核的硬阈值问题，与 P2 正交可叠加
+ **P1（初始化保护）**：显式处理初始化阶段，P2 已有隐式保护（内点率门控），P1 可进一步加固
+ **P3（深度先验）**：处理深度噪声对不确定性的污染，与 P2 互补

