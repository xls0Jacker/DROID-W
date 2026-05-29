# Formula-REASEARCH: 论文公式与代码对应关系

> 本文档逐公式映射论文 _DROID-SLAM in the Wild_ (CVPR 2026) 中的数学表达式到 `/workspace/DROID-W` 代码实现位置。

---

## 公式索引

| 公式 | 名称 | 代码位置 |
|------|------|----------|
| Eq (1) | 刚体运动对应关系 | `src/geom/projective_ops.py` |
| Eq (2) | BA 代价函数 | `src/geom/ba.py` → `BA()` |
| Eq (3) | 高斯-牛顿更新 | `src/geom/ba.py` → `BA()` |
| Eq (4) | 不确定性感知马氏距离 | `src/lib/droid_kernels.cu:187` → `projective_transform_kernel()` |
| Eq (5) | UBA 能量函数 | `src/lib/droid_kernels.cu:1799` → `ba_cuda()` + `factor_graph.py:447` |
| Eq (6) | 不确定性相似性损失 | `src/lib/droid_kernels.cu:1464` → `dino_feats_projective_transform_kernel()` |
| Eq (7) | 不确定性对数先验 | `src/lib/droid_kernels.cu:1714` → `prior_regularization_kernel()` |
| Eq (8) | 总不确定性代价 | `src/lib/droid_kernels.cu:1934` (`J_total` 组合) |
| Eq (9) | 仿射映射梯度更新 | `src/lib/droid_kernels.cu:1745` → `linear_transform_kernel()` + `ba_cuda():1958` |
| Eq (10) | 带深度正则的 BA | `src/geom/ba.py` → `BA_with_scale_shift()` |
| Eq (11) | 消融: 非解耦相似性损失 | `droid_backends.ba()` 双向标志控制 |

---

## 符号约定

| 论文符号 | 含义 | 代码变量 | 形状 |
|----------|------|----------|------|
| `I_t` | 第 t 帧 RGB 图像 | `self.images[t]` | `[3, H, W]` |
| `G_t` | 第 t 帧相机位姿 (SE3) | `self.poses[t]` | `[7]` (tx,ty,tz,qx,qy,qz,qw) |
| `d_t` | 第 t 帧逆深度图 | `self.disps[t]` | `[H/8, W/8]` |
| `p_i` | 帧 i 的像素坐标网格 | `coords0` / `coords_grid()` | `[H/8, W/8, 2]` |
| `p*_{ij}` | 网络预测的稠密对应 | `self.target` | `[1, N, H/8, W/8, 2]` |
| `w_{ij}` | 对应对的置信度图 | `self.weight` | `[1, N, H/8, W/8, 2]` |
| `u_t` | 逐像素动态不确定性 | `self.uncertainties[t]` | `[H/8, W/8]` |
| `F_t` | DINOv2 视觉特征 | `self.dino_feats_resize[t]` | `[C, H/8, W/8]` |
| `θ` | 仿射映射可学习参数 | `self.affine_weights` | `[C+1]` (权重+偏置) |
| `D_t` | 度量单目深度先验 | `self.mono_disps[t]` | `[H/8, W/8]` |

---

## Eq (1): 刚体运动对应关系

**论文公式：**

```
p_ij = Π_c( G'_ij ∘ Π_c^{-1}(p_i, d_i) )
```

其中 `Π_c` 是相机投影，`G'_ij` 是帧 i 到帧 j 的相对位姿。

### 代码实现

**文件：** `src/geom/projective_ops.py:272-362` — `projective_transform()`

| 步骤 | 公式 | 代码行 | 代码 |
|------|------|--------|------|
| 逆投影 | `Π_c^{-1}(p_i, d_i)` | L310 | `X0, Jz = iproj(depths[:,ii], intrinsics[:,ii], ...)` |
| 相对位姿 | `G'_ij = G_j ∘ G_i^{-1}` | L315 | `Gij = poses[:,jj] * poses[:,ii].inv()` |
| 变换 | `G'_ij ∘ X0` | L322 | `X1, Ja = actp(Gij, X0, ...)` |
| 投影 | `Π_c(X1)` | L326 | `x1, Jp = proj(X1, intrinsics[:,jj], ...)` |

**逆投影 `iproj()`** (L98-140)：
```python
# 核心公式: X_norm = (u - cx) / fx, Y_norm = (v - cy) / fy
X = (x - cx) / fx
Y = (y - cy) / fy
pts = torch.stack([X, Y, i, disps], dim=-1)  # [X_norm, Y_norm, 1, disp]
```

**投影 `proj()`** (L142-205)：
```python
# 核心公式: u = fx * X/Z + cx,  v = fy * Y/Z + cy
d = 1.0 / Z
x = fx * (X * d) + cx
y = fy * (Y * d) + cy
coords = torch.stack([x, y], dim=-1)  # 即 p_ij
```

**SE3 变换 `actp()`** (L207-270)：
```python
# 李群作用: X1 = Gij * X0
X1 = Gij[:,:,None,None] * X0
```

**返回值对应：**
- `x1` → `p_ij`（在帧 j 上的预测像素坐标）
- `valid` → 有效掩码（`Z > MIN_DEPTH` 的像素）

---

## Eq (2): BA 代价函数 (DROID-SLAM)

**论文公式：**

```
Σ_{(i,j)∈E} || p*_{ij} - p_{ij} ||_Σ^2
```

其中 `||·||_Σ` 是基于 DROID-SLAM 预测置信度 `w_{ij}` 的马氏距离。

### 代码实现

**文件：** `src/geom/ba.py:178-368` — `BA()`

**残差计算** (L240-256)：
```python
# coords = 预测坐标 p_ij (来自 projective_transform)
coords, valid, (Ji, Jj, Jz) = pops.projective_transform(...)

# 残差 r = p*_ij - p_ij
r = (target - coords).view(B, N, -1, 1)       # [B, N, 2*H*W, 1]

# 权重 w = valid_mask * weight * 0.001
# weight 即 DROID-SLAM 预测的置信度 w_ij
w = .001 * (valid * weight).view(B, N, -1, 1)  # [B, N, 2*H*W, 1]
```

| 论文符号 | 代码变量 | 说明 |
|----------|----------|------|
| `p*_{ij}` | `target` | 网络预测的目标光流坐标 |
| `p_{ij}` | `coords` | 基于位姿/深度的重投影坐标 |
| `w_{ij}` | `weight` | 置信度图（由 DROID GRU 预测） |
| `(i,j)∈E` | `ii, jj` | 因子图边索引 |
| `||·||_Σ` | `w * r^2` | 加权最小二乘（权重吸收进 Hessian） |

**Hessian 构造** (L264-271)：
```python
# H = J^T * W * J（近似的 Hessian）
Hii = torch.matmul(wJiT, Ji)   # 对 ii 位姿的 Hessian 块
Hij = torch.matmul(wJiT, Jj)   # 交叉 Hessian 块
Hjj = torch.matmul(wJjT, Jj)   # 对 jj 位姿的 Hessian 块

# v = J^T * W * r（梯度向量）
vi = torch.matmul(wJiT, r).squeeze(-1)
vj = torch.matmul(wJjT, r).squeeze(-1)
```

**全局累加** (L308-327) — 将帧间 Hessian 散列累加到全局矩阵：
```python
H = safe_scatter_add_mat(Hii, ii, ii, P, P) + \
    safe_scatter_add_mat(Hij, ii, jj, P, P) + \
    safe_scatter_add_mat(Hji, jj, ii, P, P) + \
    safe_scatter_add_mat(Hjj, jj, jj, P, P)

v = safe_scatter_add_vec(vi, ii, P) + \
    safe_scatter_add_vec(vj, jj, P)
```

---

## Eq (3): 高斯-牛顿更新

**论文公式：**

```
(J^T Σ^{-1} J + C) (Δξ, Δd) = J^T Σ^{-1} r
```

其中 `C` 是对角矩阵，因为每项仅依赖单个深度值，求逆为 `C^{-1} = 1/C`。

### 代码实现

**文件：** `src/geom/ba.py:178-368` — `BA()`

**深度自相关项 C** (L289-292) — 对角矩阵：
```python
# wk = w * r * Jz: 深度梯度
wk = torch.sum(w*r*Jz, dim=-1)         # [B, N, H*W]
# Ck = w * Jz * Jz: 深度近似的 Hessian（对角线上）
Ck = torch.sum(w*Jz*Jz, dim=-1)        # [B, N, H*W]

# 全局累加后得到对角矩阵 C
C = safe_scatter_add_vec(Ck, kk, M)    # [B, M, H*W]
```

**深度-位姿耦合项 E** (L283) — 对应论文中的 `E` 块：
```python
# E = J^T_pose * W * J_depth
Ei = (wJiT.view(B,N,D,H*W,-1) * Jz[:,:,None]).sum(dim=-1)  # [B,N,D,H*W]
```

**Schur 补求解** (L355)：
```python
# 使用 Schur complement 消除深度变量，先求解位姿增量
# S = H - E * C^{-1} * E^T → dx (位姿增量)
# dz = C^{-1} * (w - E^T * dx) → dz (深度增量)
dx, dz = schur_solve(H, E, C, v, w, ep, lm)
```

**Retraction 更新** (L360-363)：
```python
# 位姿: pose_new = pose_old * exp(dx)
poses = pose_retr(poses, dx, torch.arange(P) + fixedp)
# 深度: disp_new = disp_old + dz
disps = disp_retr(disps, dz.view(B,-1,ht,wd), kx)
```

| 论文符号 | 代码变量 | 说明 |
|----------|----------|------|
| `J^T Σ^{-1} J` | `H` | 块状 Hessian 矩阵 `[B, P*P, D, D]` |
| `J^T Σ^{-1} r` | `v` | 梯度向量 `[B, P, D]` |
| `C` | `C` | 深度对角度阵 `[B, M, H*W]` |
| `Δξ` | `dx` | 6 维位姿增量 (李代数) |
| `Δd` | `dz` | 深度增量 (展平) |

类 BA **仅运动变体** `MoBA()` (L553-652) 固定深度，只优化位姿，使用分块 Cholesky 求解而非 Schur 补。

---

## Eq (4): 不确定性感知马氏距离

**论文公式：**

```
||·||_{Σ^{uncer}_{ij}}
```

其中 `u_t ∈ R^{H/8 × W/8}` 是逐像素动态不确定性，用于降权不一致对应。

### 代码实现

**文件：** `src/depth_video.py:662-691` — CUDA 后端调用

```python
# 不确定性传入 CUDA 后端 BA
droid_backends.ba(
    self.poses, self.disps, self.intrinsics[0], self.mono_disps,
    target, weight,
    self.uncertainties,          # ← u_t: 逐像素不确定性 [H/8, W/8]
    self.temp_y_cdot,            # ← 仿射映射中间值
    self.dino_feats_resize,      # ← DINO 特征
    self.affine_weights,         # ← 仿射参数 θ
    eta, ii, jj, t0, t1, iters, lm, ep,
    gamma_data, gamma_prior, gamma_depth,
    lr, weight_decay, ...
)
```

**不确定性初始化** (`depth_video.py:206`)：
```python
self.uncertainties = torch.ones(buffer, H//8, W//8, ...)  # 初始全 1（无偏置）
```

**仿射映射计算不确定性** (`depth_video.py:316-322`)：
```python
# y_cdot = θ · F = w*x + b（仿射变换输出）
y_cdot = dino_feats_resize.permute(1,2,0) @ affine_weights[:-1] + affine_weights[-1]
# u = softplus(y_cdot) = log(1.1 + exp(y_cdot))（保证正值）
self.uncertainties[index] = torch.log(1.1 + torch.exp(y_cdot))
```

**CUDA 后端：** `src/lib/droid_kernels.cu` 中的 `ba()` 函数在优化时用 `u_t` 加权残差：
- 动态像素（`u_t` 大）→ 残差权重低
- 静态像素（`u_t` 小）→ 残差权重高
- `Σ^{uncer}` = `f(u_t, w_{ij})`，将语义不确定性与几何置信度结合

---

## Eq (5): UBA 能量函数

**论文公式：**

交替优化位姿/深度与不确定性，位姿-深度步最小化不确定性感知能量：

```
min_{G,d} Σ_{(i,j)} || p*_{ij} - p_{ij} ||_{Σ^{uncer}_{ij}}^2
```

### 代码实现

**文件：** `src/factor_graph.py:447-457` — `update()` 中的 BA 调用

```python
# 位姿-深度细化步骤（固定不确定性 u_t 不变）
self.video.ba(
    target, weight, damping, ii, jj, t0, t1,
    iters=itrs, lm=1e-4, ep=0.1,
    lr=...,
    weight_decay=...,
    motion_only=motion_only,          # False → 联合优化位姿+深度
    enable_update_uncer=...,
    enable_udba=...,
)
```

**文件：** `src/factor_graph.py:471-558` — `update_lowmem()` 中的全局 BA

**交替策略**：
1. BA 步：固定 `u_t`，优化 `G_t` 和 `d_t`（`update_uncer=False` 时冻结不确定性）
2. 不确定性步：固定 `G_t` 和 `d_t`，优化 `θ`（`update_uncer=True` 时在 CUDA 后端内优化）
3. 全局 BA：固定 `u_t`，只优化 `G_t` 和 `d_t`

```python
# enable_udba=True: 使用不确定性感知的 BA (Eq 5)
# enable_udba=False: 回退为普通 BA (Eq 2)
self.video.ba(..., enable_udba=enable_udba, ...)
```

---

## Eq (6): 不确定性相似性损失

**论文公式：**

```
L_sim = Σ_{(i,j)} w_{ij} · (1 - cos(F_i, F_{ij}))
```

其中 `F_i` 是帧 i 的 DINOv2 特征，`F_{ij}` 是通过刚体对应关系 `p_{ij}` 从帧 j 扭曲到帧 i 的特征。双向优化以解耦帧间动态。

### 代码实现

**文件：** `src/lib/droid_kernels.cu` — CUDA 后端实现

**DINO 特征提取和传递** (`depth_video.py:307-310`)：
```python
# 原始 DINO 特征存储（CPU）
self.dino_feats[index] = item[9].cpu()
# 缩放到 BA 分辨率并转置为 [C, H/8, W/8]
self.dino_feats_resize[index] = F.interpolate(
    item[9].permute(2,0,1).unsqueeze(0),
    target_size, mode='bilinear').squeeze()[:, slice_h, slice_w]
```

**特征扭曲（可视化中的显式计算）** (`depth_video.py:846-856`)：
```python
# 帧 j 的 DINO 特征通过重投影坐标 warp 到帧 i 的视角
dino_feats_reproj, valid_mask = self.project_images_with_mask(
    dino_feats_j, reprojected_coords)    # F_{ij} = warp(F_j, p_{ij})

# 归一化
dino_feats_i_norm = F.normalize(dino_feats_i, p=2, dim=1)
dino_feats_reproj_norm = F.normalize(dino_feats_reproj, p=2, dim=1)

# 余弦相似度
dino_feats_similarity = (dino_feats_i_norm * dino_feats_reproj_norm).sum(dim=1)
# cos(F_i, F_{ij}) ∈ [-1, 1]，高值表示相似（静态），低值表示不一致（动态）
```

**双向解耦** (`depth_video.py:178`)：
```python
self.enable_bidirectional_uncer = cfg['tracking']['uncertainty_params']['enable_bidirectional_uncer']
```

CUDA 后端在 `ba()` 中对每对 (i,j) 计算双向的 `(1 - cos(F_i, F_{ij})) * w_{ij}`，并反向传播到不确定性 `u_t` 和仿射参数 `θ`。

**优化细节**：采用梯度下降（非牛顿法），所有权重使用 L2 权重衰减 `weight_decay`。

---

## Eq (7): 不确定性对数先验

**论文公式：**

```
L_prior = log(1 + u')
```

其中 `u' = u + 1.0`（加入偏置防止先验为负）。

### 代码实现

**文件：** `src/lib/droid_kernels.cu` — CUDA 后端实现

**参数传入** (`depth_video.py:668-669`)：
```python
droid_backends.ba(...
    gamma_data,     # λ_data: 数据项权重
    gamma_prior,    # λ_prior: 先验项权重
    gamma_depth,    # λ_depth: 深度正则权重
    lr,
    weight_decay,
    ...)
```

**Softplus 函數 `depth_video.py:322` 确保了 `u ∈ (log(1.1), ∞)`**：
```python
self.uncertainties[index] = torch.log(1.1 + torch.exp(y_cdot))
# 等价于 u ≥ log(1.1) ≈ 0.095 > 0
```

CUDA 后端实现 `L_prior = log(1 + u)` 梯度，与 softplus 输出的正约束一起防止 u → +∞ 的平凡解。

---

## Eq (8): 总不确定性代价函数

**论文公式：**

```
L_total = L_sim + λ_prior · L_prior
```

### 代码实现

**文件：** `src/lib/droid_kernels.cu` — CUDA 后端实现

```python
# 总损失 = γ_data * L_sim + γ_prior * L_prior
# 配置参数 (depth_video.py ba() 方法):
gamma_data   = cfg['tracking']['uncertainty_params']['gamma_data']    # λ_sim
gamma_prior  = cfg['tracking']['uncertainty_params']['gamma_prior']   # λ_prior
```

| 论文符号 | 代码参数 | 典型值 |
|----------|----------|--------|
| `L_sim` | CUDA 内部计算 | Eq (6) 损失 |
| `L_prior` | CUDA 内部计算 | Eq (7) 损失 |
| `λ_prior` | `gamma_prior` | 配置文件中设定 |

---

## Eq (9): 仿射映射梯度更新

**论文公式：**

```
θ ← θ - lr · (∂L_total/∂θ + weight_decay · θ)
```

其中 `u = Softplus(θ · F)`，`F` 是 DINOv2 特征。

### 代码实现

**仿射映射初始化** (`depth_video.py:211-217`)：
```python
# θ = [w_1, ..., w_C, b] 维度为 C+1（C = DINO 特征维数）
self.affine_weights = torch.empty((1, n_features + 1), ...)
torch.nn.init.kaiming_normal_(self.affine_weights[:, :-1], ...)  # 权重 Kaiming 初始化
self.affine_weights[:, -1].zero_()                                  # 偏置初始化为 0
```

**前向计算** (`depth_video.py:318-322`)：
```python
# y_cdot = w · F + b（仿射映射）
y_cdot = dino_feats_resize.permute(1,2,0) @ affine_weights[:-1] + affine_weights[-1]
# u = Softplus(y_cdot)（保证 u > 0）
self.uncertainties[index] = torch.log(1.1 + torch.exp(y_cdot))
```

**反向更新** (`depth_video.py:662-691`) — CUDA 后端实现：
```python
droid_backends.ba(...
    self.affine_weights,     # θ: 可优化参数
    lr,                      # 学习率
    weight_decay,            # 权重衰减 λ
    ...)
```

CUDA 后端计算 `∂L_total/∂θ`，然后执行：
```
θ_new = θ - lr * (∂L_total/∂θ + weight_decay * θ)
```

对应雅可比形式（论文 Eq 9 中的 `J(θ)`）基于链式法则：
```
∂L/∂θ = ∂L/∂u * ∂u/∂y_cdot * ∂y_cdot/∂θ
       = ∂L/∂u * σ(y_cdot) * F
```

其中 `σ(y_cdot) = exp(y_cdot) / (1.1 + exp(y_cdot))` 是 softplus 的导数。

**学习率配置** (`depth_video.py:671-672`)：
```python
lr = cfg['tracking']['uncertainty_params']['lr']              # 前端 BA 学习率
gba_lr = cfg['tracking']['uncertainty_params']['gba_lr']      # 全局 BA 学习率
weight_decay = cfg['tracking']['uncertainty_params']['weight_decay']
gba_weight_decay = cfg['tracking']['uncertainty_params']['gba_weight_decay']
```

---

## Eq (10): 带深度正则化的 BA

**论文公式：**

```
L_BA = Σ_{(i,j)} || p*_{ij} - p_{ij} ||_{Σ^{uncer}}^2 + γ_depth · Σ_t || d_t - D_t ||^2
```

其中 `D_t` 是 Metric3D 预测的单目深度先验（逆深度形式）。

### 代码实现

**文件：** `src/geom/ba.py:374-546` — `BA_with_scale_shift()`

**深度先验残差** (L459)：
```python
# r_depth = sqrt(γ_depth) * (disp - (scale * mono_disp + shift))
r_depth = sqrt_alpha * (
    disps[:,kx] - (scales[:,kx,None,None] * mono_disps[:,kx] + shifts[:,kx,None,None])
).view(B, M, H*W, 1)
```

**合并到 Hessian** (L513-525)：
```python
# 深度先验贡献到深度正则项
C_depth = (J_d * J_d).view(B, M, H*W)    # J_d = sqrt(γ_depth)
C = C_proj + C_depth + eta                # C_proj 来自重投影，C_depth 来自深度先验

# 深度先验贡献到梯度
w_proj = safe_scatter_add_vec(wk, kk, M)
w = -w_proj - (J_d * r_depth).view(B, M, H*W)  # 负号来自高斯-牛顿残差定义
```

**CUDA 后端模式** (`depth_video.py:676-691`)：
```python
# metric_depth_reg=True → 传递单目深度作为正则化先验
droid_backends.ba(
    self.poses, self.disps, self.intrinsics[0],
    self.mono_disps,           # ← D_t: 单目深度先验（作为正则化项）
    target, weight, ...
    gamma_depth,               # ← γ_depth: 深度正则化强度
    ...)
```

**尺度/偏移对齐** (`depth_video.py:1220-1240`)：
```python
def get_depth_scale_and_shift(self, index, mono_depth, est_depth, weights):
    # 加权最小二乘: argmin_{s,q} Σ w_i · (est_depth_i - (s * mono_depth_i + q))²
    scale, shift, _ = align_scale_and_shift(mono_depth, est_depth, weights)
```

**固定不确定性**：论文明确声明在全局 BA 阶段冻结不确定性参数，因为仿射映射设计为在滑动窗口局部范围内正则化。在 `update_lowmem()` 中 `enable_update_uncer` 控制此行为。

---

## Eq (11): 消融实验 — 非解耦相似性损失

**论文公式：**

```
L_sim_undecoupled = Σ w_{ij} · (1 - cos(F_i, F_{ij})) + max(w_{ij}, 0.25) · (1 - cos(F_j, F_{ji}))
```

（注：精确公式因图片 OCR 受限，此为基础的数学形式）

### 代码实现

**文件：** `src/depth_video.py:178` — 双向开关

```python
self.enable_bidirectional_uncer = cfg['tracking']['uncertainty_params']['enable_bidirectional_uncer']
# False → 仅单向（对应于消融中的 w/o decouple 设置）
# True  → 双向解耦（完整模型）
```

CUDA 后端 `ba()` 中 `enable_bidirectional_uncer` 标志控制：
- **True（完整模型）**：`L = L_i→j + L_j→i`，双向分别计算 `1 - cos(F_i, F_{ij})` 和 `1 - cos(F_j, F_{ji})`
- **False（消融）**：仅计算一个方向的相似性

---

## 关键数据流汇总

```
输入 RGB 序列
    ↓
DROID 前端: GRU 预测 p*_ij, w_ij                  [src/modules/droid_net/gru.py]
    ↓
DINOv2 特征提取: F_t = FiT3D(I_t)                  [src/utils/mono_priors/img_feature_extractors.py]
    ↓
仿射映射: u_t = Softplus(θ · F_t)                  [src/depth_video.py:318-322]
    ↓
因子图: 管理边 (ii, jj)，存储 target/weight         [src/factor_graph.py]
    ↓
droid_backends.ba(): 交替优化
    ├─ UBA 位姿-深度步: min_{G,d} Eq(5)             [src/lib/droid_kernels.cu]
    ├─ 不确定性步: min_θ Eq(8) = Eq(6) + λ*Eq(7)   [src/lib/droid_kernels.cu]
    └─ 参数更新: θ ← Eq(9)                          [src/lib/droid_kernels.cu]
    ↓
P2 几何残差纠偏: u ← u * (1 - pull_down)           [src/depth_video.py:697-774]
    ↓
输出: 优化位姿 G_t, 深度 d_t, 不确定性 u_t
```

---

## 补充说明

1. **交替优化实现**：Eq(4-9) 的核心计算在 `droid_backends.ba()` CUDA 内核中，这是 DROID-W 对 DROID-SLAM 的主要扩展。Python 层面负责设置参数、管理状态和调用 CUDA 后端。

2. **BA 三种模式**：
   - `BA()` (`src/geom/ba.py:178`)：全 BA，联合优化位姿与深度
   - `BA_with_scale_shift()` (`src/geom/ba.py:374`)：带尺度/偏移的 BA（用于单目深度先验）
   - `MoBA()` (`src/geom/ba.py:553`)：仅运动 BA（固定深度，优化位姿）

3. **UBA 与 BA 的区别**：UBA 在标准 BA 基础上增加了不确定性感知的残差加权（Eq 4），以及不确定性自身的交替优化（Eq 6-9）。开关由 `enable_udba` 控制。

4. **P2 几何纠偏**：论文未在正文中详述，但在 `apply_geometric_correction()` (`depth_video.py:697-774`) 中实现了基于重投影残差的连续乘法纠偏，作为语义不确定性的补充信号。

5. **验证方法**：`visualize_uncertainty()` (`depth_video.py:777-1058`) 可对公式中涉及的 DINO 特征相似度、不确定性热力图、重投影误差等进行可视化验证。
