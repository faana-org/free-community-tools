---
name: video-story-edit
description: Editorial judgement for turning raw talking-head recordings into a themed series of short videos and a longer cut. Reads the verified transcript, discovers the themes and the common thread on its own with quoted evidence, proposes them, refines them with the speaker, orders the series, picks hooks that work on muted autoplay, designs splices across takes, writes cut specs and has the plan challenged before anything is rendered. Use after the transcript is verified, or when someone wants to plan, re-plan or re-cut a video series.
---

# Video Story Edit: discover → propose → refine → plan → cut specs → challenge

Part of the `video-producer` family. Input: the verified word files from `video-audio`
(`transcripts/<src>.final.json`). Output: an agreed series plan and one cut spec per video in `specs/`.

Toolkit folder: `${CLAUDE_SKILL_DIR}/../video-producer/`; every command below uses the full path. Run every command from
the project folder; never write into the plugin directory.

**You find the themes. The speaker decides which ones are true to them.** Never start by asking someone what
their videos are about: people rarely remember everything they said, and the strongest material is often
something they said in passing. Do the listening first, bring evidence, then shape it together.

**Themes come only from this footage.** Nothing in this skill is a suggested topic. Every theme, title, hook
and series name must trace to words this speaker said in these recordings.

## 1. Listen to everything first

Read every take end to end with timestamps, not a summary. Print the words readably:

```bash
python3 - <<'EOF'
import json
for src in json.load(open("project.json"))["sources"]:
    words = json.load(open(f"transcripts/{src}.final.json"))
    line, start = [], None
    for w in words:
        start = w["s"] if start is None else start
        line.append(w["w"])
        if w["w"][-1] in ".?!" or len(line) > 40:
            print(f"{src} {int(start // 60)}:{start % 60:04.1f}  {' '.join(line)}")
            line, start = [], None
    if line:
        print(f"{src} {int(start // 60)}:{start % 60:04.1f}  {' '.join(line)}")
EOF
```

Look at the picture too: one still every ~20 s shows setting, framing drift, expressions and moments
of real feeling (a laugh, a pause, a smile at the end).

```bash
ffmpeg -v error -i <source.mp4> -vf "fps=1/20,scale=270:-1,tile=7x3" analysis/<src>.contact_%02d.jpg   # one sheet per 7 min
```

Build an **evidence ledger** as you read (`plan/ledger.md`, in the project folder). For each passage worth
keeping, note:
- source and time range;
- the idea in one line, in neutral words;
- the best verbatim line(s): quotable, rhythmic, surprising, specific;
- signals of weight: the speaker returns to it, slows down, restarts to get it right, gets emotional,
  says "the thing is", "what I learned", "honestly";
- stories and turning points (before → event → after);
- named people, organisations and places;
- lines that could land badly (criticism of others, health, money, failures, private details);
- restarts, fillers and unfinished sentences that would need cutting.

Also note the speaker's **voice**: vocabulary, sentence rhythm, repeated phrases, humour, hedges. Post copy
reuses it.

## 2. Discover the themes (on your own)

Cluster the ledger into candidate themes. A candidate is a theme only if it passes every test:

| Test | Passes when |
|---|---|
| Said, not inferred | at least one line states the idea in the speaker's own words |
| Stands alone | a stranger could follow a short on it with no other video: hook, point, ending all exist in the footage |
| Enough material | about 25 s or more of usable speech after fillers and restarts are removed |
| Distinct | its best lines don't belong equally to another theme |
| Weight | the speaker gave it emphasis (see the signals above), not a passing mention |

Then find the **thread**: the one idea that connects the themes and makes them a series rather than a pile of
clips. Prefer a phrase the speaker actually says; it often becomes the series name. Offer two candidates
when there's no single obvious one. Check any series name for unintended idioms and meanings.

Also decide what's **not** a theme and why (too thin, repetitive, off-message, risky), and hold back at least
one strong passage for the long cut only, so the final video has a payoff nobody has seen yet.

Aim for 4–6 themes when the material supports it. Fewer strong videos beat more thin ones: if the footage
only supports two, say so.

## 3. Propose with evidence

Present the proposal before planning cuts, on the series page (format in `PRESENTATION.md`). For each theme:
- a working title in the speaker's words;
- the point in one sentence;
- two or three verbatim quotes with source and time (a quote that says something about a person or organisation
  must already have passed `video-audio` step 5, including its meaning check);
- the likely hook (the first line on screen) and ending;
- an estimated length;
- anything sensitive in it.

Then the thread candidates, what you left out and why, and the few questions only the speaker can answer.
Label your judgement as judgement ("this reads as the strongest opener because…"); never present an
interpretation as something they said.

## 4. Refine together

Ask with the question tool when the app has one; otherwise ask in one short, numbered message. Ask about:
- which themes feel true and which they'd rather not post;
- the goal and audience of the series (who should watch, what they should think or do after);
- lines that could land badly with their network, and named people: include, tag, or cut;
- spelling of names, titles and affiliations, and the words for any on-screen name;
- the series name.

Refining rules:
- When they merge, split, rename or drop a theme, re-check it against the ledger and say if the footage no
  longer supports it.
- When they want a theme the footage doesn't contain, say so plainly and suggest recording it. Never build
  it from lines that meant something else.
- Keep a short decision log in `plan/decisions.md` so later phases (and reviewers) don't relitigate choices.
- Stop refining when every video has an agreed point, hook and ending.

## 5. Order the series

- Open with the strongest, most candid hook, not chronological order.
- Put ownership before criticism: when a series includes both, the speaker owning their part first lets the
  criticism read as context rather than defensiveness.
- Alternate takes and moods so consecutive posts don't feel the same.
- End on resolution, not struggle: the series should land stronger than it started.
- Keep time references true on the posting date (relative dates like "recently" or "this month" go stale).
- Cadence: space posts a day or more apart, and check the publishing tool's best-time data when the account has
  history.

## 6. Build each video

| Element | Rule |
|---|---|
| Hook (0–3 s) | Must work on mute as captions. Put the tension on screen by ~3 s. Cut throat-clearing. When the natural opening is logistics, cold-open on a stronger later line, then return to context. |
| Middle | Keep the speaker's own logic. Remove fillers, restarts, repeated phrases and unfinished clauses. Where they started a sentence twice, join the better beginning to the better ending. |
| Splices | Join at sentence boundaries, with a framing change on the cut. Every splice must keep the original meaning. Never make someone say what they didn't mean. |
| Ending | End on the turn or the payoff line with a 0.9–1.2 s hold. Avoid ending on the problem. A warm closing line or a smile is a strong ending. |
| Length | Shorts 25–60 s for LinkedIn and TikTok; Instagram Reels ≤90 s through the API; YouTube Shorts ≤3 min. |
| Doubtful words | Anything `video-audio` couldn't resolve stays out of every edit. |

**The long cut.** Arc: problem → change → what was found → lesson → resolution, using the best version of each
beat from any take. Target 2–3 min unless asked otherwise; a reflective speaker's raw minutes shrink 2–3× once
tightened. Phrases cut from shorts for speed can come back when they add depth. Watch for repeated words across
new joins. Don't end on a joke after the emotional peak.

**Formats.** 9:16 for shorts everywhere; 4:5 for a LinkedIn long cut. A long cut over 90 s can't be a single
Instagram Reel: offer a two-part split or shorts only there. 16:9 isn't built yet (see `video-producer`).

## 7. Write cut specs

One JSON spec per video in `specs/<name>.json`. Specs name what to keep by its words, not timecodes:

```json
{"name": "short-01-working-title", "format": "9x16",
 "clips": [
   {"src": "B", "from": "first words of the hook", "near": 312, "to": "end of that sentence.", "punch": true},
   {"src": "A", "from": "a line from the other take", "near": 45, "to": "its last words.",
    "drop": ["um,", ["you know", 48.6]], "hold": 1.0}
 ],
 "retext": [["A", "words.", 58.4, "words,"]]}
```

| Field | Meaning |
|---|---|
| `from` / `to` | words matched ignoring case and punctuation; `near` (seconds) picks the closest occurrence |
| `drop` | fillers or restarts inside the clip; `[words, near_seconds]` targets one occurrence |
| `punch` | open this clip at the key-line zoom |
| `hold` | seconds of natural pause kept after the clip's last word |
| `retext` | caption-only text change, e.g. punctuation across a splice: `[src, word, near_seconds, new text]` |
| `lower_third` | optional `["Name", "Title"]` for this video only; otherwise project.json's name pill applies |

Build the cut list and **read the edit back as continuous text** before any render:

```bash
python3 "${CLAUDE_SKILL_DIR}/../video-producer/edl.py" short-01-working-title
```

Check the read-back for: punctuation across joins (fix with `retext`), duration in range, drops that removed
exactly the intended words, and meaning preserved at every splice. Exit 2 means a phrase wasn't found:
nothing was written; fix the spec's words or `near`.

## 8. Challenge the plan (gate: before any render)

Write `plan/series_plan.md`: goal and audience, the thread, each video's clips with times and text, the long-cut
arc, the schedule and open questions. Then get two independent reviews. When the app supports subagents, run
them in parallel, tell them not to edit files, give a ~600-word limit, MUST-FIX / SHOULD-CONSIDER labels, and
the decision log so they don't relitigate agreed choices:

1. **Editor-strategist:** the strongest and weakest videos, the opener and order, exact verbatim opening and
   closing lines per video, strong lines that were missed, the long-cut arc, the series name, the cadence.
2. **Risk reviewer:** how clients, investors, employers or peers could misread each video; splices that shift
   meaning; names and titles; privacy (location, third parties, family, health); oversharing.

Without subagents, do both passes yourself, one role at a time, and write each down before adjudicating.

**Before any render, check every video against this list** and fix or raise anything that fails:
- every splice keeps the meaning the words had where they were said: tone included (a joke or sarcasm isn't
  moved into a serious context), and no qualifier ("sometimes", "I think", "not") cut off a claim;
- no line the speaker marked sensitive, or you flagged as loaded, is in without their explicit agreement;
- third parties: every named or identifiable person, organisation and place was agreed to (include, tag or cut),
  and nothing reveals a private person's details, family, health, money or a home or live location;
- no doubtful word from `video-audio` is in any edit;
- nothing implies something the speaker didn't say, through juxtaposition, the on-screen name or a title.

**Adjudicate.** Verify every claim against the transcript and your measurements; reviewers miss corrections
already made. Adopt what's right, reject what's wrong with the reason, and tell the speaker what changed and
why. A change to something they approved (say, the number of videos) goes back to them; don't apply it silently.

**Show it, then ask.** Never ask the speaker to agree a plan or a cut they haven't seen in full. Put the series
plan and every video's read-back on the series page (`PRESENTATION.md`) first: the series table, then per video
the read-back text with each splice marked, what was removed, and the opening and closing lines with take and
time. Each revision updates the same page with its version and what changed. A table in chat isn't enough.

## Output

- `specs/*.json`, each read back and agreed on the series page.
- A series table: number, date, title, length, opening line, format.
- Per video: why it's in the series, the hook, what was removed, splices, corrections, and the ending, with
  source times. Post copy and any review page reuse this.

## Without the local toolkit

In a chat app with no local tools, this skill still works on a transcript the person uploads: discover, propose
and refine themes, order the series and draft specs. Say that timings from auto-generated transcripts are
approximate, and that cutting and rendering need Claude Code with the toolkit installed.
