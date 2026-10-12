---
name: video-dailies
description: Reviews the takes from a directed shoot. Inventories every clip, builds contact sheets, flags wind, clipping and silent mics, reads spoken slates, checks framing against the shot list, proposes the best take per shot with the actor, writes a reshoot list, and hands off to video-production for the edit. Use after filming - when someone says "review my takes", "check my footage from the shoot", or brings back clips from a shoot planned with the video-director skill.
---

# Video Dailies: what came back from the shoot

Part of the `video-director` plugin. The plan these takes are checked against (script, shot list, call sheet)
is in `<project>/director/`. If there's no plan, load the `video-director` skill first. Dailies without a shot
list can still flag sound and framing problems, but they can't say which take is best for what.

Script: `${CLAUDE_SKILL_DIR}/dailies.py`. It needs only ffmpeg. The slate read is optional and uses the video
toolkit's whisper when it's installed. If ffmpeg is missing, hand off to the `video-setup` skill
(`video-production` plugin). Never ask the person to run a command.

## 1. Get the clips onto this Mac

- **AirDrop** from the phone to Downloads, or to a folder they name. **Import from a camera app or cable.** Or
  the upload folder chosen at intake.
- **Wait for synced folders to finish downloading** before running. A clip still streaming from Drive or
  iCloud reads as broken.
- Copy nothing into the plugin folder. The project folder is where the clips and results live.

## 2. Run it

```bash
python3 "${CLAUDE_SKILL_DIR}/dailies.py" --check
python3 "${CLAUDE_SKILL_DIR}/dailies.py" "<project folder>" "<clip or folder>" ["<clip or folder>" ...]
```

It writes `<project>/dailies/`:
- `inventory.json`: fixed technical fields, audio flags, slate read and sheet path per clip;
- `sheets/`: contact sheets;
- `listen/`: 10 s samples of flagged clips.

**It refuses to write into a synced folder or a code repository**, because the sheets are stills of people and
places. Pass `--allow-synced` only if the person says yes. It keeps no location or device tags from the files.
It takes roughly 15 s per minute of footage. Run it in the background for a big shoot and wait for it to finish.

## 3. Review

Open every contact sheet with the Read tool and check each clip against its shot in the shot list:

| Check | Look for |
|---|---|
| Right shot | the slate (inventory `slate`: READ or UNCERTAIN), the place, the size |
| Eye height | eyes on the top third, the same height as the neighbouring shots it cuts with |
| Size change | differs clearly from the shots either side |
| Direction | exits right, enters left; the same all the way through |
| Title space | clear sky or space where the title goes on the opening wide |
| Clearance | face and key action out of the bottom caption band and the right-hand icon column |
| Separation | the actor stands out from the background; no bright object on the shoulder |
| Continuity | same outfit, glasses, hat and hair between shots that cut together |
| Empty frames | the walk-outs have a second or two of empty frame after exit |

For a transition moment, pull denser frames rather than guessing from 1 fps:

```bash
ffmpeg -v error -ss <t> -t 2 -i "file:<clip>" -vf "fps=8,scale=180:-2,tile=8x2" "<project>/dailies/zoom_<n>.jpg"
```

**Sound:**
- **A wind flag is an indicator, not a verdict.** It uses the same bands, pause-only measurement and 6 dB
  threshold as `video-production`'s `measure_audio.py`. On two real outdoor takes it agreed with that script to
  within 0.4 dB. Music or traffic can also trip it.
- **Have the person listen** to the sample in `listen/` before any take is rejected for wind.
- Clipping and a silent channel are reliable: a mic that wasn't paired, or one that was too close.

**What you can't judge from stills:** performance, focus hunting, a wobble or a blink between frames. Propose
the best take for each shot, but **the actor watches your pick on their phone** and confirms or swaps it.

## 4. The take log and the reshoot list

Write `<project>/dailies/takelog.md`:

| Shot | Clip | Take | Verdict | Why | In / out (s) |
|---|---|---|---|---|---|

Verdict is one of BEST, BACKUP, NG (no good, with the reason), or RESHOOT.

Then give a reshoot list, if there is one: each shot, what to change (one note per shot), and whether it can
be done at the same place and time of day.

**Show the take review as a page before asking the actor to confirm any pick** (`video-director`'s
`PRESENTATION.md`, "Dailies"): one card per shot with its stills, the pick and why, then the reshoot list. Write
it to `dailies/` and open it in their browser. It holds stills of them and their places, so publish it as a
hosted page only if they agree. In chat: one line, where the page is, and one question.

## 5. Handoff to the edit

When every shot has a confirmed take:
- **Sound, words and captions:** load the `video-production` plugin's `video-producer` skill in the same
  project folder. Its `init_project.py` takes the chosen clips as sources, and it leaves `director/` and
  `dailies/` alone.
- **Say plainly what isn't built yet.** Assembling a directed shoot is the v2 extension: picking the slated
  take per shot, sky titles, voiceover over B-roll, and held empty frames between walk-outs. The take log and
  shot list are exactly what an editor, or that future version, needs. Don't present a manual improvisation as
  the finished edit.
