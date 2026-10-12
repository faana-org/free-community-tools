# Presenting publishing to the user

The script prints for terminals; you are talking to a person. Reformat every
time and never paste raw JSON.
The examples below use a fictional person and business; they show format only.

## Accounts

Lead with the count, list platform and handle, and ask which ones this post is for.

> **4 accounts connected:** LinkedIn (Dana Ortiz), Instagram (@danaortiz), YouTube (Dana Ortiz), Facebook (Ortiz Studio).
> Which should this post go to?

Drop account ids unless asked.

## The approval preview (the most important message)

Everything the user is agreeing to, in one place, before asking. Show the full
text, not a summary, **on a page**: a designed, self-contained HTML file in the
project folder, readable on a phone. Publish it as a private page with the
Artifact tool when the app has one; otherwise open the file in their browser
(`open <file>`). A table in chat isn't enough.

The page, per platform: the account, how it posts, the title, the local time,
the full text as it will appear (line breaks kept, the cut-off point marked),
the first comment, and the media (file name, length, and a still from the
video when ffmpeg is installed).
Then every change from their draft with the reason, and what can't be undone.
For a series, one page with every post in date order, unless the videos have
their own pages (below).

**One page per video.** If the video already has a page from `video-director`,
the preview goes at the top of its **Posts** tab, marked as the version
awaiting approval, with any earlier draft copy moved below it and labelled
"earlier draft, not what will post". That same page is republished to the same
link, opening on that tab. Never a second document for the same video. For a
series of such videos, each post goes in its own video's Posts tab, and the
chat message lists them in date order with their links. The gate is the same
either way.

The chat message is one line, the link and the question:

> **Ready to schedule, nothing sent yet: your video to LinkedIn, Instagram and YouTube, Thu 1 Oct, 9:00 am
> EDT.** [Open the preview](<link>)
> One change from your draft: "Part 2 of…" became "From my series…", because part 1 isn't out yet. Instagram
> can't be taken down through the API.
> Schedule it?

Rules:
- **Times:** local, with the day name and timezone. Never raw UTC.
- **Changes:** list every change made to the user's copy, with the reason.
- **Irreversibles:** say which platforms can't be undone.
- **The question:** end with one yes/no question, not "let me know".
- **Revisions:** after any change, re-preview and update the same page with
  its version and what changed, then ask again. Never ask about a version the
  user hasn't seen.
- **Fingerprint:** never show it. It's for the script.

## After creating

> **Scheduled** for Thu 1 Oct, 9:00 am EDT on LinkedIn, Instagram and YouTube. Each is pending until then.
> I'll check the results just after 9:00. You can still cancel before then.

On partial failure, name each platform and the reason in plain words:

> **Posted to LinkedIn and YouTube; Instagram failed:** the video is 94 seconds and Reels allow 90.
> Want me to trim it to 90 seconds and retry just Instagram?

## After it publishes

Give the live links and anything still processing.

> **Live:** [LinkedIn](url) · [YouTube](url). Instagram is still processing; I'll check again in a few minutes.

## Never

- Never print, repeat or hint at the API key.
- Never say "published" when the status is scheduled, pending or partial.
- Never recompute the fingerprint to get past a refusal. Re-preview and re-ask.
- Never publish, schedule, edit, unpublish or delete without an explicit yes in this conversation.
