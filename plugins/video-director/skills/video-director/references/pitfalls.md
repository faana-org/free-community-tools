# Pitfalls

Each entry is a real failure or a near miss, with its fix. Read this at the start of every project.

## Content

- **An invented exercise presented as the person's material.** A director wrote an exercise into a script and
  flagged it only in passing. The actor had to ask whether it came from their documents.
  **Fix:** label every line (concept.md §3). Say in chat which lines are yours. `NEW` lines need an explicit
  OK.
- **Invented specifics in the craft.** An early draft of the playbook stated made-up numbers as if they were
  established practice ("8–12 steps", "record 3 s"). A review of every number in it caught them.
  **Fix:** the playbook gives a reason with every rule and a number only where one is real. When coaching,
  don't add a number it doesn't give. Say "a few paces", not a count you made up.
- **Personal claims drift.** "I've opened two practices" turns into "every practice I've opened" once it's rewritten.
  **Fix:** personal lines are `TRUE?` until the actor confirms the exact wording.
- **Confidential material in a script.** Source documents often hold pricing, finances and names.
  **Fix:** they stay out unless the person says otherwise (SKILL.md, stage 2).
- **Scripts in the right order that sound like an advert or a machine.** With the four-part order and no
  examples, drafts came out with abstract triads, the answer in line 2, two thoughts in one video, lines that
  didn't lead into each other, and the maker's "I built…" as the point. They were rejected one after another.
  **Fix:** read `script-voice.md` first, write each line by following a named pattern, run its "What it is
  NOT" check, and show each line's pattern on the page.
- **Problem-first hooks.** Scripts drafted from strategy documents open on pain.
  **Fix:** the craft asks for a positive outcome. Rewrite the hook as a promise and move the pain to the intrigue.

## Presenting

- **Approval asked for a script the actor never saw laid out.** Only script v1 was shown in full. Later
  versions and the shoot plan weren't, and the actor was asked to approve them anyway.
  **Fix:** every script, shot list and call sheet goes on a page before any approval (SKILL.md, "Show it, then
  ask"). Each revision updates the same page with its version and what changed. The chat message is one line,
  the link and the question.
- **Crew jargon on the call sheet.** A call sheet said "your stone" and never said what it was or what it was
  for. The actor isn't crew.
  **Fix:** plain words (SKILL.md, "Show it, then ask"): explain every film term where it first appears, say what
  to do and why, give shot sizes their meaning ("Mid: waist up"), and give the sheet a "Words on this sheet"
  list.

## Shooting

- **Wind at altitude or on the coast** ruins more takes than anything else.
  **Fix:** windscreen, back to the wind, a 10 s test with headphones before shot 1, and dailies' wind flag
  confirmed by listening.
- **Coaching that contradicts the playbook.** A director asked for a long walk into frame; the playbook says
  a few paces, starting just outside the frame.
  **Fix:** check craft.md before giving a specific instruction.
- **Changing layers mid-sequence** breaks every cut between those shots.
  **Fix:** wardrobe continuity goes on the call sheet.
- **A Mac-less shoot.** Clips can't come back until later, so on-set direction is impossible.
  **Fix:** the call sheet carries the direction, and dailies happen at base.

## Tools

- **`ffprobe` broken on one Mac.** `dailies.py` falls back to `ffmpeg -i`.
- **Phones write GPS and device tags into video files.** The dailies inventory keeps a fixed list of technical
  fields only.
- **Contact sheets are stills of people and places.** Never write them into a synced folder or a code
  repository. `dailies.py` refuses both unless told otherwise.
