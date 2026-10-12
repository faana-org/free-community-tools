#!/usr/bin/env python3
"""
Start a video project: probe the raw recordings and write project.json in the project folder.

The project folder holds every working file and output for this set of recordings. Pick one outside the plugin
directory (next to the footage works well). Standard library only.

Usage:
  python3 init_project.py --sources A=path/to/take1.mp4 [B=path/to/take2.mp4 ...] [--folder DIR] [--force]

Paths are stored as given if absolute, otherwise relative to the project folder.
Name pill, platforms and caption style start empty or at defaults: the agent asks the person and edits project.json.

Exit 0 = written. Exit 2 = refused (project.json exists, a source is missing or unusable).
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

HDR_TRANSFERS = {"arib-std-b67", "smpte2084"}   # HLG and PQ: rendering assumes SDR BT.709


def describe(path: Path) -> tuple[dict, list[str]]:
    info = vc.probe(path)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    problems, notes = [], []
    if not v:
        problems.append("no video stream")
    if not a:
        problems.append("no audio stream")
    if problems:
        return {}, problems
    w, h = vc.display_size(info)
    num, den = (int(x) for x in v.get("r_frame_rate", "0/1").split("/"))
    fps = num / den if den else 0.0
    if w > h:
        notes.append(f"landscape {w}x{h}: only portrait (vertical) recordings are supported so far")
    if v.get("color_transfer") in HDR_TRANSFERS:
        notes.append(f"HDR video ({v['color_transfer']}): export or re-record in SDR first; colours will be wrong")
    return {"display_size": [w, h], "duration_s": round(float(info["format"]["duration"]), 2), "fps": round(fps, 3),
            "audio": {"sample_rate": int(a.get("sample_rate", 0)), "channels": int(a.get("channels", 0))}}, notes


def main() -> None:
    ap = argparse.ArgumentParser(description="Create project.json for a set of raw recordings.")
    ap.add_argument("--sources", nargs="+", required=True, metavar="ID=PATH")
    ap.add_argument("--folder", default=".", help="project folder (default: current folder)")
    ap.add_argument("--force", action="store_true", help="replace an existing project.json")
    args = ap.parse_args()
    vc.need_binary("ffprobe", "Install ffmpeg (see doctor.py).")

    folder = Path(args.folder).expanduser().resolve()
    plugin_root = vc.HERE.parents[2]
    if folder == plugin_root or plugin_root in folder.parents:
        vc.die(f"{folder} is inside the plugin. Choose a project folder next to your footage instead.", 2)
    target = folder / "project.json"
    if target.exists() and not args.force:
        vc.die(f"{target} already exists. Edit it, or pass --force to start over (working files are kept).", 2)

    sources, blocked = {}, False
    for item in args.sources:
        m = re.fullmatch(r"([A-Za-z0-9_-]{1,16})=(.+)", item)
        if not m:
            vc.die(f"{item!r}: use ID=PATH, e.g. A=take1.mp4", 2)
        sid, raw = m.group(1), m.group(2)
        if sid in sources:
            vc.die(f"Source id {sid} is used twice.", 2)
        p = Path(raw).expanduser()
        full = p if p.is_absolute() else (Path.cwd() / p).resolve()
        if not full.is_file():
            vc.die(f"Source {sid}: {full} not found.", 2)
        facts, notes = describe(full)
        if not facts:
            print(f"  {sid}: {full.name}: unusable ({', '.join(notes)})")
            blocked = True
            continue
        stored = str(full) if p.is_absolute() else os.path.relpath(full, folder)
        sources[sid] = {"file": stored, "label": f"Take {sid}", **facts}
        w, h = facts["display_size"]
        print(f"  {sid}: {full.name}  {w}x{h}  {facts['fps']} fps  {facts['duration_s'] / 60:.1f} min  "
              f"audio {facts['audio']['sample_rate']} Hz x{facts['audio']['channels']}")
        for n in notes:
            print(f"      ! {n}")
            blocked = True
    if blocked:
        vc.die("Nothing written: fix the sources above first.", 2)

    folder.mkdir(parents=True, exist_ok=True)
    cfg = {**vc.DEFAULTS, "sources": sources}
    target.write_text(json.dumps(cfg, indent=2) + "\n")
    for d in ("specs", "edls"):
        (folder / d).mkdir(exist_ok=True)
    print(f"Wrote {target}\nNext: ask about name pill, platforms and caption style; then measure_audio.py.")


if __name__ == "__main__":
    main()
