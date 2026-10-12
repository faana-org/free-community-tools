#!/usr/bin/env python3
"""
QA: re-transcribe a rendered video and compare it with the words the edit meant to keep.

Catches clipped first/last syllables and words lost at a cut. Whisper routinely drops soft fillers and
articles, so every difference is a lead to check by listening at that point, not a verdict.

Usage:
  python3 verify_words.py NAME [--project DIR] [--threads N]

Writes work/NAME/verify/. Prints the match ratio and each difference.
Exit 0 = match ratio at least 0.98 (still read every difference). Exit 1 = ratio below 0.98, or transcription
failed. Exit 2 = refused (render or model missing).
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402

TRAILING_HALLUCINATION = ["thank", "you"]   # whisper's stock output on trailing silence
MIN_MATCH_RATIO = 0.98                      # below this, differences are more than dropped fillers


def toks(t: str) -> list[str]:
    return [x for x in re.sub(r"[^a-z0-9' ]", " ", t.lower().replace("-", " ")).split() if x]


def main() -> None:
    ap = argparse.ArgumentParser(description="Re-transcribe a render and diff it against the intended words.")
    ap.add_argument("name")
    ap.add_argument("--project")
    ap.add_argument("--threads", type=int, default=min(8, os.cpu_count() or 4))
    args = ap.parse_args()
    proj = vc.Project(args.project)
    whisper = vc.need_binary("whisper-cli", "Install whisper.cpp (see doctor.py).")
    if not vc.WHISPER_MODEL.is_file():
        vc.die(f"Whisper model not found at {vc.WHISPER_MODEL}. Run setup_toolkit.py.", 2)
    work = proj.work(args.name)
    framing, cap = work / "framing.json", work / "cap_words.json"
    if not framing.is_file() or not cap.is_file():
        vc.die(f"No finished render for {args.name}. Run render.py {args.name} first.", 2)
    mp4 = Path(json.loads(framing.read_text())["output"])
    vdir = work / "verify"
    vdir.mkdir(exist_ok=True)
    wav = vdir / "out16k.wav"
    (vdir / "out.txt").unlink(missing_ok=True)   # never read a previous run's transcript
    vc.ffmpeg(["-i", mp4, "-vn", "-ac", "1", "-ar", "16000", wav], "Extracting the rendered audio")
    vc.run([whisper, "-m", vc.WHISPER_MODEL, "-f", wav, "-t", str(args.threads), "-l", proj.cfg["language"],
            "-mc", "0", "-otxt", "-of", vdir / "out"], "Transcribing the render")
    heard = (vdir / "out.txt").read_text()
    intended = toks(" ".join(w["w"] for w in json.loads(cap.read_text())))
    got = toks(heard)
    if got[-2:] == TRAILING_HALLUCINATION and intended[-2:] != TRAILING_HALLUCINATION:
        got = got[:-2]
    sm = difflib.SequenceMatcher(a=intended, b=got, autojunk=False)
    print(f"{args.name}: {len(intended)} intended words, match ratio {sm.ratio():.3f}")
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op != "equal":
            print(f"   {op}: intended '{' '.join(intended[a0:a1])}' / heard '{' '.join(got[b0:b1])}'")
    if sm.ratio() < MIN_MATCH_RATIO:
        print(f"{args.name}: match ratio below {MIN_MATCH_RATIO}; listen at each difference before delivering.")
        sys.exit(1)


if __name__ == "__main__":
    main()
