# Concept: from sources to ideas to a labelled script

Craft rules are cited from `craft.md` by section.

## 1. What an idea is made of

Every idea answers four questions, and each answer points back to a source:

1. **What's the one thought?** One idea per video, said in 40–60 seconds. A longer piece, made only when the
   person asks for one, is still one idea.
2. **What does the viewer get?** The outcome, in the viewer's own terms (craft §9).
3. **What can they do today?** One small action, doable in minutes, that makes the idea real.
4. **What should they do next?** A soft CTA that matches the person's goal from intake (craft §13).

Where ideas come from:
- The person's own phrases that already carry a point of view. These are the best raw material.
- The problems their customers name, in the customers' words, when the sources hold them.
- The moments that bring people to their offer: "when X happens, people call us".
- Their method or framework, with one piece of it per video.
- A story only they can tell, which only they can supply (a `TRUE?` line, confirmed).

Avoid:
- Generic advice any creator could post. The test: could anyone else have made this video?
- Framing the viewer as the problem (craft §9). Invite them alongside instead.
- A lecture. Stand beside the viewer and share what works, rather than telling them what they should do.

## 2. The idea list

Give 4–8 ideas. For each:

```
<n>. <working title>
   Source: <doc/page, section> - "<the line it grows from>"
   Hook: "<spoken hook>"  ·  Title: <≤5 WORDS>
   The idea: <one sentence>
   Today: <one thing to do today>   [NEW unless it's in the source]
   CTA: <soft CTA>
   Why it fits them: <one line>
```

Recommend one idea and say why (usually the clearest next step plus the strongest source).

## 3. The script: shot units in four parts

**By default a video is one thought in 40–60 seconds**, about 105–150 words (`script-voice.md` §1). Its lines
go in four parts, in this order (craft §8):

| Part | How many shots | Job |
|---|---|---|
| Hook | 1 | The promise, or the viewer's own moment, said plainly. The title sits in the sky. |
| Intrigue | 1–2 | Why it matters, or what it costs to miss it. **Never the answer:** if the line after the hook gives it away, the viewer has what they came for and scrolls on. |
| Delivery | 2–4 | The one idea in short beats, and one thing to do today, often over B-roll. |
| Exit | 1–2 | One short ending: a question, a small thing to try today, or a soft follow ask. Walk to the lens, hold the look, walk out. |

**Longer pieces only when the person asks for one.** For about 2 minutes, chain 3–5 hook, intrigue and delivery
units around the same one idea (about 12–16 shots), end on one exit, and cut a 40–60 s version from the same
footage.

**Line rules.** How the lines sound is in `script-voice.md`: read it first, pick one of its templates, and
write each line by following a named pattern from it.
- One or two sentences per shot. Short words, plain language and no jargon: it's heard once, at speed, often
  with the sound off.
- Read every line aloud. Rewrite anything that sounds written rather than said.
- **No AI tells:** no em dashes in spoken lines, no "not X, it's Y" as a habit, no "quietly", no triads for
  rhythm.
- **No stock creator openers** ("here's the thing", "let's dive in"). Say the person's own version of the
  point instead. Plain phrases like "try this" are fine when they're how the person would say it.
- Keep the person's own phrasing. If a source line works as speech, use it `VERBATIM`.

**Script file format** (`director/script_<slug>.md`):

```
# <title> - script v<n>
Idea: <one sentence>  ·  Length: ~<s> s (~<words> words)  ·  Template: <script-voice.md §9 A, B or C>
Sources: <list from sources.md>

| # | Part | Line | Label | Source / note | Pattern (script-voice.md) |
|---|---|---|---|---|---|
| 1 | Hook | "…" | ADAPTED | brief.md: goal; source X §2 "…" | §2 name who it's for |
| 2 | Intrigue | "Because …" | TRUE? | actor to confirm | §2 invite, then "because"; holds back the answer |
| 5 | Delivery | "Grab a pen and …" | NEW | exercise written by the director | §3 show it while you say it |

Approvals: line 2 confirmed true by <name> on <date>; line 5 approved as written / changed to "…"
```

## 4. Before showing the script

- **Label audit.** For every `VERBATIM` and `ADAPTED` line, open the source and find the words. If you can't
  find them, the label is wrong: change it to `NEW`. This check is the whole point.
- **Say it in chat.** "Lines 5 and 7 are mine, not from your material. Here's why I wrote them. Keep, change or
  cut?"
- **Voice check.** Run `script-voice.md` §8 ("What it is NOT") on every line, and make sure each line names the
  pattern it follows. Then: would this person say it this way? If a sample of their speech exists (a recording
  or a transcript), compare against it.
- **Timing.** At about 2.4 words a second (~140 a minute) plus walks and holds, the script should land within
  10% of the target: 40–60 s unless the person asked for longer.
- **Build the page.** The script goes on its page (SKILL.md, "Show it, then ask"; layout in `PRESENTATION.md`)
  before you ask for anything. Each new version updates the same page.
