#!/usr/bin/env python3
"""
Transcribe each source's cleaned audio with whisper.cpp, then flatten the
result into a word list with timings.

  clean/asr/<src>.wav  ->  transcripts/<src>.16k.wav            (16 kHz mono; align.py and score_phrases.py read it too)
                       ->  transcripts/<src>.whisper.json/.srt  (whisper-cli -ojf -osrt; log in <src>.whisper.log)
                       ->  transcripts/<src>.words.json         (flat words, seconds)

Word timings here are whisper's DTW guesses. Never cut or caption on them:
run align.py next.

Usage:
  python3 transcribe.py                    # every source, one after another
  python3 transcribe.py --src A --src B
  python3 transcribe.py --words-only       # re-convert existing whisper JSON; no whisper, no audio
  python3 transcribe.py --resample-only    # only re-create transcripts/<src>.16k.wav from clean/asr (seconds)

Timing, measured on one laptop CPU: two takes of about 7 min, transcribed at
the same time as two whisper processes splitting the cores, took about 20 min
each. This script runs sources one after another; to run them at the same
time, start one job per source and split the cores between them:

  python3 transcribe.py --src A --threads 7 &
  python3 transcribe.py --src B --threads 7 &
  wait
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402

ASR_RATE = 16000                 # whisper.cpp only accepts 16 kHz input
WHISPER_ARGS = [
    "-mc", "0",                  # no text context between windows: prevents repetition loops on long takes
    "--suppress-nst",            # drop non-speech tokens ([music], (wind)...)
    "-ojf", "-osrt",             # full JSON with per-token DTW times, plus an SRT for reading
    "--dtw", "large.v3.turbo",   # DTW alignment heads for the large-v3-turbo model in WHISPER_MODEL
]
# whisper.cpp stops getting faster past the physical core count; logical/2 approximates that.
MAX_THREADS = 8
MIN_WORD_S = 0.08                # a word is never shorter than this (DTW sometimes gives zero-length words)
LOG_TAIL_LINES = 12


# --------------------------------------------------------------------------
# whisper JSON -> words
# --------------------------------------------------------------------------


def whisper_to_words(d: dict) -> list[dict]:
    """Flatten whisper.cpp -ojf JSON into [{"w", "s", "e", "p"}].

    Word start = DTW time of its first token (falls back to the token offset);
    word end = min(next word start, last token offset end), at least MIN_WORD_S.
    Special tokens ([_BEG_], [_TT_n] ...) and empty tokens are dropped; p is the
    lowest token probability in the word.
    """
    toks = []
    for seg in d["transcription"]:
        for t in seg.get("tokens", []):
            txt = t["text"]
            if txt.startswith("[_") or not txt:
                continue
            dtw = t.get("t_dtw", -1)
            s = dtw / 100.0 if dtw is not None and dtw >= 0 else t["offsets"]["from"] / 1000.0
            toks.append({"text": txt, "s": s, "o_to": t["offsets"]["to"] / 1000.0, "p": t.get("p", 1.0)})

    words: list[dict] = []
    for t in toks:
        if not words or t["text"].startswith(" "):
            words.append({"w": t["text"].strip(), "s": t["s"], "e": t["o_to"], "p": [t["p"]]})
        else:
            words[-1]["w"] += t["text"]
            words[-1]["e"] = t["o_to"]
            words[-1]["p"].append(t["p"])
    words = [w for w in words if w["w"]]
    for i, w in enumerate(words):
        nxt = words[i + 1]["s"] if i + 1 < len(words) else w["e"]
        w["e"] = round(max(w["s"] + MIN_WORD_S, min(w["e"], nxt)), 3)
        w["s"] = round(w["s"], 3)
        w["p"] = round(min(w["p"]), 2)
    return words


def write_words(proj: vc.Project, sid: str) -> None:
    src = proj.whisper_json(sid)
    if not src.is_file():
        vc.die(f"{sid}: {src} not found. Run transcribe.py --src {sid} without --words-only first.", 2)
    try:
        d = json.loads(src.read_text())
    except json.JSONDecodeError as exc:
        vc.die(f"{sid}: {src} is not valid JSON ({exc}). Re-run transcribe.py --src {sid}.")
    if "transcription" not in d:
        vc.die(f"{sid}: {src} has no \"transcription\"; it was not written by whisper-cli -ojf. Re-run transcribe.py.")
    words = whisper_to_words(d)
    if not words:
        vc.die(f"{sid}: whisper produced no words. Check the cleaned audio has speech (measure_audio.py, clean_audio.py).")
    out = proj.words(sid)
    vc.write_atomic(out, json.dumps(words, indent=0))
    print(f"{out}: {len(words)} words")


# --------------------------------------------------------------------------
# audio and whisper
# --------------------------------------------------------------------------


def resample(proj: vc.Project, sid: str) -> None:
    """clean/asr/<src>.wav -> transcripts/<src>.16k.wav. Deterministic, so re-creating it matches what whisper heard."""
    wav16 = proj.asr16(sid)
    tmp16 = wav16.with_name(wav16.stem + ".partial.wav")
    vc.ffmpeg(["-i", str(proj.clean_asr(sid)), "-ac", "1", "-ar", str(ASR_RATE), str(tmp16)],
              f"{sid}: resampling to 16 kHz")
    os.replace(tmp16, wav16)
    print(f"{wav16}: written", flush=True)


def run_whisper(proj: vc.Project, sid: str, threads: int) -> None:
    wav16 = proj.asr16(sid)
    out_json = proj.whisper_json(sid)
    stem = out_json.with_suffix("")                      # whisper-cli appends .json / .srt itself
    log = stem.with_name(stem.name + ".log")
    cmd = ["whisper-cli", "-m", str(vc.WHISPER_MODEL), "-f", str(wav16), "-t", str(threads),
           "-l", proj.cfg["language"], *WHISPER_ARGS, "-of", str(stem)]
    print(f"{sid}: transcribing {wav16.name} with {threads} threads (log: {log})", flush=True)
    out_json.unlink(missing_ok=True)                     # a stale transcript must never pass for this run's
    with open(log, "w") as fh:
        code = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT).returncode
    if code != 0 or not out_json.is_file():
        tail = log.read_text(errors="replace").strip().splitlines()[-LOG_TAIL_LINES:]
        vc.die(f"{sid}: whisper-cli failed (exit {code}):\n  " + "\n  ".join(tail))


def main() -> None:
    ap = argparse.ArgumentParser(description="Transcribe cleaned audio with whisper.cpp and write words.json.")
    ap.add_argument("--project", type=Path, help="project folder (default: this folder or the nearest parent with project.json)")
    ap.add_argument("--src", action="append", help="source id from project.json (repeatable; default: all)")
    ap.add_argument("--words-only", action="store_true",
                    help="skip whisper; re-convert the existing transcripts/<src>.whisper.json")
    ap.add_argument("--resample-only", action="store_true",
                    help="only re-create transcripts/<src>.16k.wav from clean/asr/<src>.wav (no whisper)")
    ap.add_argument("--threads", type=int, default=0, help="whisper threads (default: half the CPU count, max 8)")
    args = ap.parse_args()
    if args.words_only and args.resample_only:
        vc.die("Use --words-only or --resample-only, not both.", 2)
    if args.threads < 0:
        vc.die("--threads must be positive.", 2)

    proj = vc.Project(args.project)
    sources = proj.pick_sources(args.src)
    whisper = not (args.words_only or args.resample_only)

    if not args.words_only:
        vc.need_binary("ffmpeg", "Install ffmpeg; doctor.py shows how.")
        for sid in sources:
            if not proj.clean_asr(sid).is_file():
                vc.die(f"{sid}: {proj.clean_asr(sid)} not found. Run clean_audio.py --src {sid} first.", 2)
    if whisper:
        vc.need_binary("whisper-cli", "Run doctor.py, then setup_toolkit.py to install whisper.cpp.")
        if not vc.WHISPER_MODEL.is_file():
            vc.die(f"Whisper model not found at {vc.WHISPER_MODEL}. Run setup_toolkit.py to download it.", 2)
    threads = args.threads or max(1, min(MAX_THREADS, (os.cpu_count() or 2) // 2))

    for sid in sources:
        if not args.words_only:
            resample(proj, sid)
        if whisper:
            run_whisper(proj, sid, threads)
        if not args.resample_only:
            write_words(proj, sid)


if __name__ == "__main__":
    main()
