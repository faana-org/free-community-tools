---
name: social-publishing
description: Publish or schedule finished videos and posts to LinkedIn, Instagram, YouTube, TikTok and Facebook through Zernio, with a preview the user approves before anything goes out. Use when a post or video is ready to publish, when scheduling a series of posts, or when checking, cancelling or diagnosing a scheduled post.
---

# Social Publishing (Zernio)

Uploads media, validates a post, shows the user exactly what will go out, then
schedules or publishes it to their connected accounts through Zernio's API, and
reports each platform's result.

**Publishing is outward-facing and partly irreversible.** Instagram and TikTok
posts cannot be taken down through the API, and LinkedIn rejects near-duplicate
text for weeks. Nothing is created until the user has approved the exact text,
accounts, time and media in this conversation, and the script enforces that.

Script: `${CLAUDE_SKILL_DIR}/zernio_api.py`

Run it from the user's project folder. Never write post files or output into
the plugin directory.

## Status

Verified against the live API (Sept 2026):
- media upload and validation;
- post validation;
- a scheduled post to three platforms;
- status checks;
- deleting a post before its publish time.

**Not yet observed:** a post actually going live (per-platform `published`
status, live URLs, processing time). Treat the first real publish as a test:
watch it with `wait` and report exactly what happens.

## First: run the doctor

For a first-time setup, the `video-setup` skill (video-production plugin) walks through the Zernio account,
connected accounts and the key together with the video tools. What each platform requires is in the table there.

```bash
python3 "${CLAUDE_SKILL_DIR}/doctor.py"
```

It is read-only, checks the key, proves it works, and lists connected accounts.
When something is missing, **offer to fix it and do it if they agree**:

| Missing | What to do |
|---|---|
| API key | Ask the person for it (see below) |
| No connected accounts | The user connects them in the Zernio dashboard (Platforms). Wait, then re-run. |

### The API key

The person creates it; you store it. Open https://zernio.com/dashboard/api-keys for them (`open <url>`) and say:
click **Create API key**, then **copy** it and tell me "copied".

**Preferred: from the clipboard.** The key never enters the chat, your commands or the session log:

```bash
python3 "${CLAUDE_SKILL_DIR}/zernio_api.py" store-key --from-clipboard
```

**If they paste it into the chat instead**, that's allowed; store it straight away:

```bash
printf '%s' 'THE_PASTED_KEY' | python3 "${CLAUDE_SKILL_DIR}/zernio_api.py" store-key
```

Either way the script checks the key with Zernio first, stores it in the macOS Keychain (`--to file` for a private
`credentials/zernio.key`, kept out of git), prints only its last 4 characters, and clears the clipboard when it
read from there. Then:

- **Never repeat the key in a reply** or put it anywhere else (files, notes, memory, commit messages, other
  commands). Refer to it by its last 4 characters.
- **Be accurate about a pasted key** (tell them once): it's saved in plain text in this session's log on their Mac,
  and it was sent to Anthropic with the conversation. It also shows in the store command you ran. If that log could
  be seen or shared, they should delete the key on Zernio's API keys page and make a new one. The clipboard route
  avoids all of this.
- If the script says a different key is set in `ZERNIO_API_KEY`, that one wins: offer to remove the old line from
  their shell profile.

## The flow

### 1. Confirm accounts and mode

Show the doctor's account list and **ask which accounts this post is for**.
Handles can change and a brand account may not match the person, so never
assume. Account ids change when an account is reconnected, so read them fresh
every session.

Agree the mode, stating the consequences:

- **Public now or scheduled.** It's real. It uses up that content: posting it
  again later may be rejected as a duplicate, and posting out of order breaks a
  series.
- **Safer tests.**
  - YouTube `visibility: private` or `unlisted` is the only fully private
    end-to-end test.
  - TikTok `tiktokSettings.draft: true` goes to the creator's inbox.
  - `isDraft: true` saves a Zernio draft and publishes nothing.
  - LinkedIn and Instagram have no private option.

### 2. Upload

```bash
python3 "${CLAUDE_SKILL_DIR}/zernio_api.py" upload path/to/video.mp4
```

Prints `publicUrl` and per-platform size checks. The file name gets a random
suffix because the URL is publicly fetchable. **Uploads expire after 7 days**
unless a post uses them.

### 3. Build `post.json` (in the project folder)

One body for all platforms; per platform, override with `customContent`,
`customMedia` or `platformSpecificData`.

```json
{
  "content": "Post text…",
  "mediaItems": [{"type": "video", "url": "<publicUrl>"}],
  "scheduledFor": "2026-10-01T09:00:00",
  "timezone": "America/New_York",
  "platforms": [
    {"platform": "linkedin", "accountId": "<id>"},
    {"platform": "instagram", "accountId": "<id>"},
    {"platform": "youtube", "accountId": "<id>",
     "platformSpecificData": {"title": "≤100 chars", "visibility": "public", "madeForKids": false}}
  ]
}
```

Always send an IANA `timezone` with a local `scheduledFor`, or it is read as UTC.
For immediate posting use `"publishNow": true`; for a draft, `"isDraft": true`.

| Platform | Must know |
|---|---|
| LinkedIn | ≤3,000 chars, hook before "see more". **Links go in `platformSpecificData.firstComment`**, because a URL in the text gets less reach. `@Name` in plain text is not a tag. Video ≤10 min on personal profiles. Near-duplicate text is rejected. |
| Instagram | A single video always posts as a **Reel: ≤90 s**, 9:16, ≤300 MB. Caption ≤2,200, first 125 chars show. Cover via `thumbOffset` (ms) or `instagramThumbnail`. Links go in `firstComment`. **No unpublish via API.** |
| YouTube | Set `title`, `visibility`, `madeForKids: false`. Vertical and ≤3 min becomes a **Short automatically**; no custom thumbnail on Shorts. Tags go in the top-level `tags` array (≤500 chars total). A scheduled public video uploads as private and YouTube releases it at the time. |
| TikTok | Top-level `tiktokSettings` is required: `privacy_level` (read `GET /accounts/{id}/tiktok/creator-info` first), `allow_comment`, `allow_duet`, `allow_stitch`, `content_preview_confirmed: true`, `express_consent_given: true`. 9:16, 3 s–10 min. Business-app connections post videos public only (use `draft` otherwise). No edits after publishing; the live URL arrives minutes later. |
| Facebook | See the Facebook page in Zernio's docs before first use; not exercised yet. |

**Adjust copy per platform, and show every change in the preview:**
- A series footer ("Part 3 of…") is wrong where earlier parts don't exist yet.
- `@mentions` become plain names unless resolved.
- YouTube needs a title; offer the video's opening line as a hook option.

### 4. Validate, then preview

```bash
python3 "${CLAUDE_SKILL_DIR}/zernio_api.py" validate post.json   # dry run
python3 "${CLAUDE_SKILL_DIR}/zernio_api.py" preview post.json    # summary + fingerprint
```

Fix every validation error. Show the preview as a page first, following
`PRESENTATION.md`: every platform's full text, account, time and media exactly
as they'll go out. If this video already has a page (a `video-director`
project: `director/pages/video_<slug>.html`, its link at the top of
`director/script_<slug>.md`), the preview goes at the top of that page's Posts
tab, marked as awaiting approval, with the page opening on it; not on a new
page. Then ask for an explicit yes in chat. After any change, preview again,
update the same page with what changed, and ask again.

### 5. Create, only after an explicit yes

```bash
python3 "${CLAUDE_SKILL_DIR}/zernio_api.py" create post.json --confirm <fingerprint>
```

- **Refuses (exit 2)** if the body changed since the preview. Preview again and
  re-confirm; never recompute the fingerprint to get past this.
- **Saves a request id** next to `post.json` before sending, so re-running the
  same create can't publish twice.
- **Exit 3 means the outcome is unknown** (a timeout). Run `list` or `status`
  before anything else.
- **Exit 1 with a 207 result** means some platforms failed. Report each one's
  `errorMessage`.

### 6. Verify and watch

Right after creating, run `status <postId>` and report the local time and each
platform's state. For a publish you want to confirm, start `wait <postId>` in
the background near the scheduled time: it polls every 60 s until the post is
published, partial or failed, then prints each live URL or error.

### 7. Cancel or change

- **Before it publishes:**
  - `delete <postId> --yes`, after the user confirms which post (it verifies
    the deletion);
  - to change content, delete and create again with a new preview.
- **After it publishes:**
  - LinkedIn and YouTube text can be edited, and both can be unpublished, via
    the Zernio API (`POST /v1/posts/{id}/edit`, `/unpublish`);
  - Instagram and TikTok cannot.
- **Failed or partial:** `POST /v1/posts/{id}/retry` retries only the failed
  platforms.

## Scheduling a series

- **Timing:** one post per platform per day. Zernio caps an account at 25 posts
  an hour, Instagram at 100 a day, TikTok at 15 videos a day.
- **Recurring slots:** use a Zernio queue (`queuedFromProfile`), never copying a
  "next slot" time into `scheduledFor`, which bypasses the slot lock.
- **Best-time analytics:** `/analytics/best-time` numbers days **0 = Monday**,
  in UTC, while queue slots use **0 = Sunday** in the queue's timezone. Convert
  deliberately.
- **Time references:** keep them true ("last week" in a video goes stale).

## Known gaps

- A live publish has not been observed through this skill yet (see Status).
- Facebook, TikTok and Reddit specifics are from Zernio's docs only, not exercised.
- LinkedIn mention tags and Instagram location tags need extra lookups this
  script doesn't do.
- No bulk CSV upload or queue management commands. Use the Zernio dashboard or API directly.
