#!/usr/bin/env python3
"""
Check word timings against where the cleaned audio actually has voice.

Detects voice regions from 20 ms energy on clean/asr/<src>.wav, writes them
to analysis/<src>.voice_regions.json ([[start_s, end_s], ...]), then reports:

  - UNCOVERED voice: regions longer than UNCOVERED_MIN_S with no word overlapping.
    Re-transcribe those snippets; filler or noise is fine, missing content is not.
  - words starting in silence: word starts more than SILENCE_MARGIN_S from any
    voice region. Should be ~0 after align.py. On the footage these numbers
    were tuned on, whisper's DTW timings put 13-15% of words there and forced
    alignment 0-0.5%.

Usage:
  python3 vad_check.py                       # newest word file per source: final, else aligned, else words
  python3 vad_check.py --src B --stage words # check whisper's raw timings instead
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402

FRAME_S = 0.02             # energy frame
FLOOR_PERCENTILE = 20      # the quiet floor: 20th percentile of frame energy
VOICE_ABOVE_FLOOR_DB = 18  # voice = frames this far above the quiet floor of the denoised track
BRIDGE_FRAMES = 10         # gaps shorter than 200 ms stay inside one region (stops between syllables)
MIN_REGION_S = 0.15        # shorter bursts are clicks, not speech
UNCOVERED_MIN_S = 0.4      # shorter uncovered regions are breaths and lip noise
SILENCE_MARGIN_S = 0.3     # a word start this far outside every voice region is suspect
ENERGY_FLOOR = 1e-10       # avoids log(0) on digital silence
REPORT_MAX = 30
STAGES = ("final", "aligned", "words")


def word_file(proj: vc.Project, sid: str, stage: str | None) -> Path:
    files = {"final": proj.final_words(sid), "aligned": proj.aligned(sid), "words": proj.words(sid)}
    if stage:
        if not files[stage].is_file():
            vc.die(f"{sid}: {files[stage]} not found.", 2)
        return files[stage]
    for name in STAGES:
        if files[name].is_file():
            return files[name]
    vc.die(f"{sid}: no word file yet. Run transcribe.py --src {sid} (then align.py) first.", 2)


def voice_regions(path: Path) -> tuple[list[tuple[float, float]], float]:
    import numpy as np
    import vnum

    x, sr = vnum.read_wav_mono(path)
    hop = int(sr * FRAME_S)
    nf = len(x) // hop
    if nf < BRIDGE_FRAMES * 5:
        vc.die(f"{path} is too short ({len(x) / sr:.2f} s) to find voice regions.")
    e = np.array([10 * np.log10(np.mean(x[i * hop:(i + 1) * hop] ** 2) + ENERGY_FLOOR) for i in range(nf)])
    thr = float(np.percentile(e, FLOOR_PERCENTILE) + VOICE_ABOVE_FLOOR_DB)
    act = e > thr
    reg = []
    i = 0
    while i < nf:
        if act[i]:
            j = i
            while j < nf and (act[j] or (j + BRIDGE_FRAMES < nf and act[j:j + BRIDGE_FRAMES].any())):
                j += 1
            if (j - i) * FRAME_S >= MIN_REGION_S:
                reg.append((i * FRAME_S, j * FRAME_S))
            i = j
        i += 1
    return reg, thr


def check(proj: vc.Project, sid: str, stage: str | None) -> None:
    audio = proj.clean_asr(sid)
    if not audio.is_file():
        vc.die(f"{sid}: {audio} not found. Run clean_audio.py --src {sid} first.", 2)
    wf = word_file(proj, sid, stage)
    words = json.loads(wf.read_text())
    reg, thr = voice_regions(audio)

    print(f"== {sid}: {wf.name}: floor thr {thr:.1f} dB, {len(reg)} voice regions, {len(words)} words")
    uncovered = [(a, b) for a, b in reg
                 if b - a > UNCOVERED_MIN_S and not any(wd["s"] < b and wd["e"] > a for wd in words)]
    for a, b in uncovered:
        print(f"   UNCOVERED voice {a:7.2f}-{b:7.2f} ({b - a:.1f}s)")
    bad = [wd for wd in words if not any(a - SILENCE_MARGIN_S <= wd["s"] <= b + SILENCE_MARGIN_S for a, b in reg)]
    print(f"   words starting in silence: {len(bad)}: " + ", ".join(f'{wd["w"]}@{wd["s"]}' for wd in bad[:REPORT_MAX]))

    out = proj.voice_regions(sid)
    vc.write_atomic(out, json.dumps(reg))
    print(f"   {len(uncovered)} uncovered region(s); wrote {out}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Find voice regions and check word timings against them.")
    ap.add_argument("--project", type=Path, help="project folder (default: this folder or the nearest parent with project.json)")
    ap.add_argument("--src", action="append", help="source id from project.json (repeatable; default: all)")
    ap.add_argument("--stage", choices=STAGES, help="which word file to check (default: the newest stage present)")
    args = ap.parse_args()

    proj = vc.Project(args.project)
    sources = proj.pick_sources(args.src)
    vc.require(["numpy"], vc.VENV_CV)
    for sid in sources:
        check(proj, sid, args.stage)


if __name__ == "__main__":
    main()
