# Video Production Runbook

How to turn raw recordings of yourself (or someone you're producing) talking to camera into a series of
captioned short videos and a longer cut.

You do this by **asking Claude**, not by running commands. This guide covers what to say, what you'll see and
the decisions you'll be asked to make. Most of the time is the machine working in the background while you
answer a handful of questions.

---

## One-time setup

**1. Install and set up.** Follow [docs/SETUP.md](../../../docs/SETUP.md): paste one message into the Code tab of
the Claude desktop app to install the plugins, then say *"set up the video skills"*. Claude installs everything;
you type your Mac password when macOS asks, sign in when a browser page opens, and paste your Zernio key. It runs in the Code tab on a
Mac; so far it has been tested on an Intel Mac, so if yours is Apple Silicon, please report how it goes
by opening an issue on the repository.

**2. Let Claude install the toolkit.** On first use it checks your computer and lists what's missing with sizes,
about 3.2 GB to download. Say yes. It installs once, outside your projects, and every later project reuses it.

**3. Have disk space.** About 4 GB for the toolkit, plus working space while you edit (about 0.8 GB for 14 minutes of footage on one
project).

---

## Recording tips (before you hit record)

- Hold the phone **vertically**. Landscape and HDR video aren't supported yet; on iPhone and Pixel, turn HDR
  video off for these recordings.
- Face a window or open shade; avoid bright sky directly behind you.
- Wind ruins words more than it ruins sound. Shelter from it if you can; Claude can clean a lot, not everything.
- Talk longer than you think. More material means stronger choices for each video.
- Several takes on different days are fine; Claude can splice across them.

---

## Making a series

Start with something like:

> Here are my recordings: ~/Movies/take1.mp4 and ~/Movies/take2.mp4. Make a LinkedIn series of shorts and a
> longer video.

### What happens, and what you'll be asked

**1. Setup questions (a minute).** Where the project folder should live, which platforms, whether you want your
name on screen and how it should read, and a caption colour if you have brand colours.

**2. Audio check.** Claude measures the sound. If there's wind or noise, it cleans it and gives you two short
before/after clips. **Listen to them.** Claude can't hear; your ears are the judge. Say if the cleaned voice
sounds watery or robotic.

**3. Themes.** Claude reads everything you said and comes back with the themes it found, each with your own
quotes and times, the thread that ties them together, and what it left out. You don't need to tell it what
your videos are about. Your job here:
- say which themes feel true to you and which you'd rather not post;
- say who the series is for;
- decide about anything sensitive: named people, criticism, personal details.

This is a conversation. Merge, drop or rename themes; Claude checks each change against what you actually said
and tells you if the footage doesn't support it.

**4. Series plan.** An order, dates and an opening line per video. Claude has the plan reviewed for strategy
and for reputation risk before cutting, and tells you what it changed and why.

**5. Pilot video.** One finished video to watch before the rest are made. Watch it on your phone. Anything you
change here is fixed once for all of them.

**6. The batch.** Claude renders the rest and checks every file: the words match what you said, captions never
cover your mouth, sound levels, and no location data in the files. You get a table of results.

**7. Post copy (optional).** A post per video in your own voice, fact-checked against the recording.

**8. Publishing (optional, separate plugin).** With `social-publishing` installed, Claude can schedule the
series. Nothing goes out until you approve each exact post.

---

## What you get

In your project folder:

```
edits/shorts/   one .mp4 + .srt per short (vertical 9:16)
edits/long/     the longer cut (.mp4 + .srt, 4:5 for LinkedIn)
edits/posts/    post copy, one file per video
```

The `.srt` files are plain subtitles for platforms that want them. The videos already have captions burned in,
so don't upload both to the same platform.

---

## Good to know

- **Honesty is built in.** Claude won't put words on screen it isn't sure you said, won't splice sentences into
  a different meaning, and won't invent themes or facts.
- **Stabilisation smooths, it doesn't lock.** In testing, handheld shorts had roughly a third to a half less shake.
- **It's slow on purpose.** Transcription and tracking take minutes per recording; rendering takes a few minutes
  per video. Claude works in the background and tells you when something needs you.
- **Cleaning up.** When you're done, ask *"clean up the video project"*. Claude lists what it would delete
  (working files only, never your recordings or finished videos) and asks first.

## When something goes wrong

| You see | What to do |
|---|---|
| "landscape" or "HDR" refused | Re-record vertically with HDR off, or export an SDR vertical copy |
| A word in the captions is wrong | Tell Claude the right word; it checks it against the audio and re-renders |
| Captions cover your mouth in a shot | Tell Claude the time; it looks at that frame and re-cuts or re-frames that clip (for example, without its punch-in) |
| Voice sounds processed | Say so after the before/after clips; Claude re-cleans with a gentler setting and makes new clips |
| The toolkit check fails after an OS update | Ask Claude to check the video toolkit again; it repairs what broke |
