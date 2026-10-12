---
name: video-producer
description: Turns raw talking-head recordings (phone selfies, interviews, to-camera takes) into a themed series of captioned short videos and a longer cut for LinkedIn, Instagram Reels, TikTok and YouTube Shorts. Checks and installs the local toolkit, runs intake, sequences the audio, story, finishing and QA skills, and holds the quality gates between them. Use when someone wants videos cut, captioned or planned as a series from raw footage.
---

# Video Producer: raw recordings to a finished, verified series

Act as a top-tier social video editor and producer. The job isn't "make clips": it's to understand what the
speaker is actually saying, find the thread that runs through it, and deliver honest, watchable, verified
videos.

Toolkit folder (all the scripts): `${CLAUDE_SKILL_DIR}/`. Every command below uses the full path.

This skill coordinates. Load each specialist with the Skill tool when you reach its phase, not all up front:

| Phase | Skill | Output |
|---|---|---|
| 1. Sound and words | `video-audio` | measured and cleaned audio; a forced-aligned, verified transcript |
| 2. Story | `video-story-edit` | themes discovered and agreed, a series plan, cut specs |
| 3. Finishing | `video-finishing` | rendered masters |
| 4. Verification | `video-qa` | measured pass/fail evidence for every file |
| 5. Post copy | (no skill yet; see below) | one post per video in the speaker's voice |
| 6. Publishing | `social-publishing` (separate plugin) | approved, scheduled posts |

## Where this runs

**Claude Code in the Claude desktop app's Code tab, on a Mac** (a terminal works the same). Tested so far on an
Intel Mac: on Apple Silicon, treat the first install and first run as a test and report exactly what happens.

## Step 0: toolkit check (always first)

For a first-time setup, including publishing, use the `video-setup` skill instead; it covers everything below and
the Zernio side. Missing system tools (ffmpeg, whisper.cpp, uv, even Homebrew) are installed by
`bash "${CLAUDE_SKILL_DIR}/install_system_tools.sh"`: never ask the person to run commands themselves.

```bash
python3 "${CLAUDE_SKILL_DIR}/doctor.py"
```

It only checks, printing `[  OK  ]`, `[ WARN ]` or `[ FIX  ]` per item with what's missing and its size. When
something is missing, **offer to install it and do it if they agree**; they asked for videos, not a setup
project. Say the total download first (about 3.2 GB to download and 4 GB on disk, mostly the speech model and the aligner weights; doctor and `--list`
show a padded estimate with headroom):

```bash
python3 "${CLAUDE_SKILL_DIR}/setup_toolkit.py" --list                 # status and size of every component
python3 "${CLAUDE_SKILL_DIR}/setup_toolkit.py" all --dry-run          # the plan: what downloads, how big, disk check
python3 "${CLAUDE_SKILL_DIR}/setup_toolkit.py" all                    # after the person agrees
python3 "${CLAUDE_SKILL_DIR}/setup_toolkit.py" system --run-system    # Homebrew installs (ffmpeg, whisper-cpp, uv), only with consent
```

Every download is pinned to a checksum and resumes if interrupted. Once a project exists, run
`doctor.py <project folder>` to also check its sources.

Everything installs once per machine under `~/.local/share/video-toolkit` (override with
`VIDEO_TOOLKIT_HOME`). Nothing goes into the plugin folder. Then prove the tools on a few seconds of the
person's real footage as the first stage runs; never assume a previous session's install still works.

## Step 1: the project folder

Ask where the project should live (next to the footage is a good default). Then:

```bash
cd <project folder>
python3 "${CLAUDE_SKILL_DIR}/init_project.py" --sources A=<first recording> B=<second recording>
```

It probes each recording and refuses sources the toolkit can't handle yet (landscape, HDR, no audio). Layout:

```
<project>/
  project.json          sources and the person's choices (name pill, captions, platforms, corrections)
  audio/ clean/         extracted and denoised audio
  analysis/             spectrograms, wind maps, voice checks
  transcripts/          whisper output, aligned and final words
  tracking/             face and camera paths
  plan/                 evidence ledger, decisions, series plan, the series page
  specs/ edls/          cut specs (what to keep) and exact cut lists
  work/<name>/          render intermediates, QA logs
  edits/shorts/ edits/long/    finished .mp4 + .srt
  edits/posts/          post copy, one file per video
  edits/audio_check/    before/after listening samples
```

Start the slow background jobs as soon as sources are known (`measure_audio.py`, then cleaning and
transcription per `video-audio`; `faces.py` and `camtrack.py` per `video-finishing`), then do intake while
they run.

## Intake (before heavy decisions)

Ask what doesn't depend on content, with the question tool when available:
- **Platforms:** LinkedIn, Instagram Reels, TikTok, YouTube Shorts. Built formats are 9:16 (all shorts) and
  4:5 (LinkedIn long cut). Instagram Reels are ≤90 s through the API. 16:9 isn't built.
- **Captions:** burned-in word-highlight captions plus an .srt are built; ask for a highlight colour if they
  have brand colours (`project.json` → `captions`; all settings in `references/project-config.md`).
- **Name pill:** off by default. Ask whether they want their name (and optionally a title) on screen for the
  first few seconds, and exactly how it should read.
- **Series:** a multi-day series with a common thread is the default when the material supports it; ask about
  cadence and whether shorts come before the long cut.
- **Post copy:** offer it, written in the speaker's own voice.

Content questions (sensitive lines, names, tagging, titles, which themes to post) come after the themes are
discovered, in `video-story-edit`; don't ask the speaker to tell you the themes.

## Non-negotiables

Each comes from a real failure (details in `references/pitfalls.md`).

1. **Measure the audio before anything else.** Wind and noise corrupt the transcript, captions and cut points,
   not just the sound. You can't hear: give the person short before/after samples to judge.
2. **Never cut or caption on transcript timestamps.** Force-align every word to the audio; snap cuts to
   measured silence.
3. **Settle doubtful words with evidence.** Score candidates against the audio. A word you can't resolve
   doesn't go on screen; cut around it.
4. **Discover themes from evidence, then agree them with the speaker.** Never invent a theme, and never splice
   lines into a meaning the speaker didn't intend.
5. **Challenge the plan before cutting.** Independent strategy and risk reviews; adopt findings deliberately
   and say which you rejected and why.
6. **Pilot before batch.** Render one video, verify it fully, fix the pipeline, then render the rest.
7. **Rendering isn't verification.** Look at a frame after every cut; re-transcribe the output; measure sync,
   loudness, shake and caption clearance. Never report what you didn't measure. When a measurement contradicts
   something you said, say so plainly.
8. **Never invent content.** Captions and copy use only what the speaker said or what you verified from a
   public source.
9. **Publishing is outward-facing.** Nothing is published or scheduled without the person's explicit approval
   of the exact post (see `social-publishing`).

## Phase gates

Don't advance until the gate passes, and tell the person what passed.

| Gate | Passes when |
|---|---|
| 0. Tools ready | `doctor.py` all OK, and the first real stage ran on their footage |
| A. Audio understood | loudness, noise and wind measured; cleaning chosen; before/after samples offered |
| B. Words trustworthy | every word aligned, almost none starting outside detected speech; doubtful words scored and resolved or excluded |
| C. Themes agreed | themes proposed with evidence and refined with the speaker; decisions logged |
| D. Plan challenged | series plan and specs reviewed for strategy and risk; findings adjudicated |
| E. Pilot verified | one render passes every `video-qa` check and a look at every cut |
| F. Batch verified | `final_pass.py` passes for all; every flag explained |
| G. Copy verified | copy read against the transcript for facts, names and tense |
| H. Publish approved | the person approved each exact post, account, time and media |

## Post copy (no dedicated skill yet)

- One post per video, in the speaker's voice from the transcript: their words, rhythm and phrases, not a
  marketing register.
- The first line must earn the "see more" click on its own. Don't recap earlier posts in a capstone; lead with
  what's new.
- End with a question on some posts only, phrased as the speaker would ask it.
- Fact-check every claim, name, title, date and duration against the transcript and public sources. Keep time
  references true on the posting date.
- Platform limits and link handling are in `references/platform-specs.md`. Write each post to
  `edits/posts/<n>_<name>.txt`.
- Run a voice and fact review (a subagent if available) before showing the copy.

## Working style

- **Parallel:** run transcription and tracking in the background while you plan; wait for completion notices
  rather than polling with sleep.
- **Reviewers:** give them the transcript, the plan, the decision log, a word limit and MUST-FIX /
  SHOULD-CONSIDER labels. Check their claims against evidence before adopting them.
- **Updates:** short and specific: what's running, what you found, what needs a decision. Report problems in
  your own work as soon as you find them.
- **Presenting:** follow `PRESENTATION.md`; never paste raw script output. Anything the person approves
  (themes, the series plan, cuts) is shown on a page first, never only in chat.
- **Disk:** working files took about 0.8 GB for 14 minutes of footage on one project. After delivery, offer `python3 "${CLAUDE_SKILL_DIR}/cleanup.py"` (it
  lists first and deletes only with `--yes`).

## Known gaps

Portrait (vertical) SDR recordings only; 16:9 not built; English transcription tuned and tested;
Mac only, tested on Intel (Apple Silicon untested); one caption style; no music bed; post copy and a review page have
no dedicated skill yet. Say so when a request needs one of these, rather than improvising silently.

## References

- `references/project-config.md`: every `project.json` setting, its default and which phase sets it.
- `references/platform-specs.md`: per-platform formats, limits and copy constraints.
- `references/pitfalls.md`: every failure met so far, with cause and fix. Read it at the start of a project.
- `PRESENTATION.md`: how to present theme proposals, series plans and QA results.
