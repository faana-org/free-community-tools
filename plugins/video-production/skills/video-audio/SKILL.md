---
name: video-audio
description: Audio measurement, cleanup and trustworthy word timing for talking-head recordings. Measures loudness and noise, detects wind with spectrograms, removes it with DeepFilterNet, transcribes with whisper.cpp, force-aligns every word to the audio, checks timings against detected voice, and settles doubtful words by scoring candidates against the waveform. Use at the start of any edit of raw recordings, or whenever captions, cut points or a transcript must be accurate.
---

# Video Audio: measure → clean → transcribe → align → check → settle doubtful words

Part of the `video-producer` family. Toolkit folder: `${CLAUDE_SKILL_DIR}/../video-producer/`; every command below uses the full path. Run from the project folder (`init_project.py` first).

**You can't hear.** Every audio judgement is a measurement, and anything an ear must judge goes to the person as
a short before/after sample.

## 1. Measure first (gate: never transcribe before this)

```bash
python3 "${CLAUDE_SKILL_DIR}/../video-producer/measure_audio.py"             # every source; --src B for one
```

For each source it writes `audio/<src>.48k.wav`, a spectrogram and a wind map, and prints loudness, loudness
range, true peak, the low-band (20–120 Hz) versus voice-band (250–4000 Hz) difference, the same in pauses, and
the worst 10 s windows.

**Look at the spectrogram yourself** (`analysis/<src>.spectrogram.png`):
- voice: harmonic stripes, roughly 150–700 Hz plus formants;
- wind: fluctuating broadband energy below ~120 Hz that continues between words;
- hum, insects: thin horizontal lines.

Wind is present when pauses carry low-band energy **6 dB or more** above the voice band. Tell the person what
you found: loudness, noise character, worst time ranges.

## 2. Clean

Wind or broadband noise (the usual case outdoors):

```bash
python3 "${CLAUDE_SKILL_DIR}/../video-producer/clean_audio.py"                                         # both passes, every source
python3 "${CLAUDE_SKILL_DIR}/../video-producer/measure_audio.py" --compare                             # did cleaning work without hurting the voice?
python3 "${CLAUDE_SKILL_DIR}/../video-producer/clean_audio.py" --src B --samples-only --samples 20@95  # before/after pair from the worst window
```

- A 70 Hz high-pass, then DeepFilterNet twice: `clean/asr/<src>.wav` with no attenuation limit, for
  transcription only; `clean/edit/<src>.wav` with a 30 dB limit, the voice track every edit uses (a natural
  floor keeps pauses from sounding dead). Both stay sample-aligned with the source.
- Roughly 4 min per pass per 7 min of footage on a laptop CPU (one project): start it in the background.
- **Check it didn't over-process.** `measure_audio.py --compare` reports, per source, how far wind in pauses
  dropped (flagged under 25 dB) and how much the loudest speech lost (flagged over 3 dB), and writes
  `analysis/<src>.clean_check.json`. Also look at harmonics in a spectrogram of the cleaned track: "speech
  frames" picked by energy include wind and give false alarms.
- **Listening samples:** `--samples SECONDS@START` from the worst window writes loudness-matched MP3s
  (`<src>_<start>s_<length>s_before.mp3` / `_after.mp3`) to `edits/audio_check/`. Ask the person to listen and to
  say if the cleaned voice sounds watery or robotic.
- **If it sounds processed:** re-clean only the edit track more gently, then make new samples and re-check. A
  *lower* limit is gentler (default 30 dB; 20 dB left 21 dB of pause reduction on one test excerpt):
  `clean_audio.py --src B --edit-only --edit-limit-db 20`. The value used is saved in `clean/edit/<src>.json`.
  Word timings come from the transcription track, so no re-alignment is needed; rebuild any existing cut lists
  with `edl.py`, because cuts snap to silence measured on the edit track.
- Steady hum only, no wind: a notch filter may be enough; check the spectrogram afterwards.

## 3. Transcribe the cleaned audio

```bash
python3 "${CLAUDE_SKILL_DIR}/../video-producer/transcribe.py" --src A --threads 4    # one background job per source, at the same time;
python3 "${CLAUDE_SKILL_DIR}/../video-producer/transcribe.py" --src B --threads 4    # threads per job ≈ cores ÷ jobs
```

- whisper.cpp large-v3-turbo on `clean/asr/`, with no text context (`-mc 0`, prevents repetition loops) and
  non-speech tokens suppressed. Sources in one call run one after another, so start one job per source. Measured
  on one laptop CPU: about 20 min each for two takes of about 7 min run at once.
- `--words-only` rebuilds the word list from existing whisper output; `--resample-only` re-creates
  `transcripts/<src>.16k.wav` (needed by alignment and phrase scoring) without running whisper.
- Writes the whisper JSON and .srt plus `transcripts/<src>.words.json`. Its word times are guesses: **never cut
  or caption on them.**
- Expect whisper to drop fillers, smooth over restarts and invent "Thank you." on trailing silence.
- While it runs, start the trackers from `video-finishing`; they don't depend on the audio.

## 4. Force-align every word (gate: before any cutting or captions)

```bash
python3 "${CLAUDE_SKILL_DIR}/../video-producer/align.py"                     # runs itself in the PyTorch environment
python3 "${CLAUDE_SKILL_DIR}/../video-producer/vad_check.py" --stage words   # whisper's timings, for comparison
python3 "${CLAUDE_SKILL_DIR}/../video-producer/vad_check.py"                 # the aligned timings
```

- torchaudio's MMS_FA aligner keeps whisper's text (case and punctuation, for captions) and replaces its
  timings with a forced alignment against the waveform. Flexible "star" tokens at the ends and at gaps absorb
  untranscribed fillers, so neighbouring words don't stretch.
- `vad_check.py` compares timings with detected voice:
  - **words starting in silence:** should be about 0 after alignment (whisper's own timings put 13–15% there on
    real footage; alignment 0–0.5%);
  - **voice with no words:** re-transcribe those snippets. Filler or noise is fine; missing content means the
    word list needs fixing before re-aligning;
  - clusters of **low alignment scores** mark restarts or doubtful text: read those passages.

## 5. Settle doubtful words with evidence

Doubt arises from low scores, words that don't make sense in context, names, and anything whisper and a
re-listen of the raw audio disagree on. **Every line that says something about a person or organisation is
doubtful by default**, however confident the transcript looks: it gets scored before it is quoted in a theme
proposal or captioned.

**A verdict is only as good as its candidates.** "Clear" against a reading nobody would confuse proves nothing.
Build each case's candidates from:
- the transcript's reading;
- what whisper hears when you re-transcribe just that span from the raw source audio and from the edit track;
- **readings that flip the meaning**: "a responsible" / "irresponsible", "a moral" / "amoral", can / can't,
  is / isn't, would / wouldn't, a "not" added or dropped, always / never;
- small function-word changes that change sense: "a" / "the", "in" / "and", "for" / "four", "then" / "than";
- for names, the spellings the person might use.

Write whole-span candidates that differ only where the doubt is, and score them:

```json
[{"src": "A", "start": 64.0, "end": 69.5,
  "candidates": ["the first reading of the span", "the second reading of the span"]}]
```

```bash
python3 "${CLAUDE_SKILL_DIR}/../video-producer/score_phrases.py" --cases plan/doubts.json
```

| Margin between best and runner-up | Verdict |
|---|---|
| more than ~4 nats | clear |
| 2–4 | lean |
| under 2 | ambiguous: ask the person, or cut around it |

The script also adds meaning-flipped variants of your best candidate on its own (marked `[auto]`). If one fits
the audio as well or better, it prints **MEANING CHECK** and exits 1: don't caption that line as heard; ask the
person or leave the line out of every edit.

Rules:
- **Meaning outranks the score.** When the audio favours a reading that could misrepresent the speaker or
  someone else, keep the line out of every edit rather than caption either reading.
- Names and unusual words that score as ambiguous: ask the person how they're spelled and said.
- A word you can't resolve never goes on screen.

## 6. Write the final words

Record each correction in `project.json` with its evidence, and the caption spellings the person confirmed:

```json
"corrections": [{"src": "A", "t": 66.1, "old": "their", "new": "there", "evidence": "CTC best by 4.7"}],
"casing": {"acme": "ACME"},
"phrases": [["open", "source", "Open-", "Source"]]
```

```bash
python3 "${CLAUDE_SKILL_DIR}/../video-producer/fix_words.py"
python3 "${CLAUDE_SKILL_DIR}/../video-producer/vad_check.py"                 # re-check the final words
```

`"new": ""` deletes a word the transcriber invented (a phantom "Because", a doubled phrase); give the evidence
like any other correction, and never hand-edit the word files. `fix_words.py` writes
`transcripts/<src>.final.json`, the only word file cutting and captions may use. A
correction that matches no word or several refuses the whole run (exit 2) and writes nothing; fix `t` or `old`.

## Handing over to the next phase

- `clean/edit/<src>.wav`: the voice track for edits. `clean/asr/<src>.wav`: transcription only.
- `transcripts/<src>.final.json`: aligned, corrected words.
- A short findings note for the person: noise found, cleaning applied, before/after numbers, corrections with
  evidence, lines excluded, open questions (spellings, names).
