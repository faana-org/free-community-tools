# Shoot plan: shot list and call sheet

The script says what's said. The shoot plan says where the actor stands, how they get there, and how each shot
hands over to the next. Craft rules are cited from `craft.md` by section.

## 1. Design the shots

For every script line, choose four things:

1. **Size.** Match it to intensity (craft §4): wide or long to set the scene, mid as home, mid close-up for the
   key point, and close-up rarely. **The size changes at every cut.**
2. **Place.** Use 2–5 places in a 2-minute piece, near each other. Each place is a set-up the actor can reach
   in a minute. Reuse a place for the return at the end: a loop, or a walk to the lens.
3. **Transition out and in** (craft §7). Use the same walk direction all the way through (exit right, enter
   left). Plan one in-camera opener or reveal per video, not five.
4. **Movement.** Say whether the actor walks in, sits, leans or turns. A few paces only, starting just outside
   the frame so the walk is already natural.

**Default shape for about 2 minutes** (adapt freely):

| Shots | What happens | Transition |
|---|---|---|
| Setup ×1–2 | Clean wide with sky or space for the title; the actor enters or leans in for the hook line | lean out or walk out right |
| Problem ×2 | A new place: enter left, a line, exit right; then a walk toward the lens ending mid close-up | walk-out, then head turn |
| Payoff ×3–6 | Sit into frame (cut on landing); a closer set-up from the same side for the main point; voiceover over B-roll of the action to do today; look up to the lens for the key line | sit, match on action, voiceover, look-up |
| Payoff, the ask ×1–2 | Walk from wide into a close shot with the CTA, hold the gaze about 2 s, walk out to an empty frame | walk-out, loop |

**Cutdown map.** Mark the 4–6 shots that make a 40–60 s version on their own: hook, one Problem line, the key
Payoff line, the action and the ask. Every script line should appear in the master or the cutdown, or be
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
  - **HDR off.** On an iPhone, turn off Settings → Camera → Record Video → HDR Video before the shoot. The edit
    pipeline (`video-production`) accepts SDR portrait footage only, and `dailies.py` flags HDR clips.
  - No mic: get one before the shoot if possible; if not, shoot close and sheltered.
  - No tripod: a wall, a rock or a bag. Say how to steady it and how to frame it.
  - Apple Watch: use its camera app as a monitor and shutter.
- **Body.** Altitude, heat and cold shorten walks and energy. Put the hardest shots first (craft §10, §11).
- **The actor's words.** They aren't crew. Every film term on the call sheet and shot list is explained where
  it first appears, every instruction says what to do and why, and the sheet carries "Words on this sheet"
  (§4, SKILL.md "Show it, then ask").
- **People and privacy.** Busy places mean short sections, minimal kit and lots of B-roll (craft §11). Don't film
  identifiable strangers as B-roll without thinking about consent.

## 3. The slate protocol

Before every take, the actor looks at the lens and says **"Shot <n>, take <m>"**, pauses a second, then goes.
`video-dailies` reads it (best-effort) and uses it to file takes. The actor should also:
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
Phone: back camera, 1x, 4K, HDR Video off (iPhone: Settings > Camera > Record Video). Tripod at eye height
       for mid shots; waist height, tilted up slightly, for wides with sky for the title.
       Why: the main lens is the sharpest and doesn't bend faces; the edit can't use HDR clips.
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

Places
- <Place A> (<what's there>): shots 1, 3, 9
- <Place B>: shot 2
- …

Shots
1. <SIZE: plain meaning, height> · <action> · "<line>"      e.g. MID: waist up, lens at eye height
2. …

B-roll (5–10 s each; extra clips with no talking, shown while your voice carries on): <list>

What I'll deliver: <master and cutdown>, captions, no jump cuts.
Send the clips: <AirDrop / the folder the person chose>.

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

| # | Part | Place | Size / height | Action and transition in → out | Line (label) | Cutdown |
|---|---|---|---|---|---|---|

Keep the labels from the script so approvals travel with the lines. Show it as a page before the shoot-plan
gate (`PRESENTATION.md`, "Shot list").
