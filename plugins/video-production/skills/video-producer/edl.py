#!/usr/bin/env python3
"""
Turn a readable edit spec into an exact cut list (EDL), using forced-aligned word timings.

A spec names what to keep by its words, not by timecodes:

  {"name": "short-01", "format": "9x16",
   "clips": [
     {"src": "A", "from": "first words", "near": 12, "to": "last words.", "drop": ["um,", ["again", 40.2]]},
     {"src": "B", "from": "a later line", "near": 300, "to": "its end.", "punch": true, "hold": 1.0}
   ],
   "retext": [["A", "end.", 41.9, "end,"]]}

  from / to   words matched ignoring case and punctuation; "near" (seconds) picks the closest occurrence
  drop        filler or restart words inside the clip; [words, near_seconds] targets one occurrence
  punch       open this clip at the key-line zoom
  hold        seconds of natural pause kept after the clip's last word (a beat before the next cut)
  retext      caption-only text changes, e.g. punctuation across a splice: [src, word, near_seconds, new text]

Pauses inside a clip are tightened to 0.50 s after . ? !, 0.35 s after , ; : and 0.25 s otherwise; a cut that
would remove under 0.1 s of pause is skipped (it would only show as a jump).
Every cut snaps to real silence on the cleaned track. Framing changes only on natural beats.

Usage:
  python3 edl.py SPEC_NAME [--project DIR]      reads specs/SPEC_NAME.json, writes edls/SPEC_NAME.json
Prints the cut list and the edit read back as continuous text; read it before rendering.

Exit 0 = written. Exit 2 = a spec phrase wasn't found (nothing written).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402

vc.require(["numpy"], vc.VENV_CV)
import vnum  # noqa: E402

FORMAT_NAMES = set(vc.FORMATS)
ENV_PER_S = int(round(1 / vnum.ENVELOPE_HOP_S))   # silence envelope frames per second (100)
WORD_GUARD_S = 0.02        # a cut never comes closer than this to a word it isn't keeping
HOLD_GUARD_S = 0.05        # a held ending stops this far before the next word
QUIET_BEFORE_FRAMES = 4    # 40 ms of quiet before a start
QUIET_AFTER_FRAMES = 6     # 60 ms of quiet after an end
MIN_PAUSE_CUT_S = 0.1      # removing less pause than this (3 frames) only adds a visible jump: keep it instead


class SpecError(Exception):
    pass


def find_seq(words: list[dict], seq: str, near: float | None, lo: int = 0, hi: int | None = None) -> tuple[int, int]:
    toks = [vc.norm_word(t) for t in seq.split()]
    hi = len(words) if hi is None else hi
    hits = [i for i in range(lo, hi - len(toks) + 1)
            if all(vc.norm_word(words[i + k]["w"]) == toks[k] for k in range(len(toks)))]
    if not hits:
        raise SpecError(f"not found: {seq!r}" + (f" near {near}s" if near is not None else ""))
    return min(hits, key=lambda i: abs(words[i]["s"] - (near if near is not None else words[i]["s"]))), len(toks)


def snap_start(env, t: float, floor_t: float) -> float:
    """Latest point at or before t (back SNAP_START_BACK s, never before floor_t) preceded by 40 ms of quiet."""
    q = QUIET_BEFORE_FRAMES
    i = int(t * ENV_PER_S)
    lo = max(int(floor_t * ENV_PER_S) + q, i - int(round(vc.SNAP_START_BACK * ENV_PER_S)))
    for k in range(i, lo - 1, -1):
        if k - q >= 0 and (env[k - q:k] < vc.QUIET_DB).all():
            return (k - q // 2) / ENV_PER_S
    return max(floor_t, t - vc.SNAP_START_BACK)


def snap_end(env, t: float, ceil_t: float) -> float:
    """First point at or after t (up to SNAP_END_FORWARD s, never past ceil_t) followed by 60 ms of quiet."""
    q = QUIET_AFTER_FRAMES
    i = int(t * ENV_PER_S)
    hi = min(int(ceil_t * ENV_PER_S) - q, i + int(round(vc.SNAP_END_FORWARD * ENV_PER_S)))
    for k in range(i, hi + 1):
        if (env[k:k + q] < vc.QUIET_DB).all():
            return (k + q // 2) / ENV_PER_S
    return min(ceil_t, t + vc.SNAP_END_FORWARD)


def build(spec: dict, words: dict, env: dict) -> dict:
    if spec.get("format") not in FORMAT_NAMES:
        raise SpecError(f"format must be one of {sorted(FORMAT_NAMES)}")
    head, tail = vc.HEAD_PAD, vc.TAIL_PAD
    segs, zoom_flip, since_zoom = [], False, 99.0
    for ci, c in enumerate(spec["clips"]):
        if c.get("src") not in words:
            raise SpecError(f"clip {ci + 1}: unknown source {c.get('src')!r}")
        if not c.get("from") or not c.get("to"):
            raise SpecError(f"clip {ci + 1}: needs both \"from\" and \"to\" words")
        W = words[c["src"]]
        i0, _ = find_seq(W, c["from"], c.get("near"))
        i1, n1 = find_seq(W, c["to"], W[i0]["s"] + 1, lo=i0)
        i1 = i1 + n1 - 1
        keep = list(range(i0, i1 + 1))
        for d in c.get("drop", []):
            seq, near = (d, None) if isinstance(d, str) else (d[0], d[1])
            k, n = find_seq(W, seq, near, lo=i0, hi=i1 + 1)
            for j in range(k, k + n):
                if j in keep:
                    keep.remove(j)
        if not keep:
            raise SpecError(f"clip {ci + 1}: its drops remove every word")
        runs, cur = [], [keep[0]]
        for a, b in zip(keep, keep[1:]):
            gap = W[b]["s"] - W[a]["e"]
            last = W[a]["w"][-1]
            target = (vc.PAUSE_AFTER_SENTENCE if last in ".?!" else
                      vc.PAUSE_AFTER_COMMA if last in ",;:" else vc.PAUSE_MID_PHRASE)
            if b != a + 1 or gap > target + head + tail - 0.05:
                runs.append((cur, target))
                cur = [b]
            else:
                cur.append(b)
        runs.append((cur, 0.0))
        e_env = env[c["src"]]
        for ri, (r, target_after) in enumerate(runs):
            prev_e = W[r[0] - 1]["e"] + WORD_GUARD_S if r[0] > 0 else 0.0
            next_s = W[r[-1] + 1]["s"] - WORD_GUARD_S if r[-1] + 1 < len(W) else W[r[-1]]["e"] + 2.0
            s = min(W[r[0]]["s"] - head, snap_start(e_env, W[r[0]]["s"], prev_e))
            s = max(s, prev_e)
            e = max(W[r[-1]]["e"] + tail, snap_end(e_env, W[r[-1]]["e"], next_s))
            e = min(e, next_s)
            e = min(e + max(0.0, target_after - head - tail), W[r[-1] + 1]["s"] - WORD_GUARD_S if r[-1] + 1 < len(W) else e)
            if ri == len(runs) - 1 and c.get("hold"):
                e = min(W[r[-1]]["e"] + c["hold"], W[r[-1] + 1]["s"] - HOLD_GUARD_S) if r[-1] + 1 < len(W) else e + c["hold"]
            prev_text = segs[-1]["text"] if segs else "."
            beat = ri == 0 or (since_zoom >= vc.BEAT_MIN_S and prev_text[-1] in ".,?!;:") or since_zoom >= vc.BEAT_FORCE_S
            if beat:
                zoom_flip = not zoom_flip
                since_zoom = 0.0
                z = vc.ZOOM_PUNCH if (c.get("punch") and ri == 0) else (vc.ZOOM_ALT if zoom_flip else 1.0)
            else:
                z = segs[-1]["zoom"]
            since_zoom += e - s
            segs.append({"src": c["src"], "in": round(s, 3), "out": round(e, 3), "zoom": z,
                         "text": " ".join(W[j]["w"] for j in r)})
    merged = []
    for seg in segs:   # a pause cut that removes almost nothing is a jump for no gain: play straight through
        prev = merged[-1] if merged else None
        if (prev and prev["src"] == seg["src"] and prev["zoom"] == seg["zoom"]
                and 0 <= seg["in"] - prev["out"] < MIN_PAUSE_CUT_S
                and not any(prev["out"] <= (w["s"] + w["e"]) / 2 < seg["in"] for w in words[seg["src"]])):
            prev["out"], prev["text"] = seg["out"], prev["text"] + " " + seg["text"]
        else:
            merged.append(seg)
    segs = merged
    retext = []
    for src, word, near, new_text in spec.get("retext", []):
        k, _ = find_seq(words[src], word, near)
        retext.append({"src": src, "s": words[src][k]["s"], "w": new_text})
    return {"name": spec["name"], "format": spec["format"], "lower_third": spec.get("lower_third"),
            "segments": segs, "retext": retext}


def main() -> None:
    ap = argparse.ArgumentParser(description="Build an exact cut list from an edit spec.")
    ap.add_argument("spec", help="spec name (specs/NAME.json) or a path to a spec file")
    ap.add_argument("--project", help="project folder (default: current folder or a parent)")
    args = ap.parse_args()
    proj = vc.Project(args.project)

    spec_path = Path(args.spec) if args.spec.endswith(".json") else proj.spec(args.spec)
    if not spec_path.is_file():
        vc.die(f"Spec {spec_path} not found.", 2)
    try:
        spec = json.loads(spec_path.read_text())
    except json.JSONDecodeError as e:
        vc.die(f"{spec_path.name} isn't valid JSON (line {e.lineno}, column {e.colno}): {e.msg}. Nothing written.", 2)
    if not isinstance(spec, dict) or not spec.get("name") or not isinstance(spec.get("clips"), list) or not spec["clips"]:
        vc.die(f"{spec_path.name} needs a \"name\" and a non-empty \"clips\" list. Nothing written.", 2)
    bad = [i + 1 for i, c in enumerate(spec["clips"]) if not isinstance(c, dict)]
    if bad:
        vc.die(f"{spec_path.name}: clip(s) {bad} must be objects like {{\"src\": \"A\", \"from\": ..., \"to\": ...}}. "
               "Nothing written.", 2)
    retext = spec.get("retext", [])
    if not isinstance(retext, list) or any(not isinstance(r, list) or len(r) != 4 for r in retext):
        vc.die(f"{spec_path.name}: each retext entry must be [src, word, near_seconds, new text]. Nothing written.", 2)
    srcs = sorted({str(c.get("src")) for c in spec["clips"]} | {str(r[0]) for r in retext})
    words, env = {}, {}
    for s in srcs:
        if s not in proj.source_ids:
            vc.die(f"Spec uses source {s!r}, which isn't in project.json.", 2)
        if not proj.final_words(s).is_file():
            vc.die(f"No final words for {s}. Run align.py and fix_words.py first.", 2)
        if not proj.clean_edit(s).is_file():
            vc.die(f"No cleaned edit track for {s} (clean/edit/{s}.wav). Run clean_audio.py first.", 2)
        words[s] = json.loads(proj.final_words(s).read_text())
        env[s] = vnum.envelope_db(proj.clean_edit(s))
    try:
        edl = build(spec, words, env)
    except SpecError as e:
        vc.die(f"{spec_path.name}: {e}. Nothing written.", 2)

    out = proj.edl(spec["name"])
    vc.write_atomic(out, json.dumps(edl, indent=1))
    total = sum(s["out"] - s["in"] for s in edl["segments"])
    print(f"{edl['name']}: {len(edl['segments'])} cuts, about {total:.1f}s -> {out}")
    for s in edl["segments"]:
        print(f"  {s['src']} {s['in']:7.2f}-{s['out']:7.2f} z{s['zoom']:.2f} | {s['text']}")
    retext = {(r["src"], r["s"]): r["w"] for r in edl["retext"]}
    readback = []
    for seg in edl["segments"]:
        for w in words[seg["src"]]:
            if seg["in"] <= (w["s"] + w["e"]) / 2 < seg["out"]:
                readback.append(retext.get((seg["src"], w["s"]), w["w"]))
    print("\nRead-back (check punctuation across joins):\n  " + " ".join(readback))


if __name__ == "__main__":
    main()
