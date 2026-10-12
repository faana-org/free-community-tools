---
name: video-finishing
description: Renders talking-head edits into finished social videos - camera-shake stabilisation, face and mouth-aware framing and punch-ins, bold animated word-highlight captions, a light grade, a voice chain with loudness normalisation, silence-snapped cuts, frame-exact sync and clean 9:16 and 4:5 exports. Use when rendering cut specs, tuning how finished videos look or sound, or debugging jitter, caption placement, sync or loudness problems.
---

# Video Finishing: track → cut → stabilise → frame → caption → grade → finish sound → export

Part of the `video-producer` family. Toolkit folder: `${CLAUDE_SKILL_DIR}/../video-producer/`; every command below uses the full path. Run from the project folder; outputs go to the project's `edits/`, never the plugin directory.

Every number here was tuned and verified on real handheld footage and lives as a named constant in
`${CLAUDE_SKILL_DIR}/../video-producer/vcore.py`. Change one only with a measurement that shows the change is better.

## Inputs this phase needs

| Input | From | Check |
|---|---|---|
| `clean/edit/<src>.wav` | `video-audio` (clean_audio.py) | exists for every source in the specs |
| `transcripts/<src>.final.json` | `video-audio` (fix_words.py) | exists; the only word file cuts and captions may use |
| `tracking/<src>.faces.json` | `python3 "${CLAUDE_SKILL_DIR}/../video-producer/faces.py"` | a face in at least half the samples (refuses otherwise; `--accept` overrides) |
| `tracking/<src>.camera.json` | `python3 "${CLAUDE_SKILL_DIR}/../video-producer/camtrack.py"` | motion measured on at least 80% of frames (refuses otherwise; `--accept` overrides) |
| `specs/<name>.json` | `video-story-edit` | read back and agreed |
| fonts, face model, Python env | `setup_toolkit.py` | `doctor.py` all OK |

Start both trackers in the background as soon as sources are known; they don't depend on the audio work.
Measured on one project, on a laptop that was also rendering: about 20 s (faces) and 1 min (camera) per minute of footage.

```bash
python3 "${CLAUDE_SKILL_DIR}/../video-producer/faces.py"       # --src A for one source
python3 "${CLAUDE_SKILL_DIR}/../video-producer/camtrack.py"    # separate background job
```

## Pilot, then batch

Render one video, run the whole `video-qa` battery on it, fix anything in the pipeline, and only then render
the rest (`final_pass.py`). A defect found in the pilot is one fix; found after the batch, it's a re-render
of everything.

```bash
python3 "${CLAUDE_SKILL_DIR}/../video-producer/edl.py" <name>                  # cut list + read-back
python3 "${CLAUDE_SKILL_DIR}/../video-producer/render.py" <name> --preview     # fast encode to check cuts and framing
python3 "${CLAUDE_SKILL_DIR}/../video-producer/render.py" <name>               # master
```

`render.py` refuses (exit 2) when an input is missing and names the script that makes it. It verifies the
output frame count before reporting done.

## How a render works

```
per cut:  decode source at 30 fps ─► stabilise + crop/zoom as one affine warp (bicubic) ─► raw frames ─┐
audio:    each cut from the cleaned edit track, 12 ms in / 18 ms out fades ─► concat ─► voice chain ───┤
                                                                                                        ▼
          encode: grade + ASS captions (libass) + x264 + AAC, metadata stripped ─► edits/<kind>/<name>.mp4 + .srt
```

Intermediates go to `work/<name>/`: per-cut audio, `audio.wav`, `captions.ass`, `cap_words.json` and
`framing.json` (the zoom each cut actually used, read by the QA scripts).

## Cuts (`edl.py`)

- **Pauses** tightened to 0.50 s after `. ? !`, 0.35 s after `, ; :`, 0.25 s mid-phrase. Shorter natural gaps
  stay as they are. Slower speakers may need more; change the constants only after listening tests. A cut that
  would remove under 0.1 s (3 frames) of pause is skipped: it would only show as a jump.
- **Snap to silence:** starts move back to the last 40 ms of quiet (10 ms RMS below −62 dB on the cleaned
  track) within 0.35 s; ends move forward to 60 ms of quiet within 0.40 s. A cut never crosses into a word
  that isn't kept.
- **Framing changes only on beats:** at a clip start, or at least 3 s after the last change following
  punctuation, forced by 6 s. Framing alternates 1.00× / 1.12×; `punch` clips open at 1.22×. Changing zoom on
  every pause cut strobes.

## Stabilisation: follow the camera path, not the face

1. `camtrack.py`: corner features on one-third-size grey frames, LK optical flow, a RANSAC similarity per frame
   pair, accumulated into a camera path.
2. Each frame's motion is re-expressed as motion of the image **centre** before smoothing
   (`vnum.centre_path`). Motion measured at the origin but corrected about the centre leaves most shake in.
3. Correction = gaussian-smoothed path (σ 0.6 s) − raw path: handheld shake goes, intentional drift stays.
   Phone video has slightly irregular frame timing, so a seek can land a frame away from the frame the path was
   measured on, and the correction would then add shake. Each cut's first frames are matched against the path
   and any offset is corrected (reported in the render log and `framing.json`).
4. Each cut is planned before decoding: the crop is placed with a reserved margin (95th percentile of the
   correction + rotation × half-diagonal + 4 px); per frame, the largest correction strength that keeps frame
   edges out of the crop is found; that strength is a rolling minimum over ±8 frames smoothed by a gaussian that
   never exceeds the per-frame limit. Switching correction on and off frame by frame adds jitter.
5. One matrix per frame, crop × stabilise, warped once.

Measured on handheld selfie shorts: 28–49% less high-frequency shake at the median (`shake_metric.py`): smoother,
not tripod-still. Say so, with this video's own number.
Following a smoothed face path instead makes shake worse, because punch-ins magnify the shake it doesn't remove.

## Framing: face- and mouth-aware

**Face path:** YuNet at 10 fps, despiked with a rolling median, moved into stabilised coordinates, smoothed
(σ 0.8 s) so the crop drifts gently and never chases a nod.

| Format | Output | Base zoom | Face centre | Caption centre |
|---|---|---|---|---|
| 9x16 | 1080×1920 | 1.10 | 36% of height | y 1330 |
| 4x5 | 1080×1350 | 1.10 | 40% of height | y 1080 |

**Mouth clearance outranks everything else:**
- lower lip ≈ face box centre + 0.50 × box width (calibrated on landmarks: mouth corners sit at +0.41);
- a conservative lip path: rolling maximum over ±0.75 s, then a gaussian inside that window, so quick head dips
  don't reach the captions;
- the crop rises so the lip sits at least 60 px above the caption text; it may use the stabilisation margin to
  do so, and the correction eases off there.

**Zoom rules:** a punch-in may not make the face wider than 62% of the frame; the minimum zoom is whatever
makes mouth placement possible with the face in the middle 40% horizontally; hard cap 1.35× (upscaling shows
beyond that). Never zoom in to clear the chin: zooming enlarges the face and pushes the chin lower.

**Supported sources:** portrait (vertical) SDR recordings. `init_project.py` refuses landscape and HDR
(HLG/PQ) sources; tell the person how to re-export rather than rendering washed-out or badly cropped video.

## Captions (`captions.py`, rendered by libass)

- **Style:** Inter ExtraBold 100 px, white, 8 px black outline, shadow 4; the spoken word lights up in the
  highlight colour (default #FFD84D); each group pops in over 90 ms. Font, size and highlight colour come from
  `project.json` → `captions`.
- **Grouping:** 2–3 words and ≤16 characters (captions never wrap). Break at punctuation, pauses over 0.35 s
  and every cut. A trailing weak word ("to", "a", "and"…) moves to the next group when it fits (never across a
  cut). A lone word then merges forward when it fits, even across a cut or pause, so a group can reach 4 words
  and stay up through that pause; that was preferred to a single word flashing. Sentence case after `. ? !`.
- **Size and font:** mouth clearance scales with caption size (measured at 100 px). A different caption font
  needs its ExtraBold file in the toolkit fonts folder; `render.py` refuses rather than silently falling back.
- **Timing:** forced-aligned words only, remapped to the output timeline; a group holds through short pauses
  but never overlaps the next.
- **Name pill (optional, off by default):** Inter SemiBold 56 px on a translucent box, 72 px from the left,
  150 px above the caption centre, from 0.3 to 3.8 s. Set `project.json` → `name_pill` only after asking the
  person what, if anything, it should say. A spec's `lower_third` overrides it for one video.
- **Check legibility on real frames** before batch: bright sky, busy patterns, anything at the caption line.
  Grab frames at t ≥ 0.5 s; frame 0 shows fade-ins as transparent.
- **.srt:** lines ≤42 characters, broken at sentences and pauses over 0.6 s. For accessibility and platforms
  without burned-in captions; don't also upload it where captions are burned in, or they show twice.

## Grade

`eq=contrast=1.05:saturation=1.07:gamma=0.98` plus a slight warm colour balance (`vcore.GRADE`). Colour-match
takes only when the difference between takes is clearly visible on the face; small corrections read as
processed. (No colour-matching tool is built.)

## Voice chain and loudness

1. The cleaned edit track from `video-audio` (70 Hz high-pass + DeepFilterNet with a 30 dB limit).
2. EQ −1.5 dB at 180 Hz, +2 dB at 3.5 kHz; compressor −26 dB, 3:1, 8/160 ms, +4 dB makeup.
3. `loudnorm` I −15, TP −2.0, LRA 8. Finished shorts on one project measured −15.9 to −16.6 LUFS and −1.7 to −1.9 dBTP after AAC.
4. **Exact length:** the audio is trimmed to frames × 1600 samples (48 kHz / 30 fps). Never trim with `-t`
   after loudnorm (it shifts timestamps and drops the tail) and never mux with `-shortest` (it drops the final
   frame).
5. The last cut fades out 180 ms after its final word (≤350 ms), so the held ending is silent.

## Export

libx264 High, preset slow, CRF 17, yuv420p, BT.709 tags, 30 fps constant; AAC 192 kb/s 48 kHz; `+faststart`;
all metadata stripped (phone recordings carry GPS location). `--preview` uses veryfast / CRF 24 for checking only.

## When something looks wrong

| Symptom | Likely cause | Where to look |
|---|---|---|
| Captions over the mouth | head dip, turned head, tight framing | `qa_mouth.py` times → frames; `framing.json` zoom for that cut |
| Shake not reduced | tracking failures on dark or featureless shots | `camtrack.py` failure count; `shake_metric.py` |
| Zoom strobing | beats too frequent | the spec: clip boundaries inside a sentence |
| Audio and picture drift | a changed trim or mux flag | frame count vs audio duration (`final_pass.py`) |
| A word cut off | aligner boundary or a swallowed word | `verify_words.py`, then energy around that word in the cleaned track |
