#!/usr/bin/env python3
"""
QA: find frames where a burned-in caption covers the speaker's mouth in a rendered video.

Checks every 3rd frame while a caption is on screen: detects the face with landmarks, estimates the lower lip
(mouth corners + 0.09 box widths) and compares it with the caption text top.

Usage:
  python3 qa_mouth.py NAME [--project DIR]      NAME = the EDL/render name (reads work/NAME/)

Exit 0 = no overlaps. Exit 1 = overlaps found (times printed) or no face on most checked frames.
Exit 2 = refused (render not found).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402

vc.require(["numpy", "cv2"], vc.VENV_CV)
import cv2  # noqa: E402
import numpy as np  # noqa: E402

EVERY_NTH_FRAME = 3
LIP_BELOW_CORNERS = 0.09      # box widths from mouth-corner height to the lower lip edge
DETECT_DIVISOR = 2
SCORE_THRESHOLD = 0.6
MAX_NO_FACE_SHARE = 0.5
CAPTION_SIZE_MEASURED = 100   # vc.CAP_HALF was measured at this caption size (same rule as render.py)


def _secs(t: str) -> float:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def check(proj: vc.Project, name: str) -> int:
    work = proj.work(name)
    framing_path, ass_path = work / "framing.json", work / "captions.ass"
    if not framing_path.is_file() or not ass_path.is_file():
        vc.die(f"No finished render for {name} (work/{name}/framing.json). Run render.py {name} first.", 2)
    framing = json.loads(framing_path.read_text())
    mp4 = Path(framing["output"])
    if not mp4.is_file():
        vc.die(f"{mp4} is missing. Re-render {name}.", 2)
    fmt = vc.FORMATS[framing["format"]]
    OW, OH = fmt["size"]
    cap_top = fmt["caption_y"] - vc.CAP_HALF * proj.cfg["captions"]["size"] / CAPTION_SIZE_MEASURED
    visible = [(_secs(a), _secs(b)) for a, b in re.findall(r"Dialogue: 1,([\d:.]+),([\d:.]+),Cap,", ass_path.read_text())]
    dw, dh = OW // DETECT_DIVISOR, OH // DETECT_DIVISOR
    det = cv2.FaceDetectorYN.create(str(vc.YUNET_MODEL), "", (dw, dh), SCORE_THRESHOLD)
    p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(mp4), "-vf", f"scale={dw}:{dh}",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    i, checked, bad, noface, worst = 0, 0, [], 0, -9999.0
    size = dw * dh * 3
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        t = i / vc.FPS
        if i % EVERY_NTH_FRAME == 0 and any(a <= t < e for a, e in visible):
            _, faces = det.detect(np.frombuffer(buf, np.uint8).reshape(dh, dw, 3))
            checked += 1
            if faces is None:
                noface += 1
            else:
                f = max(faces, key=lambda q: q[2] * q[3])
                lip = ((f[11] + f[13]) / 2 + LIP_BELOW_CORNERS * f[2]) * DETECT_DIVISOR
                worst = max(worst, lip - cap_top)
                if lip > cap_top:
                    bad.append(round(t, 2))
        i += 1
    vc.check_wait(p, f"Decoding {mp4.name}")
    print(f"{name}: checked {checked} captioned frames, mouth under caption in {len(bad)}, no face {noface}, "
          f"closest lip-to-caption {-worst:.0f}px" + (f"  at t={bad[:12]}" if bad else ""))
    if bad:
        return 1
    if checked and noface > MAX_NO_FACE_SHARE * checked:
        print(f"{name}: no face on {noface}/{checked} checked frames; look at the video before trusting this check.")
        return 1
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Check captions never cover the speaker's mouth.")
    ap.add_argument("name")
    ap.add_argument("--project")
    args = ap.parse_args()
    proj = vc.Project(args.project)
    if not vc.YUNET_MODEL.is_file():
        vc.die(f"Face model not found at {vc.YUNET_MODEL}. Run setup_toolkit.py.", 2)
    sys.exit(check(proj, args.name))


if __name__ == "__main__":
    main()
