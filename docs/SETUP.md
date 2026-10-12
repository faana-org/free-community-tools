# Set up Brand Video Kit

No terminal and no technical steps. You paste two messages into the Claude desktop app, and Claude does the
installing. You only click, type your Mac password when macOS asks, sign in to Zernio and copy your Zernio key.

---

## Where to use it

In the **Code** tab of the Claude desktop app, on a Mac. That's where Claude can use the video tools installed on
your Mac. Don't add the plugins through **Customize** in the sidebar, and don't use them in the Chat tab or
Cowork: those can't run programs on your Mac.

## What you need

- **A Mac where your account is an administrator.** macOS only lets administrators install the tools. Tested on
  Intel Macs. Apple Silicon: not yet tested; treat the first install as a pilot and report back.
- **The Claude desktop app**, signed in with a plan that includes Claude Code.
- **About 6 GB of free disk space.**
- **On an Intel Mac, time.** Homebrew may have no ready-made build of ffmpeg for your Mac and compile it from
  source instead, which can take hours. Start setup when the Mac can sit plugged in for the afternoon.
- **For shooting:** your phone, ideally a wireless lav mic and a tripod with a phone mount.
- **For publishing:** a Zernio account and the social accounts you'll post to. Claude opens the pages for you.

---

## Step 1: Add the plugins to the Claude app (about 5 minutes)

1. Open the Claude desktop app, click the **Code** tab, and start a new session on your Mac (choose **Local**) in
   any folder, for example your Documents folder.
2. Copy this message, paste it into Claude and send it:

   ```text
   Please install the Brand Video Kit plugins on this Mac. I'm not technical: do every step yourself, and
   only ask me to click or type my password in a system password box.

   1. Make sure git works. If it doesn't, run `xcode-select --install`, tell me to click Install in the
      window that appears, and wait until `xcode-select -p` succeeds.
   2. Install the plugins:
      `claude plugin marketplace add https://github.com/faana-org/free-tools.git`, then
      `claude plugin install video-director@faana-community-tools`,
      `claude plugin install video-production@faana-community-tools` and
      `claude plugin install social-publishing@faana-community-tools`.
      If the claude command isn't available, add this to ~/.claude/settings.json instead, keeping
      everything already in the file:
      "extraKnownMarketplaces": {"faana-community-tools": {"source": {"source": "git", "url": "https://github.com/faana-org/free-tools.git"}}}
      "enabledPlugins": {"video-director@faana-community-tools": true, "video-production@faana-community-tools": true, "social-publishing@faana-community-tools": true}
   3. Tell me to quit and reopen the Claude app.
   ```

3. Do what Claude asks. That's at most two things: click **Install** for Apple's developer tools if they're
   missing, then quit and reopen the Claude app.
4. **Check it worked:** in a Code session, click **+** next to the message box, then **Plugins**. You should see
   **video-director**, **video-production** and **social-publishing**.

Already added the marketplace yourself and installed all three plugins? Skip to step 2.

## Step 2: Set up the video tools and publishing (15–40 minutes, mostly waiting; on an Intel Mac it can take a few hours)

Start a new Code session and send:

```text
set up the video skills
```

Claude uses the `video-setup` skill. It tells you the plan and how big the downloads are, asks once to go
ahead, then:

| Claude does | You do |
|---|---|
| Installs Homebrew, Apple's command line tools, ffmpeg, whisper.cpp and uv | Type your Mac password when a macOS box titled **Install video tools** appears |
| Downloads and installs the video toolkit (see below) | Nothing; it runs in the background |
| Opens zernio.com for you | Sign up or sign in |
| Opens Zernio's accounts page | Connect each social account you'll post to, and approve each platform's sign-in |
| Opens Zernio's API keys page | Click **Create API key**, **copy** it, and tell Claude "copied" |
| Reads the key from your clipboard, checks it with Zernio, stores it in your Mac's Keychain, clears the clipboard | Nothing |
| Runs a final check of everything | Quit and reopen the Claude app once at the end |

Then try it. Let Claude direct you:

*"Be my video director. I want LinkedIn videos about my business; here are my notes."*

Claude writes the script and the call sheet, and after the shoot reviews your takes. You just act.

Or start from recordings you already have:

*"Here are my recordings: ~/Movies/take1.mp4 and ~/Movies/take2.mp4. Make a LinkedIn series."*

### About your Zernio key

**Copying it and saying "copied" is the safest way:** Claude reads the key straight from your clipboard, so it never
appears in the chat, and nothing is left on your clipboard afterwards.

**You can also paste it into the chat.** Claude stores it the same way and never repeats it in a reply. But a pasted
key is saved in plain text in that session's log on your Mac, it's sent to Anthropic with the conversation, and it
shows in the command Claude runs to store it. If that log could ever be seen or shared, delete the key on Zernio's
API keys page and create a new one.

### What the social platforms need

| Platform | What it needs |
|---|---|
| LinkedIn | Your personal profile or an organization page (you choose when connecting) |
| Instagram | A **Business or Creator** account. Personal Instagram accounts can't post through Zernio |
| YouTube | A channel on the Google account you sign in with. Videos over 15 minutes need the channel verified by phone at youtube.com/verify |
| TikTok | Connects through TikTok's Business app. Videos posted this way are public |
| Facebook | A Facebook Page you manage |

Zernio's first 2 connected social accounts are free with no card (X always needs a card).

---

## What the video toolkit is

The toolkit is the set of models and tools the video skills run on your own Mac, so your footage is never
uploaded and nothing costs per use. It's installed once and every project reuses it.

| Part | On disk | What it does |
|---|---|---|
| Speech-to-text model | 1.5 GB | Turns what you say into words |
| Word-timing model and its PyTorch environment | 1.9 GB | Finds the exact moment each word is said, so captions and cuts land precisely |
| Tracking environment (OpenCV) | 0.1 GB | Steadies shaky footage, keeps your face framed, renders the video |
| Noise remover, caption font, face detector | about 30 MB | Removes wind and background noise; caption text; keeps captions off your mouth |

About 3.2 GB to download and 3.5 GB on disk. Each project also needs working space while you edit (about 0.8 GB for
14 minutes of footage).

---

## Updating

Ask Claude in a Code session: *"update the Brand Video Kit plugins"*. It refreshes the marketplace and updates all
three plugins; then quit and reopen the app. Installed this way, the plugins don't update in the background, so ask
now and then.

## If something goes wrong

| What you see | What to do |
|---|---|
| The plugins aren't under **+ → Plugins** | Quit and reopen the Claude app; if they're still missing, send the Step 1 message again |
| "This Mac account isn't an administrator" | Someone who manages the Mac needs to make your account an administrator (System Settings → Users & Groups), or run Step 2 for you |
| The password box was cancelled or the password was wrong | Tell Claude "try the install again" |
| "Zernio rejected this key" | The key was copied incompletely or deleted: create a new one, copy it, and say "copied" |
| An account shows as inactive | Reconnect it on Zernio's accounts page (Claude opens it) |
| Anything else | Tell Claude "check my video and publishing setup": it runs every check and explains what's wrong |

---

For people comfortable with a terminal, the [README](../README.md) has the manual commands.
