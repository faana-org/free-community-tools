#!/usr/bin/env python3
"""
QA: how much handheld shake the render removed.

Measures camera motion in the rendered video (captions and name pill masked out), converts it back to source
pixels using the zoom each cut actually used, and compares high-frequency shake (path minus a 0.25 s smoothed
path) with the source over the same frames. Cuts shorter than 20 frames are skipped.

Usage:
  python3 shake_metric.py NAME [--project DIR]

Cuts that measure more than 15% more motion than the source are listed to look at. On tight zooms the face and captions fill most
of the frame and the output measurement becomes unreliable (in testing, widening the masked band halved one cut's
reading), so a per-cut figure is a lead to check by eye, not a verdict.

Exit 0 = median shake reduced. Exit 1 = the output's median shake is no lower than the source's. Exit 2 = refused.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402

vc.require(["numpy", "cv2"], vc.VENV_CV)
import numpy as np  # noqa: E402

import camtrack  # noqa: E402
import vnum  # noqa: E402

SHAKE_SIGMA_FRAMES = 7.5      # 0.25 s: slower motion than this counts as intentional
MIN_CUT_FRAMES = 20
EDGE_TRIM = 4                 # frames at each end of a cut ignored (smoothing edge effects)
MASK_ABOVE_CAPTION = 200      # px above the caption centre masked (name pill sits here)
MASK_BELOW_CAPTION = 80
FLAG_RATIO = 1.15             # list a cut when its output shake exceeds the source's by more than this (below is noise)


def main() -> None:
    ap = argparse.ArgumentParser(description="Measure shake removed by stabilisation.")
    ap.add_argument("name")
    ap.add_argument("--project")
    args = ap.parse_args()
    proj = vc.Project(args.project)
    framing_path = proj.work(args.name) / "framing.json"
    if not framing_path.is_file():
        vc.die(f"No finished render for {args.name}. Run render.py {args.name} first.", 2)
    framing = json.loads(framing_path.read_text())
    fmt = vc.FORMATS[framing["format"]]
    OW, OH = fmt["size"]
    cy = fmt["caption_y"]
    out_traj, _ = camtrack.measure(Path(framing["output"]), OW, OH, (cy - MASK_ABOVE_CAPTION, cy + MASK_BELOW_CAPTION))
    out_path = vnum.centre_path(np.array(out_traj, float), OW, OH)
    src_paths = {}
    S, O, t, worse = [], [], 0, []
    for i, cut in enumerate(framing["cuts"]):
        n = cut["frames"]
        sid = cut["src"]
        if sid not in src_paths:
            if not proj.camtrack(sid).is_file():
                vc.die(f"Missing tracking/{sid}.camera.json. Run camtrack.py {sid}.", 2)
            sw, sh = cut["source_size"]
            src_paths[sid] = vnum.centre_path(np.array(json.loads(proj.camtrack(sid).read_text())["traj"], float), sw, sh)
        if n >= MIN_CUT_FRAMES:
            a = int(round(cut["in"] * vc.FPS)) + cut.get("frame_offset", 0)
            sp = src_paths[sid][a:a + n, :2]
            op = out_path[t:t + n, :2] / cut["scale"]
            for arr, acc in ((sp, S), (op, O)):
                r = np.hypot(arr[:, 0] - vnum.gaussian(arr[:, 0], SHAKE_SIGMA_FRAMES),
                             arr[:, 1] - vnum.gaussian(arr[:, 1], SHAKE_SIGMA_FRAMES))[EDGE_TRIM:-EDGE_TRIM]
                acc.append(r)
            if np.median(O[-1]) > FLAG_RATIO * np.median(S[-1]):
                worse.append(f"   cut {i + 1} at {t / vc.FPS:.1f}s (zoom {cut['zoom']:.2f}): output "
                             f"{np.median(O[-1]):.2f} px vs source {np.median(S[-1]):.2f} px")
        t += n
    if not S:
        vc.die(f"{args.name}: no cut is long enough ({MIN_CUT_FRAMES}+ frames) to measure.", 2)
    S, O = np.concatenate(S), np.concatenate(O)
    red_med = 100 * (1 - np.median(O) / np.median(S))
    red_p90 = 100 * (1 - np.percentile(O, 90) / np.percentile(S, 90))
    print(f"{args.name}: shake (source px) source median {np.median(S):.2f} p90 {np.percentile(S, 90):.2f} | "
          f"output median {np.median(O):.2f} p90 {np.percentile(O, 90):.2f} | "
          f"reduction median {red_med:.0f}% p90 {red_p90:.0f}%")
    if framing["format"] != "9x16":
        print(f"{args.name}: {framing['format']} crops leave the face filling most of the frame, so this measurement "
              "is unreliable here (a delivered, visually approved 4:5 cut measured p90 worse than its source). "
              "Judge stabilisation by watching.")
    if worse:
        print(f"{args.name}: {len(worse)} cut(s) measure more motion than the source. Tight framing measures "
              "unreliably, so look at these cuts before calling it shake:")
        print("\n".join(worse))
    sys.exit(0 if red_med > 0 else 1)


if __name__ == "__main__":
    main()
