# visualize_gs.py — 3DGS 点云可视化

将 `final_gs.ply` 文件渲染为交互式 3D 点云，或导出多视角截图。

## 快速开始

```bash
cd /workspace/DROID-W/Outputs
python visualize_gs.py                     # 默认 5 万点，流畅
python visualize_gs.py --scene DROID-W/downtown2  # 指定场景
```

交互操作：**鼠标左键旋转 | 滚轮缩放 | 鼠标中键平移 | 按 Q 退出**

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--scene` | str | `DROID-W/downtown1` | 场景路径（相对于 Outputs） |
| `--ply` | str | `final_gs.ply` | PLY 文件名 |
| `--max_points` | int | `50000` | 最大显示点数，超出则随机降采样 |
| `--voxel` | float | `0.0` | 体素降采样大小，如 `0.05`（优先于随机采样，结构保留更好） |
| `--opacity_th` | float | `0.0` | 不透明度阈值，只显示高于此值的高斯点（如 `0.3`） |
| `--point_size` | float | `2.0` | 点的大小 |
| `--z_min` | float | `-50` | 深度裁剪下限 |
| `--z_max` | float | `50` | 深度裁剪上限 |
| `--screenshot` | flag | — | 截图模式，无 GUI 交互，输出至 `{scene}/screenshots/` |

## 常用用法

```bash
# 流畅查看（5 万点）
python visualize_gs.py

# 体素降采样，结构完整
python visualize_gs.py --voxel 0.1

# 只显示主体结构，剔除低透明度噪点
python visualize_gs.py --opacity_th 0.3 --max_points 30000

# 高质量截图
python visualize_gs.py --max_points 200000 --point_size 1.0 --screenshot

# 查看其他场景
python visualize_gs.py --scene DROID-W/downtown2 --voxel 0.08
```

## 降采样策略

脚本采用**三级过滤**，按顺序执行：

1. **不透明度过滤** — 通过 `opacity > opacity_th` 剔除离群高斯
2. **深度裁剪** — 去掉 `z` 轴范围外的点
3. **降采样** — 体素优先（`voxel > 0`），再随机采样到 `max_points`

## 性能参考

| 点数 | 内存 | 流畅度 |
|------|------|--------|
| 5 万 | ~50 MB | 流畅 |
| 10 万 | ~100 MB | 可接受 |
| 20 万+ | ~200 MB+ | 明显卡顿 |
