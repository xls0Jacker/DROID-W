"""Convert StereoMIS dataset to DROID-W compatible TUM RGBD format.

StereoMIS is a stereo endoscopic dataset:
  - 1280x2048 video (left camera on top half, right camera on bottom half)
  - groundtruth.txt: frame_id tx ty tz qx qy qz qw
  - StereoCalibration.ini with left/right camera intrinsics
  - masks/ directory with tool segmentation masks

We extract the LEFT camera only (top half, rows 0:1024).
No depth sensor available - dummy depth created as placeholder.
"""

import os
import sys
import cv2
import numpy as np

STEREO_SRC = "/workspace/data/StereoMIS"
DST_BASE = "/workspace/DROID-W/datasets/StereoMIS"


def parse_calibration(calib_path):
    """Parse StereoCalibration.ini and return left camera intrinsics."""
    calib = {}
    with open(calib_path) as f:
        current_section = None
        for line in f:
            line = line.strip()
            if line.startswith('['):
                current_section = line
            elif '=' in line and current_section:
                k, v = line.split('=')
                calib[f"{current_section}.{k.strip()}"] = float(v.strip())
    return {
        'W': int(calib['[StereoLeft].res_x']),
        'H': int(calib['[StereoLeft].res_y']),
        'fx': calib['[StereoLeft].fc_x'],
        'fy': calib['[StereoLeft].fc_y'],
        'cx': calib['[StereoLeft].cc_x'],
        'cy': calib['[StereoLeft].cc_y'],
    }


def get_video_fps(video_path):
    """Get actual FPS from video file."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps


def convert_sequence(seq_name, step):
    """Convert a single sequence."""
    src_dir = os.path.join(STEREO_SRC, seq_name)
    dst_dir = os.path.join(DST_BASE, seq_name)

    video_files = [f for f in os.listdir(src_dir) if f.endswith('.mp4')]
    if not video_files:
        print(f"  SKIP {seq_name}: no video file found")
        return None
    video_path = os.path.join(src_dir, video_files[0])

    calib = parse_calibration(os.path.join(src_dir, 'StereoCalibration.ini'))
    fps = get_video_fps(video_path)

    rgb_dir = os.path.join(dst_dir, 'rgb')
    depth_dir = os.path.join(dst_dir, 'depth')
    os.makedirs(rgb_dir, exist_ok=True)
    os.makedirs(depth_dir, exist_ok=True)

    # Single shared dummy depth image
    dummy_depth = np.zeros((calib['H'], calib['W']), dtype=np.uint16)
    cv2.imwrite(os.path.join(depth_dir, '0.png'), dummy_depth)

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Read max GT frame_id so we don't extract frames without poses
    gt_src = os.path.join(src_dir, 'groundtruth.txt')
    max_gt_frame = 0
    with open(gt_src) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            fid = int(line.split()[0])
            if fid > max_gt_frame:
                max_gt_frame = fid

    rgb_lines = []
    depth_lines = []
    extracted = 0

    for frame_idx in range(total_frames):
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx > max_gt_frame:
            break
        if frame_idx % step != 0:
            continue

        left_frame = frame[:calib['H'], :, :]
        timestamp = frame_idx / fps
        fname = f"{timestamp:.6f}.png"
        cv2.imwrite(os.path.join(rgb_dir, fname), left_frame)
        rgb_lines.append(f"{timestamp:.6f} rgb/{fname}\n")
        depth_lines.append(f"{timestamp:.6f} depth/0.png\n")
        extracted += 1

        if extracted % 2000 == 0:
            print(f"    {extracted} frames...")

    cap.release()

    # Write index files
    with open(os.path.join(dst_dir, 'rgb.txt'), 'w') as f:
        f.write("# color images\n# file: 'stereomis'\n# timestamp filename\n")
        f.writelines(rgb_lines)
    with open(os.path.join(dst_dir, 'depth.txt'), 'w') as f:
        f.write("# depth maps\n# file: 'stereomis'\n# timestamp filename\n")
        f.writelines(depth_lines)

    # Convert groundtruth
    gt_src = os.path.join(src_dir, 'groundtruth.txt')
    gt_dst = os.path.join(dst_dir, 'groundtruth.txt')
    gt_lines = []
    with open(gt_src) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            frame_id = int(parts[0])
            if frame_id % step != 0:
                continue
            timestamp = frame_id / fps
            gt_lines.append(f"{timestamp:.6f} {parts[1]} {parts[2]} {parts[3]} {parts[4]} {parts[5]} {parts[6]} {parts[7]}\n")

    with open(gt_dst, 'w') as f:
        f.write("# ground truth trajectory\n# file: 'stereomis'\n")
        f.write("# timestamp tx ty tz qx qy qz qw\n")
        f.writelines(gt_lines)

    print(f"  {seq_name}: {extracted} frames @ {fps/step:.1f} fps effective")
    return calib


def main():
    # Parse sequences.txt
    seq_steps = {}
    with open(os.path.join(STEREO_SRC, 'sequences.txt')) as f:
        for line in f:
            line = line.strip()
            if not line or ',' not in line:
                continue
            parts = line.split(',')
            if len(parts) >= 2:
                name = parts[0].strip()
                try:
                    step = int(float(parts[1].strip()))
                except ValueError:
                    continue
                seq_steps[name] = step

    # Only convert sequences that actually exist
    available = [s for s in seq_steps if os.path.isdir(os.path.join(STEREO_SRC, s))]
    missing = [s for s in seq_steps if s not in available]

    if missing:
        print(f"Skipping missing sequences: {missing}")

    os.makedirs(DST_BASE, exist_ok=True)

    for seq_name in sorted(available):
        step = max(seq_steps[seq_name], 2)  # min step=2 -> max 30fps
        print(f"Converting {seq_name} (step={step})...")
        calib = convert_sequence(seq_name, step=step)

    print(f"\nDone! Output: {DST_BASE}")


if __name__ == '__main__':
    main()
