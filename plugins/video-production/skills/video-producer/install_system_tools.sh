#!/bin/bash
# Installs the system tools the video skills need on a Mac, so the person never has to open a terminal:
# Homebrew (with Apple's command line tools, which also provide python3 and git), then ffmpeg-full (ffmpeg with
# caption support), whisper-cpp and uv.
#
# The only thing the person does is type their Mac password into the standard macOS password box when it
# appears. The password goes from that box straight to macOS's sudo; this script never sees, prints or stores it.
# Installing Homebrew needs an administrator account.
#
# Trust: this runs Homebrew's official installer, downloaded over HTTPS from
# https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh (Homebrew's documented install method; it is
# not pinned, so it is whatever Homebrew publishes today), and installs Homebrew's own packages.
#
# It adds Homebrew and ffmpeg-full to ~/.zprofile (unless --no-profile) so a terminal finds them, and prints the
# PATH to use for the rest of the current session. The video scripts find the tools on their own.
#
# Usage:
#   bash install_system_tools.sh --check        what's missing; installs nothing
#   bash install_system_tools.sh                install what's missing
#   bash install_system_tools.sh --no-profile   install, but don't edit ~/.zprofile
#
# Exit 0 = everything present. Exit 1 = something failed (message says what). Exit 2 = refused (not a Mac, not an
# administrator, or the password box was cancelled).

set -euo pipefail

CHECK_ONLY=0
EDIT_PROFILE=1
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --no-profile) EDIT_PROFILE=0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

PROFILE="$HOME/.zprofile"
PROFILE_MARK="# added by the video-production setup"
BREW_LOCATIONS=(/opt/homebrew/bin/brew /usr/local/bin/brew)   # Homebrew's only official prefixes; nothing else is trusted

say() { printf '%s\n' "$*"; }

if [[ "$(uname -s)" != "Darwin" ]]; then
  say "This installer is for macOS only."
  exit 2
fi

official_brew() {
  local b
  for b in "${BREW_LOCATIONS[@]}"; do
    if [[ -x "$b" ]]; then printf '%s' "$b"; return 0; fi
  done
  return 0
}

missing_tools() {
  local out=() filters=""
  command -v ffmpeg >/dev/null 2>&1 && filters="$(ffmpeg -hide_banner -filters 2>/dev/null || true)"
  # captured first: piping into grep -q would cut ffmpeg off early, and pipefail would read that as failure
  # ffprobe has to start, not just exist: a Homebrew upgrade of a shared library (x265) can leave it unloadable
  if ! grep -qE '^ *[A-Z.|]+ +subtitles ' <<<"$filters" || ! ffprobe -version >/dev/null 2>&1; then
    out+=("ffmpeg-with-captions")
  fi
  command -v whisper-cli >/dev/null 2>&1 || out+=("whisper-cli")
  command -v uv >/dev/null 2>&1 || out+=("uv")
  command -v python3 >/dev/null 2>&1 || out+=("python3")
  if (( ${#out[@]} )); then printf '%s\n' "${out[@]}"; fi
}

add_profile_line() {   # idempotent; the line is built with %q quoting by the caller
  local line="$1"
  [[ "$EDIT_PROFILE" == 1 ]] || return 0
  touch "$PROFILE"
  grep -qxF "$line" "$PROFILE" || printf '\n%s\n%s\n' "$PROFILE_MARK" "$line" >> "$PROFILE"
}

ffmpeg_full_bin() {   # prints the ffmpeg-full bin folder when installed
  local brew="$1" prefix
  prefix="$("$brew" --prefix ffmpeg-full 2>/dev/null || true)"
  if [[ -n "$prefix" && -x "$prefix/bin/ffmpeg" ]]; then printf '%s' "$prefix/bin"; fi
}

session_path() {
  local brew="$1" p ff
  p="$("$brew" --prefix)/bin"
  ff="$(ffmpeg_full_bin "$brew")"
  [[ -n "$ff" ]] && p="$ff:$p"
  say "For commands in this session, start with:  export PATH=\"$p:\$PATH\""
}

BREW="$(official_brew)"
if [[ -n "$BREW" ]]; then
  eval "$("$BREW" shellenv)"
  FF="$(ffmpeg_full_bin "$BREW")"
  [[ -n "$FF" ]] && export PATH="$FF:$PATH"
fi

MISSING="$(missing_tools)"
if [[ -z "$MISSING" ]]; then
  say "All system tools are present."
  [[ -n "$BREW" ]] && session_path "$BREW"
  exit 0
fi
say "Missing: $(tr '\n' ' ' <<<"$MISSING")"
[[ "$CHECK_ONLY" == 1 ]] && exit 1

# ---------------------------------------------------------------- Homebrew
if [[ -z "$BREW" ]]; then
  if ! id -Gn "$USER" | tr ' ' '\n' | grep -qx admin; then
    say "This Mac account isn't an administrator, and only an administrator can install Homebrew."
    say "Someone who manages this Mac needs to make the account an administrator (System Settings > Users & Groups), or run this setup."
    exit 2
  fi
  say "Installing Homebrew and Apple's command line tools. This usually takes 5-15 minutes."
  say "A macOS password box titled \"Install video tools\" will appear: type your Mac password there."

  WORK="$(mktemp -d)"            # 0700; holds the password-box helper and the downloaded installer, never the password
  cleanup() { rm -rf "$WORK"; /usr/bin/sudo -k 2>/dev/null || true; }
  trap cleanup EXIT INT TERM

  cat > "$WORK/askpass.sh" <<'ASK'
#!/bin/bash
/usr/bin/osascript \
  -e 'set r to display dialog "Claude is installing Homebrew, which the video tools need. Enter your Mac password to allow it." with title "Install video tools" default answer "" with hidden answer buttons {"Cancel", "OK"} default button "OK" with icon caution' \
  -e 'text returned of r' 2>/dev/null || exit 1
ASK
  chmod 700 "$WORK/askpass.sh"

  /usr/bin/curl --proto '=https' --tlsv1.2 -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh \
    -o "$WORK/install.sh"
  if ! NONINTERACTIVE=1 SUDO_ASKPASS="$WORK/askpass.sh" /bin/bash "$WORK/install.sh"; then
    say "Homebrew didn't install. If the password box was cancelled or the password was wrong, run this again."
    exit 2
  fi
  BREW="$(official_brew)"
  [[ -z "$BREW" ]] && { say "Homebrew reported success but isn't in /opt/homebrew or /usr/local."; exit 1; }
  eval "$("$BREW" shellenv)"
fi
printf -v LINE 'eval "$(%q shellenv)"' "$BREW"
add_profile_line "$LINE"

# ---------------------------------------------------------------- packages (no password needed)
FORMULAS=()
grep -qx "ffmpeg-with-captions" <<<"$MISSING" && FORMULAS+=("ffmpeg-full")
grep -qx "whisper-cli" <<<"$MISSING" && FORMULAS+=("whisper-cpp")
grep -qx "uv" <<<"$MISSING" && FORMULAS+=("uv")
grep -qx "python3" <<<"$MISSING" && FORMULAS+=("python@3.12")
if (( ${#FORMULAS[@]} )); then
  say "Installing with Homebrew: ${FORMULAS[*]} (ffmpeg-full is several hundred MB)."
  HOMEBREW_NO_ENV_HINTS=1 "$BREW" install "${FORMULAS[@]}"
fi

FF="$(ffmpeg_full_bin "$BREW")"
if [[ -n "$FF" ]]; then
  export PATH="$FF:$PATH"
  printf -v LINE 'export PATH=%q:"$PATH"' "$FF"
  add_profile_line "$LINE"
fi

MISSING="$(missing_tools)"
if [[ -n "$MISSING" ]]; then
  say "Still missing after install: $(tr '\n' ' ' <<<"$MISSING")"
  exit 1
fi
say "All system tools are installed."
session_path "$BREW"
