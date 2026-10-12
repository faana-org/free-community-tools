# Craft: the director's playbook for one person and a phone

This is the working grammar the director plans, coaches and reviews with. None of it is new. It is the visual
and editing language that film and television crews have used for decades (eye-lines, screen direction,
cutting on action, voiceover over cutaways, the news standup) scaled down to one person, one phone and no crew.

Every rule states **what to do** and **why**. Knowing the reason lets you bend a rule when the location
demands it without breaking what the rule protects. When a rule here doesn't give a number, don't invent one
while coaching: say "a few paces", not a count nobody measured.

Sections are cited elsewhere as craft §n.

---

## 1. Three ideas underneath everything

- **The viewer should never notice the technique.** Every choice below exists so attention stays on the
  person and what they're saying. A frame that's slightly off, a jump in eye height or a hiss in the audio
  pulls the viewer out, and on social video the next swipe is always one thumb away.
- **Every cut needs a reason.** Film grammar treats a cut as something the audience should feel was
  motivated: someone moved, looked, left or arrived. Unmotivated cuts read as mistakes being hidden.
- **The person only has to act.** On a broadcast crew, sound, picture, direction and producing are four jobs.
  Here they collapse into one person, so the plan has to carry the other three. Simple, repeatable set-ups
  leave their attention for the performance.

## 2. Sound

Audiences tolerate rough pictures far longer than rough sound. Sound is set up first and checked first.

- **Wear a lavalier (lav) mic on the chest**, about a hand's width below the chin, on the sternum line.
  *Why:* that position gets a consistent voice level whichever way the head turns, and it sits out of most
  frames.
- **Hide the cable and keep fabric off the capsule.** *Why:* clothing rubbing the mic is the most common lav
  noise, and no cleanup removes it cleanly.
- **Outdoors, always fit the furry windscreen** (a "dead cat"). *Why:* foam alone doesn't stop gusts. Wind
  rumble masks words, which then can't be transcribed or captioned accurately.
- **Put your back to the wind.** Your body is a windbreak. If it still gusts, tuck the mic just under the edge
  of a collar or placket so a layer of cloth shields it, and test again.
- **Record a 10-second test and listen before the first shot**, on headphones if there are any, or with the
  phone held to the ear. *Why:* a mic that didn't pair, a muted receiver or wind only shows up on playback, and
  finding out at dailies costs the whole shoot.
- **Let a second or two of silence roll at the start of each take.** *Why:* editors use that "room tone" to
  smooth cuts and noise removal uses it as a reference.
- **No mic yet?** Get one before anything else. Until then, shoot close, indoors or sheltered, with the phone's
  bottom edge facing the speaker.

## 3. Camera and phone settings

- **Back camera, main 1x lens.** *Why:* the main sensor is the best on the phone. The ultra-wide bends faces
  near the edge, and the telephoto compresses the picture into a distant, surveillance-like look. Use the front
  camera only when the person must read a prompter on the screen.
- **Record in 4K.** *Why:* a 4K vertical frame has twice the pixels in each direction of the 1080 x 1920
  delivery, so the edit can punch in up to 2x and still be sharp. That gives a second shot size from one take.
- **Turn HDR video off.** On an iPhone it's Settings → Camera → Record Video → HDR Video. *Why:* HDR files
  look washed out or blown out on many platforms and editors, and the `video-production` pipeline accepts SDR
  only. `dailies.py` flags HDR clips.
- **Keep the frame rate the same for every shot** (30 fps is the safe default). *Why:* mixing rates causes
  stutter or speed changes at the cuts.
- **Leave exposure and focus on automatic, then lock them** (on iPhone, press and hold on the face for AE/AF
  Lock) once the frame is set. *Why:* auto gets the starting point right without any thought, and the lock
  stops the picture pulsing when someone walks into frame or a cloud passes. Every bit of attention not spent
  on settings goes to the performance.
- **Lens at the eye height of the person in the shot**, standing or seated. *Why:* a camera below the eyes
  looks up and makes the speaker loom over the viewer. One above looks down and diminishes them. Eye level
  reads as a conversation between equals.
- **Conversational distance.** For the waist-up home shot on the 1x lens, that's roughly 1.5 to 2 m (5 to
  6 ft): where someone would stand if they were talking with you. *Why:* closer feels confrontational and
  distorts features, and further makes the voice and face feel remote. Move closer only for a moment that's
  meant to land.
- **Tripod and marks.** Lock the phone on a tripod. Mark the speaker's position on the ground: tape indoors,
  a stick or a bag outdoors. For a walk-in, mark both the start and the stop. Record a few seconds, check
  the frame, adjust the mark. *Why:* marks make takes repeatable, so any take of a shot cuts with any take of
  its neighbours.
- **A live monitor helps.** An Apple Watch camera app (or a second phone) shows the frame and can start
  recording from where the speaker stands.
- **Slate every take.** Look at the lens and say "Shot 3, take 2", pause, then begin. *Why:* the slate is how
  the edit, and `video-dailies`, files takes without guessing. It's the oldest habit in production for a
  reason.
- **Set-up should take minutes, not an hour**: mic, tripod at eye height, background chosen, marks set. If it
  takes longer, the plan is too complicated for one person.

## 4. Composition and shot size

- **Choose the background first, then place the person in it.** *Why:* the background is fixed and the person
  can move. Look for depth: a long view behind the speaker and, if possible, something in the near
  foreground. Don't stand them against a wall: flat backgrounds look like a passport photo, and shadows land on
  the wall right behind the head.
- **The place should be memorable.** *Why:* a varied, real setting makes each video distinct in a feed and
  gives the viewer something to recognise the person by.
- **Rule of thirds for the eyes.** Put the eyes on the upper third line of the frame in every shot, whatever
  its size. *Why:* that's where viewers expect eyes to be. If eye height jumps between cuts, the viewer's gaze
  has to hunt for the face each time, which is tiring even when nobody can say why.
- **Headroom.** Leave a little space above the head in mid shots; in tight shots the top of the head can be
  cropped, but never the chin. In vertical video, a wide opening shot needs generous space above the head for
  the title. *Why:* too much headroom makes a person look small and sinking, and too little looks cramped.
- **Lead room (looking room).** When the speaker looks or moves off-axis, leave more space on the side they
  face. *Why:* a frame that's tight on the side the person is looking toward feels claustrophobic and
  off-balance.
- **Caption-safe zones.** Keep faces, hands and key action out of the bottom band where captions and the
  platform's own text sit, and out of the right-hand column of platform icons. *Why:* anything there gets
  covered on the phone that plays it.
- **Separate the speaker from the background.** Squint at the frame: if the person blends into what's behind
  them, change the angle, the background or the clothes. Keep bright objects off the shoulders. *Why:* the eye
  goes to brightness and contrast first, so the person should stand out on both.
- **Wardrobe:** bright, saturated colours that contrast with the place (not green in a forest, not tan in a
  desert). Avoid fine stripes and small checks, which shimmer on phone sensors. *Why:* separation from the
  background and a clean picture.
- **Avoid the set-dressed look.** A branded backdrop, a staged office or anything that looks built for the
  camera signals "advert" before the speaker says a word. *Why:* social viewers lean in to people and scroll
  past ads.
- **Shot sizes**, in standard terms:

  | Size | What's in frame | Use it for |
  |---|---|---|
  | Wide (WS) | the place, the person small in it | establishing where we are; title space |
  | Full / long (LS) | head to toe | walks, entrances and exits |
  | Mid (MS) | waist up | the home shot for talking |
  | Mid close-up (MCU) | chest up | the line that matters |
  | Close-up (CU) | the face | rarely: it's intimate and loses its power if overused |

- **Match size to intensity.** Wider for context, tighter for the point. Finish nearer the lens than you
  started so the final line lands.
- **Direct address only in face-on shots.** When the person talks to the viewer, they face the lens. An
  angled or profile shot is a cutaway: thinking, looking out, working with their hands. *Why:* this is how
  broadcast cutaways work. Cutting to a side angle of someone still talking to a lens that's no longer there
  breaks the eye-line and confuses the viewer.
- **Keep the camera still.** Several locked-off frames at different sizes beat a wandering handheld camera.
  Allow one deliberate move, maybe two, in a longer piece. The simplest push-in is the speaker walking toward a
  fixed lens, or a punch-in done in the edit. Any move starts from stillness and ends in stillness. *Why:* a
  move that starts or stops mid-shot can't be cut cleanly.

## 5. Light

- **Think in three points, even outdoors.** The classic studio set-up has a key light (the main source, to one
  side of the camera), a fill (softening the shadow side) and a back light (separating hair and shoulders from
  the background). Outdoors the sun or sky is the key, a light wall, sand or a reflector is the fill, and a low
  sun behind the speaker is the back light. *Why:* naming the jobs tells you what's missing when a face looks
  flat or muddy.
- **Never have the speaker face straight into a low sun.** They squint and the light is harsh. Turn them until
  the light falls across the face at an angle, or turn further until the sun is behind them as a rim light and
  expose for the face.
- **Overcast is easy light.** Cloud is a giant soft box. On grey days, move around until the face looks right
  and shoot.
- **The hour after sunrise and the hour before sunset** are the easiest times outdoors: the sun is low, warm
  and soft. Look up the actual times for the place and date; don't guess.
- **Midday sun** puts dark shadows in the eye sockets. Find open shade (the shady side of a building, under a
  tree's edge) with the bright area in front of the speaker.
- **Indoors, a window to one side** is the key light. Turn off mixed overhead lights if they tint the skin.
  *Why:* light from two colour temperatures can't be corrected together.

## 6. Continuity and screen direction

- **Pick a direction for movement and keep it all the way through.** If the speaker exits frame right, they
  enter the next shot from frame left. *Why:* this is screen direction, and it's what tells viewers someone is
  travelling forward. Reversing it reads as doubling back.
- **Respect the 180° line.** Imagine a line through the speaker along their direction of travel or gaze, and
  keep the camera on one side of it between shots that cut together. *Why:* crossing the line flips left and
  right on screen, and the viewer loses their bearings.
- **Eye-lines match.** In shots that cut together, the speaker looks at the same height and the same side when
  they're not addressing the lens.
- **Wardrobe and props stay identical across shots that cut together**: the same layers, glasses, hat, hair,
  the same mug in the same hand. Change only between set-ups that never cut into each other. *Why:* continuity
  errors are the most visible mistakes in amateur video, and they can't be fixed in the edit.
- **Note where hands and feet are at the end of a take** if the next shot starts in the same position.

## 7. Transitions: giving every cut a reason

A plain same-size cut of the same person in the same place is a jump cut: the subject seems to teleport.
Broadcast editors avoid it with two habits: **change the shot size noticeably at every cut** (a clear step,
such as mid to mid close-up, plus a change of angle where possible), and **hide cuts inside motion**. The
techniques below build both into the shoot.

1. **Walk out, walk in** (a clean exit and entrance). The speaker leaves the frame completely, the camera holds
   the empty frame for a beat, and the next shot, often a new place, starts empty before they enter from the
   opposite side. *Why:* the empty frame is a natural punctuation mark, and the cut on it is invisible.
   Speakers start talking as soon as they're visible, so no time is wasted.
2. **Walk to the lens.** Start small in a wide shot and walk toward a fixed camera while talking, ending in a
   mid or mid close-up. *Why:* it's a push-in with no camera move. Start a few paces outside the frame so the
   walk is already natural when they enter: the first step of a walk always looks stiff.
3. **Cut on the head turn.** The speaker turns their head away mid-sentence and the cut lands during the turn.
   The next shot, at a clearly different size, picks up mid-turn looking from where the previous camera was.
   *Why:* this is cutting on action. The eye follows the movement and doesn't register the cut.
4. **Cut on a turn of the body.** End a take mid-turn, set up the next angle, and start the next take with the
   rest of the same turn. It's cutting on action across two set-ups. Note hand and foot positions so the two
   halves match.
5. **Sit into frame.** The speaker walks in and sits, and the cut lands the instant they settle. Move the camera
   in for the main point, back out afterward, then stand and walk out. *Why:* sitting is an action that hides
   a cut, and a seated set-up gives a second home position.
6. **Match cut on an action.** Repeat the same action, with the same hand at the same pace, in two shot sizes
   (lifting a mug, taking off glasses, opening a door) and cut in the middle of it. *Why:* the continuous motion
   carries the eye across the cut. Editors have relied on this since silent film.
7. **Lean in, lean out.** For the hook or the key line, the speaker leans into a tighter frame, then back.
   *Why:* a small, natural change of size without moving the camera.
8. **In-camera wipes and reveals.** A hand covering the lens, a tilt down from the sky, lifting the phone off
   the ground, the speaker stepping out from behind a post or tree, leaving through a door and arriving through
   another. *Why:* the frame goes briefly black or empty, which makes an invisible cut. Use one per video: more
   becomes a gimmick.
9. **Voiceover over B-roll.** The news package format: the speaker's voice continues over footage of hands,
   place and process, then the picture returns to them on camera for the payoff. *Why:* the viewer gets
   something new to look at, the speaker only has to hold a short line on camera, and the edit can join takes
   under the B-roll freely.
10. **J and L cuts.** Let the next shot's sound start just before its picture (J) or let a voice run on over
    the next picture (L). *Why:* overlapping sound and picture is what makes a sequence feel continuous rather
    than a stack of clips. Shoot handles (a second or two before and after each line) so the edit has room.
11. **Cutaways and asides.** A glance to a second, closer camera for a side remark, or a short silent cutaway
    (looking at the view, writing something down). *Why:* each is a legitimate edit point and a change of
    rhythm.
12. **Punch in to cover a fluff.** If a line goes wrong, re-record just that line and cut to a tighter version of
    the same angle (the 4K punch-in), then back out. *Why:* the size change makes the join a deliberate
    emphasis instead of a jump.
13. **Book-ends.** Open on an empty frame, the speaker enters; close with them walking out to the same empty
    frame. *Why:* a tidy loop, and on platforms that replay, the ending flows into the start.

## 8. Structure: hook, intrigue, delivery, exit

- **One or two sentences per shot.** *Why:* the speaker only has to hold that much in their head, so delivery
  stays natural, and each shot is a complete unit the edit can place, trim or drop.
- **A short is one idea**, in four parts:

  | Part | Job | Rule |
  |---|---|---|
  | **Hook** | Say what the viewer gets, or name their moment | The outcome or the situation, in the viewer's terms. |
  | **Intrigue** | Show why it matters, or what it costs to miss | Raise the stakes. Never give the answer here. |
  | **Delivery** | Deliver the one idea | One idea and one thing the viewer can do today. |
  | **Exit** | End | One short, soft ending: a question, a comment or a follow. Never a hard sell. |

  *Why:* the hook earns the next few seconds, the intrigue gives a reason to stay (if the line after the hook
  gives the answer away, the viewer has what they came for and scrolls on), and the delivery is what they
  stayed for. Asking at the exit, while the value is fresh, turns attention into a relationship. How each line
  sounds is in `script-voice.md`.
- **Give each part its own shot, size or place.** *Why:* the change of picture signals the change of part,
  and it's where the transitions in §7 live.
- **Length.** By default, one thought in 40 to 60 seconds, about 105 to 150 words. Only when the person asks
  for a longer piece: about 2 minutes is 3 to 5 hook, intrigue and delivery units chained around one core idea,
  roughly 12 to 16 shots, ending on one exit. Plan a 40 to 60 second cutdown from the same footage.
- **Script first.** A written script with short lines is how a non-actor gets good takes. Improvisation comes
  later, once the patterns are second nature.

## 9. Openings, titles and spoken hooks

- **Open on a clean wide with space for the title**, and ideally something in the picture worth a second look.
  *Why:* the first frame is the thumbnail on autoplay. It has to be readable on mute.
- **On-screen title: five words or fewer**, in one bold font, naming a concrete result in the viewer's words.
  *Why:* a title is read in a fraction of a second while scrolling.
- **The spoken hook is the promise**, said plainly in the viewer's terms. The line after the hook raises the
  stakes; it doesn't give the answer away.
- **Positive and alongside, not above.** Speak as someone beside the viewer sharing what worked, not a teacher
  correcting them. Don't frame the viewer as the problem; invite them alongside. *Why:* people scroll away from
  being told off.
- **No warm-up.** No "hi, welcome back", no name-and-title intro, no request to follow at the start. *Why:* the
  first seconds decide whether anyone stays; spend them on the promise.

## 10. Performance and on-set coaching

These are the habits TV reporters build for standups and interviews.

- **Talk to one specific person.** Picture one person who'd find this useful, and speak to them through the
  lens. Never "hey everyone". *Why:* one-to-one address is warmer and is how the video is
  actually watched: one person, one phone.
- **Perform slightly bigger than you talk.** Brighter eyes, a bit more pace and expression, at normal volume.
  *Why:* the lens flattens presence; what feels a touch theatrical on set reads as natural on screen.
- **Slow down for the hard sentence.** *Why:* nerves speed people up exactly where the viewer needs time.
- **Land the key line, then hold.** After the line that matters, stop, let the hands settle and keep looking
  into the lens. *Why:* looking away immediately reads as uncertainty. At the very end of the piece, hold the
  look for a couple of seconds; the editor needs that handle anyway.
- **Look away to think, come back for what matters.** Natural speakers glance off while forming a thought and
  return to the lens for the point. *Why:* an unbroken stare reads as stiff; the return to the lens adds
  emphasis.
- **Give the body something to do.** Walking, sitting, holding a mug, coming through a door. *Why:* activity
  relaxes non-actors and gives the edit motion to cut on.
- **Keep the human edges.** A pause, a breath, the odd "um" can stay. *Why:* footage cut too tight sounds
  machine-made.
- **One note at a time.** After a take, give one specific, kind adjustment ("same again, slower on the second
  sentence, then hold the look"), never a list. *Why:* a list makes people self-conscious, and they can only act
  on one thing at once. When reviewing a video afterwards, too, take one fix forward.
- **Disliking your own face and voice is normal.** People know their mirror image and hear their voice through
  their own skull, so the recording sounds and looks wrong to them alone. *Why it matters:* it fades with
  repetition, and it fades faster when the video is about the viewer rather than the speaker.
- **Protect energy.** Shoot the hardest shots first. Stop when takes are getting worse, not better.

## 11. Locations

- **Real places beat sets.** Choose 2 to 5 places near each other for a 2-minute piece, each reachable in a
  minute. Reuse one for the ending if it makes a loop.
- **Busy public places:** keep sections very short, rely on B-roll, carry minimal kit, and don't film
  identifiable strangers as B-roll without thinking about consent.
- **Small spaces and home:** stairs, a doorway, a mirror, the kitchen counter, sitting into a sofa. Each one is a
  ready-made transition from §7.
- **Altitude, heat and cold:** keep walks short, take a breath before entering frame, and change layers only
  between set-ups that don't cut together.
- **Check the forecast and sun times** for the named place and date. Wind is the most common reason a take is
  lost (§2).

## 12. What the edit needs from the shoot

- **Two or three takes of each shot.** The last good take is usually the best: by then the line is known and
  the nerves have gone.
- **Roll a couple of seconds before speaking and after walking out.** *Why:* handles for J and L cuts, and the
  empty frame the walk-out transition needs.
- **Never delete a take on the phone.** Everything comes back for dailies.
- **Never cut same size to same size.** Every cut uses one of the reasons in §7.
- **Captions:** simple, high-contrast, a word or two at a time, clear of the mouth and inside the caption-safe
  zone (§4).
- **Title:** give it a little motion on screen and let it leave once it has been read.
- **Music:** for business accounts, use properly licensed library music, not trending tracks, which carry
  copyright risk. A short social piece, up to about 2 minutes, can have music sitting well under the voice, or
  none. Long-form talking pieces usually work best without.
- **Grade:** keep the eye on the person; darken or desaturate the background slightly if needed, rather than
  brightening the whole picture.

## 13. Strategy: why people keep watching

- **Serve before you sell.** Strangers rarely buy after one video. Most videos should give the viewer one
  useful thing. Selling is occasional, and the call to action stays soft: follow, comment, or a link to
  something genuinely useful.
- **Be recognisable.** Consistent choices (the colours you wear, the kinds of places you film) make someone
  identifiable in a feed before their name appears.
- **Early videos are reps.** Judge the first batch by whether it helped someone and what people say back, not by
  views. Comfort on camera comes from repetition, not from waiting until you feel ready.
