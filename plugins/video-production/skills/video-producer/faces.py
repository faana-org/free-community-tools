#!/usr/bin/env python3
"""
Track the speaker's face through a source video (YuNet), for framing and caption clearance.

Samples at 10 fps on a quarter-size decode; keeps the largest face per sample.
Output tracking/<src>.faces.json:
  {"w": W, "h": H, "fps_sample": 10.0, "samples": [[t, cx, cy, box_w, box_h] | [t, null, null, null, null]]}
Coordinates are full-resolution display pixels (rotation applied).

Usage:
  python3 faces.py [--src ID ...] [--project DIR] [--accept]      default: every source in project.json
  --accept   write the track even when a face was found in under half the samples

Exit 0 = written. Exit 2 = refused (model missing, unknown source). Exit 1 = decode failed, or a face was found
in under half the samples (nothing written for that source unless --accept); other sources still run.
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

SAMPLE_FPS = 10.0
DECODE_DIVISOR = 4          # detection runs on a quarter-size frame
SCORE_THRESHOLD = 0.6
MIN_FOUND_SHARE = 0.5       # below this, framing will mostly guess; stop and tell the person


def track(proj: vc.Project, sid: str, accept: bool) -> bool:
    W, H = proj.source_size(sid)
    sw, sh = W // DECODE_DIVISOR, H // DECODE_DIVISOR
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(proj.source_file(sid)),
                          "-vf", f"fps={SAMPLE_FPS},scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE)
    det = cv2.FaceDetectorYN.create(str(vc.YUNET_MODEL), "", (sw, sh), SCORE_THRESHOLD)
    samples, i = [], 0
    while True:
        buf = p.stdout.read(sw * sh * 3)
        if len(buf) < sw * sh * 3:
            break
        _, faces = det.detect(np.frombuffer(buf, np.uint8).reshape(sh, sw, 3))
        t = round(i / SAMPLE_FPS, 3)
        if faces is not None and len(faces):
            f = max(faces, key=lambda r: r[2] * r[3])
            x, y, w, h = [float(v) * (W / sw) for v in f[:4]]
            samples.append([t, round(x + w / 2), round(y + h / 2), round(w), round(h)])
        else:
            samples.append([t, None, None, None, None])
        i += 1
    vc.check_wait(p, f"Decoding {sid} for face tracking")
    found = sum(1 for s in samples if s[1] is not None)
    if not samples:
        vc.die(f"{sid}: no frames decoded.")
    out = proj.faces(sid)
    share = found / len(samples)
    if share < MIN_FOUND_SHARE and not accept:
        print(f"{sid}: a face was found in only {share:.0%} of samples, so framing would mostly guess. Nothing written. "
              "Check the footage; re-run with --accept to use the track anyway.", file=sys.stderr)
        return False
    vc.write_atomic(out, json.dumps({"w": W, "h": H, "fps_sample": SAMPLE_FPS, "samples": samples}))
    print(f"{sid}: {len(samples)} samples, face found in {found} ({share:.0%}) -> {out.relative_to(proj.root)}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Track the speaker's face in each source.")
    ap.add_argument("--src", action="append", help="source id (repeatable); default all")
    ap.add_argument("--project")
    ap.add_argument("--accept", action="store_true")
    args = ap.parse_args()
    proj = vc.Project(args.project)
    vc.need_binary("ffmpeg", "Install ffmpeg (see doctor.py).")
    if not vc.YUNET_MODEL.is_file():
        vc.die(f"Face model not found at {vc.YUNET_MODEL}. Run setup_toolkit.py.", 2)
    results = [track(proj, sid, args.accept) for sid in proj.pick_sources(args.src)]
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
