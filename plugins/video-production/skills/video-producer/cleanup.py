#!/usr/bin/env python3
"""
Free disk space in a finished project by removing large intermediates that can be regenerated.

Lists what would go and how big it is; deletes only with --yes. Never touches the source recordings,
project.json, specs, EDLs, transcripts/tracking JSON or the finished videos in the output folder.

  default          extracted source audio (audio/*.wav, re-made by measure_audio.py in seconds), per-cut render
                   audio (work/*/a*.wav, work/*/audio.wav), re-transcription scratch (work/*/verify/)
  --include-clean  also the denoised tracks in clean/ and transcripts/*.16k.wav, which alignment and phrase
                   scoring read (regenerate with clean_audio.py and transcribe.py --resample-only; a re-clean of
                   the transcription track can shift word timings, so re-align before re-rendering)

Usage:
  python3 cleanup.py [--project DIR] [--include-clean] [--yes]

Exit 0 = listed or deleted. Exit 2 = refused (no project).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402


def size_of(p: Path) -> int:
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())
    return p.stat().st_size if p.is_file() and not p.is_symlink() else 0


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def main() -> None:
    ap = argparse.ArgumentParser(description="Remove regenerable intermediates from a project.")
    ap.add_argument("--project")
    ap.add_argument("--include-clean", action="store_true")
    ap.add_argument("--yes", action="store_true", help="delete (default: list only)")
    args = ap.parse_args()
    proj = vc.Project(args.project)
    root = proj.root
    protected = {proj.source_file(s).resolve() for s in proj.source_ids}
    out = Path(proj.cfg["output_dir"]).expanduser()
    out = (out if out.is_absolute() else root / out).resolve()

    targets: list[Path] = []
    targets += sorted((root / "audio").glob("*.wav"))
    for w in sorted((root / "work").glob("*")):
        targets += sorted(w.glob("a[0-9][0-9][0-9]*.wav")) + ([w / "audio.wav"] if (w / "audio.wav").is_file() else [])
        if (w / "verify").is_dir():
            targets.append(w / "verify")
    if args.include_clean:
        targets += sorted((root / "clean").rglob("*.wav")) + sorted((root / "transcripts").glob("*.16k.wav"))

    safe = []
    for t in targets:
        r = t.resolve()
        if r in protected or r == out or out in r.parents or root not in r.parents:
            continue   # never a source, never the finished videos, never outside the project
        safe.append(t)
    total = 0
    for t in safe:
        n = size_of(t)
        total += n
        print(f"  {human(n):>9}  {t.relative_to(root)}")
    if not safe:
        print("Nothing to remove.")
        return
    if not args.yes:
        print(f"{human(total)} in {len(safe)} items would be removed. Run again with --yes to delete.")
        return
    for t in safe:
        if t.is_dir() and not t.is_symlink():
            shutil.rmtree(t)
        else:
            t.unlink()
    print(f"Removed {human(total)} in {len(safe)} items.")


if __name__ == "__main__":
    main()
