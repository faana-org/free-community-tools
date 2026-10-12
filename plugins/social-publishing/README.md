# social-publishing

Publish or schedule posts and videos to LinkedIn, Instagram, YouTube, TikTok and
Facebook through [Zernio](https://zernio.com), from a conversation.

> Schedule this video to LinkedIn and YouTube for Tuesday at 9am

Claude checks your connected accounts, uploads the file, validates the post,
shows you exactly what will go out on each platform, and only schedules it
after you say yes. Then it reports each platform's result.

## Before the first run

The full checklist, including what each platform requires, is in [docs/SETUP.md](../../docs/SETUP.md).

1. **A Zernio account** with your social accounts connected (Zernio dashboard →
   Platforms). The first two connected accounts are free.
2. **An API key:** Zernio dashboard → API keys → Create API key. **Copy** it and
   tell Claude "copied": Claude reads it from the clipboard, checks it with
   Zernio, stores it in your Mac's Keychain and clears the clipboard, so the key
   never enters the chat. You can also paste it into the chat; then it's saved
   in plain text in that session's log on your Mac and sent to Anthropic with
   the conversation, so replace the key if that log could ever be seen.
3. Ask Claude to check the setup: *"check my publishing setup"*. It runs the
   read-only doctor and lists your accounts.

## Where it runs

| | Works? |
|---|---|
| Claude desktop app, Code tab (on a Mac) | Yes |
| Claude Code in a terminal | Yes |
| Chat tab, Cowork, claude.ai | Not supported |

## What it protects you from

- **Publishing the wrong thing.** Creating a post requires a fingerprint of the
  exact preview you approved. If anything changes, it refuses until you
  approve again.
- **Double posts.** A retry after a dropped connection reuses the original
  request, and an unknown outcome is checked before anything is re-sent.
- **Surprises you can't undo.** The preview says which platforms can't be taken
  down later (Instagram, TikTok).
- **Accidental writes while testing.** With `ZERNIO_READONLY=1`, every change
  is refused and only reads and dry-run validation work.

## Known gaps

- Verified: upload, validation, scheduling to three platforms, status and
  cancelling before publish. **A live publish hasn't been observed yet**, so
  the skill watches the first one closely.
- Facebook, TikTok and Reddit follow Zernio's documentation but haven't been
  exercised.
- No bulk upload or queue management commands. Use the Zernio dashboard for those.
