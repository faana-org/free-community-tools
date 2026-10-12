#!/usr/bin/env python3
"""
Apply verified transcript corrections and caption spellings to the aligned
words, writing the only word file that cutting and captions may use:

  transcripts/<src>.aligned.json + project.json  ->  transcripts/<src>.final.json

Three project.json settings drive it, applied in this order:

  "corrections": [{"src": "A", "t": 12.3, "old": "their", "new": "there", "evidence": "CTC best by 4.1"}]
      Replaces the one word whose letters equal "old" and whose aligned start is
      within MATCH_WINDOW_S of t. The word's trailing punctuation is kept, and
      "new" may be several words. Corrections apply in list order, and each needs
      a non-empty "evidence" (e.g. a score_phrases.py margin).
      "new": "" deletes the word, e.g. a word whisper invented that isn't in the
      audio: {"src": "B", "t": 41.0, "old": "so", "new": "", "evidence": "CTC best by 5.0 without it"}.
      align.py applies deletions before aligning (matched the same way, against
      whisper's times), so the neighbours are timed without the invented word: re-run
      align.py after adding one. If aligned.json still has the word, it is removed
      here and its neighbours keep the timings they got while it was present.
  "casing": {"acme": "ACME", "github": "GitHub"}
      Lowercase word -> caption spelling. I, I'm, I've, I'll and I'd are built in.
  "phrases": [["open", "source", "Open-", "Source"]]
      Two consecutive words [w1, w2] shown as [R1, R2]; the second word's
      trailing punctuation is kept.

A correction that matches no word, or more than one, refuses the whole run
(exit 2) and writes nothing: widen or fix "t" and "old" in project.json.

Re-running is safe: it always starts again from aligned.json.

Usage:
  python3 fix_words.py
  python3 fix_words.py --src B
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402

MATCH_WINDOW_S = 1.5   # max distance from "t" to the word's aligned start; tolerates a t read off a score_phrases span
BUILTIN_CASING = {"i": "I", "i'm": "I'm", "i've": "I've", "i'll": "I'll", "i'd": "I'd"}


def load_rules(proj: vc.Project) -> tuple[list[dict], dict[str, str], list[list[str]]]:
    """Read and validate corrections, casing and phrases from project.json (exit 2 on anything malformed)."""
    cfg = proj.cfg
    corrections = cfg.get("corrections") or []
    if not isinstance(corrections, list):
        vc.die("project.json \"corrections\" must be a list of {\"src\", \"t\", \"old\", \"new\"}.", 2)
    for n, c in enumerate(corrections, 1):
        ok = (isinstance(c, dict) and isinstance(c.get("src"), str) and isinstance(c.get("t"), (int, float))
              and not isinstance(c.get("t"), bool) and isinstance(c.get("old"), str) and isinstance(c.get("new"), str)
              and vc.norm_word(c["old"]) and (c["new"] == "" or c["new"].strip()))
        if not ok:
            vc.die(f"project.json corrections #{n} must look like "
                   f"{{\"src\": \"A\", \"t\": 12.3, \"old\": \"word\", \"new\": \"replacement\" (or \"\" to delete), "
                   f"\"evidence\": \"...\"}}; got {c!r}.", 2)
        if not (isinstance(c.get("evidence"), str) and c["evidence"].strip()):
            vc.die(f"project.json corrections #{n} ({c['old']!r} -> {c['new']!r}) has no \"evidence\". "
                   f"Add what supports it, e.g. the score_phrases.py margin.", 2)
        if c["src"] not in cfg["sources"]:
            vc.die(f"project.json corrections #{n}: source {c['src']!r} is not in \"sources\".", 2)

    casing = cfg.get("casing") or {}
    if not isinstance(casing, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in casing.items()):
        vc.die("project.json \"casing\" must map lowercase words to spellings, e.g. {\"github\": \"GitHub\"}.", 2)

    phrases = cfg.get("phrases") or []
    if not isinstance(phrases, list) or not all(
            isinstance(p, list) and len(p) == 4 and all(isinstance(x, str) and x.strip() for x in p) for p in phrases):
        vc.die("project.json \"phrases\" must be a list of [word1, word2, Shown1, Shown2], "
            "e.g. [[\"open\", \"source\", \"Open-\", \"Source\"]].", 2)

    return corrections, {**BUILTIN_CASING, **{k.lower(): v for k, v in casing.items()}}, \
        [[p[0].lower(), p[1].lower(), p[2], p[3]] for p in phrases]


def matching_words(words: list[dict], correction: dict) -> list[dict]:
    """Words whose letters equal the correction's "old" and whose start is within MATCH_WINDOW_S of its "t"."""
    old = vc.norm_word(correction["old"])
    return [w for w in words if vc.norm_word(w["w"]) == old and abs(w["s"] - correction["t"]) < MATCH_WINDOW_S]


def apply_rules(sid: str, words: list[dict], corrections: list[dict], casing: dict[str, str],
                phrases: list[list[str]], whisper_words: list[dict] | None = None) -> list[dict]:
    """whisper_words (words.json) tells a deletion align.py already applied from one that matches nothing."""
    words = copy.deepcopy(words)
    for c in corrections:
        if c["src"] != sid:
            continue
        cand = matching_words(words, c)
        if c["new"] == "" and not cand and whisper_words and len(matching_words(whisper_words, c)) == 1:
            print(f"{sid} {c['t']}: {c['old']} -> (deleted before alignment by align.py)")
            continue
        if len(cand) != 1:
            found = ", ".join(f"{w['w']!r}@{w['s']}" for w in cand) or "none"
            vc.die(f"{sid}: correction {c['old']!r} -> {c['new']!r} near t={c['t']} must match exactly one word "
                f"within {MATCH_WINDOW_S} s; found {found}.\n"
                f"Fix \"t\" (use the word's aligned start from {sid}.aligned.json) or \"old\" in project.json. "
                f"Nothing was written.", 2)
        if c["new"] == "":
            i = words.index(cand[0])
            gone = words.pop(i)
            near = ", ".join(f"{w['w']!r}@{w['s']} score {w.get('score', '?')}" for w in words[max(0, i - 1):i + 1])
            dropped = re.sub(r"^[\w'-]+", "", gone["w"])
            print(f"{sid} {gone['s']}: {c['old']} -> (deleted after alignment; re-run align.py to time its "
                  f"neighbours without it); neighbours {near}" + (f"; its trailing {dropped!r} went with it" if dropped else ""))
            continue
        punct = re.sub(r"^[\w']+", "", cand[0]["w"])
        cand[0]["w"] = c["new"] + punct
        print(f"{sid} {cand[0]['s']}: {c['old']} -> {cand[0]['w']}")

    for i, w in enumerate(words):
        core = re.match(r"^([\w'-]+)(.*)$", w["w"])
        if not core:
            continue
        head = core.group(1).lower()
        if head in casing:
            w["w"] = casing[head] + core.group(2)
        if i + 1 < len(words):
            nxt = words[i + 1]["w"]
            for w1, w2, shown1, shown2 in phrases:
                rest = nxt[len(w2):]
                if head == w1 and nxt.lower().startswith(w2) and re.fullmatch(r"[^\w']*", rest):
                    w["w"] = shown1
                    words[i + 1]["w"] = shown2 + rest
                    break
    return words


def main() -> None:
    ap = argparse.ArgumentParser(description="Apply corrections, casing and phrases to aligned words (writes final.json).")
    ap.add_argument("--project", type=Path, help="project folder (default: this folder or the nearest parent with project.json)")
    ap.add_argument("--src", action="append", help="source id from project.json (repeatable; default: all)")
    args = ap.parse_args()

    proj = vc.Project(args.project)
    sources = proj.pick_sources(args.src)
    corrections, casing, phrases = load_rules(proj)

    # Work out every source before writing any, so a bad correction leaves no half-updated set of files.
    results = {}
    for sid in sources:
        src = proj.aligned(sid)
        if not src.is_file():
            vc.die(f"{sid}: {src} not found. Run align.py --src {sid} first.", 2)
        whisper = json.loads(proj.words(sid).read_text()) if proj.words(sid).is_file() else None
        results[sid] = apply_rules(sid, json.loads(src.read_text()), corrections, casing, phrases, whisper)

    for sid, words in results.items():
        out = proj.final_words(sid)
        vc.write_atomic(out, json.dumps(words, indent=0))
        print(f"{out}: {len(words)} words written")


if __name__ == "__main__":
    main()
