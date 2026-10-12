# Shoot plan: shot list and call sheet

The script says what's said. The shoot plan says where the actor stands, how they get there, and how each shot
hands over to the next. Craft rules are cited from `craft.md` by section.

## 1. Design the shots

For every script line, choose five things:

1. **Size.** Match it to intensity (craft §4): wide or long to set the scene, mid as home, mid close-up for the
   key point, and close-up rarely. **The size changes at every cut.**
2. **Place.** Use 2–5 places in a 2-minute piece, near each other. Each place is a set-up the actor can reach
   in a minute. Reuse a place for the return at the end: a loop, or a walk to the lens. **Every place says
   where it is**, so the person can find it on site: a landmark ("the bench by the boathouse"), or, when the
   spot is theirs to choose, what to look for ("your pick: any spot with the water behind you, away from the
   path"). A bare description ("gold cottonwoods") isn't a place. Every shot card names its place in those
   words, not only a letter code.
3. **Transition out and in** (craft §7). Use the same walk direction all the way through (exit right, enter
   left). Plan one in-camera opener or reveal per video, not five.
4. **Movement.** Say whether the actor walks in, sits, leans or turns. A few paces only, starting just outside
   the frame so the walk is already natural.
5. **Line length.** One or two sentences per shot (concept.md §3). If a shot has more than two, split it, or
   mark a pause between sentences on the card ("pause, 1 s") so the edit has a clean place to cut.

**Shape for a piece of about 2 minutes** (made only when asked for; adapt freely). A 40–60 s short, the
default, uses the same rows with fewer shots: hook 1, intrigue 1–2, delivery 2–4, exit 1–2 (concept.md §3).

| Shots | What happens | Transition |
|---|---|---|
| Hook ×1–2 | Clean wide with sky or space for the title; the actor enters or leans in for the hook line | lean out or walk out right |
| Intrigue ×2 | A new place: enter left, a line, exit right; then a walk toward the lens ending mid close-up | walk-out, then head turn |
| Delivery ×3–6 | Sit into frame (cut on landing); a closer set-up from the same side for the main point; voiceover over B-roll of the action to do today; look up to the lens for the key line | sit, match on action, voiceover, look-up |
| Exit ×1–2 | Walk from wide into a close shot with the CTA, hold the gaze about 2 s, walk out to an empty frame | walk-out, loop |

**Cutdown map.** Mark the 4–6 shots that make a 40–60 s version on their own: hook, one intrigue line, the key
delivery line, the action and the ask. Every script line should appear in the master or the cutdown, or be
deliberately dropped.

## 2. Adapt to the real conditions

Use what intake gave you. Ask about anything missing.

- **Light.** Find the time of day when the light suits the place.
  - The actor never faces a low sun: light across or behind them (craft §5).
  - With a place and date, work out sunrise and sunset by web search or from the person. Don't guess.
  - Easiest outdoors: roughly the hour after sunrise or the hour before sunset (craft §5).
  - Indoors: a window to the side.
- **Weather and wind.** Check the forecast by web search for the named place, or ask. Wind is the most common
  reason a take is lost. Plan windscreen, back to the wind, and sheltered alternatives.
- **Wardrobe.** Bright and saturated, contrasting with the dominant colours of the place (not green in a
  forest, not tan in a desert).
  - The same outfit, glasses and hat for every shot that cuts together.
  - Change layers only between set-ups that never cut into each other.
- **Gear.**
  - **Every phone step is for their phone.** Intake asks the model, and an iPhone and a Pixel (or another
    Android) put things in different places. Give a menu path only when you're sure it's right for that model.
    Otherwise say what to achieve and how to check it, in plain words; never invent a menu path. No camera-app
    jargon ("AE/AF LOCK"): say what to do.
  - **HDR off.** The edit pipeline (`video-production`) accepts SDR portrait footage only, and `dailies.py`
    flags HDR clips. iPhone: Settings → Camera → Record Video → HDR Video, off. Other phones: in the camera
    app's video settings, turn off anything called HDR or 10-bit; to check, record a 5 s test and send it to
    the Mac before the shoot day, so dailies can read it.
  - **Focus and exposure on automatic** when they're filming alone: the phone finds their face by itself
    (craft §3). Nothing in the plan asks them to tap the screen.
  - No mic: get one before the shoot if possible; if not, shoot close and sheltered.
  - No tripod: a wall, a rock or a bag. Say how to steady it and how to frame it.
  - A watch that works the camera (Apple Watch's camera remote with an iPhone): use it as a monitor and
    shutter. For other phones, ask whether their watch can do the same; don't assume.
- **Body.** Altitude, heat and cold shorten walks and energy. Put the hardest shots first (craft §10, §11).
- **The actor's words.** They aren't crew. Every film term on the call sheet and shot list is explained where
  it first appears, every instruction says what to do and why, and the sheet carries "Words on this sheet"
  (§4, SKILL.md "Show it, then ask").
- **People and privacy.** Busy places mean short sections, minimal kit and lots of B-roll (craft §11). Don't film
  identifiable strangers as B-roll without thinking about consent.

## 3. The slate protocol

Before every take, the actor looks at the lens and says **"Shot <n>, take <m>"**, pauses a second, then goes.
`video-dailies` reads it (best-effort) and uses it to file takes. **For a walk-in, the slate is said in frame**;
then they step out to the start mark, wait a beat and walk in (the beat of empty frame is where the edit
joins the shot). Write it on the card in those words. The actor should also:
- Record 2–3 takes of each shot. The last good take is usually the one (craft §12).
- Let the camera roll for 2 seconds after walking out of frame, so the edit has the empty frame for the
  transition.
- Never delete a take on the phone. Everything comes back for dailies.

## 4. Call sheet template (`director/callsheet_<slug>.md`)

Write it for someone standing in a field with a phone in one hand. Keep it short, readable on a phone, in plain
words, and in shot order. This file is the source; the person reads and approves the page built from it
(`PRESENTATION.md`, "Call sheet").

```
# <Title> · call sheet
Where: <place>  ·  When: <date, time window and why>  ·  Length: ~<m:ss> + ~<s> s cutdown

Wear: <colour and what to avoid>. Same outfit for every shot.
       Why: you stand out from the place, and shots that follow each other match.
Sound: mic on the chest, windscreen (the fluffy cover) on, back to the wind. Test 10 s and listen before shot 1.
       Why: wind is what ruins most takes, and your body blocks it.
Phone: back camera, 1x, 4K, HDR off (<the steps for their phone model, or what to achieve and how to
       check it: §2>). Tripod at eye height for mid shots; waist height, tilted up slightly, for wides with
       sky for the title. Leave focus and brightness on automatic: the phone finds your face.
       Why: the main lens is the sharpest and doesn't bend faces; the edit can't use HDR clips; and you
       can't reach the screen from in front of the camera.
Marks: a mark is any small thing on the ground that shows where to stop: a stone, a stick, a leaf, tape.
       Set it: stand where the shot wants you, put the mark at your toes, record a few seconds, check your
       eyes sit about a third of the way down the screen. If not, move the tripod (or the mark) until they
       do, then leave the mark alone for every take. A walk-in gets a second mark where the walk starts.
       Glance at the mark before the take, not during it.
       Why: you land in the same spot every take, so you stay sharp, framed and the same size, and any take
       cuts with any other.
Every take: "Shot <n>, take <m>", pause, go. 2–3 takes each. Roll 2 s after you leave frame.
       Why: the spoken label (the slate) tells the edit which take is which; the empty frame after you leave
       is where the next shot joins on.

Places (each one findable on site)
- <Place A> · <where it is: a landmark, or "your pick: any spot with <X> behind you, away from <Y>"> · shots 1, 3, 9
- <Place B> · <where it is> · shot 2
- …

Shots
1. <Place, in words> · <SIZE: plain meaning, height> · <action> · "<line>"   e.g. MID: waist up, lens at eye height
   Walk-in: "Say the slate in frame, step out to your start mark, wait a beat, then walk in."
2. …

B-roll (5–10 s each; extra clips with no talking, shown while your voice carries on): <list>

What I'll deliver: <master and cutdown>, captions, no jump cuts.
Send the clips: <AirDrop (iPhone only) / the folder the person chose>.

Words on this sheet (only the ones it uses, one plain line each)
- Take: one go at a shot, from "Shot 3, take 2" to stopping.
- Mark: the small thing on the ground that shows where you stop (see Marks).
- Wide: the place, you small in it. Long: head to toe. Mid: waist up. Mid close-up: chest up. Close-up: face.
- Empty frame: the picture with nobody in it, before you walk in or after you walk out.
- Windscreen: the fluffy cover on the mic; it stops wind roaring.
- Cutdown: the short version (40–60 s) made from the same takes.
- …
```

## 5. Shot list format (`director/shotlist_<slug>.md`)

| # | Part | Place (in words, where it is) | Size / height | Action and transition in → out | Line (label) | Cutdown |
|---|---|---|---|---|---|---|

Keep the labels from the script so approvals travel with the lines. Show it as a page before the shoot-plan
gate (`PRESENTATION.md`, "Shot list").

## 6. Check the plan before you show it

Read every shot as the person will do it: alone, with one phone on the tripod filming them, unless intake says
someone will be behind the camera. Fix every failure before building the page.

- **One phone can't do two jobs.** The phone on the tripod is filming, so it can't also be in their hand or be
  shown on camera, and from the back camera they can't read from it. "Sit, phone in hand, look at the phone"
  needs a second phone or a rewrite.
- **They can't see or touch the screen** while they stand in front of the back camera. Nothing asks them to tap,
  check or change anything on it during a shot. Focus and exposure stay on automatic (the phone finds the face)
  unless someone else is behind the camera. Framing is checked before the take, from behind the phone or on a
  watch that shows the camera.
- **Anything that must appear on a screen is recorded separately**, after the shoot (a screen recording on
  their phone or computer, with the steps for that device), and the edit cuts to it. Say it in plain words on
  the card: "The video cuts away to a recording of your plan here. You'll record that afterwards." Never
  unexplained shorthand like "plays over your screen recording".
- **Walk-ins:** the card says "Say the slate in frame, step out to your start mark, wait a beat, then walk in" (§3).
- **Every place can be found on site**, and every shot card names its place in words (§1).
- **One or two sentences per shot**, or a marked pause between them (§1).
- **Every phone step is for their phone** (§2).
