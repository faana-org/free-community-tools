#!/usr/bin/env python3
"""
Installs the video toolkit's downloaded pieces, one named component at a time.

Everything lands in the toolkit home (~/.local/share/video-toolkit, or
$VIDEO_TOOLKIT_HOME), never in the plugin folder. Nothing is installed unless
it is named, and a component that is already installed is skipped. The skill
asks for consent before running this, so this script asks nothing: it prints
what it will fetch and how big it is, checks the disk, then does it.

Every download is pinned to an immutable revision and a SHA-256. A file is
written as <target>.partial; only after its hash matches is it made
executable, un-quarantined and renamed into place. An interrupted download
resumes when the same command is run again.

Usage:
  python3 setup_toolkit.py --list                      status and sizes of every component
  python3 setup_toolkit.py whisper-model deep-filter   install just these
  python3 setup_toolkit.py all                         install everything missing
  python3 setup_toolkit.py all --adopt DIR             copy matching files from DIR instead of downloading
  python3 setup_toolkit.py venv-align --dry-run         print the plan and any refusal, install nothing
  python3 setup_toolkit.py system --run-system         install missing system tools (install_system_tools.sh)

Components:
  system         ffmpeg (with libass and libx264), whisper-cpp, uv, curl
  whisper-model  whisper.cpp large-v3-turbo model
  deep-filter    DeepFilterNet 0.5.6 command-line binary
  yunet          YuNet face detection model
  fonts          Inter 4.1 static TTFs: Black, ExtraBold, Bold, SemiBold, Medium
  venv-cv        Python environment with numpy and opencv
  venv-align     Python environment with torch and torchaudio, plus the MMS_FA aligner weights

--adopt DIR looks for each file in DIR and up to two folders below it (an old
toolkit home or a torch cache both work) and copies it only if its SHA-256
matches the pin. Fonts are adopted from the release zip, Inter-4.1.zip.
Anything not found in DIR is downloaded as usual; the plan printed before
starting says which is which.

Exit 0 = done. Exit 1 = a step failed, or something still needs fixing.
Exit 2 = refused before doing anything.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

sys.dont_write_bytecode = True   # importing vcore must not leave __pycache__ in the plugin folder
import vcore  # noqa: E402

MB, GB = 1000 ** 2, 1000 ** 3
HEADROOM = 2 * GB                # free space kept beyond what the install itself needs


# --------------------------------------------------------------------------
# platform
# --------------------------------------------------------------------------


def rosetta() -> bool:
    """True when this process is x86_64 code translated by Rosetta on an Apple Silicon Mac."""
    if platform.system() != "Darwin":
        return False
    r = subprocess.run(["sysctl", "-n", "sysctl.proc_translated"], capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == "1"


def host() -> str | None:
    """The toolkit platform for this machine's hardware (an arm64 Mac stays arm64 under Rosetta), or None."""
    system, machine = platform.system(), platform.machine().lower()
    if system == "Darwin":
        if machine == "arm64" or rosetta():
            return "macos-arm64"
        return "macos-x86_64" if machine == "x86_64" else None
    if system == "Linux":
        if machine in ("x86_64", "amd64"):
            return "linux-x86_64"
        if machine in ("aarch64", "arm64"):
            return "linux-arm64"
    return None


UNSUPPORTED = ("The video toolkit runs on macOS (arm64 or x86_64) and Linux (x86_64 or arm64).\n"
               "On Windows, use WSL2: run `wsl --install`, then run this inside the Linux shell.")


# --------------------------------------------------------------------------
# pins
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Pin:
    url: str
    sha256: str
    size: int
    magic: bytes   # first bytes of the real file; an HTML error page saved under the right name fails this


MACHO, ELF, ZIP, TTF = b"\xcf\xfa\xed\xfe", b"\x7fELF", b"PK\x03\x04", b"\x00\x01\x00\x00"

# whisper.cpp model. Hugging Face commit 5359861 is the head of ggerganov/whisper.cpp (2024-10-29); the file last
# changed 2024-10-01. The SHA-256 is the LFS oid Hugging Face reports for the file, and matches an earlier download.
WHISPER_PIN = Pin(
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/5359861c739e955e79d9a303bcbc70fb988958b1"
    "/ggml-large-v3-turbo.bin",
    "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69", 1624555275, b"lmgg")

# DeepFilterNet 0.5.6 release binaries, hashed from fresh downloads (the macOS x86_64 one also matches an earlier
# download). Linux x86_64 uses the static musl build, so it runs on any distribution.
DEEP_FILTER_RELEASE = "https://github.com/Rikorose/DeepFilterNet/releases/download/v0.5.6/deep-filter-0.5.6-"
DEEP_FILTER_PINS = {
    "macos-arm64": Pin(DEEP_FILTER_RELEASE + "aarch64-apple-darwin",
                       "4601e7f4e4c03e59a4c5b5000216ef3add3e808799cfccd95e14e83ea4611081", 27877081, MACHO),
    "macos-x86_64": Pin(DEEP_FILTER_RELEASE + "x86_64-apple-darwin",
                        "d3be84003acb7c23e738ad7f70a158ec779a8d233a82e7fa3e717d112eb5b50f", 29933512, MACHO),
    "linux-x86_64": Pin(DEEP_FILTER_RELEASE + "x86_64-unknown-linux-musl",
                        "70775e251eee44c0f2451a1e833326cf8bcbbe304d3e7cd12851e6fce72ef7da", 36417296, ELF),
    "linux-arm64": Pin(DEEP_FILTER_RELEASE + "aarch64-unknown-linux-gnu",
                       "14e02a1c0028f3ca0bdf83b62b3336e56ba0556894ef295a95e8573f06557166", 39238496, ELF),
}

# YuNet at opencv_zoo commit f12e127 ("update yunet to v2"), the last commit to touch the file. The SHA-256 is the
# Git LFS oid at that commit; the downloaded file and an earlier copy both match it. ONNX files start with field 1.
YUNET_PIN = Pin(
    "https://github.com/opencv/opencv_zoo/raw/f12e12798e8314f7c074a6656816c048dcc95b7a"
    "/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4", 232589, b"\x08")

# Inter 4.1 release zip, hashed from a fresh download. Only the static TTFs are extracted: libass does not pick
# weights from the variable font reliably. The zip's own CRCs guard each extracted file.
INTER_PIN = Pin("https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip",
                "9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e", 33707794, ZIP)
INTER_FONTS = {"Inter-Black.ttf": 419968, "Inter-ExtraBold.ttf": 421796, "Inter-Bold.ttf": 420428,
               "Inter-SemiBold.ttf": 419744, "Inter-Medium.ttf": 417300}
REQUIRED_FONTS = ("Inter-ExtraBold.ttf", "Inter-SemiBold.ttf", "Inter-Medium.ttf")   # captions, name pill, its title

# MMS_FA aligner weights: the URL torchaudio's MMS_FA bundle loads (pipelines/_wav2vec2/impl.py, the same in
# torchaudio 2.2.2 through 2.11). The host publishes no hash. This is the SHA-256 of a copy torch.hub downloaded;
# its first 64 MB, last 64 MB and a 32 MB slice from the middle match the live file byte for byte.
MMS_FA_PIN = Pin("https://dl.fbaipublicfiles.com/mms/torchaudio/ctc_alignment_mling_uroman/model.pt",
                 "20ef12963ab4924bef49ac4fc7f58ad5da2ee43b2c11bc8c853c9b90ecdbc680", 1262047414, ZIP)
MMS_FA_WEIGHTS = vcore.TORCH_HOME / "hub" / "checkpoints" / "model.pt"   # where torch.hub looks for that URL


# --------------------------------------------------------------------------
# Python environment plans
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EnvPlan:
    python: str
    packages: tuple[str, ...]
    index: str = ""   # extra package index searched before PyPI


# The versions of a working environment the pipeline has run in.
CV_PLAN = EnvPlan("3.12", ("numpy==2.5.3", "opencv-python==5.0.0.93"))

# PyPI's Linux torch wheels pull several GB of CUDA libraries; the CPU index has the same release without them.
CPU_TORCH_INDEX = "https://download.pytorch.org/whl/cpu"


def align_plan(plat: str) -> EnvPlan:
    if plat == "macos-x86_64":
        # torch 2.2.2 is the last release with Intel-Mac wheels; it needs numpy<2. Verified on Python 3.11.
        return EnvPlan("3.11", ("torch==2.2.2", "torchaudio==2.2.2", "numpy==1.26.4", "soundfile==0.13.1"))
    # torchaudio 2.9 moved torchaudio.load onto torchcodec and FFmpeg shared libraries. 2.8 still reads WAV through
    # soundfile and still has pipelines.MMS_FA and functional.forced_align. Not yet run on arm64 macOS or Linux.
    return EnvPlan("3.12", ("torch==2.8.0", "torchaudio==2.8.0", "soundfile==0.13.1"),
                   CPU_TORCH_INDEX if plat.startswith("linux") else "")


# Environment sizes are estimates: wheel sizes from PyPI, installed sizes measured on macOS, plus uv's cached copy
# of the wheels. A machine without a suitable Python also downloads an interpreter (about 40 MB).
CV_DOWNLOAD, CV_DISK = 100 * MB, 300 * MB
ALIGN_DOWNLOAD, ALIGN_DISK = 250 * MB, 1100 * MB

# Each probe exits non-zero unless the environment can do its job, and prints its versions as JSON.
CV_PROBE = """
import json, cv2, numpy
cv2.FaceDetectorYN.create
print(json.dumps({"opencv": cv2.__version__, "numpy": numpy.__version__}))
"""
ALIGN_PROBE = """
import json, torch, torchaudio
from torchaudio.pipelines import MMS_FA
from torchaudio.functional import forced_align
forced_align(torch.zeros(1, 4, 3), torch.tensor([[1]], dtype=torch.int32), blank=0)
backends = torchaudio.list_audio_backends() if hasattr(torchaudio, "list_audio_backends") else ["not checked"]
if not backends:
    raise SystemExit("torchaudio has no audio backend, so torchaudio.load cannot read files")
print(json.dumps({"torch": torch.__version__, "torchaudio": torchaudio.__version__, "audio": backends}))
"""
# Loads the real weights and runs one second of silence through them: the proof the aligner works.
ALIGN_LOAD = """
import torch
from torchaudio.pipelines import MMS_FA
model = MMS_FA.get_model(with_star=True)
with torch.inference_mode():
    emission, _ = model(torch.zeros(1, 16000))
print(tuple(emission.shape))
"""


# --------------------------------------------------------------------------
# checks (cheap: sizes, headers and imports; doctor.py uses these too)
# --------------------------------------------------------------------------


def human(n: float) -> str:
    if n >= GB:
        return f"{n / GB:.1f} GB"
    if n >= MB:
        return f"{n / MB:.{0 if n >= 100 * MB else 1}f} MB"
    return f"{n / 1000:.0f} kB"


def file_problem(path: Path, size: int, magic: bytes) -> str:
    """Why this file is not a good copy, or "" if its size and first bytes are right."""
    if not path.is_file():
        return "missing"
    actual = path.stat().st_size
    if actual != size:
        return f"wrong size ({actual:,} bytes, expected {size:,})"
    with path.open("rb") as f:
        if f.read(len(magic)) != magic:
            return "not the expected kind of file (an error page saved under its name?)"
    return ""


def probe_env(venv: Path, code: str) -> tuple[dict | None, str]:
    """(versions, "") when the environment passes its probe, else (None, what went wrong)."""
    py = vcore.venv_python(venv)
    if not py.is_file():
        return None, "missing"
    try:
        r = subprocess.run([str(py), "-c", code], capture_output=True, text=True, timeout=600,
                           env={**os.environ, "TORCH_HOME": str(vcore.TORCH_HOME)})
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"broken ({exc.__class__.__name__})"
    if r.returncode != 0:
        tail = (r.stderr or r.stdout).strip().splitlines()[-1:] or [f"exit {r.returncode}"]
        return None, f"broken: {tail[0]}"
    try:
        return json.loads(r.stdout.strip().splitlines()[-1]), ""
    except (ValueError, IndexError):
        return None, "broken: the probe printed nothing"


def ffmpeg_problems() -> list[str]:
    """What is missing from ffmpeg for this toolkit; [] when it is complete."""
    if not shutil.which("ffmpeg"):
        return ["ffmpeg missing"]
    if not shutil.which("ffprobe"):
        problems = ["ffprobe missing"]
    elif subprocess.run(["ffprobe", "-version"], capture_output=True).returncode != 0:
        # Found but unloadable, e.g. after Homebrew upgraded a shared library (x265) underneath it
        problems = ["ffprobe doesn't run"]
    else:
        problems = []
    filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    encoders = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    if not any(ln.split()[1:2] == ["subtitles"] for ln in filters.splitlines()):
        problems.append("ffmpeg has no subtitles filter (built without libass)")
    if not any(ln.split()[1:2] == ["libx264"] for ln in encoders.splitlines()):
        problems.append("ffmpeg has no libx264 encoder")
    return problems


def system_problems() -> list[str]:
    problems = ffmpeg_problems()
    problems += [f"{tool} missing" for tool in ("whisper-cli", "uv", "curl") if not shutil.which(tool)]
    return problems


# Homebrew's plain ffmpeg formula no longer links libass (checked on 9.0.1). ffmpeg-full has it, but it is keg-only,
# so its bin folder has to go first on PATH. Sizes are rough: Homebrew downloads only the dependencies it lacks.
BREW_SIZE = {"ffmpeg-full": "several hundred MB with its dependencies", "whisper-cpp": "about 10 MB",
             "uv": "about 50 MB", "curl": "a few MB"}
FFMPEG_FULL_PATH = 'export PATH="$(brew --prefix ffmpeg-full)/bin:$PATH"'


def brew_formulas(problems: list[str]) -> list[str]:
    tools = {p.split()[0] for p in problems}
    wanted = (("ffmpeg-full", bool(tools & {"ffmpeg", "ffprobe"})), ("whisper-cpp", "whisper-cli" in tools),
              ("uv", "uv" in tools), ("curl", "curl" in tools))
    return [formula for formula, needed in wanted if needed]


def ffmpeg_full_installed() -> bool:
    brew = shutil.which("brew")
    if not brew:
        return False
    prefix = subprocess.run([brew, "--prefix", "ffmpeg-full"], capture_output=True, text=True).stdout.strip()
    return bool(prefix) and (Path(prefix) / "bin" / "ffmpeg").is_file()


def system_fix(plat: str, problems: list[str]) -> list[str]:
    """The commands that fix these system problems, one per line, with sizes."""
    installer = f"bash {vcore.HERE / 'install_system_tools.sh'}"
    if plat.startswith("macos"):
        return [f"{installer}   (installs everything missing, Homebrew included; the person only types their Mac "
                "password into the macOS password box)"]
    formulas = brew_formulas(problems)
    if plat.startswith("macos") or shutil.which("brew"):
        lines = [] if shutil.which("brew") else ["Install Homebrew first: https://brew.sh"]
        if "ffmpeg-full" in formulas and ffmpeg_full_installed():
            formulas.remove("ffmpeg-full")
            lines.append("ffmpeg-full is installed but not first on PATH. "
                         f"Add to your shell profile:  {FFMPEG_FULL_PATH}")
        elif "ffmpeg-full" in formulas:
            lines.append(f"then put it first on PATH (add to your shell profile):  {FFMPEG_FULL_PATH}")
        if formulas:
            sizes = "; ".join(f"{f}: {BREW_SIZE[f]}" for f in formulas)
            lines.insert(0 if shutil.which("brew") else 1, f"brew install {' '.join(formulas)}   ({sizes})")
        return lines
    lines = []
    apt = [pkg for pkg, needed in (("ffmpeg", "ffmpeg-full" in formulas), ("curl", "curl" in formulas)) if needed]
    if apt:
        size = "ffmpeg: a few hundred MB with its libraries" if "ffmpeg" in apt else "a few MB"
        lines.append(f"sudo apt-get install -y {' '.join(apt)}   ({size})")
    if "uv" in formulas:
        lines.append("pipx install uv   (about 50 MB)")
    if "whisper-cpp" in formulas:
        lines.append("whisper-cli: build whisper.cpp (https://github.com/ggml-org/whisper.cpp#quick-start, a few MB) "
                     "and put build/bin on PATH, or with Homebrew on Linux: brew install whisper-cpp")
    return lines


# --------------------------------------------------------------------------
# downloading and copying
# --------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download(pin: Pin, partial: Path, label: str) -> None:
    """curl into partial, resuming what an earlier run left; fails on any HTTP error or non-https redirect."""
    if partial.exists() and partial.stat().st_size >= pin.size:
        if partial.stat().st_size == pin.size and sha256_file(partial) == pin.sha256:
            return
        partial.unlink()   # a complete-looking leftover that is wrong: start over rather than trust it
    for attempt in (1, 2):
        cmd = ["curl", "--fail", "--location", "--proto", "=https", "--proto-redir", "=https",
               "--retry", "3", "--retry-delay", "2", "--silent", "--show-error",
               "--continue-at", "-", "--output", str(partial), pin.url]
        proc = subprocess.Popen(cmd)
        while True:
            try:
                code = proc.wait(timeout=15)
                break
            except subprocess.TimeoutExpired:
                done = partial.stat().st_size if partial.exists() else 0
                print(f"    {label}: {human(done)} of {human(pin.size)}", flush=True)
        if code == 33 and attempt == 1:   # the server refused to resume: start the file again
            partial.unlink(missing_ok=True)
            continue
        if code != 0:
            vcore.die(f"{label}: download failed (curl exit {code}; its message is above).\n"
                      "Re-run the same command to retry; an interrupted download resumes where it stopped.")
        return


def copy_file(src: Path, partial: Path) -> None:
    partial.unlink(missing_ok=True)
    shutil.copyfile(src, partial)   # data only: no quarantine flag or other attributes come along


def check_hash(partial: Path, pin: Pin, label: str) -> None:
    size = partial.stat().st_size
    if size != pin.size or sha256_file(partial) != pin.sha256:
        partial.unlink()
        got = f"{size:,} bytes, expected {pin.size:,}" if size != pin.size else "right size, different content"
        vcore.die(f"{label}: the file does not match its pinned SHA-256 ({got}).\n"
                  "Deleted it. Re-run to try again; if it keeps failing, the upstream file has changed.")


def unquarantine(path: Path) -> None:
    if platform.system() != "Darwin":
        return
    if subprocess.run(["xattr", "-p", "com.apple.quarantine", str(path)], capture_output=True).returncode == 0:
        vcore.run(["xattr", "-d", "com.apple.quarantine", path], f"Removing the quarantine flag from {path.name}")


def fetch(pin: Pin, dest: Path, label: str, adopt: Path | None, executable: bool = False) -> None:
    """Download (or copy) to dest.partial, verify the SHA-256, then chmod, un-quarantine and rename into place."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".partial")
    if adopt:
        print(f"  {label}: copying {adopt}", flush=True)
        copy_file(adopt, partial)
    else:
        print(f"  {label}: downloading {human(pin.size)}", flush=True)
        download(pin, partial, label)
    check_hash(partial, pin, label)
    if executable:
        partial.chmod(0o755)
        unquarantine(partial)
    os.replace(partial, dest)


def find_adoptable(root: Path, names: list[str], pin: Pin) -> tuple[Path | None, str]:
    """(copy whose SHA-256 matches, ""), (None, "") when root has no copy, or (None, why) when none match."""
    found: list[Path] = []
    for pattern in ("{}", "*/{}", "*/*/{}"):
        for name in names:
            found += [p for p in sorted(root.glob(pattern.format(name))) if p.is_file() and p not in found]
    if not found:
        return None, ""
    for p in found:
        if p.stat().st_size == pin.size and sha256_file(p) == pin.sha256:
            return p, ""
    return None, f"found {', '.join(str(p) for p in found)}, but none matches the pinned SHA-256"


# --------------------------------------------------------------------------
# components
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Component:
    name: str
    status: Callable[[str], str]                        # "" when installed, else what is wrong
    download: Callable[[str], int]
    disk: Callable[[str], int]
    install: Callable[[str, Path | None], None]
    adopt_pin: Callable[[str], Pin | None] = lambda plat: None
    adopt_names: Callable[[str], list] = lambda plat: []
    estimated: bool = False
    needs_uv: bool = False


def whisper_status(plat: str) -> str:
    return file_problem(vcore.WHISPER_MODEL, WHISPER_PIN.size, WHISPER_PIN.magic)


def deep_filter_status(plat: str) -> str:
    pin = DEEP_FILTER_PINS[plat]
    return file_problem(vcore.DEEP_FILTER, pin.size, pin.magic)


def yunet_status(plat: str) -> str:
    return file_problem(vcore.YUNET_MODEL, YUNET_PIN.size, YUNET_PIN.magic)


def fonts_status(plat: str) -> str:
    bad = {name: why for name, size in INTER_FONTS.items() if (why := file_problem(vcore.FONTS_DIR / name, size, TTF))}
    if len(bad) == len(INTER_FONTS) and set(bad.values()) == {"missing"}:
        return "missing"
    return "; ".join(f"{name} {why}" for name, why in bad.items())


def cv_status(plat: str) -> str:
    return probe_env(vcore.VENV_CV, CV_PROBE)[1]


def align_status(plat: str) -> str:
    env = probe_env(vcore.VENV_ALIGN, ALIGN_PROBE)[1]
    weights = file_problem(MMS_FA_WEIGHTS, MMS_FA_PIN.size, MMS_FA_PIN.magic)
    parts = (f"environment {env}" if env else "", f"aligner weights {weights}" if weights else "")
    return "; ".join(p for p in parts if p)


def install_fonts(plat: str, adopt: Path | None) -> None:
    vcore.FONTS_DIR.mkdir(parents=True, exist_ok=True)
    zip_partial = vcore.FONTS_DIR / "Inter-4.1.zip.partial"
    if adopt:
        print(f"  fonts: copying {adopt}", flush=True)
        copy_file(adopt, zip_partial)
    else:
        print(f"  fonts: downloading {human(INTER_PIN.size)}", flush=True)
        download(INTER_PIN, zip_partial, "fonts")
    check_hash(zip_partial, INTER_PIN, "fonts")
    with zipfile.ZipFile(zip_partial) as z:
        for name, size in INTER_FONTS.items():
            dest = vcore.FONTS_DIR / name
            partial = dest.with_name(name + ".partial")
            with z.open(f"extras/ttf/{name}") as src, partial.open("wb") as out:
                shutil.copyfileobj(src, out)
            if file_problem(partial, size, TTF):
                partial.unlink()
                vcore.die(f"fonts: {name} in the verified zip is not the expected font file.")
            os.replace(partial, dest)
    zip_partial.unlink()


def build_env(label: str, venv: Path, plan: EnvPlan, plat: str) -> None:
    """A fresh uv environment for the plan. uv reads no config or project, so nothing in the working folder leaks in."""
    if venv.is_symlink():
        venv.unlink()         # a link to an environment elsewhere: drop the link, leave its target alone
    elif venv.exists():
        shutil.rmtree(venv)   # the plan step confirmed this is a Python environment
    request = python_request(plan.python, plat)
    print(f"  {label}: creating a Python {plan.python} environment", flush=True)
    os.environ.pop("VIRTUAL_ENV", None)   # an activated environment must not become the base interpreter
    vcore.run(["uv", "venv", "--no-config", "--no-project", "--python", request, venv],
              f"{label}: creating the environment")
    py = vcore.venv_python(venv)
    arch = vcore.run([py, "-c", "import platform; print(platform.machine())"],
                     f"{label}: checking the interpreter").stdout.strip()
    want = {"macos-arm64": "arm64", "macos-x86_64": "x86_64", "linux-x86_64": "x86_64", "linux-arm64": "aarch64"}[plat]
    if arch != want:
        vcore.die(f"{label}: uv picked a {arch} Python, but this machine needs {want}. "
                  f"Remove {venv} and install a native uv.")
    print(f"  {label}: installing {' '.join(plan.packages)} (this can take a few minutes)", flush=True)
    cmd = ["uv", "pip", "install", "--no-config", "--python", py, "--only-binary", ":all:", *plan.packages]
    if plan.index:
        cmd += ["--index", plan.index]
    vcore.run(cmd, f"{label}: installing packages")


def python_request(version: str, plat: str) -> str:
    """Names the architecture too, so a shell running under Rosetta cannot hand uv the wrong interpreter."""
    os_name, arch = plat.split("-")
    arch = "aarch64" if arch == "arm64" else arch
    return f"cpython-{version}-{os_name}-{arch}-{'none' if os_name == 'macos' else 'gnu'}"


def install_cv(plat: str, adopt: Path | None) -> None:
    build_env("venv-cv", vcore.VENV_CV, CV_PLAN, plat)
    versions, why = probe_env(vcore.VENV_CV, CV_PROBE)
    if not versions:
        vcore.die(f"venv-cv: the new environment fails its check: {why}")
    print(f"  venv-cv: ok {versions}")


def install_align(plat: str, adopt: Path | None) -> None:
    os.environ["TORCH_HOME"] = str(vcore.TORCH_HOME)   # the aligner weights live in the toolkit home, not ~/.cache
    versions, why = probe_env(vcore.VENV_ALIGN, ALIGN_PROBE)
    if not versions:
        build_env("venv-align", vcore.VENV_ALIGN, align_plan(plat), plat)
        versions, why = probe_env(vcore.VENV_ALIGN, ALIGN_PROBE)
        if not versions:
            vcore.die(f"venv-align: the new environment fails its check: {why}")
    if file_problem(MMS_FA_WEIGHTS, MMS_FA_PIN.size, MMS_FA_PIN.magic):
        fetch(MMS_FA_PIN, MMS_FA_WEIGHTS, "venv-align weights", adopt)
    print("  venv-align: loading the aligner once to prove the weights work", flush=True)
    shape = vcore.run([vcore.venv_python(vcore.VENV_ALIGN), "-c", ALIGN_LOAD],
                      "venv-align: loading MMS_FA").stdout.strip()
    print(f"  venv-align: ok {versions}, emission {shape.splitlines()[-1] if shape else '?'}")


COMPONENTS = {c.name: c for c in (
    Component("system", lambda plat: "; ".join(system_problems()), lambda plat: 0, lambda plat: 0,
              lambda plat, adopt: None),
    Component("whisper-model", whisper_status, lambda plat: WHISPER_PIN.size, lambda plat: WHISPER_PIN.size,
              lambda plat, adopt: fetch(WHISPER_PIN, vcore.WHISPER_MODEL, "whisper-model", adopt),
              lambda plat: WHISPER_PIN, lambda plat: [WHISPER_PIN.url.rsplit("/", 1)[1]]),
    Component("deep-filter", deep_filter_status, lambda plat: DEEP_FILTER_PINS[plat].size,
              lambda plat: DEEP_FILTER_PINS[plat].size,
              lambda plat, adopt: fetch(DEEP_FILTER_PINS[plat], vcore.DEEP_FILTER, "deep-filter", adopt,
                                        executable=True),
              lambda plat: DEEP_FILTER_PINS[plat],
              lambda plat: ["deep-filter", DEEP_FILTER_PINS[plat].url.rsplit("/", 1)[1]]),
    Component("yunet", yunet_status, lambda plat: YUNET_PIN.size, lambda plat: YUNET_PIN.size,
              lambda plat, adopt: fetch(YUNET_PIN, vcore.YUNET_MODEL, "yunet", adopt),
              lambda plat: YUNET_PIN, lambda plat: [vcore.YUNET_MODEL.name]),
    Component("fonts", fonts_status, lambda plat: INTER_PIN.size,
              lambda plat: sum(INTER_FONTS.values()) + INTER_PIN.size,
              install_fonts, lambda plat: INTER_PIN, lambda plat: ["Inter-4.1.zip"]),
    Component("venv-cv", cv_status, lambda plat: CV_DOWNLOAD, lambda plat: CV_DISK, install_cv,
              estimated=True, needs_uv=True),
    Component("venv-align", align_status, lambda plat: ALIGN_DOWNLOAD + MMS_FA_PIN.size,
              lambda plat: ALIGN_DISK + MMS_FA_PIN.size, install_align,
              lambda plat: MMS_FA_PIN, lambda plat: ["model.pt"], estimated=True, needs_uv=True),
)}


def still_needed(plat: str, statuses: dict[str, str]) -> tuple[int, int]:
    """(download bytes, disk bytes) for every component whose status is not installed."""
    todo = [COMPONENTS[n] for n, why in statuses.items() if why]
    return sum(c.download(plat) for c in todo), sum(c.disk(plat) for c in todo)


def free_bytes() -> int:
    p = vcore.VT
    while not p.exists():
        p = p.parent
    return shutil.disk_usage(p).free


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def show_list(plat: str) -> None:
    print(f"Video toolkit components  (home: {vcore.VT}, platform: {plat})\n")
    print(f"  {'component':<14} {'download':>10} {'on disk':>10}   status")
    statuses = {}
    for c in COMPONENTS.values():
        why = statuses[c.name] = c.status(plat)
        mark = "~" if c.estimated else ""
        dl = f"{mark}{human(c.download(plat))}" if c.download(plat) else "-"
        disk = f"{mark}{human(c.disk(plat))}" if c.disk(plat) else "-"
        print(f"  {c.name:<14} {dl:>10} {disk:>10}   {why or 'installed'}", flush=True)
    download, disk = still_needed(plat, statuses)
    print(f"\nStill needed: {human(download)} to download, {human(disk)} on disk "
          f"(~ = estimate). {human(free_bytes())} free.")
    if statuses["system"]:
        print("System tools come from your package manager:")
        for ln in system_fix(plat, statuses["system"].split("; ")):
            print(f"  {ln}")


def do_system(plat: str, run_brew: bool) -> int:
    """Report system tools; with run_brew, run install_system_tools.sh for what is missing. 0 when all present."""
    problems = system_problems()
    if not problems:
        print("  system: ffmpeg (libass, libx264), whisper-cli, uv and curl are all present")
        return 0
    print("  system: " + "; ".join(problems))
    if run_brew:
        print("  system: running install_system_tools.sh", flush=True)
        if subprocess.run(["bash", str(vcore.HERE / "install_system_tools.sh")]).returncode != 0:
            vcore.die("system: install_system_tools.sh did not finish; see its output above.")
        vcore._find_installed_tools()
        problems = system_problems()
        if not problems:
            print("  system: all present now")
            return 0
        print("  system: still not right: " + "; ".join(problems))
        return 1
    brew = shutil.which("brew")
    formulas = [f for f in brew_formulas(problems) if not (f == "ffmpeg-full" and ffmpeg_full_installed())]
    if run_brew and brew and formulas:
        print(f"  system: running brew install {' '.join(formulas)}", flush=True)
        if subprocess.run([brew, "install", *formulas]).returncode != 0:
            vcore.die("system: brew install failed; see its output above.")
        problems = system_problems()
        if not problems:
            print("  system: all present now")
            return 0
        print("  system: still not right: " + "; ".join(problems))
    elif run_brew and not brew:
        print("  --run-system only runs Homebrew, and Homebrew is not installed.")
    print("  Fix with:")
    for ln in system_fix(plat, problems):
        print(f"    {ln}")
    return 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Install the video toolkit's components.", usage="%(prog)s [--list] "
                                 "[--adopt DIR] [--run-system] [--dry-run] [component ...]", epilog="Components: all, "
                                 + ", ".join(COMPONENTS) + ". See the top of this file for details.")
    ap.add_argument("components", nargs="*", help="components to install, or 'all'")
    ap.add_argument("--list", action="store_true", help="show each component's status, download size and disk size")
    ap.add_argument("--adopt", metavar="DIR", type=Path, help="copy files from DIR when their SHA-256 matches the pin")
    ap.add_argument("--run-system", action="store_true", help="install missing system tools (Homebrew included)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and any refusal, then stop")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)   # progress and plan lines stay in order with errors on stderr

    plat = host()
    if not plat:
        vcore.die(UNSUPPORTED, 2)
    plugin_root = vcore.HERE.parent.parent.resolve()
    if vcore.VT.resolve() == plugin_root or plugin_root in vcore.VT.resolve().parents:
        vcore.die(f"The toolkit home {vcore.VT} is inside the plugin folder. "
                  "Point VIDEO_TOOLKIT_HOME somewhere else.", 2)

    if args.list:
        show_list(plat)
        return

    names = list(COMPONENTS) if "all" in args.components else list(dict.fromkeys(args.components))
    unknown = [n for n in names if n not in COMPONENTS]
    if not names or unknown:
        ap.print_usage(sys.stderr)
        vcore.die((f"Unknown component(s): {', '.join(unknown)}. " if unknown else "Name what to install. ")
                  + "Choose from: all, " + ", ".join(COMPONENTS), 2)
    if args.adopt:
        if not args.adopt.is_dir():
            vcore.die(f"--adopt {args.adopt}: not a folder.", 2)
        args.adopt = args.adopt.resolve()

    vcore.VT.mkdir(parents=True, exist_ok=True)
    lock = (vcore.VT / ".setup.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        vcore.die("Another setup_toolkit.py is already installing into this toolkit home. Wait for it to finish.", 2)

    print(f"Video toolkit setup  (home: {vcore.VT}, platform: {plat})")
    if rosetta():
        print("Note: this Python runs under Rosetta; installing native arm64 components anyway.")
    result = 0
    if "system" in names:
        result = do_system(plat, args.run_system and not args.dry_run)
        names.remove("system")

    # ---- plan: decide everything, and refuse, before touching anything
    todo: list[tuple[Component, Path | None]] = []
    refusals: list[str] = []
    for name in names:
        c = COMPONENTS[name]
        why = c.status(plat)
        if not why:
            print(f"  {name}: already installed")
            continue
        source = None
        pin = c.adopt_pin(plat)
        if args.adopt and pin:
            source, mismatch = find_adoptable(args.adopt, c.adopt_names(plat), pin)
            if mismatch:
                refusals.append(f"{name}: {mismatch}. Refusing to adopt it; run without --adopt to download.")
        venv = {"venv-cv": vcore.VENV_CV, "venv-align": vcore.VENV_ALIGN}.get(name)
        if venv and venv.exists() and not (venv / "pyvenv.cfg").is_file():
            refusals.append(f"{name}: {venv} exists but is not a Python environment. Move it aside, then re-run.")
        todo.append((c, source))
        print(f"  {name}: {why}")
    if not todo:
        if names:
            print("\nNothing to install.")
        sys.exit(result)

    if any(c.needs_uv for c, _ in todo) and not shutil.which("uv"):
        refusals.append("uv is missing, and the Python environments need it:  " + system_fix(plat, ["uv missing"])[-1])
    if any(c.adopt_pin(plat) and source is None for c, source in todo) and not shutil.which("curl"):
        refusals.append("curl is missing, and downloads need it:  " + system_fix(plat, ["curl missing"])[-1])

    print("\nPlan:")
    total_download = total_disk = 0
    for c, source in todo:
        mark = "~" if c.estimated else ""
        download = c.download(plat) - (source.stat().st_size if source else 0)
        total_download += download
        total_disk += c.disk(plat)
        how = f"copy {source}" + (f", download {mark}{human(download)}" if download else "") if source \
            else f"download {mark}{human(download)}"
        print(f"  {c.name:<14} {how}, {mark}{human(c.disk(plat))} on disk")
    free = free_bytes()
    mark = "~" if any(c.estimated for c, _ in todo) else ""
    print(f"Total: {mark + human(total_download) if total_download else 'nothing'} to download, "
          f"{mark}{human(total_disk)} on disk. {human(free)} free.")
    if free < total_disk + HEADROOM:
        refusals.append(f"Not enough disk: this needs {human(total_disk)} plus {human(HEADROOM)} of headroom, "
                        f"and {human(free)} is free where the toolkit lives. Free space or set VIDEO_TOOLKIT_HOME.")
    if refusals:
        vcore.die("\nRefusing to start:\n  " + "\n  ".join(refusals), 2)
    if args.dry_run:
        print("\nDry run: nothing installed.")
        sys.exit(result)

    # ---- install
    print()
    for c, source in todo:
        started = time.monotonic()
        c.install(plat, source)
        why = c.status(plat)
        if why:
            vcore.die(f"{c.name}: installed, but it still fails its check: {why}")
        print(f"  {c.name}: installed ({time.monotonic() - started:.0f}s)", flush=True)

    print("\nDone." + (" System tools still need the commands above." if result else "")
          + " Run doctor.py to check everything together.")
    sys.exit(result)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        vcore.die("\nInterrupted. Re-run the same command to resume; finished pieces are kept.")
