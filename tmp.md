# PlanA 几何纠偏方案对比

## 1. 概述

两个方案都试图用**几何重投影残差**来纠正语义不确定性的系统性偏差（"语义上看着像动态，但实际上几何是静态的"），但在**纠偏哲学、融合方式、平滑策略**上有本质区别。

---

## 2. 方案一（PlanA 分支，`depth_video.py:697`）

### 核心思想：**乘法下拉（Multiplicative Pull-Down）**

> 几何信号的作用是"降低"语义不确定性，而非"替换"它。动态像素自动免疫纠偏。

### 公式

定义重投影残差范数（经 5×5 空间平滑后）：

$$\tilde{r} = \text{AvgPool}_{5\times5}\big(\|\mathbf{x}_{\text{target}} - \mathbf{x}_{\text{reproj}}\|_2\big)$$

**静态置信度**（高残差 → 置信度低 → 不纠偏）：

$$s = e^{-\lambda_1 \tilde{r}}, \quad \lambda_1 = 0.8$$

**软内点权重**（在 $3\times\text{median}(\tilde{r})$ 附近 sigmoid 平滑过渡）：

$$w_{\text{in}} = \sigma\Big(5 \cdot \big(1 - \frac{\tilde{r}}{3 \cdot \text{median}(\tilde{r})}\big)\Big)$$

**逐像素纠偏权重**（三因子连乘）：

$$c = s \cdot w_{\text{in}} \cdot w_{\text{valid}}$$

**帧级自适应强度**（内点率越高 → 几何越可靠 → 下拉越猛）：

$$\alpha = \mathbb{E}[w_{\text{in}}], \quad \beta = \alpha \cdot w_{\text{geo}}^{\max}, \quad w_{\text{geo}}^{\max} = 0.5$$

**最终不确定度更新**：

$$\boxed{u_{\text{new}} = u_{\text{sem}} \cdot \big(1 - \beta \cdot \bar{c}_{\text{frame}}\big)}$$

其中 $\bar{c}_{\text{frame}} = \mathbb{E}_{\text{edges}}[c]$ 是该帧所有边的平均纠偏权重。

### 关键特性

| 特性 | 取值/策略 |
|------|----------|
| 残差→置信度映射 | $e^{-\lambda r}$，连续、可微 |
| 空间平滑 | 5×5 均值池化 |
| 内点判定 | 软 sigmoid（连续，无硬阈值） |
| 融合方式 | **乘法**：$u_{\text{sem}} \times (1 - \text{pull\_down})$ |
| 动态像素行为 | $s \approx 0$ → pull_down ≈ 0 → $u_{\text{new}} \approx u_{\text{sem}}$（自动免疫） |
| 静态像素行为 | $s \approx 1$ → 强力下拉 → $u_{\text{new}} \ll u_{\text{sem}}$ |
| 几何权重上限 | 0.5 |
| $\lambda$ | 0.8（温和衰减） |

---

## 3. 方案二（用户提供，`RESEARCH_E §4.4`）

### 核心思想：**插值融合（Interpolation/Blending）**

> 用几何不确定性 $u_{\text{geo}}$ 与语义不确定性 $u_{\text{sem}}$ 做加权平均，几何权重受内点率门控。

### 公式

定义重投影残差范数（无空间平滑）：

$$r = \|\mathbf{x}_{\text{target}} - \mathbf{x}_{\text{reproj}}\|_2$$

**几何不确定性**：

$$u_{\text{geo}} = 1 - e^{-\lambda_2 r}, \quad \lambda_2 = 5.0$$

**硬内点掩码**：

$$M_{\text{in}} = \big(r < 3 \cdot \text{median}(r)\big) \land M_{\text{valid}}$$

**帧级自适应几何权重**：

$$\beta = w_{\text{geo}}^{\max} \cdot \mathbb{E}[M_{\text{in}}], \quad w_{\text{geo}}^{\max} = 0.25$$

**逐帧融合**：

$$\bar{u}_{\text{geo}} = \mathbb{E}_{\text{edges}}[u_{\text{geo}} \cdot M_{\text{in}}]$$

$$u_{\text{fused}} = (1 - \beta) \cdot u_{\text{sem}} + \beta \cdot \bar{u}_{\text{geo}}$$

$$\boxed{u_{\text{new}} = \begin{cases} u_{\text{fused}} & \text{if } \bigvee_{\text{edges}} M_{\text{in}} = 1 \\ u_{\text{sem}} & \text{otherwise} \end{cases}}$$

### 关键特性

| 特性 | 取值/策略 |
|------|----------|
| 残差→不确定性映射 | $1 - e^{-\lambda r}$，连续但外点处硬归零 |
| 空间平滑 | 无 |
| 内点判定 | 硬二值掩码 |
| 融合方式 | **插值**：$(1-\beta)u_{\text{sem}} + \beta u_{\text{geo}}$ |
| 动态像素行为 | $u_{\text{geo}} \approx 1$（高不确定），但被 $M_{\text{in}}=0$ 硬截断 → 回退 $u_{\text{sem}}$ |
| 静态像素行为 | $u_{\text{geo}} \approx 0$ → $u_{\text{fused}} \approx (1-\beta)u_{\text{sem}}$（下拉但有限） |
| 几何权重上限 | 0.25 |
| $\lambda$ | 5.0（陡峭衰减） |

---

## 4. 核心差异对比

| 维度 | 方案一（PlanA） | 方案二 |
|------|:---:|:---:|
| **融合哲学** | 乘法纠偏：几何"压低"语义 | 插值混合：几何"补充"语义 |
| **几何角色** | 纠偏信号（只降不升） | 替代信号（可降可升） |
| **更新公式** | $u \leftarrow u \cdot (1-p)$ | $u \leftarrow (1-\beta)u + \beta u_{\text{geo}}$ |
| **动态像素** | 自然免疫（$p \to 0$） | 硬掩码回退+硬截断 |
| **连续性** | 全连续（sigmoid + exp + 均值） | 部分离散（hard mask + where） |
| **空间平滑** | 有（抑制斑点） | 无 |
| **$\lambda$ 值** | 0.8（温和） | 5.0（陡峭） |
| **几何上限** | 0.5（更强纠偏） | 0.25（更保守） |
| **初始化鲁棒性** | 低内点率 → $\beta$ 小 → 自动退化为纯语义 | 低内点率 → $\beta$ 小 → 自动退化为纯语义 |
| **伪影风险** | 低（连续过渡） | 中（硬掩码可能在边缘产生斑点） |

---

## 5. 关键权衡

### 方案一的核心优势
- **连续性**：所有操作都是连续的（sigmoid、exp、mean），没有硬阈值，避免了"同一物体上一半纠偏一半不纠偏"的斑点伪影。
- **乘法语义清晰**：几何信号只能"降低"不确定性，不能"制造"不确定性。这意味着几何不可靠时最坏情况是不纠偏（$u$ 不变），而不会把 $u$ 改大。
- **空间平滑**：5×5 均值滤波在 H/8 分辨率下约等效 40px 感受野，抹平了单个像素的光照/遮挡噪声。

### 方案二的核心优势
- **$\lambda=5.0$ 更陡峭**：对静态/动态的区分更锐利，在几何质量极高时能更快分离动静。
- **保守的上限**：max_geo_weight=0.25 意味着几何最多影响 25%，更依赖语义主导，降低了错误几何的破坏性。
- **硬内点掩码更安全**：外点处直接回退纯语义，不会因"半吊子"信号污染不确定度。

### 本质差异
方案一是**"信任语义，几何辅助证伪"**（semantic-first, geometry-corrects）；方案二是**"语义和几何互相校验"**（semantic-geometry consensus）。前者更激进（上限 0.5），后者更保守（上限 0.25）。

---

## 6. 逐像素 vs 全局调制

方案一（PlanA）代码中 `pull_down = base_strength * correction_weight` 虽然 `[H, W]` 逐像素，但 `base_strength = max_geo_weight * mean(inlier_weight)` 是一个**全局标量**，导致像素间被不合理耦合。

### 当前公式（有全局耦合）

$$\alpha = \frac{1}{N \cdot H \cdot W} \sum_{n,i,j} w_{\text{in}}[n,i,j]$$

$$p[h,w] = w_{\text{geo}}^{\max} \cdot \alpha \cdot s[h,w] \cdot w_{\text{in}}[h,w] \cdot w_{\text{valid}}[h,w]$$

问题：像素 A 的纠偏力度被像素 B 的几何质量影响。

### 纯逐像素公式（推荐）

$$\boxed{p[h,w] = w_{\text{geo}}^{\max} \cdot s[h,w] \cdot w_{\text{in}}[h,w] \cdot w_{\text{valid}}[h,w]}$$

```python
# 删除全局调制，直接逐像素
pull_down = max_geo_weight * correction_weight  # [H, W]
self.uncertainties[idx] = u_sem_frame * (1.0 - pull_down)
```

理由：
- 外点像素 $s \approx 0$ 已天然免疫纠偏，无需全局 `inlier_ratio` 叠加保护
- 全局调制会惩罚几何质量好的像素（如静态背景被动态前景拉低内点率）
- `max_geo_weight` 本身就是硬上限，不需要额外缩放

---

## 7. 推荐实现方案

### 7.1 问题重述

在 DROID-W 的 BA 优化结束后，我们同时拥有两套信号：

| 信号 | 来源 | 含义 |
|------|------|------|
| $u_{\text{sem}}[h,w] \in [0.1, 2.0]$ | DINOv2 特征相似度 + BA Phase 2 优化 | "这个像素有多大概率是动态的" |
| $r[h,w] \in \mathbb{R}^+$ (像素) | BA 优化后的重投影残差 $\|\mathbf{x}_{\text{target}} - \mathbf{x}_{\text{reproj}}\|$ | "这个像素与刚体几何模型的吻合程度" |

**纠偏逻辑**：当几何残差 $r$ 很小（像素完美重投影），但 DINO 特征却给出了高不确定度 $u_{\text{sem}}$ 时，说明 DINO"看错了"——可能是光照变化、视角变化导致的特征差异被误判为动态。此时应该用几何信号把 $u$ **拉低**。

当 $r$ 很大时，存在两种可能：(a) 像素确实是运动的，(b) 几何估计本身不准。**两种情况下都不应该改 $u$**——纠正方向是单向的。

### 7.2 设计原则

1. **单向纠偏**：几何只能压低 $u$，不能抬高 $u$。$r$ 大 → 不做任何事，回退给 DINO 判断。
2. **逐像素**：每个像素的纠偏力度仅取决于自己的 $r$，不引入全局调制因子。
3. **池化在纠偏信号上，而非残差上**：$r$→$s$（exp 非线性）应保持逐像素锐利；空间平滑作用在最终的 $c$（纠偏权重）上，直接抑制斑点伪影。
4. **乘法形式**：$u_{\text{new}} = u \cdot (1-p)$，纠偏量与 $u$ 自身成正比——DINO 越不信任的像素，几何证据的说服力越强。

### 7.3 公式

**Step 1 — 逐像素静态置信度**（无池化，保持几何信号锐利）：

$$r = \|\mathbf{x}_{\text{target}} - \mathbf{x}_{\text{reproj}}\|_2 \quad \in \mathbb{R}^{N \times H \times W}$$

$$s = \exp(-\lambda \cdot r) \quad \in [0, 1]^{N \times H \times W}$$

其中 $\lambda = 0.8$ 使得 $r=0.5 \to s \approx 0.67$，$r=1 \to s \approx 0.45$，$r=4 \to s \approx 0.04$。

**Step 2 — 逐像素纠偏权重**（可选内点门控）：

$$c = s \cdot w_{\text{in}} \cdot w_{\text{valid}} \quad \in [0, 1]^{N \times H \times W}$$

其中 $w_{\text{in}}$ 是相对于每条边中位残差的软内点权重（sigmoid 平滑，处理整帧残差偏高的情况），$w_{\text{valid}}$ 标记投影有效的像素。

**Step 3 — 空间平滑纠偏信号**（抑制像素级噪声造成的斑点）：

$$\tilde{c} = \text{AvgPool}_{3 \times 3}(c)$$

相比在 $r$ 上做 5×5 池化，3×3 在 $\tilde{c}$ 上更精确——exp 非线性已压缩了残差差异，小核足以平滑。

**Step 4 — 帧级聚合与更新**：

对每个源帧 $k$，聚合其所有边的纠偏权重（平均），然后逐像素乘法更新：

$$\tilde{c}_k[h,w] = \frac{1}{|\mathcal{E}_k|} \sum_{e \in \mathcal{E}_k} \tilde{c}_e[h,w]$$

$$\boxed{u_{\text{new}}[h,w] = u_{\text{sem}}[h,w] \cdot \big(1 - w_{\max} \cdot \tilde{c}_k[h,w]\big)}$$

其中 $w_{\max} = 0.5$ 为最大纠偏比例。

### 7.4 与方案一/二的关键区别

| 维度 | 方案一（当前 PlanA） | 方案二 | **推荐方案** |
|------|:---:|:---:|:---:|
| 池化位置 | 残差 $r$ 上（5×5） | 无 | **纠偏权重 $c$ 上（3×3）** |
| 全局调制 | `inlier_ratio.mean()` | `inlier_ratio.mean()` | **无（纯逐像素）** |
| 内点判定 | soft sigmoid | hard mask | **soft sigmoid（可选关闭）** |
| 融合方式 | 乘法 | 插值 | **乘法** |
| $\lambda$ | 0.8 | 5.0 | **0.8** |
| $w_{\max}$ | 0.5 | 0.25 | **0.5** |

### 7.5 伪代码（适配现有 `depth_video.py` 结构）

```python
@torch.no_grad()
def apply_geometric_correction(self, target, ii, jj,
                                lambda_geo=0.8, max_geo_weight=0.5):
    """几何重投影残差纠偏语义不确定性。

    仅做单向乘法纠偏：几何只能压低 u，不能抬高。
    每个像素的纠偏力度仅取决于自己的几何残差，无全局耦合。
    """
    if not self.uncertainty_aware:
        return

    # -- 统一形状 --
    if target.dim() == 5:
        target = target.squeeze(0)

    # -- Step 1: 重投影残差（逐像素，不做池化）--
    coords, valid_mask = self.reproject(ii, jj)
    coords = coords.squeeze(0)          # [N, H, W, 2]
    valid_mask = valid_mask.squeeze(0)   # [N, H, W, 1]

    residual = target - coords           # [N, H, W, 2]
    residual_norm = torch.norm(residual, dim=-1)  # [N, H, W]

    # -- Step 2: 逐像素静态置信度 --
    static_confidence = torch.exp(-lambda_geo * residual_norm)  # [N, H, W]

    # -- Step 3: 有效像素掩码 --
    valid_weight = valid_mask.squeeze(-1).float()  # [N, H, W]

    # -- Step 4: 纠偏权重（纯逐像素，无全局调制）--
    correction_weight = static_confidence * valid_weight  # [N, H, W]

    # -- Step 5: 在纠偏信号上做空间平滑（3×3，替代残差上的 5×5）--
    correction_weight = F.avg_pool2d(
        correction_weight.unsqueeze(1),
        kernel_size=3, stride=1, padding=1
    ).squeeze(1)  # [N, H, W]

    # -- Step 6: 逐帧聚合 + 乘法更新 --
    unique_ii = torch.unique(ii)
    for idx in unique_ii:
        edge_mask = (ii == idx)
        if edge_mask.sum() == 0:
            continue

        # 跨边平均聚合（保留 [H, W] 空间结构）
        c_frame = correction_weight[edge_mask].mean(dim=0)  # [H, W]

        # 逐像素乘法纠偏，无全局 base_strength
        pull_down = max_geo_weight * c_frame               # [H, W]
        self.uncertainties[idx] = self.uncertainties[idx] * (1.0 - pull_down)
```

### 7.6 为什么去掉 `inlier_weight`

方案一中的 `inlier_weight = sigmoid(5 * (1 - r/(3*median(r))))` 本意是帧级自适应门控——当整帧残差异常偏高时，用相对偏差代替绝对残差来判定内外点。但这引入了一个隐蔽 bug：

**当中位残差被动态像素主导时**，`median(r)` 偏高 → 所有像素（包括动态像素）的 `r/median(r)` 都很小 → 动态像素被错误地赋予高 `w_in` → 动态像素获得虚假的 static_confidence 补充。

例如：场景 70% 是运动物体（$r \approx 5\text{px}$），30% 是静态背景（$r \approx 0.5\text{px}$），median ≈ 5px。动态像素的 $r/3\text{median} \approx 0.33$，sigmoid 后 $w_{\text{in}} \approx 0.84$——**运动物体被标记为内点**。

纯逐像素方案不依赖整帧统计量，不存在这个问题。如果后续实验发现某些场景确实需要帧级归一化，可以用 20 分位数替代中位数（假设场景中至少 20% 的像素是静态的），但那是后续优化，不应进入基线版本。

### 7.7 参数调优建议

| 参数 | 推荐值 | 说明 |
|------|:---:|------|
| `lambda_geo` | 0.8 | $r=1\text{px} \to s=0.45$，$r=4\text{px} \to s=0.04$ |
| `max_geo_weight` | 0.5 | 几何最多将 $u$ 压低 50% |
| 平滑核 | 3×3 | 在 $c$ 上池化，仅抑制像素级噪声 |
| 平滑位置 | 纠偏权重 $c$ | **不在残差 $r$ 上做任何池化** |

`lambda_geo` 的标定逻辑：在 H/8×W/8 分辨率下，静态物体的重投影残差通常在 0.3-1.0px 范围，动态物体 ≥ 3px。$\lambda=0.8$ 确保静态区 $s>0.45$（有效纠偏），动态区 $s<0.09$（纠偏归零）。如果用全分辨率图像做几何校验，需要同比例缩小 $\lambda$。

---

## 8. 跨边平均聚合（`mean(dim=0)` 的语义）

### 8.1 为什么需要聚合

在 factor graph 中，一个源帧会与多个目标帧建立边。例如帧 5 可能与帧 3、4、6、7 各有边：

```
  帧5 ──→ 帧3  (边0: target=光流(5→3), r₀)
  帧5 ──→ 帧4  (边1: target=光流(5→4), r₁)
  帧5 ──→ 帧6  (边2: target=光流(5→6), r₂)
  帧5 ──→ 帧7  (边3: target=光流(5→7), r₃)
```

每条边独立计算了一个 `correction_weight[K, H, W]`——不同目标帧带来不同的相对位姿、遮挡关系和深度视角，同一源像素在不同边上的 $c$ 可能差异很大。但 `self.uncertainties[5]` 只有一份 `[H, W]`，必须将 K 条边的纠偏信号合并。

### 8.2 为什么选 `mean` 而非 `max`/`min`

$$\tilde{c}_k[h,w] = \frac{1}{|\mathcal{E}_k|} \sum_{e \in \mathcal{E}_k} \tilde{c}_e[h,w]$$

**mean 的语义**：每条边对像素 $[h,w]$ 进行一次独立"投票"。mean 给出的是共识度：

| 场景 | K=4 边的 c 值 | mean | 含义 |
|------|-------------|------|------|
| 全部静态 | [0.82, 0.79, 0.91, 0.85] | 0.84 | 强共识 → 强力纠偏 |
| 一条边遮挡 | [0.82, 0.00, 0.91, 0.85] | 0.65 | 少数反对票降权但不归零 |
| 两条边遮挡 | [0.82, 0.00, 0.00, 0.85] | 0.42 | 纠偏力度显著降低 |
| 全部动态/遮挡 | [0.00, 0.05, 0.00, 0.03] | 0.02 | 接近不纠偏 |

对比其他聚合方式：

| 聚合 | 行为 | 风险 |
|------|------|------|
| `.max(dim=0)` | 只要一条边说"静态"就全额纠偏 | 某条边几何崩溃时可能误判动态像素为静态 |
| `.min(dim=0)` | 必须全部边说"静态"才纠偏 | 一条边有遮挡就完全阻断静态像素的纠偏 |
| `.mean(dim=0)` | 按共识比例纠偏 | 少数反对票降权，多数反对票自然接近不纠偏 |

### 8.3 隐式遮挡处理

当像素在目标帧中投影越界（遮挡/出视野），该边的 `valid_weight=0` → `c=0` → 自动拉低均值。不需要显式的遮挡检测逻辑。

### 8.4 `dim=0` 是边维度，不是空间维度

```python
correction_weight[edge_mask]  # shape: [K, H, W]，K 条边
c_frame = correction_weight[edge_mask].mean(dim=0)  # mean over dim=0 → [H, W]
```

`dim=0` 在第 K（边）维度上求均值，输出仍是 `[H, W]`。**像素 $[h,w]$ 之间没有互相影响**——与全局 `inlier_ratio` 把所有像素坍缩为一个标量完全不同。每个像素独立地跨边聚合自己的纠偏证据，像素间保持解耦。
