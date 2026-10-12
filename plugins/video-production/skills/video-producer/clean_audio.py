#!/usr/bin/env python3
"""
Remove wind and broadband noise from each source's 48 kHz audio.

  audio/<src>.48k.wav  -> 70 Hz high-pass (2-pole)
                       -> DeepFilterNet, no attenuation limit  -> clean/asr/<src>.wav   (transcription only)
                       -> DeepFilterNet, 30 dB limit           -> clean/edit/<src>.wav  (the voice track for edits)
                                                                  clean/edit/<src>.json (the settings used)

The edit track keeps a natural floor so pauses don't go dead; the ASR track is
fully reduced, which transcribes better but sounds processed. Both start
sample-aligned with the source (deep-filter -D compensates its delay) and end
about 30 ms short of it (measured: 1440 samples at 48 kHz on deep-filter 0.5.6).

Each source gets its own deep-filter call: a shared call carries one take's
internal state into the next, changing its first ~60 s.

Check the result by ear, because you cannot hear it:
  - --samples writes loudness-matched before/after MP3s from the worst stretch
    (see measure_audio.py's worst windows) to <output_dir>/audio_check/. Ask the
    person to listen, and to say if the voice sounds watery or robotic.
  - If it does, clean more gently: a lower --edit-limit-db removes less noise and
    leaves the voice more natural (e.g. --edit-only --edit-limit-db 20; 100 = full
    reduction). --edit-only leaves the ASR track alone, so the transcript and word
    timings stay valid.
  - measure_audio.py --compare reports how far pauses dropped and how much the
    loudest speech lost.

Usage:
  python3 clean_audio.py                          # every source (about 4 min per pass per 7 min take, one laptop)
  python3 clean_audio.py --src B --samples 20@95  # also a 20 s before/after pair starting at 95 s
  python3 clean_audio.py --src B --edit-only --edit-limit-db 20 --samples 20@95
  python3 clean_audio.py --src B --samples-only --samples 20@95

Run measure_audio.py first; it writes the audio this reads.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import wave  # frame counts only: this script needs no numpy, so it runs on any python3
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402

HIGHPASS_POLES = 2
SAMPLE_TARGET_LUFS = -16.0       # listening level for samples; lowered together if either clip would clip
SAMPLE_PEAK_CEILING_DBTP = -1.5  # headroom for MP3 encoding overshoot
SAMPLE_MAX_S = 120               # longer clips don't help a before/after judgement (15-30 s is typical)
SAMPLE_BITRATE = "192k"
LIMIT_RANGE_DB = (1, 100)        # deep-filter -a: 0 would remove nothing, 100 is full reduction


def parse_sample(text: str) -> tuple[float, float]:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)@(\d+(?:\.\d+)?)", text.strip())
    if not m:
        raise argparse.ArgumentTypeError(f"{text!r} must be SECONDS@START, e.g. 20@95")
    dur, start = float(m.group(1)), float(m.group(2))
    if not 1 <= dur <= SAMPLE_MAX_S:
        raise argparse.ArgumentTypeError(f"sample length must be 1-{SAMPLE_MAX_S} s; got {dur:g}")
    return dur, start


def wav_frames(path: Path) -> tuple[int, int]:
    with wave.open(str(path)) as w:
        return w.getnframes(), w.getframerate()


def edit_settings(proj: vc.Project, sid: str) -> Path:
    return proj.path("clean", "edit", f"{sid}.json")


def clean(proj: vc.Project, sid: str, limit_db: float, edit_only: bool) -> None:
    wav48 = proj.wav48(sid)
    tmp = proj.root / "clean" / f".tmp-{sid}"   # deep-filter names its output after its input file
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        hp = tmp / f"{sid}.wav"
        vc.ffmpeg(["-i", str(wav48), "-af", f"highpass=f={vc.HIGHPASS_HZ}:poles={HIGHPASS_POLES}", str(hp)],
                  f"{sid}: high-pass filter")
        passes = [("edit", ["-a", f"{limit_db:g}"], proj.clean_edit(sid), f"{limit_db:g} dB limit")]
        if not edit_only:
            passes.insert(0, ("asr", [], proj.clean_asr(sid), "no limit"))
        for kind, limit, dest, label in passes:
            print(f"{sid}: deep-filter ({label}) -> {dest}", flush=True)
            vc.run([str(vc.DEEP_FILTER), "-D", *limit, "-o", str(tmp / kind), str(hp)], f"{sid}: deep-filter ({label})")
            produced = tmp / kind / hp.name
            if not produced.is_file():
                vc.die(f"{sid}: deep-filter finished but wrote no {produced}. Run doctor.py to check the binary.")
            os.replace(produced, dest)
        vc.write_atomic(edit_settings(proj, sid), json.dumps(
            {"limit_db": limit_db, "highpass_hz": vc.HIGHPASS_HZ, "highpass_poles": HIGHPASS_POLES}, indent=1))
        n_in, sr = wav_frames(wav48)
        n_out, _ = wav_frames(proj.clean_edit(sid))
        print(f"{sid}: edit track cleaned with a {limit_db:g} dB limit; {n_in / sr:.2f} s in, {n_out / sr:.2f} s out "
              f"({(n_in - n_out) / sr * 1000:.0f} ms shorter at the end)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def clip_loudness(path: Path, start: float, dur: float) -> tuple[float, float]:
    """Integrated loudness (LUFS) and true peak (dBTP) of one stretch of a file."""
    r = vc.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{start}", "-t", f"{dur}", "-i", str(path),
                "-af", "loudnorm=print_format=json", "-f", "null", "-"], f"Measuring {path.name} at {start:g}s")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    if not m:
        vc.die(f"Could not read loudnorm JSON for {path} at {start:g}s.")
    stats = json.loads(m.group(0))
    i, tp = float(stats["input_i"]), float(stats["input_tp"])
    if i == float("-inf"):
        vc.die(f"{path.name} is silent from {start:g}s for {dur:g}s; pick a stretch with speech.", 2)
    return i, tp


def samples(proj: vc.Project, sid: str, dur: float, start: float) -> None:
    pair = {"before": proj.wav48(sid), "after": proj.clean_edit(sid)}
    n, sr = wav_frames(pair["after"])
    if start + dur > n / sr:
        vc.die(f"{sid}: --samples {dur:g}@{start:g} runs past the end of the audio ({n / sr:.1f} s).", 2)
    settings = edit_settings(proj, sid)
    limit = json.loads(settings.read_text()).get("limit_db") if settings.is_file() else None
    levels = {k: clip_loudness(p, start, dur) for k, p in pair.items()}
    # one common level, as loud as the target allows without either clip passing the peak ceiling
    target = min(SAMPLE_TARGET_LUFS, *(i + (SAMPLE_PEAK_CEILING_DBTP - tp) for i, tp in levels.values()))
    out_dir = proj.output_dir("audio_check")
    for kind, path in pair.items():
        gain = target - levels[kind][0]
        out = out_dir / f"{sid}_{start:g}s_{dur:g}s_{kind}.mp3"
        vc.ffmpeg(["-ss", f"{start}", "-t", f"{dur}", "-i", str(path), "-af", f"volume={gain:.2f}dB",
                   "-ac", "1", "-c:a", "libmp3lame", "-b:a", SAMPLE_BITRATE, str(out)], f"{sid}: writing {out.name}")
        note = "" if kind == "before" else (f", {limit:g} dB limit" if limit is not None else ", limit not recorded")
        print(f"{sid}: {out}  (was {levels[kind][0]:.1f} LUFS, matched to {target:.1f}{note})")


def main() -> None:
    ap = argparse.ArgumentParser(description="High-pass and DeepFilterNet-denoise source audio into ASR and edit tracks.")
    ap.add_argument("--project", type=Path, help="project folder (default: this folder or the nearest parent with project.json)")
    ap.add_argument("--src", action="append", help="source id from project.json (repeatable; default: all)")
    ap.add_argument("--edit-limit-db", type=float, default=float(vc.DENOISE_EDIT_LIMIT_DB), metavar="N",
                    help=f"attenuation limit for the edit track; lower is gentler (default {vc.DENOISE_EDIT_LIMIT_DB})")
    ap.add_argument("--edit-only", action="store_true", help="re-clean only the edit track; keep clean/asr as it is")
    ap.add_argument("--samples", action="append", type=parse_sample, default=[], metavar="SECONDS@START",
                    help="write a loudness-matched before/after MP3 pair (repeatable)")
    ap.add_argument("--samples-only", action="store_true", help="skip cleaning; only write --samples from existing tracks")
    args = ap.parse_args()

    if not LIMIT_RANGE_DB[0] <= args.edit_limit_db <= LIMIT_RANGE_DB[1]:
        vc.die(f"--edit-limit-db must be {LIMIT_RANGE_DB[0]}-{LIMIT_RANGE_DB[1]} (lower is gentler); "
               f"got {args.edit_limit_db:g}.", 2)
    if args.samples_only and not args.samples:
        vc.die("--samples-only needs at least one --samples SECONDS@START.", 2)
    if args.samples_only and args.edit_only:
        vc.die("Use --samples-only or --edit-only, not both.", 2)
    proj = vc.Project(args.project)
    sources = proj.pick_sources(args.src)
    vc.need_binary("ffmpeg", "Install ffmpeg; doctor.py shows how.")
    if not args.samples_only and not (vc.DEEP_FILTER.is_file() and os.access(vc.DEEP_FILTER, os.X_OK)):
        vc.die(f"deep-filter not found at {vc.DEEP_FILTER}. Run doctor.py, then setup_toolkit.py to install DeepFilterNet.", 2)
    for sid in sources:
        if not proj.wav48(sid).is_file():
            vc.die(f"{sid}: {proj.wav48(sid)} not found. Run measure_audio.py --src {sid} first.", 2)
        if args.samples_only and not proj.clean_edit(sid).is_file():
            vc.die(f"{sid}: {proj.clean_edit(sid)} not found. Run clean_audio.py --src {sid} without --samples-only.", 2)
        if args.edit_only and not proj.clean_asr(sid).is_file():
            vc.die(f"{sid}: {proj.clean_asr(sid)} not found; --edit-only needs a finished clean. "
                   f"Run clean_audio.py --src {sid} without --edit-only.", 2)

    for sid in sources:
        if not args.samples_only:
            clean(proj, sid, args.edit_limit_db, args.edit_only)
        for dur, start in args.samples:
            samples(proj, sid, dur, start)


if __name__ == "__main__":
    main()
