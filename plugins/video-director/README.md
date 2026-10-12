# video-director

Claude as your video director and producer, so you only have to act.

> Be my video director. I want a couple of LinkedIn videos about my practice; here's my newsletter and my website.

Claude reads your own material and brings you video ideas, each traced to something you wrote or said. It writes
the script one sentence per shot, and marks every line: yours word for word, adapted from yours, or new (which
you approve). Then it plans the shoot for where you'll actually be: which shot goes where, the time of day for
the light, what to wear, and how each shot hands over to the next. Walk-outs, head turns and sitting into frame
replace jump cuts. You go and film with the call sheet. When you're back, Claude reviews every take: framing,
wind and slates. It proposes the best take per shot for you to confirm, and lists anything to reshoot.

The camera and performance craft is standard film and broadcast grammar (eye-lines, screen direction, cutting
on action, voiceover over B-roll, the news standup) scaled down to one person and a phone. Every rule in the
playbook comes with its reason.

## Skills

| Skill | What it does |
|---|---|
| `video-director` | Intake, your sources, ideas, labelled scripts, shot list and call sheet, and direction on set. |
| `video-dailies` | After the shoot: contact sheets, wind and clipping flags, slate reading, a take log and a reshoot list, then handoff to the edit. |

## What it needs

- ffmpeg, which the `video-setup` skill in the `video-production` plugin installs. Reading spoken slates also uses
  that plugin's video toolkit if it's there; without it, dailies still work.
- Your phone, ideally a wireless lav mic and a tripod with a phone mount.

## Not built yet

Cutting a directed shoot into the finished video: picking the chosen take for each shot, titles in the sky,
voiceover over B-roll, and held empty frames between walk-outs. `video-production` handles sound, transcripts
and captions today. The assembly is the next version. Until then the take log and shot list are what an editor
works from.
