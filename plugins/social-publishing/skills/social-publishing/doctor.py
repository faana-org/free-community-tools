#!/usr/bin/env python3
"""
Pre-flight check for social publishing through Zernio.

Answers one question: if I try to publish right now, what will go wrong?
Every failure line says what to do about it. Read-only: it never creates,
uploads or changes anything.

Usage:  python3 doctor.py [path-to-api-key-file]

Exit 0 = ready. Exit 1 = something needs fixing first.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# Everything below is read-only; this also blocks any accidental write.
os.environ["ZERNIO_READONLY"] = "1"
sys.dont_write_bytecode = True  # never write __pycache__ into the plugin directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import zernio_api as z  # noqa: E402

OK, WARN, BAD = "  OK  ", " WARN ", " FIX  "
problems = 0
warnings = 0


def line(state: str, what: str, detail: str = "") -> None:
    print(f"[{state}] {what}" + (f"\n         {detail}" if detail else ""))


def fail(what: str, detail: str) -> None:
    global problems
    problems += 1
    line(BAD, what, detail)


def warn(what: str, detail: str) -> None:
    global warnings
    warnings += 1
    line(WARN, what, detail)


def check_python() -> None:
    v = sys.version_info
    if (v.major, v.minor) < (3, 9):
        fail(f"Python {v.major}.{v.minor} is too old", "Install Python 3.9 or newer.")
    else:
        line(OK, f"Python {v.major}.{v.minor}")


def check_curl() -> None:
    if shutil.which("curl"):
        line(OK, "curl (used for media uploads)")
    else:
        fail("curl missing", "macOS includes curl; reinstall Apple's command line tools:  xcode-select --install")


def check_key(explicit: str | None) -> str | None:
    key, where = z.find_key(explicit)
    if not key:
        fail("No Zernio API key found",
             "Create one at https://zernio.com/dashboard/api-keys, then either give it to the assistant\n"
             "         (it stores it with: zernio_api.py store-key) or store it yourself:\n"
             f"         security add-generic-password -a \"$USER\" -s {z.KEYCHAIN_SERVICE} -w")
        return None
    src = Path(where)
    if src.is_file():
        mode = src.stat().st_mode & 0o777
        if mode & 0o077:
            warn(f"{where} is readable by other users (mode {mode:o})", f"Tighten it:  chmod 600 {where}")
    line(OK, f"API key found in {where}")
    return key


def check_api(key: str) -> None:
    """The only check that proves the key works: list the connected accounts."""
    try:
        st, d = z.call(key, "GET", "/accounts")
    except z.Unknown as exc:
        warn("Could not reach Zernio", f"{exc}. Check your network connection.")
        return
    if st == 401:
        fail("Zernio rejected the API key", "It may have been revoked. Create a new one in the Zernio dashboard.")
        return
    if st != 200:
        fail(f"Zernio returned HTTP {st}", str(d.get("error", "Unexpected response."))[:200])
        return
    accounts = d.get("accounts", [])
    if not accounts:
        fail("No social accounts are connected",
             "Connect them in the Zernio dashboard (Platforms), then re-run this check.")
        return
    line(OK, f"Zernio accepts the key; {len(accounts)} connected account(s):")
    for a in accounts:
        state = "active" if a.get("isActive") else "INACTIVE (reconnect it in Zernio)"
        print(f"         - {a.get('platform')}: {a.get('username') or a.get('displayName')} ({state})")
        if not a.get("isActive"):
            warn(f"{a.get('platform')} account is inactive", "Reconnect it in the Zernio dashboard before publishing.")
    if z.readonly():
        line(OK, "Read-only mode was on for this check (no writes possible)")


def main() -> None:
    explicit = sys.argv[1] if len(sys.argv) > 1 else None
    print("Social publishing (Zernio) -- pre-flight check\n")
    check_python()
    check_curl()
    key = check_key(explicit)
    if key:
        check_api(key)
    print()
    if problems:
        print(f"{problems} thing(s) need fixing before publishing will work.")
        sys.exit(1)
    print(f"Ready, with {warnings} warning(s) above." if warnings else "Ready.")
    print("\nNext:  confirm with the user which of these accounts the post is for.")


if __name__ == "__main__":
    main()
