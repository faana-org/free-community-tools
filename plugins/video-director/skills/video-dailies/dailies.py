#!/usr/bin/env python3
"""Dailies: inventory, contact sheets and audio flags for every take from a directed shoot.

Usage:
  python3 dailies.py --check
  python3 dailies.py <project folder> <clip or folder> [<clip or folder> ...] [options]

Writes <project folder>/dailies/:
  inventory.json         one entry per clip: fixed technical fields, audio flags, slate read, sheet path
  sheets/NN_<name>.jpg   contact sheet, one frame per interval with a timestamp, for judging framing
  listen/NN_<name>.m4a   10 s listening sample for every clip flagged for wind or clipping

What the checks can and can't tell you:
  - Contact sheets catch composition: shot size, eye height, where the person enters and exits, space for a
    title, a clutter or exposure problem. They can't judge a performance, focus hunting or a wobble between
    frames. The actor watches the real playback before a take is chosen.
  - The wind flag mirrors video-production's measure_audio.py (same bands, measured only in pauses, same 6 dB
    threshold) but uses ffmpeg band filters instead of an FFT. It's an indicator: a person confirms it by
    listening to the sample, and measure_audio.py gives the real answer during the edit.
  - The slate read transcribes the first seconds with whisper-cli when the video toolkit is installed. It is
    best-effort: anything that doesn't read as "shot N take M" is marked UNCERTAIN.

Options:
  --interval S        seconds between frames on the sheet (default: 1, widened automatically for long clips)
  --no-slate          skip the slate read
  --allow-synced      allow writing into iCloud / Google Drive / Dropbox synced folders (off by default: sheets
                      are stills of people and places and would upload)

Privacy: the inventory records a fixed list of technical fields. Location, device and software tags that
phones write into the file are never copied.

Exit 0 = done (individual clip failures are listed in the inventory). Exit 2 = nothing usable or refused.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from array import array
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".avi", ".mts", ".hevc"}
TOOLKIT = Path(os.environ.get("VIDEO_TOOLKIT_HOME", Path.home() / ".local" / "share" / "video-toolkit"))
WHISPER_MODEL = TOOLKIT / "models" / "ggml-large-v3-turbo.bin"

# Wind indicator: bands, pause percentile and threshold copied from video-production measure_audio.py, where they
# were measured on handheld outdoor talking-head footage. Change only with a new measurement.
LOW_BAND_HZ = (20, 120)
VOICE_BAND_HZ = (250, 4000)
PAUSE_PERCENTILE = 25
WIND_EXCESS_DB = 6.0
FRAME_HOP_S = 0.1
ANALYSIS_SR = 16000
POWER_FLOOR = 1e-12

CLIP_PEAK_DBFS = -0.5          # sample peak at or above this = likely clipped
MAX_TILES = 60                 # frames per sheet; the interval widens to stay under it
SHEET_COLS = 6
TILE_W = 240
SLATE_SECONDS = 6
SAMPLE_SECONDS = 10
SYNCED_DIRS = [Path.home() / "Library" / "CloudStorage", Path.home() / "Library" / "Mobile Documents",
               Path.home() / "Dropbox", Path.home() / "Google Drive"]
NUMBER_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen twenty".split())}
NUMBER_WORDS.update({"to": 2, "too": 2, "for": 4, "won": 1})


# --------------------------------------------------------------------------
# tools
# --------------------------------------------------------------------------

def find_installed_tools() -> None:
    """Same PATH ordering as video-production's vcore: Homebrew dirs added, ffmpeg-full first."""
    parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    extra = [d for d in ("/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".local" / "bin"))
             if Path(d).is_dir() and d not in parts]
    full = [d for d in ("/opt/homebrew/opt/ffmpeg-full/bin", "/usr/local/opt/ffmpeg-full/bin") if Path(d).is_dir()]
    os.environ["PATH"] = os.pathsep.join(full + [p for p in parts if p not in full] + extra)


find_installed_tools()


def run(cmd: list[str], timeout: float, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=not binary, timeout=timeout)


def ffin(path: Path) -> str:
    """ffmpeg input spec that can't be read as a protocol (a ':' in the name) or an option (a leading '-')."""
    return "file:" + str(path.resolve())


def ffmpeg_filters() -> set[str]:
    try:
        r = run(["ffmpeg", "-hide_banner", "-filters"], 30)
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return {m.group(1) for m in re.finditer(r"^\s*\S+\s+(\w+)\s", r.stdout, re.M)}


def whisper_cli() -> str | None:
    return shutil.which("whisper-cli") if WHISPER_MODEL.exists() else None


def check() -> int:
    ok = True
    ff = shutil.which("ffmpeg")
    print(f"[{'  OK  ' if ff else ' FIX  '}] ffmpeg {'at ' + ff if ff else 'not found: set up with the video-setup skill'}")
    ok &= bool(ff)
    fp = shutil.which("ffprobe")
    print(f"[{'  OK  ' if fp else ' WARN '}] ffprobe {'found' if fp else 'missing: falling back to ffmpeg -i'}")
    if ff:
        f = ffmpeg_filters()
        for name, why in (("ebur128", "loudness"), ("drawtext", "timestamps on sheets"),
                          ("zscale", "HDR colour on sheets"), ("tonemap", "HDR colour on sheets")):
            print(f"[{'  OK  ' if name in f else ' WARN '}] ffmpeg filter {name} ({why})")
    w = whisper_cli()
    print(f"[{'  OK  ' if w else ' WARN '}] slate read {'available' if w else 'off: video toolkit not installed (optional)'}")
    free = shutil.disk_usage(Path.home()).free / 1e9
    print(f"[{'  OK  ' if free > 2 else ' WARN '}] free disk {free:.1f} GB")
    return 0 if ok else 2


# --------------------------------------------------------------------------
# probing
# --------------------------------------------------------------------------

def probe(path: Path) -> dict:
    """Fixed technical fields only. Never copy format or stream tags (they carry GPS and device data)."""
    info = {"duration_s": None, "width": None, "height": None, "fps": None, "rotation": 0, "vcodec": None,
            "pix_fmt": None, "color_transfer": None, "audio_channels": 0}
    if shutil.which("ffprobe"):
        try:
            r = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", ffin(path)], 120)
            if r.returncode == 0:
                d = json.loads(r.stdout)
                info["duration_s"] = float(d.get("format", {}).get("duration") or 0) or None
                for s in d.get("streams", []):
                    if s.get("codec_type") == "video" and info["width"] is None:
                        info.update(width=s.get("width"), height=s.get("height"), vcodec=s.get("codec_name"),
                                    pix_fmt=s.get("pix_fmt"), color_transfer=s.get("color_transfer"))
                        num, _, den = (s.get("avg_frame_rate") or "0/1").partition("/")
                        info["fps"] = round(float(num) / float(den or 1), 3) if float(den or 1) else None
                        for sd in s.get("side_data_list", []) or []:
                            if "rotation" in sd:
                                info["rotation"] = int(sd["rotation"])
                    elif s.get("codec_type") == "audio" and not info["audio_channels"]:
                        info["audio_channels"] = int(s.get("channels") or 0)
                if info["duration_s"]:
                    return info
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
    # Fallback: parse ffmpeg -i (ffprobe has been seen broken on some Macs)
    r = run(["ffmpeg", "-hide_banner", "-i", ffin(path)], 120)
    err = r.stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", err)
    if m:
        info["duration_s"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    v = re.search(r"Stream #.*?Video:\s*(\w+)[^,]*,\s*([\w]+)(\(([^)]*)\))?.*?,\s*(\d{2,5})x(\d{2,5}).*?([\d.]+)\s*fps", err)
    if v:
        info.update(vcodec=v.group(1), pix_fmt=v.group(2), width=int(v.group(5)), height=int(v.group(6)),
                    fps=float(v.group(7)))
        if v.group(4):
            if "arib-std-b67" in v.group(4):
                info["color_transfer"] = "arib-std-b67"
            elif "smpte2084" in v.group(4):
                info["color_transfer"] = "smpte2084"
    rot = re.search(r"rotation of (-?[\d.]+) degrees", err) or re.search(r"rotate\s*:\s*(-?\d+)", err)
    if rot:
        info["rotation"] = int(float(rot.group(1)))
    a = re.search(r"Stream #.*?Audio:.*?,\s*\d+ Hz,\s*(mono|stereo|[\d.]+ channels|\d+\.\d)", err)
    if a:
        info["audio_channels"] = 1 if a.group(1) == "mono" else 2
    return info


def is_hdr(info: dict) -> bool:
    return info.get("color_transfer") in ("arib-std-b67", "smpte2084")


def display_orientation(info: dict) -> str:
    w, h = info.get("width") or 0, info.get("height") or 0
    if abs(info.get("rotation") or 0) in (90, 270):
        w, h = h, w
    return "portrait" if h > w else "landscape" if w > h else "square"


# --------------------------------------------------------------------------
# contact sheet
# --------------------------------------------------------------------------

def contact_sheet(path: Path, info: dict, out: Path, interval: float, filters: set[str]) -> tuple[str | None, str]:
    dur = info["duration_s"] or 0
    step = max(interval, math.ceil(dur / MAX_TILES)) if dur else interval
    tiles = max(1, min(MAX_TILES, math.ceil(dur / step))) if dur else 1
    rows = max(1, math.ceil(tiles / SHEET_COLS))
    chain = []
    note = ""
    if is_hdr(info):
        if {"zscale", "tonemap"} <= filters:
            chain.append("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
                         "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
        else:
            note = "HDR footage: sheet colours are approximate"
    chain += [f"fps=1/{step}", f"scale={TILE_W}:-2"]
    ts = "drawtext=text='%{pts\\:hms}':x=4:y=4:fontsize=14:fontcolor=yellow:box=1:boxcolor=black@0.7"
    tile = f"tile={SHEET_COLS}x{rows}:padding=2:color=black"
    timeout = 60 + 2 * dur
    for with_ts in ((True, False) if "drawtext" in filters else (False,)):
        vf = ",".join(chain + ([ts] if with_ts else []) + [tile])
        # Keyframes only is fast; some encoders leave too few keyframes, so retry decoding every frame.
        for skip in (["-skip_frame", "nokey"], []):
            cmd = ["ffmpeg", "-hide_banner", "-v", "error", "-y", *skip, "-i", ffin(path),
                   "-vf", vf, "-frames:v", "1", "-q:v", "5", str(out)]
            try:
                r = run(cmd, timeout)
            except subprocess.TimeoutExpired:
                return None, f"contact sheet timed out after {timeout:.0f} s"
            if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
                return str(out), (note + ("" if with_ts else "; no timestamps (drawtext failed)")).strip("; ")
    return None, "contact sheet failed: " + (r.stderr.strip().splitlines() or ["unknown ffmpeg error"])[-1][:200]


# --------------------------------------------------------------------------
# audio
# --------------------------------------------------------------------------

def band_pcm(path: Path, lo: float, hi: float, timeout: float) -> array:
    af = f"highpass=f={lo}:poles=2,highpass=f={lo}:poles=2,lowpass=f={hi}:poles=2,lowpass=f={hi}:poles=2"
    r = run(["ffmpeg", "-hide_banner", "-v", "error", "-i", ffin(path), "-vn", "-ac", "1", "-ar", str(ANALYSIS_SR),
             "-af", af, "-f", "s16le", "-"], timeout, binary=True)
    a = array("h")
    a.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    return a


def frame_db(a: array) -> list[float]:
    hop = int(ANALYSIS_SR * FRAME_HOP_S)
    out = []
    for i in range(0, len(a) - hop + 1, hop):
        seg = a[i:i + hop]
        p = sum(x * x for x in seg) / (hop * 32768.0 * 32768.0)
        out.append(10 * math.log10(p + POWER_FLOOR))
    return out


def percentile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    k = (len(s) - 1) * q / 100
    f, c = math.floor(k), math.ceil(k)
    return s[f] if f == c else s[f] + (s[c] - s[f]) * (k - f)


def median(xs: list[float]) -> float:
    return percentile(xs, 50)


def audio_flags(path: Path, info: dict) -> dict:
    res = {"has_audio": info["audio_channels"] > 0}
    if not res["has_audio"]:
        res["flags"] = ["no audio track"]
        return res
    dur = info["duration_s"] or 0
    timeout = 60 + 2 * dur
    flags = []
    try:
        r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", ffin(path), "-vn", "-af", "ebur128=peak=sample,astats",
                 "-f", "null", "-"], timeout)
        m = re.search(r"Integrated loudness:\s*I:\s*([-\d.]+)\s*LUFS", r.stderr)
        res["integrated_lufs"] = float(m.group(1)) if m else None
        pk = re.search(r"Sample peak:\s*Peak:\s*([-\d.inf]+)\s*dBFS", r.stderr)
        res["sample_peak_dbfs"] = float(pk.group(1)) if pk and pk.group(1) not in ("-inf", "inf") else None
        rms = [float(x) for x in re.findall(r"Channel: \d+.*?RMS level dB:\s*([-\d.inf]+)", r.stderr, re.S)
               if x not in ("-inf", "inf")]
        chans = re.findall(r"Channel: (\d+)", r.stderr)
        if len(chans) > 1 and len(rms) < len(set(chans)):
            flags.append("one audio channel is silent (check the mic is paired and on)")
        if res["sample_peak_dbfs"] is not None and res["sample_peak_dbfs"] >= CLIP_PEAK_DBFS:
            flags.append(f"peaks at {res['sample_peak_dbfs']:.1f} dBFS: possible clipping")
        if res["integrated_lufs"] is not None and res["integrated_lufs"] < -35:
            flags.append(f"very quiet ({res['integrated_lufs']:.0f} LUFS): mic may be off or far away")
    except subprocess.TimeoutExpired:
        flags.append("loudness check timed out")
    if dur >= 3:
        try:
            low = frame_db(band_pcm(path, *LOW_BAND_HZ, timeout))
            voice = frame_db(band_pcm(path, *VOICE_BAND_HZ, timeout))
            n = min(len(low), len(voice))
            readable = n * FRAME_HOP_S
            if dur and readable < 0.9 * dur - 1:
                flags.append(f"only {readable:.1f} s of {dur:.1f} s is readable: the file is incomplete or damaged "
                             f"(still copying or syncing?)")
                res["readable_s"] = round(readable, 1)
            if n >= 20:
                low, voice = low[:n], voice[:n]
                cut = percentile(voice, PAUSE_PERCENTILE)
                quiet = [i for i in range(n) if voice[i] < cut] or list(range(n))
                excess = median([low[i] for i in quiet]) - median([voice[i] for i in quiet])
                res["wind_pause_excess_db"] = round(excess, 1)
                res["wind_indicator"] = excess >= WIND_EXCESS_DB
                if res["wind_indicator"]:
                    worst = max(range(0, n, 10), key=lambda i: median([low[j] - voice[j] for j in range(i, min(n, i + 10))]))
                    res["wind_worst_at_s"] = round(worst * FRAME_HOP_S, 1)
                    flags.append(f"wind likely: pauses carry low band {excess:+.1f} dB over the voice band "
                                 f"(threshold +{WIND_EXCESS_DB:.0f}); confirm by listening")
        except subprocess.TimeoutExpired:
            flags.append("wind check timed out")
    res["flags"] = flags
    return res


def listening_sample(path: Path, info: dict, at_s: float | None, out: Path) -> str | None:
    dur = info["duration_s"] or 0
    start = max(0.0, min((at_s if at_s is not None else dur / 2) - SAMPLE_SECONDS / 2, dur - SAMPLE_SECONDS))
    try:
        r = run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", str(SAMPLE_SECONDS),
                 "-i", ffin(path), "-vn", "-ac", "1", "-c:a", "aac", "-b:a", "128k", str(out)], 120)
    except subprocess.TimeoutExpired:
        return None
    return str(out) if r.returncode == 0 and out.exists() else None


# --------------------------------------------------------------------------
# slate
# --------------------------------------------------------------------------

def to_int(tok: str) -> int | None:
    tok = tok.lower().strip(".,!?")
    if tok.isdigit():
        return int(tok)
    return NUMBER_WORDS.get(tok)


def read_slate(path: Path, whisper: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="dailies_") as td:
        wav = Path(td) / "slate.wav"
        try:
            r = run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-t", str(SLATE_SECONDS), "-i", ffin(path), "-vn",
                     "-ac", "1", "-ar", "16000", str(wav)], 120)
            if r.returncode != 0 or not wav.exists():
                return {"status": "UNCERTAIN", "heard": "", "why": "no audio in the first seconds"}
            t = run([whisper, "-m", str(WHISPER_MODEL), "-f", str(wav), "-nt", "-l", "en"], 300)
        except subprocess.TimeoutExpired:
            return {"status": "UNCERTAIN", "heard": "", "why": "slate read timed out"}
    heard = " ".join(t.stdout.split()).strip()
    m = re.search(r"\bshot\s+(\w+)[\s,.-]*(?:take\s+(\w+))?", heard, re.I)
    if m:
        shot, take = to_int(m.group(1)), to_int(m.group(2)) if m.group(2) else None
        if shot is not None:
            return {"status": "READ" if take is not None else "UNCERTAIN", "shot": shot, "take": take, "heard": heard}
    return {"status": "UNCERTAIN", "heard": heard, "why": "no 'shot N take M' heard"}


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def collect(inputs: list[str]) -> list[Path]:
    clips: list[Path] = []
    for raw in inputs:
        p = Path(raw).expanduser()
        if p.is_symlink():
            print(f"skipped (symlink): {p}")
            continue
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and not f.is_symlink() and not f.name.startswith(".") and f.suffix.lower() in VIDEO_EXT:
                    clips.append(f)
        elif p.is_file() and not p.name.startswith("."):
            clips.append(p)
        else:
            print(f"skipped (not found or hidden): {p}")
    seen, unique = set(), []
    for c in clips:
        k = c.resolve()
        if k not in seen:
            seen.add(k)
            unique.append(c)
    return unique


def refuse_location(folder: Path, allow_synced: bool) -> str | None:
    f = folder.resolve()
    for parent in [f, *f.parents]:
        if (parent / ".claude-plugin" / "marketplace.json").exists() or (parent / ".claude-plugin" / "plugin.json").exists():
            return f"{folder} is inside a plugin repository; dailies hold personal footage stills and must live elsewhere"
    if not allow_synced:
        for d in SYNCED_DIRS:
            try:
                f.relative_to(d.resolve())
                return (f"{folder} is inside a synced folder ({d}); contact sheets would upload. "
                        f"Choose a local folder, or pass --allow-synced if the person agrees")
            except (ValueError, OSError):
                continue
    return None


def safe_stem(p: Path) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", p.stem)[:60] or "clip"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", nargs="?")
    ap.add_argument("inputs", nargs="*")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--no-slate", action="store_true")
    ap.add_argument("--allow-synced", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    if not a.project or not a.inputs:
        ap.error("give a project folder and at least one clip or folder")
    if not shutil.which("ffmpeg"):
        print("ffmpeg isn't installed. Set it up with the video-setup skill (video-production plugin).")
        return 2
    project = Path(a.project).expanduser()
    why = refuse_location(project, a.allow_synced)
    if why:
        print("Refused: " + why)
        return 2
    clips = collect(a.inputs)
    if not clips:
        print("No video clips found.")
        return 2
    total = sum(c.stat().st_size for c in clips)
    free = shutil.disk_usage(project if project.exists() else project.parent if project.parent.exists() else Path.home()).free
    if free < 2e9:
        print(f"Refused: only {free / 1e9:.1f} GB free; dailies need about 2 GB of headroom.")
        return 2
    out = project / "dailies"
    (out / "sheets").mkdir(parents=True, exist_ok=True)
    (out / "listen").mkdir(exist_ok=True)
    filters = ffmpeg_filters()
    whisper = None if a.no_slate else whisper_cli()
    print(f"{len(clips)} clips, {total / 1e9:.2f} GB. Slate read: {'on' if whisper else 'off'}.")
    entries = []
    for i, clip in enumerate(clips, 1):
        name = f"{i:02d}_{safe_stem(clip)}"
        e = {"n": i, "file": str(clip), "name": clip.name}
        try:
            info = probe(clip)
        except (OSError, subprocess.TimeoutExpired) as ex:
            e["error"] = f"could not read file: {ex}"
            entries.append(e)
            print(f"{i:02d} {clip.name}: could not read")
            continue
        if not info.get("duration_s"):
            e["error"] = "could not read duration: file may be incomplete, still syncing, or not a video"
            entries.append(e)
            print(f"{i:02d} {clip.name}: unreadable")
            continue
        e.update(info)
        e["orientation"] = display_orientation(info)
        e["hdr"] = is_hdr(info)
        sheet, note = contact_sheet(clip, info, out / "sheets" / f"{name}.jpg", a.interval, filters)
        e["sheet"], e["sheet_note"] = sheet, note
        e["audio"] = audio_flags(clip, info)
        if e["audio"].get("wind_indicator") or any("clipping" in f for f in e["audio"].get("flags", [])):
            e["listen"] = listening_sample(clip, info, e["audio"].get("wind_worst_at_s"), out / "listen" / f"{name}.m4a")
        if whisper and e["audio"].get("has_audio"):
            e["slate"] = read_slate(clip, whisper)
        e["edit_notes"] = []
        if e["hdr"]:
            e["edit_notes"].append("HDR: video-production needs SDR; export as SDR or reshoot with HDR Video off")
        if e["orientation"] != "portrait":
            e["edit_notes"].append(f"{e['orientation']}: video-production supports portrait recordings only")
        entries.append(e)
        flags = e["audio"].get("flags", []) + e["edit_notes"]
        slate = e.get("slate", {})
        sl = f" slate: shot {slate.get('shot')} take {slate.get('take')}" if slate.get("status") == "READ" else \
             (" slate: UNCERTAIN" if slate else "")
        print(f"{i:02d} {clip.name}: {info['duration_s']:.1f}s {e['orientation']}{' HDR' if e['hdr'] else ''}"
              f"{sl}{' | ' + '; '.join(flags) if flags else ''}{' | ' + note if note else ''}")
    (out / "inventory.json").write_text(json.dumps({"clips": entries}, indent=2))
    sheets_mb = sum(p.stat().st_size for p in (out / "sheets").glob("*.jpg")) / 1e6
    print(f"Wrote {out / 'inventory.json'} and {len(list((out / 'sheets').glob('*.jpg')))} sheets ({sheets_mb:.1f} MB).")
    return 0 if any("error" not in e for e in entries) else 2


if __name__ == "__main__":
    sys.exit(main())
