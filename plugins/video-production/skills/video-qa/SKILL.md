---
name: video-qa
description: Verification battery for finished social videos - re-transcribes each render and compares it with the intended words, checks captions never cover the speaker's mouth, confirms frame-exact sync, loudness, true peak and stripped location metadata, measures shake reduction, and reviews a frame after every cut. Use before showing or delivering any rendered video, after any pipeline change, or when asked whether a video is correct.
---

# Video QA: prove it, don't assume it

Part of the `video-producer` family. Toolkit folder: `${CLAUDE_SKILL_DIR}/../video-producer/`; every command below uses the full path. Run from the project folder.

A render that finishes proves nothing. Look at the picture, measure the sound, re-read the words. Report only
what you measured, and say plainly what you didn't check.

## One command for the batch

```bash
python3 "${CLAUDE_SKILL_DIR}/../video-producer/final_pass.py"            # every spec: cut list, render, all checks, one table
python3 "${CLAUDE_SKILL_DIR}/../video-producer/final_pass.py" <spec> --shake    # one video, including the shake measurement
```

Renders run in parallel (`--jobs`, default a quarter of the CPU cores). It exits 0 only when every render and
check passes; logs are in `work/<name>/final_pass.log`. Run it in the background and wait for the completion
notice instead of polling.

## The battery (every file)

| Check | Script | Pass |
|---|---|---|
| Frame count | `final_pass.py` (render.py also refuses a mismatch) | frames = the cut list's total |
| Sync | `final_pass.py` | audio duration within one frame of the video |
| Loudness | `final_pass.py` | integrated −18 to −13 LUFS (expect about −16); true peak ≤ −1.0 dBTP (expect −1.7 to −1.9) |
| Location metadata | `final_pass.py` | no `location` tag in format or stream metadata |
| Words | `verify_words.py <name>` | match ratio ≥ 0.98 and **every** difference explained (below) |
| Mouth vs captions | `qa_mouth.py <name>` | 0 overlapping frames; any flag checked by eye |
| Shake | `shake_metric.py <name>` (after any stabilisation change) | output median below the source (the script's pass/fail); state the median and p90 reduction, and look at every cut it lists. On 4:5 and other tight framing the face fills the frame and the number is unreliable (a visually approved 4:5 long cut measured p90 worse than its source): watch it instead |
| Every cut | frame review (below) | framing consistent, face clear of captions, no frame edge visible, name pill legible |
| Legibility | full-size frames at the hook (t ≈ 1 s) and at the busiest background | captions readable |

## Frame review

Pull one frame just after each cut and look at every one yourself:

```bash
python3 - <<'EOF'
import json, math, subprocess
name = "<name>"
f = json.load(open(f"work/{name}/framing.json"))
t = 0.0
for i, c in enumerate(f["cuts"]):
    grab = t + min(0.5, c["frames"] / 60)          # inside this cut, past any fade-in
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{grab:.2f}", "-i", f["output"], "-frames:v", "1",
                    "-vf", "scale=360:-1", f"work/{name}/cut{i + 1:02d}.jpg"], check=True)
    t += c["frames"] / 30
n = len(f["cuts"])
cols = min(6, n)
rows = min(4, math.ceil(n / cols))                 # 24 cuts per sheet; more cuts make more sheets
subprocess.run(["ffmpeg", "-v", "error", "-y", "-start_number", "1", "-i", f"work/{name}/cut%02d.jpg",
                "-vf", f"tile={cols}x{rows}", f"work/{name}/cuts_sheet_%02d.jpg"], check=True)
EOF
```

Then read every contact sheet image. A frame grabbed at exactly 0 s shows fade-ins as transparent; the script
uses +0.5 s.

## Adjudicating flags

| Flag | Likely cause | How to tell |
|---|---|---|
| A word missing from the re-transcription | clipped cut, a swallowed word, or a transcriber miss | 10 ms energy around the word in `clean/edit/<src>.wav`: does its onset start before the cut's `in`? If the word was far quieter than its neighbours even in the raw audio, it was swallowed, not clipped |
| The last sentence missing | whisper drops speech at the end of a file | transcribe the last 5 s alone, padded with 2 s of silence |
| A substituted word ("a" ↔ "the") | transcriber variance | compare with the corrections `video-audio` already verified; score candidates if it's new |
| "Thank you." at the end, doubled words | whisper artefacts on silence and line breaks | confirm no audio could produce it (the previous word ended seconds earlier) |
| Mouth overlap on 1–2 frames | head dip, or the lip estimate on a turned head | look at the frame: caption over chin or beard with the mouth visible is acceptable, report it; over the lips, fix the framing |
| Mouth overlap on many consecutive frames | tight framing or a lagging face path | fix in `video-finishing` and re-render |
| Shake not reduced | tracking failures, exhausted margin | `camtrack.py` failure count; eased-frame counts in the render log |
| Loudness out of range | an unusually quiet or dynamic take | measure the cleaned source; don't change the chain for one file without listening samples |

## Tool hygiene

- **You can't hear.** For any audio judgement, give the person short before/after samples to listen to.
- **Burned-in captions fool motion tracking;** `shake_metric.py` masks the caption and name-pill band for you.
- **Browser previews:** if screenshots don't change after scrolling, the automation window may be hidden; check
  layout by script and media with `ffmpeg -v error -i file -f null -`, and say playback wasn't watched.

## Reporting

Use `PRESENTATION.md` in `video-producer`. Per file: length, frames, word match, mouth overlaps with the closest
clearance, LUFS, true peak, location metadata, shake reduction if measured. Then every flag and its explanation,
the limits ("smoother, not tripod-still"), and anything not verified. If a measurement contradicts something
you said earlier, correct it explicitly.
