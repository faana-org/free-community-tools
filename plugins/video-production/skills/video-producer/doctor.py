#!/usr/bin/env python3
"""
Pre-flight check for the video-production toolkit.

Answers one question: if I start a project right now, what will go wrong?
Every FIX line gives the exact command that fixes it and how big the download is.

This only looks. It never installs or downloads anything; setup_toolkit.py does.

Usage:  python3 doctor.py [project-folder]

With a project folder it also checks that project.json loads and that every
source video exists and is portrait.

Exit 0 = ready to run. Exit 1 = something needs fixing first.
Exit 2 = refused before checking anything (bad argument).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # importing vcore must not leave __pycache__ in the plugin folder
import setup_toolkit as st  # noqa: E402
import vcore  # noqa: E402

OK, WARN, BAD = "  OK  ", " WARN ", " FIX  "
problems = 0
warnings = 0
needed: set[str] = set()   # setup components still to install, for the disk check


def line(state: str, what: str, detail: str = "") -> None:
    print(f"[{state}] {what}" + ("\n         " + detail.replace("\n", "\n         ") if detail else ""))


def fail(what: str, detail: str) -> None:
    global problems
    problems += 1
    line(BAD, what, detail)


def warn(what: str, detail: str) -> None:
    global warnings
    warnings += 1
    line(WARN, what, detail)


def setup_base() -> str:
    home = f"VIDEO_TOOLKIT_HOME={shlex.quote(str(vcore.VT))} " if "VIDEO_TOOLKIT_HOME" in os.environ else ""
    return f"{home}python3 {shlex.quote(str(vcore.HERE / 'setup_toolkit.py'))}"


def setup_cmd(component: str, plat: str, size: str = "") -> str:
    """The exact command that installs a component, with its download size (or the size given)."""
    c = st.COMPONENTS[component]
    size = size or f"{'~' if c.estimated else ''}{st.human(c.download(plat))} download"
    return f"Install it:  {setup_base()} {component}   ({size})"


def runs(cmd: list[str], timeout: int = 60) -> tuple[bool, str]:
    """(exit code was 0, last line of output)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, exc.__class__.__name__
    tail = (r.stderr or r.stdout).strip().splitlines()[-1:] or [f"exit {r.returncode}"]
    return r.returncode == 0, tail[0]


# --------------------------------------------------------------------------
# machine
# --------------------------------------------------------------------------


def check_platform() -> str:
    system, machine = platform.system(), platform.machine()
    plat = st.host()
    if not plat:
        windows = system == "Windows" or system.startswith(("CYGWIN", "MSYS", "MINGW"))
        where = "Windows" if windows else f"{system} {machine}"
        fail(f"{where} is not supported", st.UNSUPPORTED)
        print(f"\n{problems} thing(s) need fixing before the toolkit will work.")
        sys.exit(1)

    if plat.startswith("macos"):
        version = platform.mac_ver()[0]
        if st.rosetta():
            warn(f"macOS {version}: Python is running as x86_64 under Rosetta on an arm64 Mac",
                 "The toolkit installs native arm64 pieces, but anything this Python runs is slower.\n"
                 "Use a native python3 (for example /opt/homebrew/bin/python3) in a terminal not set to open\n"
                 "with Rosetta.")
        else:
            line(OK, f"macOS {version} {machine}")
        # opencv-python 5.0.0.93 publishes wheels for macOS 14+ on Intel and macOS 13+ on Apple Silicon.
        minimum = 13 if plat == "macos-arm64" else 14
        if version and int(version.split(".")[0]) < minimum:
            warn(f"macOS {version} is older than the opencv wheels support ({minimum}+ on this hardware)",
                 "venv-cv will not install here. Update macOS first.")
    else:
        wsl = "microsoft" in platform.release().lower()
        libc, libc_version = platform.libc_ver()
        name = f"Linux{' (WSL2)' if wsl else ''} {machine}"
        glibc = tuple(int(x) for x in libc_version.split(".")[:2] if x.isdigit()) if libc == "glibc" else ()
        if libc != "glibc":
            warn(f"{name}: could not confirm glibc", "The torch and opencv wheels need glibc 2.28 or newer; musl "
                 "distributions such as Alpine are not supported.")
        elif glibc < (2, 28):
            fail(f"{name} with glibc {libc_version}", "The torch and opencv wheels need glibc 2.28 or newer. "
                 "Upgrade the distribution (Ubuntu 20.04+, Debian 10+).")
        else:
            line(OK, f"{name}, glibc {libc_version}")
    return plat


def check_python() -> None:
    v = sys.version_info
    if (v.major, v.minor) < (3, 9):
        fail(f"Python {v.major}.{v.minor} is too old", "Install Python 3.9 or newer.")
    else:
        line(OK, f"Python {v.major}.{v.minor}")


def check_system(plat: str) -> None:
    ffmpeg = st.ffmpeg_problems()
    if ffmpeg:
        fail("; ".join(ffmpeg), "Fix:  " + "\n".join(st.system_fix(plat, ffmpeg)))
    else:
        first = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.split()
        version = first[2] if len(first) > 2 else "(unknown version)"
        line(OK, f"ffmpeg {version} with libass (subtitles filter) and libx264; ffprobe")

    if not shutil.which("whisper-cli"):
        fail("whisper-cli missing", "Fix:  " + "\n".join(st.system_fix(plat, ["whisper-cli missing"])))
    else:
        ok, tail = runs(["whisper-cli", "--help"])
        if ok:
            line(OK, "whisper-cli runs")
        else:
            fail(f"whisper-cli is installed but `whisper-cli --help` fails ({tail})",
                 "Reinstall:  " + ("brew reinstall whisper-cpp" if shutil.which("brew") else "rebuild whisper.cpp"))

    for tool, why in (("uv", "builds the Python environments"), ("curl", "downloads the models")):
        if shutil.which(tool):
            line(OK, tool)
        else:
            fail(f"{tool} missing ({why})", "Fix:  " + "\n".join(st.system_fix(plat, [f"{tool} missing"])))


# --------------------------------------------------------------------------
# toolkit assets
# --------------------------------------------------------------------------


def check_file(label: str, component: str, path: Path, pin: st.Pin, plat: str) -> None:
    why = st.file_problem(path, pin.size, pin.magic)
    if why:
        needed.add(component)
        fail(f"{label}: {why}", f"{path}\n{setup_cmd(component, plat)}")
    else:
        line(OK, f"{label} ({st.human(pin.size)})")


def check_assets(plat: str) -> None:
    check_file("whisper model", "whisper-model", vcore.WHISPER_MODEL, st.WHISPER_PIN, plat)

    pin = st.DEEP_FILTER_PINS[plat]
    why = st.file_problem(vcore.DEEP_FILTER, pin.size, pin.magic)
    if why:
        needed.add("deep-filter")
        fail(f"deep-filter: {why}", f"{vcore.DEEP_FILTER}\n{setup_cmd('deep-filter', plat)}")
    else:
        ok, tail = runs([str(vcore.DEEP_FILTER), "--help"])
        path = shlex.quote(str(vcore.DEEP_FILTER))
        if ok:
            line(OK, "deep-filter 0.5.6 runs")
        elif not os.access(vcore.DEEP_FILTER, os.X_OK):
            fail("deep-filter is not executable", f"Fix:  chmod +x {path}")
        elif platform.system() == "Darwin" and subprocess.run(
                ["xattr", "-p", "com.apple.quarantine", str(vcore.DEEP_FILTER)], capture_output=True).returncode == 0:
            fail("deep-filter is blocked by macOS quarantine", f"Fix:  xattr -d com.apple.quarantine {path}")
        else:
            needed.add("deep-filter")
            fail(f"deep-filter does not run ({tail})",
                 f"Replace it:  rm {path} && {setup_base()} deep-filter"
                 f"   ({st.human(pin.size)} download)")

    check_file("YuNet face model", "yunet", vcore.YUNET_MODEL, st.YUNET_PIN, plat)

    bad = {name: st.file_problem(vcore.FONTS_DIR / name, size, st.TTF) for name, size in st.INTER_FONTS.items()}
    required = [f"{n} {bad[n]}" for n in st.REQUIRED_FONTS if bad[n]]
    optional = [f"{n} {why}" for n, why in bad.items() if why and n not in st.REQUIRED_FONTS]
    if required or optional:
        needed.add("fonts")
    if required:
        fail("Caption fonts: " + "; ".join(required + optional), f"{vcore.FONTS_DIR}\n{setup_cmd('fonts', plat)}")
    elif optional:
        warn("Optional Inter weights: " + "; ".join(optional), setup_cmd("fonts", plat))
    else:
        line(OK, f"Inter fonts ({', '.join(n[6:-4] for n in st.INTER_FONTS)})")


def check_envs(plat: str) -> None:
    versions, why = st.probe_env(vcore.VENV_CV, st.CV_PROBE)
    if versions:
        line(OK, f"Python environment for tracking and rendering "
                 f"(opencv {versions['opencv']}, numpy {versions['numpy']})")
    else:
        needed.add("venv-cv")
        hint = "\nOn Linux, opencv also needs:  sudo apt-get install -y libgl1 libglib2.0-0" if "libGL" in why else ""
        fail(f"Python environment for tracking and rendering: {why}",
             f"{vcore.VENV_CV}\n{setup_cmd('venv-cv', plat)}{hint}")

    versions, why = st.probe_env(vcore.VENV_ALIGN, st.ALIGN_PROBE)
    if versions:
        line(OK, f"Python environment for forced alignment (torch {versions['torch']}, "
                 f"torchaudio {versions['torchaudio']}, "
                 f"MMS_FA and forced_align present, audio backend {', '.join(versions['audio'])})")
    else:
        needed.add("venv-align")
        fail(f"Python environment for forced alignment: {why}",
             f"{vcore.VENV_ALIGN}\n"
             + setup_cmd("venv-align", plat, f"~{st.human(st.ALIGN_DOWNLOAD)} of packages; weights below"))

    # One venv-align command installs both; each line states only its own download, so nothing is counted twice.
    weights = st.file_problem(st.MMS_FA_WEIGHTS, st.MMS_FA_PIN.size, st.MMS_FA_PIN.magic)
    weights_size = f"{st.human(st.MMS_FA_PIN.size)} download"
    if weights and "venv-align" in needed:
        fail(f"MMS_FA aligner weights: {weights}",
             f"{st.MMS_FA_WEIGHTS}\nInstalled by the same venv-align command above   ({weights_size})")
    elif weights:
        needed.add("venv-align")
        fail(f"MMS_FA aligner weights: {weights}",
             f"{st.MMS_FA_WEIGHTS}\n{setup_cmd('venv-align', plat, weights_size)}")
    else:
        line(OK, f"MMS_FA aligner weights ({st.human(st.MMS_FA_PIN.size)})")


def check_disk(plat: str) -> None:
    need = sum(st.COMPONENTS[c].disk(plat) for c in needed)
    free = st.free_bytes()
    # The per-component disk figures are padded estimates (uv's wheel cache, the fonts zip while it unpacks),
    # so a finished install measures less than this.
    if free < need + st.HEADROOM:
        fail(f"Only {st.human(free)} free where the toolkit lives",
             f"Setup still needs up to ~{st.human(need)} (a padded estimate) "
             f"plus {st.human(st.HEADROOM)} of headroom.\n"
             "Free some space, or set VIDEO_TOOLKIT_HOME to a folder on a bigger disk.")
    elif need:
        line(OK, f"{st.human(free)} free disk (setup needs up to ~{st.human(need)}, a padded estimate, "
                 f"plus {st.human(st.HEADROOM)} headroom)")
    else:
        line(OK, f"{st.human(free)} free disk")


# --------------------------------------------------------------------------
# project
# --------------------------------------------------------------------------


def check_project(folder: Path) -> None:
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            project = vcore.Project(folder)
    except SystemExit:
        fail("project.json does not load", err.getvalue().strip())
        return
    except ValueError as exc:
        fail("project.json is not valid JSON", f"{folder}: {exc}")
        return
    line(OK, f"project.json loads ({len(project.source_ids)} source(s), every file present)")

    if not shutil.which("ffprobe"):
        warn("Skipped the source orientation check", "It needs ffprobe (see the ffmpeg line above).")
        return
    for sid in project.source_ids:
        name = project.source_file(sid).name
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                w, h = project.source_size(sid)
        except SystemExit:
            fail(f"Source {sid} ({name}) could not be read", err.getvalue().strip())
            continue
        if h > w:
            line(OK, f"Source {sid} ({name}) is portrait, {w}x{h}")
        else:
            warn(f"Source {sid} ({name}) is {'landscape' if w > h else 'square'}, {w}x{h}",
                 "Only portrait sources are supported yet; framing and captions assume a vertical frame.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Pre-flight check for the video-production toolkit. Changes nothing.")
    ap.add_argument("project", nargs="?", type=Path, help="project folder (where project.json lives) to check too")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)   # keeps result lines in order with messages on stderr
    if args.project and not args.project.is_dir():
        vcore.die(f"{args.project} is not a folder. Pass the project folder that holds project.json.", 2)

    print("Video toolkit -- pre-flight check\n")
    print(f"Toolkit home: {vcore.VT}\n")
    plat = check_platform()
    check_python()
    check_system(plat)
    check_assets(plat)
    check_envs(plat)
    check_disk(plat)
    if args.project:
        print("\nProject\n")
        check_project(args.project)

    print()
    if problems:
        print(f"{problems} thing(s) need fixing before the toolkit will work.")
        missing = [c for c in st.COMPONENTS if c in needed]
        if missing:
            print(f"To install every missing component at once:  {setup_base()} {' '.join(missing)}")
        sys.exit(1)
    if warnings:
        print(f"Ready to run, with {warnings} warning(s) above.")
    else:
        print("Ready to run.")


if __name__ == "__main__":
    main()
