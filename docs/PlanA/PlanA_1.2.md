# PlanA_1: P2 几何残差纠偏
> 实现 RESEARCH.md §4.5「几何残差作为不确定性纠偏信号」。将 BA 重投影残差作为语义不确定性的**纠偏信号**（非主导信号），在 BA 优化后自适应融合。
>

---

## 一、问题定位
DROID-W 的不确定性估计完全依赖 DINOv2 语义特征的仿射映射（RESEARCH.md §2.2）。这存在一个**范畴错误**（RESEARCH.md §3.1）：DINOv2 特征编码物体的身份（"是什么"），而非运动状态（"是否在动"）。静止汽车与行驶汽车在特征空间中几乎不可区分——这就是全局仿射变换无法为同语义不同运动状态的物体分配不同不确定性的根本原因。

几何重投影残差携带了运动状态的直接信息——静态像素的 BA 残差小，动态/误匹配像素的残差大。但如 RESEARCH.md §3.5 所述，几何信号在 SLAM 不同阶段质量差异巨大：

+ **初始化阶段**：位姿不准 → 几何残差噪声 > 信号 → 直接融合会恶化 ATE
+ **稳定运行阶段**：位姿收敛 → 几何残差可靠 → 可提供有效纠偏
+ **快速运动/回环后**：位姿突变 → 几何残差暂时不可靠

P2 的设计必须解决这个矛盾：几何信号有价值，但在不同阶段可靠性不同。

## 二、设计原则
与 RESEARCH.md §5.2 方向一（多源不确定性融合）的**本质区别**：

| 维度 | 多源融合方案 | P2（本方案） |
| --- | --- | --- |
| 几何信号角色 | 与语义"平权"融合 | 仅做"纠偏"（权重上限 0.25） |
| 外点处理 | 未明确 | 外点几何信号自动归零 |
| 初始化安全 | 时间常数调度 `w_geo(t)` | 基于内点率自适应（零风险） |
| 可学习性 | 融合权重可学习 | 固定规则（可验证、可解释） |
| ATE 安全性 | 初始化阶段可能恶化 | 初始化自动退化为纯语义模式 |


P2 在整个改进体系中（RESEARCH.md §4.2）的定位：

| 方案 | ATE 收益 | 改动量 | P2 与它的关系 |
| --- | --- | --- | --- |
| P0 数值修复 | 15-25% | ~20行 CUDA | 正交可叠加：P0 修复 CUDA 硬阈值，P2 引入几何信号 |
| P1 初始化保护 | 10-15% | ~50行 | P2 已有隐式保护（内点率门控），P1 可进一步加固 |
| P3 深度先验 | 5-10% | ~150行 | 互补：P2 处理运动信号，P3 处理深度信号 |


## 三、实现细节
### 3.1 在 ATE 因果链中的位置
```plain
DINO特征 → 仿射变换 → u_sem ─┐
                               ├→ u_fused → w_uncer 映射 → BA 加权 → 位姿 → ATE
BA残差 → u_geo ────────────────┘     ↑
                                     P2 作用于此
```

P2 直接修改不确定性值，进而影响 `w_uncer` 映射（RESEARCH.md §2.3）、BA 权重分配、最终位姿估计精度。

### 3.2 核心公式（连续乘法纠偏）
```python
# 重投影残差范数 + 空间平滑
||r|| = ||target - reproject(pose, depth)||
||r||_smooth = AvgPool2d(||r||, kernel=5)  # 5×5 均值滤波抑制像素级残差噪声

# 静态置信度：exp(-λ · 平滑残差)，1.0=确定静态，0=确定非静态
static_confidence = exp(-λ · ||r||_smooth)

# 软内点权重：sigmoid 在 3x 中位残差附近平滑过渡，替代二值内点掩码
inlier_weight = sigmoid((1.0 - ||r||_smooth / (3.0 · median(||r||_smooth))) · 5.0)

# 有效像素的浮点权重（投影越界/深度无效 → 权重=0）
valid_weight = float(valid_mask > 0)

# 连续纠偏权重：三个因子均为连续值 → 无斑点伪影
# 动态像素 static_confidence ≈ 0 → 纠偏自动归零
# 静态像素 static_confidence ≈ 1 → 强力下拉
correction_weight = static_confidence · inlier_weight · valid_weight

# 自适应纠偏强度：内点加权率越高 → 几何整体越可靠
base_strength = max_geo_weight · mean(inlier_weight)
pull_down = base_strength · correction_weight

# 连续乘法纠偏：所有像素统一施加，无需 torch.where 或二值掩码
u_new = u_sem · (1 - pull_down)
```

**与旧版融合式设计的本质区别**：

| 维度 | 旧版（对称融合） | 新版（连续纠偏） |
| --- | --- | --- |
| 几何信号角色 | u_geo 参与计算新不确定性 | static_confidence 作为连续下拉权重 |
| 对动态像素 | u_geo≈1.0 + 小权重 → 轻微上拉 | static_confidence≈0 → 纠偏自动归零 |
| 对静态像素 | u_geo≈0.5 + 小权重 → 轻微下拉 | static_confidence≈1 → 连续强力下拉 |
| 数学形式 | 加法融合 u=(1-w)·u_sem + w·u_geo | 连续乘法 u=u_sem·(1-pull_down)，无二值掩码 |
| 空间连续性 | N/A | 所有因子连续可微 → 无斑点伪影 |
| λ 取值 | 5.0（饱和快，无区分力） | 0.8（0.05px→sc=0.96, 2px→sc=0.20） |


### 3.3 安全性机制
1. **空间平滑**（防止像素级噪声）：`F.avg_pool2d(||r||, kernel=5)` 在计算 static_confidence 前对残差做 5×5 均值滤波。复杂形状静态物体的个别像素易因光照/遮挡跟丢产生残差尖峰——平滑后邻域信息填补，同一静态表面纠偏力度一致
2. **静态置信度连续门控**（替代二值阈值）：`static_confidence = exp(-λ||r||)` 作为连续下拉权重。动态物体（大残差）confidence≈0 → 纠偏自动归零，静态物体（小残差）confidence≈1 → 连续强力下拉
3. **软内点权重**：`inlier_weight = sigmoid((1 - r/(3·median))·5)` 在 3x 中位残差附近平滑过渡，替代二值 `inlier_mask`
4. **帧级可靠性门控**：`base_strength = max_geo_weight × mean(inlier_weight)`，位姿不准时内点加权率低 → 自动退化
5. **连续乘法纠偏**：`u_new = u_sem × (1 - pull_down)` 对所有像素统一施加，无需 `torch.where` 分段

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
    def apply_geometric_correction(self, target, ii, jj, lambda_geo=0.8, max_geo_weight=0.5):
        """P2: 使用几何重投影残差纠正语义不确定性的系统性偏差。

        核心设计（RESEARCH.md §4.5）：
          - 连续纠偏：static_confidence = exp(-λ||r||) 自然提供从 1.0（静态）
            到 0.0（动态）的连续过渡，无需硬阈值。
          - 动态像素（大残差）static_confidence≈0 → 纠偏自动归零。
          - 静态像素（小残差）static_confidence≈1 → 强力下拉。
          - 所有像素施加连续纠正，无二值掩码分段，避免"斑点状"伪影。
        """
        if not self.uncertainty_aware:
            return

        # 统一 target 形状为 [N, H, W, 2]
        if target.dim() == 5:
            target = target.squeeze(0)

        # 用优化后的位姿/深度计算重投影坐标
        coords, valid_mask = self.reproject(ii, jj)
        coords = coords.squeeze(0)  # [N, H, W, 2]
        valid_mask = valid_mask.squeeze(0)  # [N, H, W, 1]

        # 重投影残差范数
        residual = target - coords  # [N, H, W, 2]
        residual_norm = torch.norm(residual, dim=-1)  # [N, H, W]

        # 空间平滑：5×5 均值滤波抑制像素级残差噪声
        # 复杂静态物体上个别像素易因光照/遮挡跟丢，产生残差尖峰 → 斑点
        residual_norm = F.avg_pool2d(
            residual_norm.unsqueeze(1),
            kernel_size=5, stride=1, padding=2
        ).squeeze(1)

        # 静态置信度：exp(-λ||r||)，自身就是平滑的连续权重——无需硬阈值
        static_confidence = torch.exp(-lambda_geo * residual_norm)

        # 软内点权重：sigmoid 在 3x 中位残差附近平滑过渡，替代二值内点掩码
        N, H, W = residual_norm.shape
        flat_res = residual_norm.reshape(N, -1)
        median_res = flat_res.median(dim=1).values.clamp(min=1e-8)
        deviation = residual_norm / (3.0 * median_res[:, None, None])
        inlier_weight = torch.sigmoid((1.0 - deviation) * 5.0)

        # 有效像素的浮点权重（投影越界/深度无效 → 权重=0）
        valid_weight = valid_mask.squeeze(-1).float()  # [N, H, W]

        # 自适应纠偏强度：内点加权率越高 → 几何整体越可靠 → 下拉力度越大
        inlier_ratio = inlier_weight.mean()
        base_strength = max_geo_weight * inlier_ratio

        # 逐帧连续纠偏
        unique_ii = torch.unique(ii)
        for idx in unique_ii:
            edge_mask = (ii == idx)
            if edge_mask.sum() == 0:
                continue

            # 跨边聚合：取平均值（连续值，不会产生二值 .any() 的拼接痕迹）
            frame_static_conf = static_confidence[edge_mask].mean(dim=0)  # [H, W]
            frame_inlier_weight = inlier_weight[edge_mask].mean(dim=0)    # [H, W]
            frame_valid = valid_weight[edge_mask].mean(dim=0)             # [H, W]

            # 连续纠偏权重：static_confidence × inlier_weight × valid
            # 动态像素 → static_confidence≈0 → 纠偏自动归零
            correction_weight = frame_static_conf * frame_inlier_weight * frame_valid

            u_sem_frame = self.uncertainties[idx]
            pull_down = base_strength * correction_weight
            self.uncertainties[idx] = u_sem_frame * (1.0 - pull_down)

    @torch.no_grad()
    def visualize_uncertainty(self, target, weight, ii, jj, ...):
```

软内点权重：认为大于 3 倍中位数残差为外点，降低其权重。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1778554869607-1009feb7-9c7a-454c-a70c-aa4a4fc07a41.png)

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
| `lambda_geo` | 0.8 | 残差→static_confidence 衰减速率。0.05px→0.96, 0.2px→0.85, 2px→0.20 |
| `max_geo_weight` | 0.5 | 对语义不确定性的最大下拉比例。u_new = u_sem × (1 - 0.5 × sc) |


**数值标定**（λ=0.8, max_geo_weight=0.5, base_strength=0.5）：

| ‖r‖ (px) | static_confidence | inlier_weight | correction_weight | pull_down | 场景 |
| --- | --- | --- | --- | --- | --- |
| 0.02 | 0.984 | ~1.000 | 0.984 | 0.492 | 完美静态 |
| 0.10 | 0.923 | ~1.000 | 0.923 | 0.462 | 轻微噪声 |
| 0.20 | 0.852 | ~1.000 | 0.852 | 0.426 | 纹理/边界 |
| 0.28 | 0.799 | ~0.994 | 0.794 | 0.397 | 原硬阈值边界 |
| 0.50 | 0.670 | ~0.880 | 0.590 | 0.295 | 中度残差 |
| 2.00 | 0.202 | ~0.006 | 0.001 | 0.001 | 明显动态 |


> 与旧版的关键区别：correction_weight 从 0.984 到 0.001 连续变化，不存在二值"触发/不触发"边界。原 0.28px 处的硬截断（✗→✓）现在变为自然的 0.397 中间值。
>

## 六、预期效果
+ **稳定运行阶段**：5-15% ATE 改善（几何残差有效纠偏语义不确定性）
+ **初始化阶段**：零退化（自动降级为纯语义模式）
+ **高动态场景**：改善显著——直接回应 RESEARCH.md §3.7 的同语义不同运动与静态人形误判问题
+ **低动态/静态场景**：改善有限（语义信号已足够准确）

## 七、在 ATE 优化路线图中的位置
按 RESEARCH.md §4.2 的推荐执行顺序：

```plain
Phase 1 (P0)  →  Phase 2 (P1)  →  Phase 3 (P2) ← 本方案
   CUDA修复        初始化保护        几何纠偏
```

+ **P2 依赖于 P0**：在 P0 软化 `w_uncer` 映射后，几何纠偏的效果更容易体现（不再有悬崖效应吞噬中等程度的不确定性改善）
+ **P2 与 P1 互补**：P1 显式保护初始化阶段，P2 基于内点率门控提供隐式保护——两者叠加可覆盖更全面的安全场景
+ **P2 与 P3 互补**：P2 处理运动信号维度（动态 vs 静态），P3 处理深度信号维度（可靠 vs 不可靠几何）

## 八、结果对比
### 8.1 数值对比
| **方案** | **场景** | **ATE** |
| --- | --- | --- |
| 原论文方案<br/><font style="background-color:#FBDE28;">无卷积二值化纠偏</font><br/>卷积连续纠偏 | downtown1 | 0.16031271438077396<br/><font style="background-color:#FBDE28;">0.1560757491452484</font><br/>0.15702433386865766 |
| 原论文方案<br/><font style="background-color:#FBDE28;">无卷积二值化纠偏</font><br/>卷积连续纠偏 | downtown2 | 0.24360698871648637<br/><font style="background-color:#FBDE28;">0.2277995958690717</font><br/>0.25020661321772275 |
| 原论文方案<br/><font style="background-color:#FBDE28;">无卷积二值化纠偏</font><br/>卷积连续纠偏 | downtown3 | 0.19989616914705813<br/><font style="background-color:#FBDE28;">0.19916306102800732</font><br/>0.20128162329230032 |
| 原论文方案<br/>无卷积二值化纠偏<br/><font style="background-color:#FBDE28;">卷积连续纠偏</font> | downtown4 | 0.33343853205297774<br/>0.29739478818153536<br/><font style="background-color:#FBDE28;">0.28805398297631685</font> |
| <font style="background-color:#FBDE28;">原论文方案</font><br/>无卷积二值化纠偏<br/>卷积连续纠偏 | downtown5 | <font style="background-color:#FBDE28;">1.6719782222797126</font><br/>1.6769190761381154<br/>1.6805289018011111 |
| 原论文方案<br/><font style="background-color:#FBDE28;">无卷积二值化纠偏</font><br/>卷积连续纠偏 | downtown6 | 0.4280681103502662<br/><font style="background-color:#FBDE28;">0.3774183972492357</font><br/>0.4165367378233989 |
| <font style="background-color:#FBDE28;">原论文方案</font><br/>无卷积二值化纠偏<br/>卷积连续纠偏 | downtown7 | <font style="background-color:#FBDE28;">0.06445414891250303</font><br/>0.08556674435281536<br/>0.08425320721238738 |


### 8.3 可视化对比
#### 8.3.1 downtown1：同一时刻同类物体 运动与静态 纠偏对比
<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1778556615921-4f4c3560-4c1e-44eb-ad93-39e0fddb9a15.png)

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1778556641832-0aa48531-9950-4375-bc95-125718183bbe.png)

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1778556672429-0f4cd320-6130-46b7-91f3-1c07b821abc3.png)

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1778556833031-c1a660f8-21a2-4c82-89bc-32c3dc649411.png)

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1778556863463-945a12ab-1e9b-48d2-9017-88c2c415be43.png)

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1778556897414-31302712-9147-40e9-b32e-58b86383e748.png)

#### 8.3.2 downtown6：复杂静态物体被错误识别为高不确定性 纠偏对比
<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1778557027333-f238747b-6dbe-4f5d-a8f7-99945ab6b6db.png)

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1778557051924-9f527778-10c7-45fa-9dba-2f7514ea38c8.png)

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/45861457/1778557091701-f10d2337-aaec-49f5-9f5f-a8c9d17fa83f.png)

## 九、参考文献
+ RESEARCH.md §2.2 — 不确定性估计全链路
+ RESEARCH.md §2.3 — w_uncer 映射与悬崖效应
+ RESEARCH.md §3.1 — 范畴错误（语义特征 ≠ 运动信息）
+ RESEARCH.md §3.4 — 梯度不对称性（不确定性易升难降）
+ RESEARCH.md §3.7 — 两种典型失效模式
+ RESEARCH.md §4.1 — 不确定性→ATE 因果链
+ RESEARCH.md §4.2 — P0-P3 方案优先级总览
+ RESEARCH.md §4.5 — P2 完整设计
+ RESEARCH.md §6.1 — 避免可视化改善但 ATE 不变的陷阱

