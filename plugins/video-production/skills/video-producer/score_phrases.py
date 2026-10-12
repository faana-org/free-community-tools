#!/usr/bin/env python3
"""
Settle a disputed word or phrase by scoring candidate transcriptions against
the audio. Each candidate's CTC loss is how badly its letters fit the span's
waveform under the MMS_FA acoustic model: lower is a better fit.

A verdict is only as good as its candidates. If the reading that is really in
the audio isn't in the list, the best of the wrong ones still wins, and it can
win "clear". The costly miss is a reading that flips the meaning about a person
("a fair decision" vs "unfair decision", "can" vs "can't"). So every case also
scores automatic meaning-flip variants of the supplied candidates, marked
[auto]: one change each, at most MAX_AUTO_VARIANTS per case.
  - negation: can/can't/cannot, could/couldn't, do/don't, does/doesn't, did/didn't, is/isn't,
    was/wasn't, are/aren't, were/weren't, will/won't, would/wouldn't, should/shouldn't,
    have/haven't, has/hasn't; "not" added after an auxiliary or removed;
  - opposites: always/never, ever/never;
  - negative prefixes on adjective-like words: "an X"/"a X" <-> "unX", and "X" <-> "unX", "nonX";
    "in-" as it is spelled before the word ("a responsible" <-> "irresponsible", "impossible", "illegal",
    "inactive"), only for known negatable adjectives or -ible/-able/-ent/-ive/-ate words; "a-" for a
    short list ("a moral" <-> "amoral").
If a variant fits as well as or better than the best supplied candidate
(within MEANING_MARGIN nats), a MEANING CHECK line is printed and the script
exits 1: don't caption that line as heard; ask the person or leave it out.
A variant with exactly the same letters as a supplied candidate ("a moral" /
"amoral") can't be told apart by audio at all, so it isn't scored: a SOUNDS
IDENTICAL line is printed instead, and it also exits 1.

Cases file (JSON), one entry per disputed span:

  [{"src": "A", "start": 64.0, "end": 69.5,
    "candidates": ["the first reading of the span", "the second reading of the span"]}]

  - start/end: seconds in the source, a little wider than the phrase itself;
    take them from the aligned words either side.
  - candidates: whole-span readings that differ only where the doubt is.
    Numbers and symbols are read the way align.py reads them ("20%" = "twenty percent").

Output per case: every candidate ranked by loss margin over the best (0.00 = best),
auto variants marked [auto], and a verdict on the gap between the two best
supplied candidates. The verdict is a rule of thumb from one project, not a
calibrated threshold:

  > 4 nats  clear       2-4  lean       < 2  ambiguous

Treat "lean" and "ambiguous" as questions for the person, or cut around the words.

Record a correction in project.json only with its evidence, e.g.
{"src": "A", "t": 66.1, "old": "their", "new": "there", "evidence": "CTC best by 4.2"}.
Meaning still matters: when the audio favours a reading that could misrepresent
the speaker, leave the words out of the edit rather than caption either one.

Usage:
  python3 score_phrases.py --cases doubts.json
  python3 score_phrases.py --cases doubts.json --no-auto   # debugging only: supplied candidates alone

Exit 0 = scored. Exit 1 = a MEANING CHECK or SOUNDS IDENTICAL fired. Exit 2 = refused (bad cases file, missing audio).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vcore as vc  # noqa: E402
from align import normalise  # noqa: E402

# Rule of thumb from one project, not calibrated. There, corrections were applied at margins of 4.3-4.7 nats
# and once at 1.85, and a name with three plausible spellings separated by only 3.8 still needed the speaker.
MARGIN_CLEAR = 4.0
MARGIN_LEAN = 2.0
# A meaning-flip variant this close to the best supplied candidate is as plausible as it: the same 2-nat line
# below which supplied candidates count as ambiguous.
MEANING_MARGIN = 2.0
MAX_AUTO_VARIANTS = 12

# ---- meaning-flip variants (English)
NEGATIONS = {"can": ["can't", "cannot"], "could": ["couldn't"], "do": ["don't"], "does": ["doesn't"],
             "did": ["didn't"], "is": ["isn't"], "was": ["wasn't"], "are": ["aren't"], "were": ["weren't"],
             "will": ["won't"], "would": ["wouldn't"], "should": ["shouldn't"], "have": ["haven't"], "has": ["hasn't"]}
UNNEGATED = {neg: pos for pos, negs in NEGATIONS.items() for neg in negs}
AUXILIARIES = {"am", "is", "are", "was", "were", "do", "does", "did", "have", "has", "had", "can", "could",
               "will", "would", "should", "may", "might", "must"}
OPPOSITES = {"always": ["never"], "never": ["always", "ever"], "ever": ["never"]}
# bare adjectives that commonly take "un"; longer adjectives are recognised by their suffix
UN_ADJECTIVES = {"aware", "fair", "kind", "clear", "sure", "well", "true", "wise", "safe", "fit", "just", "able",
                 "happy", "easy", "real", "known", "like", "wanted", "willing", "sound"}
ADJECTIVE_SUFFIX = re.compile(r"(?:able|ible|al|ful|ic|ive|ous|ent|ant|ary|ed|ing|ish|y)$")
IN_SUFFIX = re.compile(r"(?:ible|able|ent|ive|ate)$")     # incapable, incompetent, insensitive, inaccurate
NON_SUFFIX = re.compile(r"(?:al|ic|ent)$")                 # nonverbal, nonspecific, nonexistent
NOT_ADJECTIVES = {"that", "this", "they", "them", "then", "than", "very", "only", "many", "every", "anything",
                  "everything", "nothing", "something", "being", "during", "thing", "really", "maybe", "family",
                  "need", "feel", "deal", "real", "early", "story", "company", "money", "body", "lady"} - UN_ADJECTIVES
AMORAL_BASES = {"moral", "political", "typical", "symmetric", "social", "sexual", "theist", "historical"}   # a- prefix
# ir-/im-/il- are added or stripped only for these, or for adjectives with an IN_SUFFIX ending
IN_NEGATABLE = {"responsible", "regular", "relevant", "rational", "reversible", "legal", "logical", "literate",
                "mature", "moral", "mortal", "patient", "perfect", "polite", "possible", "practical", "precise",
                "proper", "balanced", "partial", "personal", "plausible", "probable", "pure"}
# ir-/im-/il- words whose remainder only looks like an IN_SUFFIX adjective ("pressive"): never stripped
ASSIMILATED_LOOKALIKES = {"impressive", "immersive", "impulsive", "immediate", "imminent", "imitate", "illustrate",
                          "irritate", "irrigate"}
NOT_ADJECTIVE_ENDING = re.compile(r"(?:ity|ly|ay|ey|oy|ment)$")   # nouns and adverbs the suffix rules catch: creativity, deeply, environment
EDGE = ".,?!;:\"()[]{}…“”"                                  # apostrophes stay: they belong to can't


def adjective_like(w: str) -> bool:
    if not w.isalpha() or w in NOT_ADJECTIVES:
        return False
    if w in UN_ADJECTIVES:
        return True
    return len(w) >= 5 and bool(ADJECTIVE_SUFFIX.search(w)) and not NOT_ADJECTIVE_ENDING.search(w)


def assimilated_prefix(w: str) -> str:
    """The form "in-" takes before this word: irresponsible, impossible, illegal; "" when it doesn't apply."""
    return {"r": "ir", "l": "il", "m": "im", "p": "im", "b": "im"}.get(w[:1], "")


def in_negatable(w: str) -> bool:
    """Whether ir-/im-/il- may be added to w (or stripped back to it)."""
    return w in IN_NEGATABLE or (adjective_like(w) and bool(IN_SUFFIX.search(w)))


def negative_prefix(w: str) -> tuple[str, str]:
    """("un", "fair") for "unfair", ("ir", "responsible") for "irresponsible"; ("", w) when w isn't negated."""
    for prefix, rule in (("un", None), ("non", None), ("in", IN_SUFFIX)):
        base = w[len(prefix):]
        if w.startswith(prefix) and adjective_like(base) and (rule is None or rule.search(base)):
            return prefix, base
    for prefix in ("ir", "il", "im"):
        base = w[2:]
        if (w.startswith(prefix) and w not in ASSIMILATED_LOOKALIKES and assimilated_prefix(base) == prefix
                and in_negatable(base)):
            return prefix, base
    if w.startswith("a") and len(w) > 5 and w[1:] in AMORAL_BASES:
        return "a", w[1:]
    return "", w


def flip_variants(text: str) -> list[str]:
    """Single-change meaning flips of one candidate, highest-value rules first."""
    toks = text.split()
    low = [t.strip(EDGE).lower().replace("’", "'") for t in toks]
    out: list[str] = []

    def swap(i: int, j: int, words: list[str]) -> None:
        """Replace tokens i..j-1 with words, keeping the last replaced token's trailing punctuation."""
        tail = toks[j - 1][len(toks[j - 1].rstrip(EDGE)):]
        out.append(" ".join(toks[:i] + words[:-1] + [words[-1] + tail] + toks[j:]))

    for i, w in enumerate(low):                          # negation, "not", opposites
        for neg in NEGATIONS.get(w, []):
            swap(i, i + 1, [neg])
        if w in UNNEGATED:
            swap(i, i + 1, [UNNEGATED[w]])
        if w in AUXILIARIES:
            if i + 1 < len(low) and low[i + 1] == "not":
                swap(i, i + 2, [w])
            else:
                swap(i, i + 1, [w, "not"])
        for opp in OPPOSITES.get(w, []):
            swap(i, i + 1, [opp])
    for i, w in enumerate(low):                          # "an X" / "a X" -> "unX", "irX"/"imX"/"ilX", "aX"
        nxt = low[i + 1] if i + 1 < len(low) else ""
        if w in ("a", "an") and adjective_like(nxt):
            swap(i, i + 2, ["un" + nxt])
        if w in ("a", "an") and assimilated_prefix(nxt) and in_negatable(nxt):
            swap(i, i + 2, [assimilated_prefix(nxt) + nxt])
        if w == "a" and nxt in AMORAL_BASES:
            swap(i, i + 2, ["a" + nxt])
    for i, w in enumerate(low):                          # drop a negative prefix
        prefix, base = negative_prefix(w)
        if prefix in ("un", "a"):
            swap(i, i + 1, ["an" if base[0] in "aeiou" else "a", base])
        if prefix:
            swap(i, i + 1, [base])
    for i, w in enumerate(low):                          # add a negative prefix
        if negative_prefix(w)[0]:
            continue
        added = []
        if adjective_like(w):
            added.append("un" + w)
        if assimilated_prefix(w):
            if in_negatable(w):
                added.append(assimilated_prefix(w) + w)
        elif adjective_like(w) and IN_SUFFIX.search(w) and not w.startswith(("in", "im", "ir", "il")):
            added.append("in" + w)
        if adjective_like(w) and NON_SUFFIX.search(w):
            added.append("non" + w)
        if w in AMORAL_BASES:
            added.append("a" + w)
        for new in added:
            if i and low[i - 1] in ("a", "an"):          # keep the article grammatical: "a moral" -> "an immoral"
                swap(i - 1, i + 1, ["an" if new[0] in "aeiou" else "a", new])
            else:
                swap(i, i + 1, [new])
    return out


def load_cases(path: Path, proj: vc.Project) -> list[dict]:
    if not path.is_file():
        vc.die(f"Cases file {path} not found.", 2)
    try:
        cases = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        vc.die(f"{path} is not valid JSON ({exc}).", 2)
    if not isinstance(cases, list) or not cases:
        vc.die(f"{path} must be a non-empty list of {{\"src\", \"start\", \"end\", \"candidates\"}}.", 2)
    english = proj.cfg["language"] == "en"
    for n, c in enumerate(cases, 1):
        where = f"{path} case #{n}"
        if not isinstance(c, dict):
            vc.die(f"{where} must be an object with src, start, end, candidates.", 2)
        if c.get("src") not in proj.cfg["sources"]:
            vc.die(f"{where}: src {c.get('src')!r} is not a source in project.json ({', '.join(proj.source_ids)}).", 2)
        a, b = c.get("start"), c.get("end")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (a, b)) or not 0 <= a < b:
            vc.die(f"{where}: start and end must be seconds with 0 <= start < end; got {a!r}, {b!r}.", 2)
        cands = c.get("candidates")
        if not isinstance(cands, list) or len(cands) < 2 or not all(isinstance(x, str) and x.strip() for x in cands):
            vc.die(f"{where}: candidates must be a list of at least two non-empty strings.", 2)
        for x in cands:
            if not normalise(x, english).replace(" ", ""):
                vc.die(f"{where}: candidate {x!r} has no letters to score; write it as spoken.", 2)
    return cases


def ctc_loss(lp, labels: dict, english: bool, text: str) -> float:
    """Summed CTC loss of text's letters over one span's log-probabilities (T, 1, C): lower fits better."""
    import torch

    t = [labels[ch] for ch in normalise(text, english).replace(" ", "") if ch in labels]
    return float(torch.nn.functional.ctc_loss(lp, torch.tensor([t]), torch.tensor([lp.shape[0]]),
                                              torch.tensor([len(t)]), blank=0, reduction="sum"))


def verdict(gap: float) -> str:
    if gap > MARGIN_CLEAR:
        return "clear"
    if gap >= MARGIN_LEAN:
        return "lean"
    return "ambiguous"


def main() -> None:
    ap = argparse.ArgumentParser(description="Rank candidate transcriptions of audio spans by CTC loss.")
    ap.add_argument("--project", type=Path, help="project folder (default: this folder or the nearest parent with project.json)")
    ap.add_argument("--cases", type=Path, required=True, help="JSON list of {src, start, end, candidates}")
    ap.add_argument("--no-auto", action="store_true", help="debugging only: don't add meaning-flip variants")
    args = ap.parse_args()

    proj = vc.Project(args.project)
    cases = load_cases(args.cases, proj)
    for sid in dict.fromkeys(c["src"] for c in cases):
        if not proj.asr16(sid).is_file():
            vc.die(f"{sid}: {proj.asr16(sid)} not found. Re-create it with transcribe.py --src {sid} --resample-only.", 2)

    os.environ.setdefault("TORCH_HOME", str(vc.TORCH_HOME))
    vc.require(["torch", "torchaudio"], vc.VENV_ALIGN)
    import torch
    import torchaudio

    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model(with_star=False).eval()
    labels = bundle.get_dict(star=None)
    rate = bundle.sample_rate
    english = proj.cfg["language"] == "en"
    audio: dict[str, torch.Tensor] = {}
    flagged = 0

    for c in cases:
        sid, a, b = c["src"], c["start"], c["end"]
        if sid not in audio:
            w, sr = torchaudio.load(str(proj.asr16(sid)))
            audio[sid] = torchaudio.functional.resample(w.mean(0, keepdim=True), sr, rate)
        total_s = audio[sid].shape[1] / rate
        if b > total_s:
            vc.die(f"{sid} {a}-{b}: the audio is only {total_s:.1f} s long. Fix the case's end time.", 2)
        wav = audio[sid][:, int(a * rate):int(b * rate)]
        with torch.inference_mode():
            em, _ = model(wav)
        lp = em.log_softmax(-1).transpose(0, 1)  # T,1,C

        print(f"== {sid} {a}-{b}")
        supplied = sorted(((ctc_loss(lp, labels, english, x), x) for x in c["candidates"]), key=lambda r: r[0])
        autos: list[tuple[float, str]] = []
        identical: list[tuple[str, str]] = []   # (supplied, variant) with the same letters: audio can't separate them
        if english and not args.no_auto:
            by_letters = {normalise(x, english).replace(" ", ""): x for _, x in supplied}
            seen = set(by_letters)
            for _, source in supplied:                  # variants of the best supplied candidate first
                for v in flip_variants(source):
                    key = normalise(v, english).replace(" ", "")
                    twin = by_letters.get(key)
                    if twin is not None and normalise(twin, english) != normalise(v, english):
                        if (twin, v) not in identical:
                            identical.append((twin, v))
                        continue
                    if key and key not in seen and len(autos) < MAX_AUTO_VARIANTS:
                        seen.add(key)
                        autos.append((ctc_loss(lp, labels, english, v), v))

        best_supplied = supplied[0][0]
        ranked = sorted([(loss, x, False) for loss, x in supplied] + [(loss, x, True) for loss, x in autos],
                        key=lambda r: r[0])
        best = ranked[0][0]
        if math.isinf(best):
            print("   every candidate is too long for this span; widen start/end")
            continue
        for loss, text, auto in ranked:
            margin = f"{loss - best:7.2f}" if math.isfinite(loss) else "    inf"
            print(f"   {margin}  {text}" + ("  [auto]" if auto else ""))
        if math.isinf(best_supplied):
            print("   verdict: none (no supplied candidate fits the span)")
        else:
            gap = supplied[1][0] - best_supplied
            print(f"   verdict: {verdict(gap)} (best supplied by {gap:.2f})" if math.isfinite(gap)
                  else "   verdict: clear (supplied runner-up cannot fit the span)")
        close = [(loss, text) for loss, text in autos if math.isfinite(loss) and loss <= best_supplied + MEANING_MARGIN]
        for loss, text in close:
            print(f"   MEANING CHECK: '{text}' fits the audio as well or better — do not caption this line as heard; "
                  f"ask the person or leave the line out. ({loss - best_supplied:+.2f} vs best supplied)")
        for twin, v in identical:
            print(f"   SOUNDS IDENTICAL: '{twin}' vs '{v}' can't be settled by audio; decide from context or ask the person")
        flagged += bool(close or identical)
        sys.stdout.flush()

    if flagged:
        print(f"MEANING CHECK or SOUNDS IDENTICAL on {flagged} case(s).")
        sys.exit(1)


if __name__ == "__main__":
    main()
