#!/usr/bin/env python3
"""
Shared core for the video-production toolkit. Standard library only, so doctor
and init run on any python3.

Everything a stage script needs to agree on lives here: where the toolkit's
downloaded assets are, how a project folder is laid out, how project.json is
read and validated, how ffmpeg is called, and the numbers that were tuned on
real footage.

A *project folder* is wherever project.json lives (created by init_project.py).
Scripts never write into the plugin directory; every output path comes from
Project.path().
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

# --------------------------------------------------------------------------
# toolkit home: models, binaries, fonts, Python environments (downloaded once per machine)
# --------------------------------------------------------------------------

VT = Path(os.environ.get("VIDEO_TOOLKIT_HOME", Path.home() / ".local" / "share" / "video-toolkit"))
WHISPER_MODEL = VT / "models" / "ggml-large-v3-turbo.bin"
YUNET_MODEL = VT / "models" / "face_detection_yunet_2023mar.onnx"
DEEP_FILTER = VT / "bin" / "deep-filter"
FONTS_DIR = VT / "fonts"
VENV_CV = VT / "venv"            # numpy + opencv: tracking, cutting, rendering, QA
VENV_ALIGN = VT / "venv_align"   # torch + torchaudio: forced alignment, phrase scoring
TORCH_HOME = VT / "torch"        # aligner weights live here, not in ~/.cache

HERE = Path(__file__).resolve().parent
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")   # OpenCV's face model prints a harmless backend warning otherwise


def _find_installed_tools() -> None:
    """Put tools installed by install_system_tools.sh on PATH, so a session started before the install (or a shell
    profile nobody edited) still finds them. ffmpeg-full goes first: another ffmpeg may lack caption support."""
    parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    extra = [d for d in ("/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".local" / "bin"))
             if Path(d).is_dir() and d not in parts]
    full = [d for d in ("/opt/homebrew/opt/ffmpeg-full/bin", "/usr/local/opt/ffmpeg-full/bin") if Path(d).is_dir()]
    os.environ["PATH"] = os.pathsep.join(full + [p for p in parts if p not in full] + extra)


_find_installed_tools()

# --------------------------------------------------------------------------
# tuned constants (measured on handheld talking-head footage; change only with a new measurement)
# --------------------------------------------------------------------------

FPS = 30
AUDIO_RATE = 48000
SAMPLES_PER_FRAME = AUDIO_RATE // FPS          # 1600: exact audio length = frames x this

# output formats: size, base zoom (stabilisation headroom), preferred face-centre height, caption centre y
FORMATS = {
    "9x16": {"size": (1080, 1920), "base_zoom": 1.10, "face_y": 0.36, "caption_y": 1330},
    "4x5": {"size": (1080, 1350), "base_zoom": 1.10, "face_y": 0.40, "caption_y": 1080},
}

# ---- cutting (edl.py)
PAUSE_AFTER_SENTENCE = 0.50   # s of silence kept after . ? !   (0.42 felt rushed for a reflective speaker)
PAUSE_AFTER_COMMA = 0.35
PAUSE_MID_PHRASE = 0.25
HEAD_PAD = 0.10               # s before a word's aligned start
TAIL_PAD = 0.16               # s after a word's aligned end
QUIET_DB = -62.0              # 10 ms RMS on the cleaned track: speech -20..-45 dB, pauses -75..-100 dB
SNAP_START_BACK = 0.35        # look back this far for 40 ms of quiet before a word
SNAP_END_FORWARD = 0.40       # look forward this far for 60 ms of quiet after a word
BEAT_MIN_S = 3.0              # framing changes at most this often, on punctuation
BEAT_FORCE_S = 6.0            # ...and at least this often
ZOOM_ALT = 1.12               # alternate framing on beats
ZOOM_PUNCH = 1.22             # key-line punch-in

# ---- framing (render.py)
MOUTH_K = 0.50                # lower lip = YuNet box centre + 0.50 box widths (corners measured +0.41, p90 +0.44)
CAP_HALF = 60                 # half the caption text height (100 px Inter ExtraBold + outline)
MOUTH_CLEAR = 60              # px between lower lip and caption text top
FACE_MAX_FRAC = 0.62          # punch-ins stop when the face would exceed this share of frame width
Z_MAX = 1.35                  # upscale softness shows beyond this
CAM_SIGMA_S = 0.6             # camera path smoothing
FACE_SIGMA_S = 0.8            # reframing smoothing (never chase a nod)
MOUTH_ENVELOPE_S = 0.75       # rolling max half-window for the conservative lip path
KK_WINDOW = 8                 # frames: rolling-min window for shake-correction strength
FADE_IN_S, FADE_OUT_S = 0.012, 0.018     # per-cut audio edges (no clicks)
END_FADE_AFTER_WORD_S, END_FADE_MAX_S = 0.18, 0.35
NAME_PILL_SECONDS = (0.3, 3.8)
NAME_PILL_ABOVE_CAPTION = 150
NAME_PILL_X = 72

GRADE = "eq=contrast=1.05:saturation=1.07:gamma=0.98,colorbalance=rs=0.015:bs=-0.015:rh=0.01:bh=-0.01"
VOICE_CHAIN = ("equalizer=f=180:t=q:w=1.0:g=-1.5,equalizer=f=3500:t=q:w=1.2:g=2,"
               "acompressor=threshold=-26dB:ratio=3:attack=8:release=160:makeup=4,"
               "loudnorm=I=-15:TP=-2.0:LRA=8,aresample=48000")

# ---- audio cleaning
HIGHPASS_HZ = 70
DENOISE_EDIT_LIMIT_DB = 30    # keeps a natural floor so pauses don't go dead; transcription uses no limit

# --------------------------------------------------------------------------
# errors and subprocesses
# --------------------------------------------------------------------------


def die(message: str, code: int = 1) -> NoReturn:
    """Exit with a message that says what went wrong and how to fix it. Code 2 = refused before doing anything."""
    print(message, file=sys.stderr)
    sys.exit(code)


def run(cmd: list[str], what: str) -> subprocess.CompletedProcess:
    """Run a command, capturing its output; on failure, exit naming the step and the tail of stderr."""
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout or "").strip().splitlines()[-6:]
        die(f"{what} failed (exit {r.returncode}):\n  " + "\n  ".join(tail))
    return r


def ffmpeg(args: list[str], what: str) -> None:
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], what)


def check_wait(proc: subprocess.Popen, what: str) -> None:
    code = proc.wait()
    if code != 0:
        die(f"{what} failed (exit {code}).")


def filter_path(p: Path | str) -> str:
    """Escape a path for an ffmpeg filter option (e.g. subtitles=...): once for the option value, once for the
    filtergraph. Quoting with '...' can't carry an apostrophe, which is common in folder names."""
    s = re.sub(r"([\\':])", r"\\\1", str(p))
    return re.sub(r"([\\'\[\],;])", r"\\\1", s)


def write_atomic(path: Path, text: str) -> None:
    """Write via a .partial file and rename, so a crash never leaves a half-written file that looks finished."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".partial")
    tmp.write_text(text)
    os.replace(tmp, path)


def concat_line(p: Path | str) -> str:
    """One line of an ffmpeg concat list, safe for quotes in the path."""
    return "file '" + str(p).replace("'", "'\\''") + "'\n"


# --------------------------------------------------------------------------
# media probing
# --------------------------------------------------------------------------


def probe(path: Path | str) -> dict:
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height,pix_fmt,color_transfer,r_frame_rate,sample_rate,channels"
             ":stream_side_data=rotation:format_tags",
             "-of", "json", str(path)], f"Reading {path}")
    return json.loads(r.stdout)


def display_size(info: dict) -> tuple[int, int]:
    """Width, height as displayed (phone video stores rotation separately)."""
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        die("No video stream found.")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = abs(int(float(sd["rotation"])))
    return (h, w) if rot in (90, 270) else (w, h)


# --------------------------------------------------------------------------
# words
# --------------------------------------------------------------------------


def norm_word(t: str) -> str:
    """The one normaliser for matching words across transcripts, specs and re-transcriptions."""
    return re.sub(r"[^a-z0-9']", "", t.lower())


def ass_colour(hex_rgb: str) -> str:
    """#RRGGBB -> ASS &H00BBGGRR (opaque)."""
    m = re.fullmatch(r"#?([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})", hex_rgb.strip())
    if not m:
        die(f"Caption highlight colour {hex_rgb!r} must look like #FFD84D.", 2)
    r, g, b = (x.upper() for x in m.groups())
    return f"&H00{b}{g}{r}"


# --------------------------------------------------------------------------
# project
# --------------------------------------------------------------------------

DEFAULTS = {
    "version": 1,
    "language": "en",
    "output_dir": "edits",
    "name_pill": {"text": "", "title": ""},          # empty = no name pill; the agent asks
    "captions": {"font": "Inter", "size": 100, "highlight": "#FFD84D"},
    "platforms": [],
    "corrections": [],        # [{"src","t","old","new","evidence"}] evidence-backed only
    "casing": {},             # {"lowercase word": "Proper Form"} applied to caption words
    "phrases": [],            # [["word1", "word2", "Shown1", "Shown2"]] two-word caption spellings
}


class Project:
    """A project folder: project.json plus the working files every stage reads and writes."""

    def __init__(self, folder: Path | str | None = None):
        start = Path(folder or ".").resolve()
        found = next((d for d in [start, *start.parents] if (d / "project.json").is_file()), None)
        if not found:
            die("No project.json here or in any parent folder.\n"
                "Create one with init_project.py from the video-producer skill folder:\n"
                "  python3 <video-producer folder>/init_project.py --sources A=path/to/take1.mp4 B=path/to/take2.mp4", 2)
        self.root = found
        try:
            raw = json.loads((found / "project.json").read_text())
        except json.JSONDecodeError as e:
            die(f"{found / 'project.json'} isn't valid JSON (line {e.lineno}, column {e.colno}): {e.msg}", 2)
        if not isinstance(raw, dict):
            die(f"{found / 'project.json'} must be a JSON object.", 2)
        self.cfg = {k: ({**v, **raw[k]} if isinstance(v, dict) and isinstance(raw.get(k), dict) else raw.get(k, v))
                    for k, v in DEFAULTS.items()}
        self.cfg.update({k: v for k, v in raw.items() if k not in DEFAULTS})
        self._validate()

    def _validate(self) -> None:
        src = self.cfg.get("sources")
        if not isinstance(src, dict) or not src:
            die("project.json needs \"sources\": {\"A\": {\"file\": \"take1.mp4\"}, ...}", 2)
        for sid, s in src.items():
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,16}", sid):
                die(f"Source id {sid!r} must be short letters/digits (e.g. A, B, take2).", 2)
            if not self.source_file(sid).is_file():
                die(f"Source {sid}: {self.source_file(sid)} not found. Fix the path in project.json.", 2)

    # ---- sources
    @property
    def source_ids(self) -> list[str]:
        return list(self.cfg["sources"])

    def source_file(self, sid: str) -> Path:
        f = Path(self.cfg["sources"][sid]["file"]).expanduser()
        return f if f.is_absolute() else (self.root / f).resolve()

    def source_size(self, sid: str) -> tuple[int, int]:
        info = self.cfg["sources"][sid]
        if "display_size" in info:
            return tuple(info["display_size"])
        return display_size(probe(self.source_file(sid)))

    def pick_sources(self, wanted: list[str] | None) -> list[str]:
        """The source ids a script should work on: all of them, or the ones asked for (refusing unknown ids)."""
        if not wanted:
            return self.source_ids
        unknown = [w for w in wanted if w not in self.cfg["sources"]]
        if unknown:
            die(f"Unknown source id(s): {', '.join(unknown)}. project.json has: {', '.join(self.source_ids)}.", 2)
        return list(dict.fromkeys(wanted))

    # ---- working files (all relative to the project folder)
    def path(self, *parts: str, mkdir: bool = True) -> Path:
        p = self.root.joinpath(*parts)
        if mkdir:
            p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def wav48(self, sid): return self.path("audio", f"{sid}.48k.wav")
    def clean_asr(self, sid): return self.path("clean", "asr", f"{sid}.wav")
    def clean_edit(self, sid): return self.path("clean", "edit", f"{sid}.wav")
    def asr16(self, sid): return self.path("transcripts", f"{sid}.16k.wav")
    def whisper_json(self, sid): return self.path("transcripts", f"{sid}.whisper.json")
    def words(self, sid): return self.path("transcripts", f"{sid}.words.json")
    def aligned(self, sid): return self.path("transcripts", f"{sid}.aligned.json")
    def final_words(self, sid): return self.path("transcripts", f"{sid}.final.json")
    def voice_regions(self, sid): return self.path("analysis", f"{sid}.voice_regions.json")
    def faces(self, sid): return self.path("tracking", f"{sid}.faces.json")
    def camtrack(self, sid): return self.path("tracking", f"{sid}.camera.json")
    def spec(self, name): return self.path("specs", f"{name}.json")
    def edl(self, name): return self.path("edls", f"{name}.json")
    def work(self, name, create: bool = False) -> Path:
        """work/<name>/; only render.py and final_pass.py create it, so a mistyped name in a check creates nothing."""
        d = self.root / "work" / name
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d
    def output_dir(self, kind: str) -> Path:
        out = Path(self.cfg["output_dir"]).expanduser()
        d = (out if out.is_absolute() else self.root / out) / kind
        d.mkdir(parents=True, exist_ok=True)
        return d


# --------------------------------------------------------------------------
# environments
# --------------------------------------------------------------------------


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python")


def require(modules: list[str], venv: Path) -> None:
    """Import-or-re-exec: if a module is missing here but the toolkit venv exists, re-run this script inside it."""
    missing = []
    for m in modules:
        try:
            __import__(m)
        except ImportError:
            missing.append(m)
    if not missing:
        return
    py = venv_python(venv)
    if py.is_file() and Path(sys.executable).resolve() != py.resolve():
        os.environ.setdefault("TORCH_HOME", str(TORCH_HOME))
        os.execv(str(py), [str(py), *sys.argv])
    die(f"Missing Python modules: {', '.join(missing)}.\n"
        f"Run doctor.py, then setup_toolkit.py to install the toolkit environments.", 2)


def need_binary(name: str, fix: str) -> str:
    p = shutil.which(name)
    if not p:
        die(f"{name} not found. {fix}", 2)
    return p
