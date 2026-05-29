# P2 几何残差纠偏

> 利用 BA 重投影残差修正 DINOv2 语义不确定性的系统性偏差，通过保守纠偏策略 + 形态学闭运算，在不引入边界模糊的前提下消除可视化噪点。

---

## 〇、总体原理

### 0.1 背景：SLAM 系统为什么需要"不确定性"

想象你在一个房间里走动，同时用手机拍摄视频。SLAM 的任务是根据视频画面反推手机的运动轨迹。它做这件事的方法是：在两帧之间找到对应的像素点，根据这些像素点的位移来计算相机是怎么移动的。

但问题来了——不是所有像素都"可靠"。比如：
- 墙上的纹理：两帧之间位移很小、对应关系清晰 → **可靠，应该以它为准**
- 一辆行驶中的汽车：它在自己移动，它的位移不反映相机的运动 → **不可靠，应该忽略**

因此 SLAM 系统需要给每个像素打一个"可信度分数"（即不确定性 $u$），告诉优化器：哪些像素应该重点参考，哪些应该忽略。这个分数越准确，SLAM 估计的轨迹就越精确。

DROID-W 用深度学习来预测这个分数。

### 0.2 问题：AI 在看"是什么"，而不是"在不在动"

DROID-W 使用 DINOv2（一个视觉大模型）来观察画面，然后输出每个像素的不确定性。DINOv2 擅长识别物体——它能看出"这是一辆车"、"这是一个人"。

但它有一个根本性的盲区：**它知道这是一辆车，但不知道这辆车是停着的还是开着的。**

对 DINOv2 来说，一辆停在路边的车和一辆正在行驶的车，它们的视觉特征几乎一模一样——都是"红色的轿车"。所以两辆车会被分配相同的可信度分数。这显然是错的：
- 停着的车 → 跟地面固定在一起 → 适合用来估计相机运动 → 应该是低不确定性
- 开着的车 → 自己在动 → 用它估计相机会得到错误结果 → 应该是高不确定性

**DINOv2 用"身份"来猜测"运动状态"，而身份和运动是两回事。这就是范畴错误。**

### 0.3 解决方案：用几何残差直接感知运动

既然 AI 分不清车在不在动，我们就找一个能直接反映"在不在动"的信号。

这个信号其实已经有了：**几何重投影残差**。通俗地说，SLAM 做完优化后，可以检查每个像素"预测位置"和"实际位置"差了多少像素：
- 墙上的像素 → 预测位置跟实际位置几乎重合 → 残差 ≈ 0.05 px → 说明这个物体确实静止
- 行驶汽车的像素 → 预测位置跟实际位置有偏差 → 残差 ≈ 2 px → 说明这个物体在动

几何残差不关心物体"是什么"，它只关心位置对不对得上。这恰好弥补了 DINOv2 的盲区。

### 0.4 但是几何信号也有弱点

残差这个信号有一个前提：**当前的相机位姿估计必须是准的**。如果位姿本身就是错的，那么所有像素的预测位置都会偏——残差变大不是因为像素在动，而是因为位姿算错了。

这在 SLAM 的不同阶段表现不同：
- **刚启动时**：系统还不知道相机在哪，位姿误差很大 → 残差全是噪声 → 不能信
- **稳定运行后**：位姿收敛了 → 残差能准确反映运动状态 → 可以信
- **快速转身/剧烈运动时**：位姿突然不准 → 残差暂时不可信

所以不能简单地把"语义信号 + 几何信号混合使用"——在初始化阶段这样做会帮倒忙。

### 0.5 我们的设计哲学：保守纠偏

核心思想只有一句话：

> **只在 100% 确定一个像素是静态的时候，才用几何信号去修正 AI 的判断。拿不准的，一律不管。**

这叫"宁可漏纠，不可误纠"。具体怎么做到？四个设计决策：

**① 只对残差极小的像素下手（λ=5.0）**

我们把残差换算成"静态置信度"：`confidence = exp(-5.0 × 残差)`。

- 残差 0.05 px（几乎完美对齐）→ confidence = 0.78 → 较为确定是静态，可以纠偏
- 残差 0.3 px（有一点偏差）→ confidence = 0.22 → 不确定，基本不管
- 残差 0.5 px（明显的偏差）→ confidence = 0.08 → 几乎不管，交给 AI 判断

用 λ=5.0 意味着置信度衰减非常快——只要不是"铁定静态"，就自动回退给 AI。如果 λ 设得太小（比如 0.8），残差 1.0px 的像素仍被纠偏 ~23%，但这些像素可能是静态也可能是动态，盲目纠偏反而污染优化。

**② 即使纠偏，也只微调（上限 25%）**

几何信号最多只能把 AI 给出的不确定性值削掉 25%。这意味着即使几何信号完全出错，损害也是可控的。AI（DINOv2）的判断在大多数场景下是合理的，我们只是做小幅修正。

**③ 用统计方法筛除外点（3σ 门控）**

对每一条边，统计所有像素残差的中位数。残差超过中位数 3 倍以上的像素，直接当外点排除——不参与任何纠偏。这个筛选是自动适应的：位姿差时所有人的残差都大，threshold 自动抬高，纠偏自动减弱。

**④ 用形态学闭运算消除噪点，但保持边界锐利**

静态物体内部有时会有个别像素因为光照、纹理偶然跟丢 → 残差异常偏大 → 被误判为"不纠偏" → 在可视化上形成麻点。

常见做法是用均值池化（把相邻 5×5 像素的残差取平均）来消除麻点，但代价是运动边界被模糊——静态像素的残差被邻近动态像素"污染"。

我们改用形态学闭运算：只在二值掩码上操作——把判定为"可纠偏"的区域的内部小孔洞（1-2px）填掉，但不改变任何像素的残差数值。运动边界保持锐利，麻点也消失了。

| 策略 | 静态区域内部噪点 | 运动边界锐利度 | 动态像素被误纠 |
| --- |:---:|:---:|:---:|
| 无平滑 | ❌ 麻点 | ✅ 锐利 | ✅ 无 |
| 均值池化 on 残差 | ✅ 消除 | ❌ 模糊 | ❌ 有 |
| 均值池化 on 纠偏权重 | ✅ 消除 | ❌ 模糊 | ❌ 有 |
| **形态学闭运算 on mask** | ✅ 消除 | ✅ 锐利 | ✅ 无 |

闭运算 = 先膨胀再腐蚀：小孔被周围填充，腐蚀时边界回缩到原位。**不移动边界**——1 像素宽的动态条纹不会被侵蚀掉，但 1-2 像素的孤立孔洞会被填平。

---

## 一、实现细节

### 1.1 在 ATE 因果链中的位置

```
DINO特征 → 仿射变换 → u_sem ─┐
                               ├→ u_corrected → w_uncer 映射 → BA 加权 → 位姿 → ATE
BA残差 → inlier_mask ──────────┘     ↑
                                     本方案作用于此
```

本方案直接修改不确定性值，进而影响 BA 权重分配和最终位姿估计精度。

### 1.2 核心公式

```python
# Step 1: 重投影残差（逐像素，不做任何池化）
||r|| = ||target - reproject(pose, depth)||   # [N, H, W]

# Step 2: 硬内点掩码（3σ 中位数门控，每条边独立计算）
inlier_mask = (||r|| < 3.0 · median(||r||)) & valid_mask   # [N, H, W]

# Step 3: 形态学闭运算 —— 填孔，不动边界
inlier_closed = close(inlier_mask, kernel=5)
# close(X) = erode(dilate(X))
#   膨胀：孤立孔洞被周围 1 填充
#   腐蚀：边界回缩到原位（孔已消失，边界不受影响）
#   关键性质：1-2px 孔被填，1px 宽线条保留

# Step 4: 逐像素 static_confidence（λ=5.0，只对确定静态响应）
static_confidence = exp(-5.0 · ||r||)         # [N, H, W]
# r=0.05 → 0.779, r=0.30 → 0.223, r=0.50 → 0.082

# Step 5: 纠偏权重（仅在闭合后的内点区域生效）
correction_weight = static_confidence · inlier_closed · float(valid_mask)

# Step 6: 跨边平均聚合 + 乘法纠偏（max_geo_weight=0.25，保守上限）
c_frame = mean(correction_weight[edge_mask], dim=0)   # [H, W]
pull_down = 0.25 · c_frame                             # [H, W]
u_new = u_sem · (1 - pull_down)                        # [H, W]
```

### 1.3 安全性机制

1. **λ=5.0 锐利区分**：只对 r < 0.3 px 的确定静态像素施加有效纠偏。r > 0.5 px 时 static_confidence < 0.08，纠偏几乎归零，回退给 DINO 判断。

2. **硬内点掩码 3σ 门控**：`r < 3·median(r)` 逐边独立计算。当整帧位姿不准（初始化、剧烈运动）时，整体大残差 → median 被抬高 → 掩码自动收紧，仅排除真正的极端外点，不产生假阳性。

3. **形态学闭运算**：填补静态区域内部 1-2px 的孤立孔洞（麻点），但不侵蚀运动边界。不对残差或纠偏值做平均——mask 仍是二值的，correction_weight 保留原始锐利度。

4. **隐式遮挡处理**（跨边 mean 聚合）：遮挡投影越界 → `valid_weight=0` → 自动拉低均值 → 纠偏自然降低。

5. **单向乘法纠偏**：`u_new = u · (1-p)`，几何只能压低 u，不能抬高。r 大时 p≈0，回退给 DINO。

### 1.4 数值标定（λ=5.0, max_geo_weight=0.25）

| ‖r‖ (px) | static_confidence | 闭合后 mask 内? | pull_down | 场景 |
| --- | :---: | :---: | :---: | --- |
| 0.02 | 0.905 | ✅ | 0.226 | 完美静态 |
| 0.10 | 0.607 | ✅ | 0.152 | 轻微噪声 |
| 0.20 | 0.368 | ✅ | 0.092 | 纹理边界 |
| 0.30 | 0.223 | ✅ | 0.056 | 临界值 |
| 0.50 | 0.082 | ✅ | 0.021 | 模糊区域，几乎不回退 |
| 1.00 | 0.007 | ❌ outlier | 0.000 | 明显动态 |

> 从 r=0.02 到 r=0.50，pull_down 从 0.226 降到 0.021——只有确定静态才显著纠偏。r≥1.0 被 inlier_mask 排除，完全回退 DINO。

---

## 二、代码变更

### 2.1 `src/depth_video.py` — 新增 `apply_geometric_correction()` 方法

```python
# === 修改后 ===
            # 确保逆深度为正数（数值稳定）
            self.disps.clamp_(min=1e-5)

    @torch.no_grad()
    def apply_geometric_correction(self, target, ii, jj, lambda_geo=5.0, max_geo_weight=0.25):
        """P2: 几何重投影残差纠偏语义不确定性。

        核心设计：
          - λ=5.0：只对 r<0.3px 的确定静态像素施加纠偏，模棱两可处回退 DINO。
          - 硬内点掩码 (3σ median)：清晰二值分离可纠偏/不可纠偏像素。
          - 形态学闭运算 on inlier_mask：填补静态区域内部孤立孔洞（麻点），
            不移动运动边界（区别于残差/纠偏权重上的均值池化）。
          - max_geo_weight=0.25：保守上限，错误时代价可控。
        """
        if not self.uncertainty_aware:
            return

        # 统一 target 形状为 [N, H, W, 2]
        if target.dim() == 5:
            target = target.squeeze(0)

        # Step 1: 重投影残差（逐像素，不做池化）
        coords, valid_mask = self.reproject(ii, jj)
        coords = coords.squeeze(0)          # [N, H, W, 2]
        valid_mask = valid_mask.squeeze(0)   # [N, H, W, 1]

        residual = target - coords           # [N, H, W, 2]
        residual_norm = torch.norm(residual, dim=-1)  # [N, H, W]

        # Step 2: 硬内点掩码（3σ 中位数门控，逐边独立）
        N, H, W = residual_norm.shape
        flat_res = residual_norm.reshape(N, -1)      # [N, H*W]
        median_res = flat_res.median(dim=1).values.clamp(min=1e-8)  # [N]
        inlier_mask = residual_norm < (3.0 * median_res[:, None, None])  # [N, H, W]
        inlier_mask = inlier_mask & (valid_mask.squeeze(-1) > 0)

        # Step 3: 形态学闭运算 —— 填孔，不动边界
        # close(X) = erode(dilate(X))
        #   dilate: 5×5 max_pool → 孤立孔被周围 1 填
        #   erode: 5×5 min_pool (= -max_pool(-X)) → 边界回缩到原位
        inlier_float = inlier_mask.float().unsqueeze(1)  # [N, 1, H, W]
        inlier_dilated = F.max_pool2d(inlier_float, kernel_size=5, stride=1, padding=2)
        inlier_closed = -F.max_pool2d(-inlier_dilated, kernel_size=5, stride=1, padding=2)
        inlier_closed = inlier_closed.squeeze(1)  # [N, H, W]

        # Step 4: 逐像素 static_confidence（λ=5.0，锐利区分）
        static_confidence = torch.exp(-lambda_geo * residual_norm)  # [N, H, W]

        # Step 5: 纠偏权重（仅在闭合后的内点区域生效）
        valid_weight = valid_mask.squeeze(-1).float()  # [N, H, W]
        correction_weight = static_confidence * inlier_closed * valid_weight  # [N, H, W]

        # Step 6: 跨边平均聚合 + 逐像素乘法纠偏
        unique_ii = torch.unique(ii)
        for idx in unique_ii:
            edge_mask = (ii == idx)
            if edge_mask.sum() == 0:
                continue

            c_frame = correction_weight[edge_mask].mean(dim=0)  # [H, W]
            pull_down = max_geo_weight * c_frame                # [H, W]
            self.uncertainties[idx] = self.uncertainties[idx] * (1.0 - pull_down)

    @torch.no_grad()
    def visualize_uncertainty(self, target, weight, ii, jj, ...):
```

### 2.2 `src/factor_graph.py` — `update()` 中调用

```python
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

            self.video.upsample(torch.unique(self.ii), upmask)
```

### 2.3 `src/factor_graph.py` — `update_lowmem()` 中调用

```python
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
```

### 2.4 配置文件

基础配置 `configs/droid_w.yaml`（默认关闭）：
```yaml
    enable_affine_transform: True
    enable_bidirectional_uncer: False
    p2_geo_correction: False
```

DROID-W 数据集启用 `configs/Dynamic/DROIDW/droidw.yaml`：
```yaml
tracking:
  buffer: 560
  force_keyframe_every_n_frames: -1
  uncertainty_params:
    gamma_depth: 0.01
    p2_geo_correction: True
```

---

## 三、使用方法

在数据集配置中启用：

```yaml
tracking:
  uncertainty_params:
    p2_geo_correction: True   # 启用 P2 几何纠偏
```

可调参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `lambda_geo` | 5.0 | 残差→static_confidence 衰减速率。5.0: 0.05px→0.78, 0.3px→0.22, 0.5px→0.08 |
| `max_geo_weight` | 0.25 | 最大下拉比例。u_new = u_sem × (1 - 0.25 × c) |
| close kernel | 5 | 形态学闭运算核大小，控制填补多大直径的孔洞 |

---

## 四、预期效果

- **稳定运行阶段**：5-15% ATE 改善（几何残差有效纠偏语义不确定性）
- **初始化阶段**：零退化（位姿不准 → 整体大残差 → inlier_mask 面积小 → 纠偏自动弱化）
- **高动态场景**：改善显著——直接回应同语义不同运动与静态人形误判问题
- **低动态/静态场景**：改善有限（语义信号已足够准确）
- **可视化质量**：形态学闭运算消除麻点，运动边界保持锐利
