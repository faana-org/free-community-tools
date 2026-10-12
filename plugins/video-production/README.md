# video-production

Turn raw talking-head recordings into a themed series of captioned short videos and a longer cut, from a
conversation.

> Here are two recordings from my phone. Make a series of LinkedIn shorts and one longer video.

Claude measures and cleans the audio, builds a word-accurate transcript, finds the themes and the thread that
runs through what you said and shows you the evidence, shapes the series with you, then renders stabilised,
face-framed videos with animated captions and checks every file before handing it over.

**Operator guide:** [video-production-runbook.md](docs/video-production-runbook.md)

## Skills

| Skill | What it does |
|---|---|
| `video-setup` | Gets a computer ready: system tools, the video toolkit, and the Zernio account, connected accounts and API key for publishing. |
| `video-producer` | Coordinates the whole job: toolkit check and install, project setup, intake, phase gates. Holds the scripts. |
| `video-audio` | Measures loudness and wind, cleans the voice, transcribes, aligns every word to the audio, settles doubtful words with evidence. |
| `video-story-edit` | Discovers themes with quoted evidence, refines them with the speaker, orders the series, writes cut specs, has the plan reviewed. |
| `video-finishing` | Cuts on silence, stabilises, frames around the face and mouth, captions, grades, finishes the sound, exports. |
| `video-qa` | Re-transcribes each render, checks captions never cover the mouth, sync, loudness, location metadata and shake. |

Publishing lives in the separate `social-publishing` plugin.

## Before the first run

Follow [docs/SETUP.md](../../docs/SETUP.md): two messages pasted into the Code tab of the Claude desktop app, and
Claude installs everything, Homebrew included. You only type your Mac password when macOS asks, sign in to
Zernio in your browser, and copy your Zernio API key.

- **System tools:** ffmpeg with caption support (`ffmpeg-full` on macOS), whisper.cpp and uv.
- **Video toolkit:** about **3.2 GB** to download and **4 GB** on disk, installed once per computer under
  `~/.local/share/video-toolkit`: the speech model, DeepFilterNet, two Python environments (OpenCV; PyTorch for word
  alignment), the Inter font and a face-detection model.

Working files take space too: about **0.8 GB** for 14 minutes of footage on the project it was built on. Claude
offers to clean them up afterwards.

## Where it runs

| | Works? |
|---|---|
| Claude desktop app, Code tab (on a Mac) | Yes. Tested on an Intel Mac; Apple Silicon not yet tested |
| Claude Code in a terminal (Mac) | Yes |
| Chat tab, Cowork, claude.ai | No: they can't run the video tools on your Mac |

## Measured on real footage

- Word timing: forced alignment put words starting outside detected speech at under 1%, against 13–15% for
  the transcriber's own timings.
- Stabilisation: 28–49% less high-frequency shake (median, per video) on the handheld selfie shorts measured, with
  `shake_metric.py`: smoother, not tripod-still.
- These scripts were generalised from a hand-tuned project and checked against it byte for byte: all cut lists,
  face and camera tracks, and a finished short's audio, captions and decoded picture matched exactly. Changes
  since then are deliberate fixes: masters no longer lose their final frame; stabilisation no longer lands one
  frame late on some cuts (on one short, 6 of 18 cuts; median shake reduction went from 40% to 49%); and pause
  cuts under 0.1 s, which only showed as jumps, are skipped (2 of the 6 original cut lists had one).
- A fresh Claude Code session given only these plugins and two short real recordings found the themes itself with
  quoted evidence, refined them with the speaker, had the plan reviewed and delivered a pilot that passed QA. It
  also exposed a gap now closed: it quoted a line about a person in its theme proposal as the opposite of what
  the audio supports, because the opposite reading was never scored.

## Known gaps

- Portrait (vertical) SDR recordings only; landscape and HDR are refused with an explanation.
- 9:16 and 4:5 only; 16:9 for YouTube long-form isn't built.
- English is the tuned and tested language.
- One caption style; no music bed.
- No dedicated skills yet for post copy or a review web page; the coordinator gives interim guidance.
