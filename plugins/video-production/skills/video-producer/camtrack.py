#!/usr/bin/env python3
"""
Measure handheld camera motion in a source video, frame by frame at 30 fps, for stabilisation.

Corner features tracked with LK optical flow on a one-third-size decode, a similarity transform per frame
pair fitted with RANSAC. Output tracking/<src>.camera.json:
  {"fps": 30, "traj": [[x, y, angle], ...]}   cumulative motion; x, y in full-resolution px, angle in radians;
                                               measured at the image origin (render.py converts to the centre)

Usage:
  python3 camtrack.py [--src ID ...] [--project DIR] [--exclude-band Y1,Y2] [--accept]
  --exclude-band   ignore a horizontal band (full-res px) such as burned-in text that doesn't move with the camera
  --accept         write the path even when motion couldn't be measured on more than 20% of frames

Exit 0 = written. Exit 2 = refused. Exit 1 = decode failed, or motion couldn't be measured on more than 20% of
frames (nothing written for that source unless --accept); other sources still run.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402

vc.require(["numpy", "cv2"], vc.VENV_CV)
import cv2  # noqa: E402
import numpy as np  # noqa: E402

DECODE_DIVISOR = 3
MAX_CORNERS, QUALITY, MIN_DISTANCE, BLOCK = 300, 0.01, 12, 5
MIN_POINTS = 12
LK_WINDOW, LK_LEVELS = (21, 21), 3
RANSAC_PX = 1.5
MAX_FAIL_SHARE = 0.2


def decode_args(video: Path, W: int, H: int, start: float | None = None, seconds: float | None = None) -> list[str]:
    """The one decode used for motion: render.py reuses it so its frames line up with the stored path."""
    sw, sh = W // DECODE_DIVISOR, H // DECODE_DIVISOR
    seek = ["-ss", f"{start:.3f}"] if start is not None else []
    dur = ["-t", f"{seconds:.4f}"] if seconds is not None else []
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", *seek, "-i", str(video), *dur,
            "-vf", f"fps={vc.FPS},scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]


def pair_motion(prev: np.ndarray, g: np.ndarray, k: float, mask: np.ndarray | None = None):
    """(dx, dy, angle) from frame prev to frame g in full-resolution px, or None when it can't be measured."""
    pts = cv2.goodFeaturesToTrack(prev, maxCorners=MAX_CORNERS, qualityLevel=QUALITY,
                                  minDistance=MIN_DISTANCE, blockSize=BLOCK, mask=mask)
    if pts is None or len(pts) < MIN_POINTS:
        return None
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev, g, pts, None, winSize=LK_WINDOW, maxLevel=LK_LEVELS)
    ok = st.reshape(-1) == 1
    if ok.sum() < MIN_POINTS:
        return 0.0, 0.0, 0.0      # too few tracked points: treated as no motion (not counted as a failure)
    m, _ = cv2.estimateAffinePartial2D(pts[ok], nxt[ok], method=cv2.RANSAC, ransacReprojThreshold=RANSAC_PX)
    if m is None:
        return None
    return m[0, 2] * k, m[1, 2] * k, float(np.arctan2(m[1, 0], m[0, 0]))


def measure(video: Path, W: int, H: int, band: tuple[int, int] | None = None) -> tuple[list, int]:
    """Cumulative (x, y, angle) per frame at 30 fps, and the number of frame pairs that couldn't be measured."""
    sw, sh = W // DECODE_DIVISOR, H // DECODE_DIVISOR
    k = W / sw
    p = subprocess.Popen(decode_args(video, W, H), stdout=subprocess.PIPE)
    prev, traj = None, [(0.0, 0.0, 0.0)]
    x = y = a = 0.0
    fails = 0
    while True:
        buf = p.stdout.read(sw * sh)
        if len(buf) < sw * sh:
            break
        g = np.frombuffer(buf, np.uint8).reshape(sh, sw)
        if prev is not None:
            mask = None
            if band:
                mask = np.full(prev.shape, 255, np.uint8)
                mask[int(band[0] / k):int(band[1] / k)] = 0
            motion = pair_motion(prev, g, k, mask)
            if motion is None:
                fails += 1
                motion = (0.0, 0.0, 0.0)
            dx, dy, da = motion
            x, y, a = x + dx, y + dy, a + da
            traj.append((round(x, 3), round(y, 3), round(a, 6)))
        prev = g
    vc.check_wait(p, f"Decoding {video.name} for camera tracking")
    return traj, fails


def track(proj: vc.Project, sid: str, band: tuple[int, int] | None, accept: bool) -> bool:
    W, H = proj.source_size(sid)
    traj, fails = measure(proj.source_file(sid), W, H, band)
    out = proj.camtrack(sid)
    if fails > MAX_FAIL_SHARE * len(traj) and not accept:
        print(f"{sid}: camera motion couldn't be measured on {fails / len(traj):.0%} of frames (featureless or very "
              "dark shots), so stabilisation would be unreliable. Nothing written; re-run with --accept to use it "
              "anyway.", file=sys.stderr)
        return False
    vc.write_atomic(out, json.dumps({"fps": vc.FPS, "traj": traj}))
    print(f"{sid}: {len(traj)} frames, motion not measurable on {fails} -> {out.relative_to(proj.root)}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Measure camera shake in each source.")
    ap.add_argument("--src", action="append", help="source id (repeatable); default all")
    ap.add_argument("--project")
    ap.add_argument("--exclude-band", help="Y1,Y2 in full-resolution px")
    ap.add_argument("--accept", action="store_true")
    args = ap.parse_args()
    band = None
    if args.exclude_band:
        try:
            y1, y2 = (int(v) for v in args.exclude_band.split(","))
            band = (y1, y2)
        except ValueError:
            vc.die("--exclude-band must look like 1500,1700", 2)
    proj = vc.Project(args.project)
    vc.need_binary("ffmpeg", "Install ffmpeg (see doctor.py).")
    results = [track(proj, sid, band, args.accept) for sid in proj.pick_sources(args.src)]
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
