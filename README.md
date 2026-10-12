# Brand Video Kit

Short videos of you, talking about your business, without learning to film or edit.

You act. Claude directs, produces, edits and publishes, and nothing goes out without your approval.
(The edit handles talking-head recordings today; cutting a fully directed shoot together is still being built.
See [Honest limits](#honest-limits).)

<!-- VIDEO -->
<!-- Launch video embed goes here. -->
<!-- /VIDEO -->

## Just show up: the idea in five steps

You don't need these plugins to use the idea. They just do the parts you don't want to.

1. **Split the two jobs.** Thinking about content is one job. Showing up is another. Do the thinking once,
   when you're fresh, instead of switching into it in the middle of a busy week.
2. **Pick the one thing you explain all the time.** The question customers ask you every week, the one you
   could answer in your sleep. That's your first video.
3. **Hand Claude the planning.** Say "be my director", tell it your topic, and point it at an email, post or
   page where you've already explained it. It turns that into a short script, marks any line it added so you
   can approve or cut it, and plans the shoot for where you'll actually be.
4. **Show up.** Phone, clip-on mic, tripod, and the call sheet on your phone. Say it to one customer you like,
   the way you would across a table.
5. **Say yes.** Claude reviews your takes, cleans the sound, captions the video, and schedules the posts once
   you approve them.

## Can you use the plugins? Three checks

- **A Mac.** Tested on Intel Macs. Apple Silicon isn't tested yet.
- **The Claude desktop app on a paid plan** that includes Claude Code (you'll use its Code tab).
- **An afternoon for the first setup.** Claude does the installing; you type your Mac password when asked. On
  an Intel Mac it can take a few hours, because some tools may have to be built.

All three? **[Set it up →](docs/SETUP.md)** No terminal needed.

---

## What it does, in plain words

Making a video usually means four jobs: planning it, filming it, editing it and posting it. Brand Video Kit
hands all four to Claude, running on your own Mac, and leaves you the one only you can do: being on camera.

1. **Direct.** Tell Claude what your business is and give it your own material: a newsletter, your website, notes,
   past posts. It brings back video ideas, each traced to something you wrote or said. It writes the script one
   short line per shot and marks every line: your words, your idea reworded, or new (which you approve). Then it
   plans the shoot for where you'll actually be: where to stand, the time of day for the light, what to wear,
   and how each shot leads into the next.
2. **Shoot.** You go out with your phone and a one-page call sheet. You act; the plan has already made the
   camera decisions. When you're back, Claude reviews every take for framing, wind and sound, proposes the best
   one for each shot for you to confirm, and lists anything worth reshooting.
3. **Edit.** Claude cleans the audio, builds a word-accurate transcript, finds the themes in what you said (with
   your own quotes as evidence), shapes a series with you, and renders steadied, face-framed vertical videos
   with animated captions. It checks every file before handing it over.
4. **Publish.** Claude schedules the videos to LinkedIn, Instagram, YouTube, TikTok or Facebook through
   [Zernio](https://zernio.com). It shows you exactly what will go out, on which account and when, and only
   schedules it after you say yes.

You can start at any step. If you already have recordings, skip straight to the edit.

## What you need

- **A Mac.** It doesn't run on Windows or Linux.
- **The Claude desktop app**, signed in with a plan that includes Claude Code. You use its **Code** tab.
- **Your phone**, recording 4K video.
- **A wireless lav mic** (the small clip-on kind). Sound matters more than picture.
- **A tripod with a phone mount.**
- **About 6 GB of free disk space** for the tools, which install once.
- **For publishing:** a Zernio account (the first two connected social accounts are free) and the social
  accounts you want to post to.

## Install

**Follow [docs/SETUP.md](docs/SETUP.md).** You paste one message into the Code tab of the Claude desktop app and
Claude installs the plugins, then a second message and it sets up the video tools and publishing. You click,
type your Mac password when macOS asks, and sign in to Zernio. No terminal.

## What's inside

| Plugin | Skills | What it does |
|---|---|---|
| [`video-director`](plugins/video-director) | `video-director`, `video-dailies` | Ideas, labelled scripts, shot lists and call sheets, coaching, and review of your takes |
| [`video-production`](plugins/video-production) | `video-setup`, `video-producer`, `video-audio`, `video-story-edit`, `video-finishing`, `video-qa` | Sets up your Mac, then turns raw recordings into a captioned series of short videos and a longer cut |
| [`social-publishing`](plugins/social-publishing) | `social-publishing` | Publishes or schedules posts and videos through Zernio, with an approval step before anything goes out |

Each plugin's README has the detail.

## Honest limits

- **Mac only.** Tested on Intel Macs. Apple Silicon: not yet tested; treat the first install as a pilot and
  report back.
- **Claude desktop Code tab or Claude Code in a terminal.** The Chat tab, Cowork and claude.ai can't run the
  video tools on your Mac.
- **Not built yet: assembling a directed shoot.** The director plans the shoot and reviews the takes, and the
  edit cleans the sound and captions talking-head footage. What doesn't exist yet is the step that cuts a
  directed shoot together automatically: picking the chosen take for each shot, titles over the opening wide,
  voiceover over B-roll, and the held empty frames between walk-outs. Until it's built, the take log and shot
  list are what an editor works from.
- **Vertical (portrait) SDR recordings only.** Landscape and HDR video are refused with an explanation. Turn HDR
  video off on your phone before you shoot.
- **9:16 and 4:5 only.** 16:9 for YouTube long-form isn't built.
- **English** is the tuned and tested language.
- **One caption style, no music bed.**
- **Publishing:** upload, validation, scheduling, status and cancelling have been verified. A live publish
  hasn't been observed yet, and Facebook and TikTok follow Zernio's documentation but haven't been exercised.

## Measured, not promised

- **Word timing:** forced alignment put words starting outside detected speech at under 1%, against 13–15% for
  the transcriber's own timings. That's what keeps captions and cuts on the right syllable.
- **Stabilisation:** 28–49% less high-frequency shake (median, per video) on the handheld selfie shorts
  measured. Smoother, not tripod-still.
- **A clean run:** a fresh Claude Code session given only these plugins and two short real recordings found the
  themes itself with quoted evidence, refined them with the speaker, had the plan reviewed and delivered a pilot
  that passed QA.

## Your footage stays on your Mac

Transcription, cleanup, tracking and rendering all run locally. Your recordings aren't uploaded anywhere for
editing, and nothing costs per use. The only things that leave your Mac are the finished videos and posts you
approve for publishing, which go to Zernio and on to the platforms you chose. As with any Claude Code session,
what you type and what Claude reads in the conversation (including the still frames it reviews) is sent to
Anthropic.

## For terminal users

```bash
claude plugin marketplace add faana-org/free-tools
claude plugin install video-director@faana-community-tools
claude plugin install video-production@faana-community-tools
claude plugin install social-publishing@faana-community-tools
```

Or merge this into `~/.claude/settings.json` (keep any keys already there) and restart Claude Code:

```json
{
  "extraKnownMarketplaces": {
    "faana-community-tools": {
      "source": { "source": "github", "repo": "faana-org/free-tools" }
    }
  },
  "enabledPlugins": {
    "video-director@faana-community-tools": true,
    "video-production@faana-community-tools": true,
    "social-publishing@faana-community-tools": true
  }
}
```

Then start a Code session and say *"set up the video skills"*: Claude installs the system tools and the video
toolkit, and walks you through connecting Zernio.

**Updates** don't arrive on their own. Refresh the catalog, then update each plugin:

```bash
claude plugin marketplace update faana-community-tools
claude plugin update video-director@faana-community-tools
claude plugin update video-production@faana-community-tools
claude plugin update social-publishing@faana-community-tools
```

In the desktop app, use **+ → Plugins → Manage plugins**, or just ask Claude to update them. Restart afterwards.

## For maintainers

```
.claude-plugin/marketplace.json     the catalog Claude Code reads
plugins/<plugin>/
  .claude-plugin/plugin.json        the plugin's manifest
  skills/<skill>/SKILL.md           instructions Claude follows
  skills/<skill>/PRESENTATION.md    how results are shown to the person
  skills/<skill>/*.py, *.sh         scripts the skills run
  docs/                             human-facing guides
docs/SETUP.md                       the no-terminal setup guide
```

Before pushing a change, validate and bump the plugin's `version` in both `plugin.json` and `marketplace.json`
(installed copies only update when it changes):

```bash
claude plugin validate .
claude plugin validate ./plugins/<plugin>
```

Never commit credentials or anyone's footage: `.gitignore` covers keys, project files and media.

## License

[MIT](LICENSE)
