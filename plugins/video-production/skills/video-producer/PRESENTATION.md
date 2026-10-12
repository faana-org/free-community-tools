# Presenting video work to the person

The scripts print for terminals; you're talking to a person. Reformat every time and never paste raw output.
The examples below are fictional (a physiotherapist recording tips on a phone) and show format only. Every real
title, quote and theme comes from the person's own footage.

## The rules

- **Lead with the decision or the result**, then the evidence.
- **Humanise numbers:** `412.36` s → `6m 52s`; `B 312.4` → `take B, 5:12`; LUFS and dBTP only in QA tables.
- **Quotes are verbatim** and carry a take and time. Your judgement is labelled as yours.
- **Approvals happen on a page.** The theme proposal, the series plan and every video's read-back go on one
  series page before you ask for agreement: a designed, self-contained HTML file in `plan/`, readable on a
  phone. Publish it as a private page with the Artifact tool when the app has one; otherwise open the file in
  their browser (`open <file>`). Each revision updates the same page, with its version and what changed. The
  chat message is one line, the link and the question. A table in chat isn't enough. When the footage comes
  from a `video-director` shoot, that video already has one page (`director/pages/video_<slug>.html`): its
  read-back, captions check and final cut go on that page as a tab or section, never a new page; the series
  page then holds only the series plan.
- **End with one specific question** and the real options, never "let me know".

## Before installing tools

> **The video toolkit isn't installed yet: about 3.2 GB to download, 4 GB on disk.**
>
> | Missing | Download | Used for |
> |---|---|---|
> | Speech model | 1.6 GB | transcription |
> | Word-timing model and PyTorch | 1.4 GB | aligning every word to the audio |
> | … | | |
>
> It installs once for this computer, outside your project. Install it now?

## Audio findings

> **Take B has steady wind; take A is clean.** Wind sits 9 dB above the voice between words in B, worst at
> 2:10–3:40. Cleaning removed 31 dB of it in pauses and cost the voice under 2 dB.
>
> Two 20-second samples are in `edits/audio_check/`: `B_130s_20s_before.mp3` and
> `B_130s_20s_after.mp3`. Does the cleaned
> version sound natural to you, or watery?

## Theme proposal

The first version of the series page. Lead with the thread, then one block per theme, then what was left out,
then the questions. The chat gets the headline, the link and the questions; the page has every block in full.

> **I found four themes and one thread running through them: *"your body keeps score of the small stuff"*
> (your words, take A, 4:02).**
>
> **1. Rest is training** · about 40 s
> The point: recovery days are where the gains happen.
> - "Nobody gets stronger in the gym. You get stronger on the couch after." (A, 1:15)
> - "I had to learn that the hard way, twice." (B, 0:48)
> Hook: the couch line. Ending: "twice", with a pause. My read: the strongest opener, it's surprising and short.
>
> **2. …**
>
> **Left out:** the equipment section (A, 6:00–7:30) repeats theme 3 with weaker lines. **Held for the long
> cut:** the story about your first marathon (B, 3:10), so the final video has something new.
>
> Before I plan cuts:
> 1. Do all four feel true to you, or would you rather not post any of them?
> 2. Who should these reach, and what should they do after watching?
> 3. You name a clinic at B, 2:05. Keep it, tag it, or cut the name?

## Series plan

On the series page: a table (number, date, title, length, opening line), then one section per video with its
read-back text, each splice marked, what was removed and the closing line, all with take and time.

> **Series plan v2 is on the same page: five posts over ten days, ending with the longer cut.**
> [Open the series plan](<link>)
> Changed since v1: posts 2 and 3 swapped, as the reviewers suggested (it alternates the takes). I didn't drop
> post 5, because it's the only one about prevention, which you said matters most.
>
> Render the first video as a pilot?

## QA results

> **All 5 videos pass.** One flag explained below; nothing needs a re-render.
>
> | Video | Length | Words | Captions vs mouth | Loudness | Location data |
> |---|---|---|---|---|---|
> | Rest is training | 0:41 | 99.1% | clear (closest 38 px) | −16.2 LUFS | none |
> | … | | | | | |
>
> - **Word flag, video 4:** the check heard "the" where you say "a" (B, 1:02). The audio supports "a"; it's a
>   transcriber miss.
> - **Not verified:** playback in a browser; how captions sit under TikTok's buttons (needs a draft upload).

## Handing over

Finish with a table of files (title, length, path), what was done, what was measured with the numbers, what
wasn't verified, and the one next decision (usually post copy or publishing).
