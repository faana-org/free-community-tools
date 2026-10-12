# Pitfalls: real failures, with cause and fix

Each of these cost time or would have shipped a defect on real footage. Check this list at the start of every
project, and add to it when you meet a new one.

## Audio and transcript

| Pitfall | Cause | Fix |
|---|---|---|
| Wind noise missed until the viewer pointed it out | only loudness was measured, never noise | always make a spectrogram and compare low-band (20–120 Hz) energy in pauses with the voice band; 6 dB or more above = wind |
| The transcript looped the same phrase for 40 s | whisper hallucinates on wind | denoise first; transcribe the cleaned audio with `-mc 0 --suppress-nst` |
| A denoise metric said speech lost 8–20 dB | "speech frames" chosen by energy included loud wind | judge on spectrogram harmonics and on the loudest 20% of frames only (those lost 0.5–3 dB) |
| Captions and cuts would have drifted | whisper word times were off by a median 0.4 s, and by 2.6 s or more for one word in ten | forced alignment on the cleaned audio; words starting in silence dropped from 13–15% to under 1% |
| "Thank you." at the end of files | whisper's stock hallucination on trailing silence | drop it after a voice-activity check confirms no speech there |
| Ambiguous words that change meaning | transcription guesses | score candidate phrases against the audio; if still ambiguous, cut around the line |
| A "clear" verdict on a line about a person was wrong | the candidates never included the reading that flips the meaning (a negative prefix); the audio favoured it | score_phrases.py adds meaning-flipped variants itself and stops with MEANING CHECK; every line about a person is scored before it's quoted |
| Phantom words removed by hand-editing the word file | no way to delete a word through corrections; a later re-run would undo it | a correction with `"new": ""` and evidence; alignment skips it |
| A word looked clipped | the speaker swallowed it (far quieter than the next word even in the raw audio) | compare raw and cleaned band energy before blaming the cut |

## Story

| Pitfall | Cause | Fix |
|---|---|---|
| Series opened on logistics | narrative order instead of hook order | open with the most candid, highest-tension line; context comes later |
| Criticism felt defensive | it came before the speaker owned their part | put ownership first; criticism then reads as context |
| Two shorts carried the same line | themes weren't checked for overlap | each theme's best lines must belong to it alone |
| The capstone had nothing new | every strong passage went into shorts | hold back at least one strong passage for the long cut |
| Stale time references | a relative date ("recently", "this month") in a post published much later | check every time reference against the posting date |

## Cutting

| Pitfall | Cause | Fix |
|---|---|---|
| A cut landed 20 ms from a word onset | fixed padding around aligner times | snap starts back to 40 ms of quiet and ends forward to 60 ms of quiet, never crossing a word you aren't keeping |
| 26 zoom changes in 30 s (strobing) | zoom alternated on every pause cut | change framing only on beats: ≥3 s since the last change, after punctuation, forced at 6 s |
| Pauses too tight for a reflective speaker | a 0.2 s mid-phrase target | 0.50 s after `. ? !`, 0.35 s after commas, 0.25 s otherwise |
| A two-frame jump for no reason | a pause cut that removed only 0.05 s | skip pause cuts under 0.1 s (edl.py merges them, never across a dropped word) |
| The held ending picked up a breath or rustle | the hold ran into noise | fade out 180 ms after the last word |

## Picture

| Pitfall | Cause | Fix |
|---|---|---|
| "Face-lock stabilisation" made shake worse | following a smoothed face path removes only slow drift; punch-ins magnify the rest | real camera-path stabilisation from optical flow |
| Stabilisation weak, p90 worse | crop parked against the frame edge; correction switched on and off per frame | reserve a margin; plan correction strength per cut (rolling minimum, then smoothed) |
| Still weak after that | motion measured at the image origin but corrected about the centre (0.5° is a 5–13 px error) | convert per-frame motion to centre translation before accumulating |
| Suspected off-by-one frame | an unverified assumption | measured motion correlation at offsets −3…+3 first; it wasn't the cause on the cuts tested. Test before fixing |
| One cut shook as much as the source, later | phone video's irregular frame timing made a seek land one frame from the frame the camera path was measured on, so the correction was applied to the wrong frame | test every cut, not a sample: render.py matches each cut's first frames against the path and corrects the offset |
| Captions on the chin at 1.6× zoom | a "chin clearance" rule zoomed in, enlarging the face and pushing the chin down | raise the crop to keep the lower lip above the captions; cap punch-ins at 62% face width and 1.35× |
| The mouth rule used the wrong offset | guessed lip = box centre + 0.30 width | calibrated on landmarks: corners +0.41, lip +0.50 |
| Quick head dips still reached the captions | the smoothed face path lags | rolling-max lip envelope, then a gaussian inside that window |
| Output shake measured too low | burned-in captions gave the tracker static corners | mask the caption band when measuring output shake |

## Captions

| Pitfall | Cause | Fix |
|---|---|---|
| Name pill invisible on bright sky | small white text with no box | a translucent box behind it, larger text |
| Dangling words at a group's end | fixed three-word grouping | break at pauses and punctuation; move weak words forward; merge lone words forward |
| Wrong punctuation across a splice | source punctuation doesn't fit the new sentence | a caption-only `retext` in the spec; confirm it hit the intended word |

## Sync and export

| Pitfall | Cause | Fix |
|---|---|---|
| Audio 0.1 s short, video trimmed | `loudnorm` shifts timestamps and `-t` trims by timestamp | trim by sample count (frames × 1600); verify frame count and audio duration |
| Every master one frame short | `-shortest` at mux dropped the final frame | don't use `-shortest`; the audio is already exact |
| True peak −1.3 dBTP after AAC | limiter ceiling −1.5 before encoding | ceiling −2.0 → −1.7 to −1.9 after encoding |
| GPS location in delivered files | phone metadata copied through | `-map_metadata -1`; `final_pass.py` checks for location tags |

## Environment

| Pitfall | Cause | Fix |
|---|---|---|
| A shell loop ran once with all arguments | zsh doesn't word-split unquoted variables | run such loops under `bash -c` |
| Browser screenshots frozen, media won't load | the automation window was hidden | check layout by script and media with an ffmpeg decode; say playback wasn't watched |
| Long jobs blocked the conversation | foreground waits | run in the background and wait for the completion notice |

## Publishing

| Pitfall | Cause | Fix |
|---|---|---|
| A test would have used up a real post | a public test of a series post; LinkedIn rejects near-duplicates for weeks | state the consequence before any public test; offer a private or draft test first |
| Copy wrong at posting time | "part 3" before parts 1–2 exist; mentions sent as plain text | adjust per platform and show the change in the approval preview |
| Account state assumed from an earlier session | accounts were connected or removed in between | list accounts fresh and confirm handles with the person every time |
| A status watcher kept running after a post was deleted | it only stops on final states | stop it, then confirm the deletion |
