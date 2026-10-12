---
name: video-setup
description: Sets up a computer for the video-production and social-publishing skills with no technical steps for the person - installs Homebrew and the system tools (ffmpeg with caption support, whisper.cpp, uv), the video toolkit, and the Zernio publishing setup (account, connected social accounts, API key copied or pasted and stored in the Keychain). The person only clicks, signs in and types their computer password into the system's password box. Use when someone is setting up or onboarding onto the video skills, asks to check their setup, or a video or publishing check failed.
---

# Video Setup: from nothing to ready, with no terminal for the person

Assume the person is not technical. **You do every step.** They only:
- type their computer password into the system's password box when it appears;
- sign in and click approve in their browser (Zernio, social accounts);
- copy their Zernio API key (or paste it into this chat).

Never ask them to open a terminal or run a command. If something truly can't be automated, say so plainly and
say why.

Scripts: `${CLAUDE_SKILL_DIR}/../video-producer/` holds `install_system_tools.sh`, `doctor.py` and
`setup_toolkit.py`. The publishing check and key storage belong to the `social-publishing` skill.

## Rules

- **Say the plan first**, in plain words, and ask once for the go-ahead. List what you'll install, how big it is,
  roughly how long it takes, and the few things they'll be asked to do (password box, browser sign-ins, copying
  the key).
- **Never show or repeat a password or key.** You never see their computer password: it goes from the macOS
  password box straight to the system.
- Long installs run in the background; tell them roughly how long and wait for them to finish rather than polling.
- **Re-check after every step** and report only what the checks confirm.
- Open web pages for them with `open <url>`.

## 1. Where they stand

```bash
bash "${CLAUDE_SKILL_DIR}/../video-producer/install_system_tools.sh" --check
python3 "${CLAUDE_SKILL_DIR}/../video-producer/doctor.py"
```

On a brand-new Mac, `python3` may not exist yet. That's fine: skip the second command until step 2 has run, since
Homebrew brings it.

Ask what they want: **make videos**, **publish**, or both (usually both).

## 2. System tools (you install; they type their password once)

```bash
bash "${CLAUDE_SKILL_DIR}/../video-producer/install_system_tools.sh"
```

Run it in the background. On a Mac without Homebrew it takes about 5–15 minutes and first installs Homebrew and
Apple's command line tools. **Before starting, tell them a macOS password box titled "Install video tools" will
appear, and they should type their Mac password there.** After that it installs ffmpeg-full, whisper-cpp and uv
with no further password. It also adds Homebrew to their shell profile.

- **"This Mac account isn't an administrator"**: Apple only lets an administrator install Homebrew. Tell them
  that plainly: someone who manages the Mac needs to make their account an administrator (System Settings → Users &
  Groups) or run this step for them.
- **Cancelled or wrong password**: just run it again.

The script ends with an `export PATH=...` line. Start later shell commands in this session with it; the video scripts
find the tools on their own. Re-run the `--check`, then `doctor.py`.

## 3. The video toolkit (you install; nothing for them to do)

Tell them what it is, in plain words: the models the video skills run on their own computer, so nothing is uploaded
and nothing costs per use.

| Part | Size on disk | Job |
|---|---|---|
| Speech-to-text model | 1.5 GB | turns what they say into words |
| Word-timing model and its PyTorch environment | 1.9 GB | finds the exact moment each word is said, so captions and cuts land precisely |
| Tracking environment (OpenCV) | 0.1 GB | stabilisation, face-aware framing, rendering |
| Noise remover, caption font, face detector | ~30 MB | removes wind; caption text; keeps captions off the mouth |

About 3.2 GB to download and 3.5 GB on disk, once per computer.

```bash
python3 "${CLAUDE_SKILL_DIR}/../video-producer/setup_toolkit.py" all
```

Run it in the background. Downloads are hash-checked and resume if interrupted, so if it stops, run it again. Then
run `doctor.py`: it should end with **Ready to run.**

## 4. Publishing: Zernio

Load the `social-publishing` skill and run its doctor. If that skill isn't available, the plugin isn't installed:
go back to the setup message in `docs/SETUP.md` of the repository these plugins came from. Then work through what the
doctor reports.

**No Zernio account.** Open https://zernio.com for them to sign up. The first 2 connected social accounts are free
with no card (X always needs one).

**No API key.** Open https://zernio.com/dashboard/api-keys and tell them: click **Create API key**, **copy** it, and
tell me "copied". Then store it with the social-publishing skill's `store-key --from-clipboard`: the key never enters
the chat, and the clipboard is cleared afterwards. If they paste it into the chat instead, store it straight away
with `store-key` and follow that skill's rules: never repeat it, and tell them accurately what happens to a pasted
key.

**No social accounts, or an inactive one.** Open https://zernio.com/dashboard for them to connect each account; the
platform's own sign-in page does the rest. Tell them what each platform needs before they try:

| Platform | What it needs |
|---|---|
| LinkedIn | their personal profile or an organization page (chosen on the connect screen) |
| Instagram | a Business or Creator account; personal accounts can't post through Zernio |
| YouTube | a channel on the Google account they sign in with; over 15 min needs phone verification (youtube.com/verify) |
| TikTok | connects through TikTok's Business app; posts made this way are public |
| Facebook | a Page they manage |

Re-run the doctor until it lists their accounts and says **Ready.** Confirm the accounts and handles are the ones
they expect.

## 5. Finish

Run both checks one last time and report in plain words:

| Area | Status |
|---|---|
| System tools | ready / what's left |
| Video toolkit | ready (size on disk) / what's left |
| Zernio key | stored in the Keychain and working (ending in its last 4 characters) |
| Connected accounts | platforms and handles |

Then tell them to quit and reopen the Claude app once, so every tool is picked up, and suggest a first request:
*"Here are my recordings: … Make a LinkedIn series."*

## Where this runs

In the Claude desktop app's **Code** tab on a Mac (or Claude Code in a terminal). If they're in the Chat tab or
Cowork, tell them to open a Code session instead: those can't run the video tools.
