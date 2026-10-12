#!/usr/bin/env python3
"""
Measure each source's audio before anything is cleaned or transcribed, and
check what cleaning did afterwards.

Default (before cleaning):
  source video  ->  audio/<src>.48k.wav                  (mono 48 kHz, the input to clean_audio.py)
                ->  analysis/<src>.spectrogram.png       (look at it: wind, hum, voice)
                ->  analysis/<src>.wind.json             (loudness + wind map)

  Printed per source:
    - integrated loudness (LUFS), loudness range (LU) and true peak (dBTP) of the source;
    - low band (20-120 Hz) minus voice band (250-4000 Hz), median and p90 over 0.1 s frames;
    - in pauses (quietest 25% of voice-band frames), the low band against the voice band.
      Wind is present when pauses carry low-band energy WIND_EXCESS_DB or more above the voice band;
    - a 10 s map of that difference, and the worst windows.

  Reading the spectrogram: voice is harmonic stripes, roughly 150-700 Hz plus
  formants; wind is fluctuating broadband energy below ~120 Hz that continues
  between words; hum and insects are thin horizontal lines.

--compare (after clean_audio.py): clean/edit/<src>.wav against audio/<src>.48k.wav,
on the same frames, writing analysis/<src>.clean_check.json:
    - pause drop: how far the low band fell in the source's pauses (wind removed);
    - loud-speech loss: how much the loudest 20% of voice-band frames lost (voice damaged).
  A pause drop under PAUSE_DROP_MIN_DB (or, for a gentler --edit-limit-db, under that limit minus
  LIMIT_MARGIN_DB) means wind may remain; a loud-speech loss over LOUD_LOSS_MAX_DB means the voice may be
  damaged. Either is flagged: a reason to listen, not a failure.

Usage:
  python3 measure_audio.py
  python3 measure_audio.py --src B
  python3 measure_audio.py --src B --compare
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402

# Wind map. Bands and windows are the ones that separated windy from calm takes on handheld outdoor footage.
FRAME_HOP_S = 0.1            # one spectrum every 100 ms
NFFT = 8192                  # 5.9 Hz bins at 48 kHz, fine enough to resolve the 20-120 Hz band
LOW_BAND_HZ = (20, 120)      # where wind energy concentrates on the spectrogram
VOICE_BAND_HZ = (250, 4000)  # voice harmonics and formants, above most wind energy
PAUSE_PERCENTILE = 25        # frames below this voice-band percentile are between words
WIND_EXCESS_DB = 6.0         # pause low band this far above the voice band = audible wind
MAP_WINDOW_S = 10            # resolution of the printed wind map
WORST_COUNT = 5
POWER_FLOOR = 1e-12          # avoids log(0) on digital silence (-120 dB)

# Cleaning check, one-sided: too little pause drop means wind may remain; too much loud-speech loss means the voice
# may be damaged. Evidence, all from one project's windy takes: on three short excerpts (slightly different bands
# and frames) pauses fell 25.5-26.8 dB with a 28 dB limit and 33.5-35.5 dB with no limit, and the loudest speech
# lost 0.5-3.3 dB with no limit. On a full 7 min take this function measured the delivered 30 dB edit track at
# 35.1 dB pause drop and 0.4 dB loud-speech loss (no limit: 53.9 and 0.4).
LOUD_PERCENTILE = 80
PAUSE_DROP_MIN_DB = 25.0
LOUD_LOSS_MAX_DB = 3.0
LIMIT_MARGIN_DB = 5.0        # a gentler --edit-limit-db caps the possible drop: expect at least limit - 5 dB
                             # (one project: a 20 dB limit gave 20.7 dB, a 28 dB limit 25.5-26.8 dB)

SPECTROGRAM = "showspectrumpic=s=2400x600:mode=combined:scale=log:fscale=log:legend=1:stop=8000"


def loudness(src: Path) -> dict:
    """Integrated loudness, loudness range and true peak from ffmpeg's loudnorm analysis."""
    r = vc.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-vn",
                "-af", "loudnorm=print_format=summary", "-f", "null", "-"], f"Measuring loudness of {src}")
    found = {}
    for key, label in (("integrated_lufs", "Input Integrated"), ("true_peak_dbtp", "Input True Peak"),
                       ("lra_lu", "Input LRA"), ("threshold_lufs", "Input Threshold")):
        m = re.search(rf"{label}:\s*([-+]?(?:\d+(?:\.\d*)?|inf))", r.stderr)
        if not m:
            vc.die(f"Could not read \"{label}\" from ffmpeg loudnorm output for {src}. "
                   f"Check `ffmpeg -hide_banner -i <file> -af loudnorm=print_format=summary -f null -` works.")
        found[key] = float(m.group(1))
    return found


def db1(v: float) -> float:
    """The value exactly as printed (one decimal), so the JSON and the console never disagree."""
    return float(f"{v:.1f}")


def band_frames(x, sr: int):
    """One row per FRAME_HOP_S: (time s, low-band dB, voice-band dB)."""
    import numpy as np

    hop = int(sr * FRAME_HOP_S)
    f = np.fft.rfftfreq(NFFT, 1 / sr)
    lo = (f >= LOW_BAND_HZ[0]) & (f < LOW_BAND_HZ[1])
    sp = (f >= VOICE_BAND_HZ[0]) & (f < VOICE_BAND_HZ[1])
    window = np.hanning(NFFT)
    rows = []
    for i in range(0, len(x) - NFFT, hop):
        S = np.abs(np.fft.rfft(x[i:i + NFFT] * window)) ** 2
        rows.append((i / sr, 10 * np.log10(S[lo].sum() + POWER_FLOOR), 10 * np.log10(S[sp].sum() + POWER_FLOOR)))
    return np.array(rows)


def wind_map(sid: str, wav: Path) -> dict:
    import numpy as np
    import vnum

    x, sr = vnum.read_wav_mono(wav)
    if len(x) < NFFT + int(sr * FRAME_HOP_S) or len(x) / sr < MAP_WINDOW_S + 1:
        vc.die(f"{sid}: audio is {len(x) / sr:.1f} s; the wind map needs at least {MAP_WINDOW_S + 1} s.")
    r = band_frames(x, sr)
    ratio = r[:, 1] - r[:, 2]
    quiet = r[:, 2] < np.percentile(r[:, 2], PAUSE_PERCENTILE)

    median, p90 = float(np.median(ratio)), float(np.percentile(ratio, 90))
    pause_low, pause_voice = float(np.median(r[quiet, 1])), float(np.median(r[quiet, 2]))
    print(f"== {sid}: low-band minus speech-band dB  median={median:.1f}  p90={p90:.1f}")
    print(f"   in pauses: low-band median {pause_low:.1f} dB vs speech-band {pause_voice:.1f} dB")
    windows, medians = [], []
    for t0 in range(0, int(r[-1, 0]), MAP_WINDOW_S):
        m = (r[:, 0] >= t0) & (r[:, 0] < t0 + MAP_WINDOW_S)
        v = float(np.median(ratio[m]))
        windows.append({"start_s": t0, "end_s": t0 + MAP_WINDOW_S, "low_minus_voice_db": db1(v)})
        medians.append(v)
        print(f"   {t0:4d}s {v:6.1f} {'#' * max(0, int(v + 10))}")

    excess = pause_low - pause_voice
    order = sorted(range(len(windows)), key=lambda k: medians[k], reverse=True)
    worst = [windows[k] for k in order[:WORST_COUNT]]
    present = excess >= WIND_EXCESS_DB
    print("   worst windows: " + ", ".join(f"{w['start_s']}-{w['end_s']}s ({w['low_minus_voice_db']:.1f})" for w in worst))
    print(f"   wind {'PRESENT' if present else 'not detected'}: pauses carry low band {excess:+.1f} dB "
          f"vs voice band (threshold {WIND_EXCESS_DB:+.0f} dB)")
    return {
        "frame_hop_s": FRAME_HOP_S, "nfft": NFFT, "low_band_hz": list(LOW_BAND_HZ), "voice_band_hz": list(VOICE_BAND_HZ),
        "low_minus_voice_median_db": db1(median), "low_minus_voice_p90_db": db1(p90),
        "pause_low_band_median_db": db1(pause_low), "pause_voice_band_median_db": db1(pause_voice),
        "pause_excess_db": db1(excess), "wind_threshold_db": WIND_EXCESS_DB, "wind_present": bool(present),
        "windows": windows, "worst_windows": worst,
    }


def measure(proj: vc.Project, sid: str) -> None:
    src = proj.source_file(sid)
    wav = proj.wav48(sid)
    tmp = wav.with_name(wav.stem + ".partial.wav")
    vc.ffmpeg(["-i", str(src), "-vn", "-ac", "1", "-ar", str(vc.AUDIO_RATE), str(tmp)], f"{sid}: extracting audio")
    os.replace(tmp, wav)

    loud = loudness(src)
    print(f"== {sid}: {src.name}")
    print(f"   integrated {loud['integrated_lufs']:.1f} LUFS   range {loud['lra_lu']:.1f} LU   "
          f"true peak {loud['true_peak_dbtp']:.1f} dBTP")

    png = proj.path("analysis", f"{sid}.spectrogram.png")
    vc.ffmpeg(["-i", str(wav), "-lavfi", SPECTROGRAM, "-frames:v", "1", str(png)], f"{sid}: drawing spectrogram")

    wind = wind_map(sid, wav)
    out = proj.path("analysis", f"{sid}.wind.json")
    vc.write_atomic(out, json.dumps({"src": sid, "audio": str(wav), "spectrogram": str(png),
                                     "loudness": loud, "wind": wind}, indent=1))
    print(f"   wrote {wav}, {png}, {out}", flush=True)


def compare(proj: vc.Project, sid: str) -> None:
    import numpy as np
    import vnum

    raw_path, clean_path = proj.wav48(sid), proj.clean_edit(sid)
    raw, sr = vnum.read_wav_mono(raw_path)
    cln, sr_clean = vnum.read_wav_mono(clean_path)
    if sr != sr_clean:
        vc.die(f"{sid}: {raw_path.name} is {sr} Hz but {clean_path} is {sr_clean} Hz. Re-run clean_audio.py --src {sid}.")
    n = min(len(raw), len(cln))   # the cleaned track starts sample-aligned and ends ~30 ms early
    R, C = band_frames(raw[:n], sr), band_frames(cln[:n], sr)
    if len(R) < 10:
        vc.die(f"{sid}: audio too short to compare ({n / sr:.1f} s).")
    pause = R[:, 2] < np.percentile(R[:, 2], PAUSE_PERCENTILE)
    loud = R[:, 2] > np.percentile(R[:, 2], LOUD_PERCENTILE)
    pause_drop = float(np.median(R[pause, 1]) - np.median(C[pause, 1]))
    loud_loss = float(np.median(R[loud, 2] - C[loud, 2]))
    silent = float(np.median(C[pause, 1])) <= 10 * np.log10(POWER_FLOOR) + 1

    settings = proj.path("clean", "edit", f"{sid}.json")
    limit = json.loads(settings.read_text()).get("limit_db") if settings.is_file() else None
    print(f"== {sid}: {clean_path.name} vs {raw_path.name}"
          + (f" (cleaned with a {limit:g} dB limit)" if limit is not None else ""))
    drop_min = PAUSE_DROP_MIN_DB if limit is None else min(PAUSE_DROP_MIN_DB, limit - LIMIT_MARGIN_DB)
    wind_left, voice_hurt = pause_drop < drop_min, loud_loss > LOUD_LOSS_MAX_DB
    print(f"   pause drop (low band, quietest {PAUSE_PERCENTILE}% of frames): {pause_drop:.1f} dB   "
          + (f"LOW (under {drop_min:g}): wind may remain; listen" if wind_left else f"ok (>= {drop_min:g})")
          + ("   (cleaned pauses are digital silence)" if silent else ""))
    print(f"   loud-speech loss (voice band, loudest {100 - LOUD_PERCENTILE}% of frames): {loud_loss:.1f} dB   "
          + (f"HIGH (over {LOUD_LOSS_MAX_DB:g}): voice may be damaged; listen, or re-clean with a lower "
             f"--edit-limit-db" if voice_hurt else f"ok (<= {LOUD_LOSS_MAX_DB:g})"))
    out = proj.path("analysis", f"{sid}.clean_check.json")
    vc.write_atomic(out, json.dumps({
        "src": sid, "raw": str(raw_path), "clean": str(clean_path), "limit_db": limit,
        "pause_drop_db": db1(pause_drop), "pause_drop_min_db": drop_min, "wind_may_remain": bool(wind_left),
        "loud_speech_loss_db": db1(loud_loss), "loud_speech_loss_max_db": LOUD_LOSS_MAX_DB,
        "voice_may_be_damaged": bool(voice_hurt), "pauses_digital_silence": bool(silent)}, indent=1))
    print(f"   wrote {out}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract 48 kHz audio, measure loudness, draw a spectrogram and map wind.")
    ap.add_argument("--project", type=Path, help="project folder (default: this folder or the nearest parent with project.json)")
    ap.add_argument("--src", action="append", help="source id from project.json (repeatable; default: all)")
    ap.add_argument("--compare", action="store_true",
                    help="after clean_audio.py: report pause drop and loud-speech loss of clean/edit against the source")
    args = ap.parse_args()

    proj = vc.Project(args.project)
    sources = proj.pick_sources(args.src)
    if args.compare:
        for sid in sources:
            for need, step in ((proj.wav48(sid), "measure_audio.py"), (proj.clean_edit(sid), "clean_audio.py")):
                if not need.is_file():
                    vc.die(f"{sid}: {need} not found. Run {step} --src {sid} first.", 2)
    else:
        vc.need_binary("ffmpeg", "Install ffmpeg; doctor.py shows how.")
    vc.require(["numpy"], vc.VENV_CV)
    for sid in sources:
        if args.compare:
            compare(proj, sid)
        else:
            measure(proj, sid)


if __name__ == "__main__":
    main()
