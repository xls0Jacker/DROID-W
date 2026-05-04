"""
3DGS 点云可视化脚本 — 使用 Open3D 交互查看

用法:
    cd /workspace/DROID-W/Outputs
    python visualize_gs.py                          # 默认 5 万点，流畅
    python visualize_gs.py --max_points 200000      # 20 万点
    python visualize_gs.py --max_points 50000 --voxel 0.1  # 体素降采样
    python visualize_gs.py --scene DROID-W/downtown2 --screenshot  # 截图模式
"""
import argparse
import os
import numpy as np
from plyfile import PlyData
import open3d as o3d


def load_gs_ply(ply_path: str):
    """读取 3DGS PLY 文件，返回位置、颜色、不透明度"""
    ply = PlyData.read(ply_path)
    verts = ply["vertex"]

    positions = np.stack([verts["x"], verts["y"], verts["z"]], axis=-1)
    # f_dc 是 SH 第 0 阶系数，需要 sigmoid 激活
    colors = np.stack([verts["f_dc_0"], verts["f_dc_1"], verts["f_dc_2"]], axis=-1)
    colors = 1.0 / (1.0 + np.exp(-colors))
    colors = np.clip(colors, 0, 1)

    # 提取不透明度用于过滤（logit_opacity -> sigmoid）
    if "opacity" in verts.data.dtype.names:
        logit_opacity = verts["opacity"]
    else:
        logit_opacity = np.full(len(positions), 10.0)
    opacity = 1.0 / (1.0 + np.exp(-logit_opacity))

    return positions, colors, opacity


def downsample(points, colors, max_points=50000, voxel_size=0.0):
    """多种降采样策略级联"""
    n = len(points)

    # 1. 体素降采样（保留结构，优先）
    if voxel_size > 0 and n > max_points:
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        pcd.colors = o3d.utility.Vector3dVector(colors)
        pcd = pcd.voxel_down_sample(voxel_size)
        points = np.asarray(pcd.points)
        colors = np.asarray(pcd.colors)
        n = len(points)

    # 2. 随机采样到目标点数
    if n > max_points:
        rng = np.random.default_rng(42)
        idx = rng.choice(n, max_points, replace=False)
        points = points[idx]
        colors = colors[idx]

    return points, colors


def create_pcd(points, colors):
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    return pcd


def view_interactive(points, colors, point_size=2.0):
    """交互式查看器"""
    pcd = create_pcd(points, colors)
    vis = o3d.visualization.VisualizerWithKeyCallback()
    vis.create_window(window_name="3DGS Viewer", width=1400, height=900)
    vis.add_geometry(pcd)

    opt = vis.get_render_option()
    opt.point_size = point_size
    opt.background_color = np.array([0.1, 0.1, 0.1])

    print(f"\n点云: {len(points)} 个点  |  点大小: {point_size}")
    print("鼠标左键旋转 | 滚轮缩放 | 中键平移 | Q 退出\n")
    vis.run()
    vis.destroy_window()


def take_screenshots(points, colors, output_dir: str, scene: str, point_size=2.0):
    """无 GUI 模式：多视角截图"""
    pcd = create_pcd(points, colors)
    vis = o3d.visualization.Visualizer()
    vis.create_window(visible=False, width=1400, height=900)
    vis.add_geometry(pcd)

    opt = vis.get_render_option()
    opt.point_size = point_size
    opt.background_color = np.array([0.1, 0.1, 0.1])

    ctr = vis.get_view_control()
    viewpoints = {
        "front":  ( 0.0,  0.0, 1.0),
        "top":    ( 0.0, -1.0, 0.0),
        "side":   (-1.0,  0.0, 0.0),
        "persp":  (-0.5, -0.3, 0.8),
    }
    out_dir = os.path.join(output_dir, scene, "screenshots")
    os.makedirs(out_dir, exist_ok=True)

    for name, xyz in viewpoints.items():
        ctr.set_front(np.array(xyz))
        ctr.set_up(np.array([0.0, -1.0, 0.0]) if name != "top" else np.array([0.0, 0.0, -1.0]))
        vis.poll_events()
        vis.update_renderer()
        path = os.path.join(out_dir, f"view_{name}.png")
        vis.capture_screen_image(path)
        print(f"  截图: {path}")
    vis.destroy_window()
    print(f"\n完成: {out_dir}")


def main():
    parser = argparse.ArgumentParser(description="3DGS PLY 点云可视化")
    parser.add_argument("--scene", default="DROID-W/downtown1")
    parser.add_argument("--ply", default="final_gs.ply")
    parser.add_argument("--max_points", type=int, default=50000, help="最大显示点数")
    parser.add_argument("--voxel", type=float, default=0.0, help="体素下采样大小 (如 0.05)")
    parser.add_argument("--point_size", type=float, default=2.0, help="点大小")
    parser.add_argument("--z_min", type=float, default=-50, help="深度裁剪下限")
    parser.add_argument("--z_max", type=float, default=50, help="深度裁剪上限")
    parser.add_argument("--opacity_th", type=float, default=0.0, help="不透明度阈值 (0~1)")
    parser.add_argument("--screenshot", action="store_true")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    ply_path = os.path.join(base_dir, args.scene, args.ply)

    if not os.path.exists(ply_path):
        print(f"错误: 找不到 {ply_path}")
        return

    print(f"加载: {ply_path}")
    positions, colors, opacity = load_gs_ply(ply_path)
    print(f"原始: {len(positions)} 点")

    # 不透明度过滤
    if args.opacity_th > 0:
        mask = opacity > args.opacity_th
        positions, colors = positions[mask], colors[mask]
        print(f"不透明度过滤后 (> {args.opacity_th}): {len(positions)} 点")

    # 深度裁剪
    z = positions[:, 2]
    mask = (z > args.z_min) & (z < args.z_max)
    positions, colors = positions[mask], colors[mask]
    print(f"深度裁剪后: {len(positions)} 点")

    # 降采样
    positions, colors = downsample(positions, colors, args.max_points, args.voxel)
    print(f"降采样后: {len(positions)} 点")

    if args.screenshot:
        take_screenshots(positions, colors, base_dir, args.scene, args.point_size)
    else:
        view_interactive(positions, colors, args.point_size)


if __name__ == "__main__":
    main()
