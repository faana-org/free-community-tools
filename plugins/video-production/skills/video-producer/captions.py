#!/usr/bin/env python3
"""
Animated word-highlight captions (ASS, rendered by libass) and plain .srt files.

Library module used by render.py; not run directly. Input words are already on
the output timeline: [{"w": text, "s": start_s, "e": end_s, "brk": bool}], where
"brk" marks the first word after a cut (a real pause in delivery).

Style decisions, each checked on real frames:
  * 2-3 words per group (up to 4 after the lone-word merge below), max 16 characters (WrapStyle 2 never wraps,
    so longer runs off-screen)
  * break at punctuation, pauses > 0.35 s, and every cut (the lone-word merge below is the one exception)
  * never leave a weak word ("to", "a", "and"...) dangling at a group's end when it fits the next group
    (not across a cut)
  * never flash a lone word when it fits the next group; this merge runs last and does cross cuts and
    pauses, so a group can have 4 words and a lone opening word stays up through the pause
  * the spoken word lights up; each group pops in over 90 ms
"""

from __future__ import annotations

import re

MAX_WORDS = 3
MAX_CHARS = 16
GROUP_GAP_S = 0.35
HOLD_AFTER_GROUP_S = 0.15     # keep a group up through short pauses (never over the next group)
POP_MS = 90
SRT_MAX_CHARS = 42
SRT_GAP_S = 0.6
LAST_GROUP_HOLD_S = 0.4       # the final group stays up this long after its last word
PILL_FADE_MS = (250, 300)     # name pill fade in, fade out
TITLE_DELAY_S = 0.12          # the title line follows the name by this much
TITLE_BELOW_NAME_PX = 76

WEAK = {"a", "an", "the", "to", "of", "and", "with", "i", "at", "in", "on", "my", "that", "for", "but", "or",
        "is", "was", "you", "your", "from", "by", "as", "so", "it", "be"}


def _ts_ass(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ts_srt(t: float) -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _chars(g: list[dict]) -> int:
    return sum(len(x["w"]) for x in g) + len(g) - 1


def group_words(words: list[dict], max_words: int = MAX_WORDS, max_chars: int = MAX_CHARS,
                gap: float = GROUP_GAP_S) -> list[list[dict]]:
    groups, cur = [], []
    for w in words:
        if cur:
            chars = _chars(cur) + 1 + len(w["w"])
            if (len(cur) >= max_words or chars > max_chars or w.get("brk")
                    or w["s"] - cur[-1]["e"] > gap
                    or re.search(r"[.?!,;:]$", cur[-1]["w"])):
                groups.append(cur)
                cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    for _ in range(3):
        for i in range(len(groups) - 1):
            g, nx = groups[i], groups[i + 1]
            last = re.sub(r"[^a-z']", "", g[-1]["w"].lower())
            if (len(g) > 1 and last in WEAK and not re.search(r"[.?!,;:]$", g[-1]["w"]) and not nx[0].get("brk")
                    and len(nx) < max_words + 1 and _chars(nx) + 1 + len(g[-1]["w"]) <= max_chars):
                nx.insert(0, g.pop())
        groups = [g for g in groups if g]
    i = 0
    while i < len(groups) - 1:
        g, nx = groups[i], groups[i + 1]
        if (len(g) == 1 and not re.search(r"[.?!,;:]$", g[0]["w"])
                and len(nx) + 1 <= max_words + 1 and _chars(nx) + 1 + len(g[0]["w"]) <= max_chars):
            groups[i + 1] = g + nx
            groups.pop(i)
            continue
        i += 1
    return groups


def _ass_text(t: str) -> str:
    """Caption text can't carry ASS override braces or line breaks."""
    return t.replace("{", "").replace("}", "").replace("\\", "")


def build_ass(words: list[dict], W: int, H: int, y_pos: int, font: str = "Inter", size: int = 100,
              hi: str = "&H004DD8FF", name_pill: tuple | None = None) -> str:
    """hi is the ASS colour (&H00BBGGRR) of the spoken word. name_pill = (text, title, t0, t1, x, y) or None."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font} ExtraBold,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,8,4,5,60,60,0,1
Style: LTName,Inter SemiBold,56,&H00FFFFFF,&H00FFFFFF,&H4D000000,&H4D000000,0,0,0,0,100,100,1,0,3,16,0,4,0,0,0,1
Style: LTTitle,Inter Medium,36,&H00FFFFFF,&H00FFFFFF,&H4D000000,&H4D000000,0,0,0,0,100,100,0,0,3,12,0,4,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    x = W // 2
    groups = group_words(words)
    for gi, g in enumerate(groups):
        g_end = g[-1]["e"]
        nxt = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else g_end + LAST_GROUP_HOLD_S
        g_end = min(max(g_end, g[-1]["e"] + HOLD_AFTER_GROUP_S), nxt)
        for wi, w in enumerate(g):
            s = w["s"] if wi else g[0]["s"]
            e = g[wi + 1]["s"] if wi + 1 < len(g) else g_end
            if e <= s:
                continue
            parts = []
            for k, ww in enumerate(g):
                txt = _ass_text(ww["w"])
                parts.append(f"{{\\c{hi}}}{txt}{{\\c&H00FFFFFF&}}" if k == wi else txt)
            pop = f"{{\\fscx88\\fscy88\\t(0,{POP_MS},\\fscx100\\fscy100)}}" if wi == 0 else ""
            ev.append(f"Dialogue: 1,{_ts_ass(s)},{_ts_ass(e)},Cap,,0,0,0,,{{\\pos({x},{y_pos})}}{pop}{' '.join(parts)}")
    if name_pill:
        text, title, t0, t1, lx, ly = name_pill
        fade = f"{{\\fad({PILL_FADE_MS[0]},{PILL_FADE_MS[1]})}}"
        ev.append(f"Dialogue: 2,{_ts_ass(t0)},{_ts_ass(t1)},LTName,,0,0,0,,{fade}{{\\pos({lx},{ly})}}{_ass_text(text)}")
        if title:
            ev.append(f"Dialogue: 2,{_ts_ass(t0 + TITLE_DELAY_S)},{_ts_ass(t1)},LTTitle,,0,0,0,,{fade}{{\\pos({lx},{ly + TITLE_BELOW_NAME_PX})}}{_ass_text(title)}")
    return head + "\n".join(ev) + "\n"


def build_srt(words: list[dict], max_chars: int = SRT_MAX_CHARS, gap: float = SRT_GAP_S) -> str:
    lines, cur = [], []
    for w in words:
        if cur and (sum(len(x["w"]) + 1 for x in cur) + len(w["w"]) > max_chars
                    or w["s"] - cur[-1]["e"] > gap or re.search(r"[.?!]$", cur[-1]["w"])):
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    out = []
    for i, ln in enumerate(lines, 1):
        out.append(f"{i}\n{_ts_srt(ln[0]['s'])} --> {_ts_srt(ln[-1]['e'])}\n{' '.join(x['w'] for x in ln)}\n")
    return "\n".join(out)
