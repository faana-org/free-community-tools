#!/usr/bin/env python3
"""
Force-align whisper's words to the cleaned audio with torchaudio MMS_FA.

Keeps whisper's word text (punctuation and case, for captions) and replaces
its timings with a CTC forced alignment against the waveform:

  transcripts/<src>.16k.wav + transcripts/<src>.words.json  ->  transcripts/<src>.aligned.json

Each output word is {"w", "s", "e", "score", "dtw_s"}: aligned start/end in
seconds, mean per-character alignment confidence (0-1), and whisper's original
start for comparison.

The aligner only knows letters, so in English projects numbers and symbols are
aligned as they are usually spoken while the caption keeps whisper's text:
"$5,000" as "five thousand dollars", "20%" as "twenty percent", "1.5" as "one
point five", "1st" as "first", "1990" as "nineteen ninety", "90s" as "nineties",
"&" as "and". A different spoken form only lowers that word's score. A word
that still has nothing to align (a stray dash, a non-Latin word, digits in a
non-English project) refuses the run (exit 2) and names each one: spell it out
in words.json, or delete it if nothing was said there, then re-run.

Words that project.json deletes ("corrections" with "new": "", matched by src,
"old" and "t" as fix_words.py matches them, but against whisper's times) are
left out before aligning, so an invented word can't pull its neighbours' timings.

Star tokens go at the start, the end, and between words separated by more
than GAP_STAR_S, so untranscribed fillers or noise are absorbed instead of
stretching neighbouring words.

Usage:
  python3 align.py                 # every source
  python3 align.py --src B

Runs in the torch environment (re-executes itself there). Measured on one
project, one laptop CPU: about 2 min for a 7 min take. The aligner weights
(~1.2 GB) load from $VIDEO_TOOLKIT_HOME/torch.
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
from fix_words import MATCH_WINDOW_S, load_rules, matching_words  # noqa: E402

WINDOW_S = 30        # emissions computed per window: bounds memory on long takes
CONTEXT_S = 2        # extra audio each side of a window so edge frames see real context
GAP_STAR_S = 0.6     # whisper gaps longer than this get a star token (fillers, restarts, noise)
LOW_SCORE = 0.3      # below this mean confidence a word is reported as doubtful
REPORT_MAX = 25

# ---- spoken forms of numbers and symbols (English)
ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
SCALES = [(10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")]
MAX_CARDINAL_DIGITS = 12                      # longer digit runs are read digit by digit
ORDINAL_ENDINGS = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
                   "nine": "ninth", "twelve": "twelfth"}
CURRENCY = {"$": ("dollar", "dollars", "cent", "cents"), "£": ("pound", "pounds", "penny", "pence"),
            "€": ("euro", "euros", "cent", "cents")}
MULTIPLIERS = {"k": "k", "m": "million", "mm": "million", "bn": "billion"}   # "$5k" is said "five k"
SYMBOL_WORDS = {"&": "and", "+": "plus", "%": "percent", "@": "at", "=": "equals"}
EDGE_PUNCTUATION = ".,?!;:\"'()[]{}…“”‘’"
NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"   # 1,000 / 1,000.5 / 1000 / 1.5


def number_words(n: int) -> str:
    """Cardinal words, space-separated ("42" -> "forty two"); spaces because each part aligns as its own unit."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + number_words(n % 100))
    for size, name in SCALES:
        if n >= size:
            return number_words(n // size) + " " + name + ("" if n % size == 0 else " " + number_words(n % size))
    raise ValueError(n)  # unreachable: every n >= 1000 meets a scale


def integer_words(digits: str, as_year: bool) -> str:
    """A digit string as spoken. Bare 4-digit numbers from 1100 to 2099 read as years ("1990" -> "nineteen ninety")."""
    if len(digits) > MAX_CARDINAL_DIGITS:
        return " ".join(ONES[int(d)] for d in digits)
    n = int(digits)
    if as_year and len(digits) == 4 and (1100 <= n <= 1999 or 2010 <= n <= 2099):
        hi, lo = divmod(n, 100)
        tail = "hundred" if lo == 0 else (f"oh {ONES[lo]}" if lo < 10 else number_words(lo))
        return f"{number_words(hi)} {tail}"
    return number_words(n)


def amount_words(number: str) -> str:
    """"5,000" -> "five thousand"; "1.5" -> "one point five" (never read as a year)."""
    whole, _, frac = number.replace(",", "").partition(".")
    spoken = integer_words(whole, as_year=False)
    return spoken + (" point " + " ".join(ONES[int(d)] for d in frac) if frac else "")


def last_word(words: str, change) -> str:
    head, _, last = words.rpartition(" ")
    return (head + " " if head else "") + change(last)


def ordinal(words: str) -> str:
    return last_word(words, lambda w: ORDINAL_ENDINGS.get(w) or (w[:-1] + "ieth" if w.endswith("y") else w + "th"))


def plural(words: str) -> str:
    return last_word(words, lambda w: w[:-1] + "ies" if w.endswith("y") else w + ("es" if w.endswith("x") else "s"))


def spoken(word: str) -> str:
    """Whisper's word text with numbers and symbols written the way they are usually said.

    Words without digits or "&" come back unchanged, so ordinary words align exactly as before.
    """
    core = word.strip(EDGE_PUNCTUATION)
    if core in SYMBOL_WORDS:
        return SYMBOL_WORDS[core]
    if not re.search(r"[0-9&]", core):
        return word
    if m := re.fullmatch(rf"([$£€])({NUMBER})(k|m|mm|bn)?", core, re.I):
        sym, num, mult = m.groups()
        one, many, sub_one, sub_many = CURRENCY[sym]
        if mult:
            mult = MULTIPLIERS[mult.lower()]
            return f"{amount_words(num)} {mult}" + ("" if mult == "k" else f" {many}")
        whole, _, frac = num.partition(".")
        unit = one if whole == "1" else many
        if len(frac) == 2:
            cents = int(frac)
            return f"{amount_words(whole)} {unit}" + ("" if cents == 0 else
                                                      f" {number_words(cents)} {sub_one if cents == 1 else sub_many}")
        return f"{amount_words(num)} {unit}"
    if m := re.fullmatch(rf"({NUMBER})(k|m|mm|bn)", core, re.I):
        return f"{amount_words(m.group(1))} {MULTIPLIERS[m.group(2).lower()]}"
    if m := re.fullmatch(rf"({NUMBER})%", core):
        return f"{amount_words(m.group(1))} percent"
    if m := re.fullmatch(r"(\d+)(?:st|nd|rd|th)", core, re.I):
        return ordinal(integer_words(m.group(1), as_year=False))
    if m := re.fullmatch(r"(\d{2}|\d{4})'?s", core):
        return plural(integer_words(m.group(1), as_year=True))
    if re.fullmatch(NUMBER, core):
        return amount_words(core) if re.search(r"[,.]", core) else integer_words(core, as_year=True)
    # anything else with digits (B2B, 24/7, 10:30, a date): each digit run as spoken, "&" as "and"
    text = core.replace("&", " and ")
    return re.sub(r"\d+", lambda d: f" {integer_words(d.group(), as_year=True)} ", text)


def normalise(word: str, english: bool) -> str:
    """Word text -> the lowercase letters, apostrophes and spaces the aligner can match."""
    text = spoken(word) if english else word
    return " ".join(re.sub(r"[^a-z' ]", "", text.lower().replace("-", "")).split())


# --------------------------------------------------------------------------


def drop_deleted(sid: str, words: list[dict], corrections: list[dict]) -> list[dict]:
    """words.json minus the words project.json deletes for this source (refuses an ambiguous deletion)."""
    for c in corrections:
        if c["src"] != sid or c["new"] != "":
            continue
        found = matching_words(words, c)
        if len(found) > 1:
            vc.die(f"{sid}: deletion of {c['old']!r} near t={c['t']} matches {len(found)} words within "
                   f"{MATCH_WINDOW_S} s of whisper's times (" + ", ".join(f"{w['w']!r}@{w['s']}" for w in found)
                   + "). Make \"t\" more precise in project.json. Nothing was written.", 2)
        if not found:
            print(f"{sid}: deletion of {c['old']!r} near t={c['t']} matches no word in whisper's times; "
                  f"fix_words.py will remove it after alignment instead.")
            continue
        words = [w for w in words if w is not found[0]]
        print(f"{sid}: left out {found[0]['w']!r}@{found[0]['s']} before aligning (deleted in project.json)")
    return words


def check_alignable(proj: vc.Project, sid: str, words: list[dict], labels: dict, english: bool) -> None:
    """Refuse before any alignment if a word has nothing to align: it would silently vanish from the captions."""
    bad = [w for w in words if not any(ch in labels for ch in normalise(w["w"], english).replace(" ", ""))]
    if not bad:
        return
    listed = "\n".join(f"  {w['w']!r} at {w['s']} s" for w in bad[:REPORT_MAX])
    more = f"\n  ... and {len(bad) - REPORT_MAX} more" if len(bad) > REPORT_MAX else ""
    vc.die(f"{sid}: {len(bad)} word(s) have no letters the aligner can match, so they would vanish from the captions:\n"
           f"{listed}{more}\n"
           f"Fix: in {proj.words(sid)}, change each \"w\" to how it was said (e.g. \"twenty twenty six\"), or delete "
           f"the entry if nothing was said there. Then re-run align.py --src {sid}; don't re-run transcribe.py, "
           f"which would overwrite the edit. Nothing was written.", 2)


def align_source(proj: vc.Project, sid: str, words: list[dict], model, labels: dict, sample_rate: int,
                 english: bool) -> None:
    import torch
    import torchaudio

    out_path = proj.aligned(sid)
    wav, sr = torchaudio.load(str(proj.asr16(sid)))
    wav = torchaudio.functional.resample(wav.mean(0, keepdim=True), sr, sample_rate)

    # emissions in windows with context each side, stitched at the model's 20 ms frame resolution
    chunk, ctx = WINDOW_S * sample_rate, CONTEXT_S * sample_rate
    ems = []
    total = wav.shape[1]
    with torch.inference_mode():
        for start in range(0, total, chunk):
            a, b = max(0, start - ctx), min(total, start + chunk + ctx)
            em, _ = model(wav[:, a:b])
            fpf = (b - a) / em.shape[1]  # samples per emission frame
            s_idx = int(round((start - a) / fpf))
            e_idx = int(round((min(total, start + chunk) - a) / fpf))
            ems.append(em[:, s_idx:e_idx])
    emission = torch.cat(ems, dim=1)
    ratio = total / emission.shape[1] / sample_rate  # seconds per frame

    units, unit_word = ["*"], [None]  # for each aligned unit, its index into words (None for a star)
    for i, w in enumerate(words):
        n = normalise(w["w"], english)
        if i and w["s"] - words[i - 1]["e"] > GAP_STAR_S:
            units.append("*")
            unit_word.append(None)
        for part in n.split():
            units.append(part)
            unit_word.append(i)
    units.append("*")
    unit_word.append(None)

    targets, unit_of_token = [], []
    for u_i, u in enumerate(units):
        for ch in u:
            if ch in labels:
                targets.append(labels[ch])
                unit_of_token.append(u_i)

    try:
        aligned, scores = torchaudio.functional.forced_align(
            emission, torch.tensor([targets], dtype=torch.int32), blank=0)
    except RuntimeError as exc:
        vc.die(f"{sid}: forced alignment failed ({exc}).\n"
               f"The word list may not belong to this audio, or is longer than the audio can hold. "
               f"Re-run transcribe.py --src {sid}.")
    aligned, scores = aligned[0], scores[0].exp()
    tok_spans = torchaudio.functional.merge_tokens(aligned, scores)
    if len(tok_spans) != len(targets):
        vc.die(f"{sid}: aligner returned {len(tok_spans)} character spans for {len(targets)} characters, "
               f"so timings cannot be matched back to words. Nothing was written; report this with {proj.words(sid)}.")

    out = []
    for i, w in enumerate(words):
        idx = [k for k, u in enumerate(unit_of_token) if unit_word[u] == i]
        sp = [tok_spans[k] for k in idx]   # never empty: check_alignable refused words with nothing to align
        out.append({"w": w["w"], "s": round(sp[0].start * ratio, 3), "e": round(sp[-1].end * ratio, 3),
                    "score": round(float(sum(x.score for x in sp) / len(sp)), 3), "dtw_s": w["s"]})

    vc.write_atomic(out_path, json.dumps(out, indent=0))
    low = [x for x in out if x["score"] < LOW_SCORE]
    print(f"{out_path}: {len(out)} words aligned, {len(low)} low-confidence: "
          + ", ".join(f"{x['w']}@{x['s']}" for x in low[:REPORT_MAX]), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Force-align words.json to the audio (writes aligned.json).")
    ap.add_argument("--project", type=Path, help="project folder (default: this folder or the nearest parent with project.json)")
    ap.add_argument("--src", action="append", help="source id from project.json (repeatable; default: all)")
    args = ap.parse_args()

    proj = vc.Project(args.project)
    sources = proj.pick_sources(args.src)
    for sid in sources:
        if not proj.words(sid).is_file():
            vc.die(f"{sid}: {proj.words(sid)} not found. Run transcribe.py --src {sid} first.", 2)
        if not proj.asr16(sid).is_file():
            vc.die(f"{sid}: {proj.asr16(sid)} not found. Re-create it with transcribe.py --src {sid} --resample-only.", 2)

    os.environ.setdefault("TORCH_HOME", str(vc.TORCH_HOME))
    vc.require(["torch", "torchaudio"], vc.VENV_ALIGN)
    import torchaudio

    bundle = torchaudio.pipelines.MMS_FA
    labels = bundle.get_dict(star="*")
    english = proj.cfg["language"] == "en"
    corrections, _, _ = load_rules(proj)
    word_lists = {}
    for sid in sources:   # check every source before the slow model load, so a refusal costs seconds
        words = json.loads(proj.words(sid).read_text())
        if not words:
            vc.die(f"{sid}: {proj.words(sid)} has no words. Re-run transcribe.py --src {sid}.")
        words = drop_deleted(sid, words, corrections)
        check_alignable(proj, sid, words, labels, english)
        word_lists[sid] = words

    model = bundle.get_model(with_star=True).eval()
    for sid in sources:
        align_source(proj, sid, word_lists[sid], model, labels, bundle.sample_rate, english)


if __name__ == "__main__":
    main()
