#!/usr/bin/env python3
"""
Final pass over every edit: rebuild the cut lists, render the masters, run every QA check, report one table.

For each spec: edl.py -> render.py (in parallel) -> qa_mouth.py -> verify_words.py -> [shake_metric.py]
-> delivery checks on the file itself:
   frame count matches the cut list; audio length matches the video within one frame; no location metadata;
   integrated loudness within LOUDNESS_RANGE_LUFS; true peak at or below TRUE_PEAK_MAX_DBTP.

Usage:
  python3 final_pass.py [SPEC ...] [--project DIR] [--jobs N] [--shake] [--preview]
  SPEC        spec names (specs/SPEC.json); default: all specs
  --jobs      renders at once (default: a quarter of the CPU cores; each render uses several)
  --shake     also measure shake reduction (re-tracks each render; slower)

Logs per edit in work/<name>/final_pass.log. verify_words differences are leads to listen to, not failures.
Exit 0 = every render and check passed. Exit 1 = something failed (see the table). Exit 2 = refused.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402

LOUDNESS_RANGE_LUFS = (-18.0, -13.0)   # the voice chain targets about -15; short clips measure ~1 LU lower
TRUE_PEAK_MAX_DBTP = -1.0
LOG_TAIL_LINES = 12


def step(script: str, args: list[str], log: Path) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(vc.HERE / script), *args], capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    with log.open("a") as fh:
        fh.write(f"\n$ {script} {' '.join(args)}\n{out}(exit {r.returncode})\n")
    return r.returncode, out


def delivery_checks(mp4: Path, expected_frames: int) -> tuple[bool, str]:
    frames = vc.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                     "stream=nb_read_frames", "-of", "csv=p=0", mp4], "Counting frames").stdout.strip()
    adur = vc.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration",
                   "-of", "csv=p=0", mp4], "Reading audio length").stdout.strip()
    tags = vc.run(["ffprobe", "-v", "error", "-show_entries", "format_tags:stream_tags", "-of", "json", mp4],
                  "Reading metadata").stdout
    loud = vc.run(["ffmpeg", "-hide_banner", "-nostats", "-i", mp4, "-af", "loudnorm=print_format=summary",
                   "-f", "null", "-"], "Measuring loudness").stderr
    m_lufs = re.search(r"Input Integrated:\s+(-?(?:[\d.]+|inf))", loud)
    m_tp = re.search(r"Input True Peak:\s+(-?(?:[\d.]+|inf))", loud)
    if not m_lufs or not m_tp:
        return False, "loudness couldn't be measured (no audio track?)"
    lufs, tp = float(m_lufs.group(1)), float(m_tp.group(1))
    problems = []
    if frames != str(expected_frames):
        problems.append(f"frames {frames} != {expected_frames}")
    if abs(float(adur or 0) - expected_frames / vc.FPS) > 1 / vc.FPS + 1e-3:
        problems.append(f"audio {adur}s vs video {expected_frames / vc.FPS:.3f}s")
    if "location" in tags.lower():
        problems.append("location metadata present")
    if not LOUDNESS_RANGE_LUFS[0] <= lufs <= LOUDNESS_RANGE_LUFS[1]:
        problems.append(f"loudness {lufs} LUFS")
    if tp > TRUE_PEAK_MAX_DBTP:
        problems.append(f"true peak {tp} dBTP")
    summary = f"{expected_frames / vc.FPS:.1f}s {lufs} LUFS {tp} dBTP"
    return not problems, summary + ("" if not problems else "  ! " + "; ".join(problems))


def main() -> None:
    ap = argparse.ArgumentParser(description="Render every edit and run all QA checks.")
    ap.add_argument("specs", nargs="*")
    ap.add_argument("--project")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) // 4))
    ap.add_argument("--shake", action="store_true")
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()
    proj = vc.Project(args.project)
    vc.need_binary("ffmpeg", "Install ffmpeg (see doctor.py).")
    names = args.specs or sorted(p.stem for p in (proj.root / "specs").glob("*.json"))
    if not names:
        vc.die("No specs in specs/. Write the edit specs first.", 2)
    pflag = ["--project", str(proj.root)]

    edits = []   # (spec, edl name, log)
    for spec in names:
        sp = proj.spec(spec)
        if not sp.is_file():
            vc.die(f"specs/{spec}.json not found.", 2)
        try:
            name = json.loads(sp.read_text())["name"]
        except (json.JSONDecodeError, KeyError, TypeError):
            vc.die(f"specs/{spec}.json isn't a valid spec (it needs a \"name\"). Check it with edl.py {spec}.", 2)
        log = proj.work(name, create=True) / "final_pass.log"
        log.write_text("")
        code, out = step("edl.py", [spec, *pflag], log)
        if code != 0:
            vc.die(f"{spec}: edl.py failed:\n{out.strip()}", 2 if code == 2 else 1)
        edits.append((spec, name, log))

    def render(e):
        _, name, log = e
        return step("render.py", [name, *pflag, *(["--preview"] if args.preview else [])], log)

    print(f"Rendering {len(edits)} edit(s), {args.jobs} at a time...", flush=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        renders = list(pool.map(render, edits))

    rows, ok_all = [], True
    for (spec, name, log), (rcode, rout) in zip(edits, renders):
        if rcode != 0:
            ok_all = False
            tail = "\n    ".join(rout.strip().splitlines()[-LOG_TAIL_LINES:])
            rows.append(f"FAIL {name}: render failed\n    {tail}")
            continue
        framing = json.loads((proj.work(name) / "framing.json").read_text())
        mp4 = Path(framing["output"])
        expected = sum(c["frames"] for c in framing["cuts"])
        mcode, mout = step("qa_mouth.py", [name, *pflag], log)
        vcode, vout = step("verify_words.py", [name, *pflag], log)
        scode, sout = step("shake_metric.py", [name, *pflag], log) if args.shake else (0, "")
        dok, dsum = delivery_checks(mp4, expected)
        passed = dok and mcode == 0 and vcode == 0 and scode == 0
        ok_all &= passed
        lines = [f"{'PASS' if passed else 'FAIL'} {name}: {dsum}"]
        for out in (mout, vout, sout if args.shake else ""):
            lines += ["    " + ln for ln in out.strip().splitlines() if ln.startswith((f"{name}:", "   "))]
        rows.append("\n".join(lines))
    print("\n".join(rows))
    print("ALL PASSED" if ok_all else "SOME CHECKS FAILED (logs: work/<name>/final_pass.log)")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
