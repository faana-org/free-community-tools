#!/usr/bin/env python3
"""
Zernio publishing client: upload, validate, preview, schedule, check, cancel.

Zernio (https://docs.zernio.com) publishes one post to many social accounts
(LinkedIn, Instagram, YouTube, TikTok, ...) through a single API. This script
wraps the calls a publishing session needs and enforces the safety rules in
code, not just in instructions:

  * Nothing is created without --confirm <fingerprint>, where the fingerprint is
    the SHA-256 of the exact post body shown to the user by `preview`. Change
    one character and the fingerprint no longer matches.
  * ZERNIO_READONLY=1 or CI=true refuses every write except dry-run validation.
    doctor.py and tests run with it on.
  * The idempotency request id is saved next to the post file BEFORE the create
    call and reused on any retry, so a retried create returns the original post
    instead of publishing twice.
  * A timeout on create means "unknown", not "failed": run `status`/`list` first.

Usage (run from the project folder, never from the plugin folder):
  python3 zernio_api.py accounts
  python3 zernio_api.py upload VIDEO.mp4                 -> prints publicUrl (valid 7 days)
  python3 zernio_api.py validate post.json               -> dry run, publishes nothing
  python3 zernio_api.py preview post.json                -> human summary + fingerprint
  python3 zernio_api.py create post.json --confirm FP    -> schedules / publishes / drafts
  python3 zernio_api.py status POST_ID
  python3 zernio_api.py wait POST_ID [--minutes 30]      -> polls until published/partial/failed
  python3 zernio_api.py list --status scheduled
  python3 zernio_api.py delete POST_ID --yes             -> only for posts not yet published
  python3 zernio_api.py store-key --from-clipboard       -> store the key the person copied (never printed)
  printf '%s' 'sk_...' | python3 zernio_api.py store-key -> same, for a key pasted into the chat

Storing a key: `store-key` reads it from the clipboard (--from-clipboard), stdin, or a hidden prompt in a
terminal; checks it looks like a Zernio key; confirms Zernio accepts it; then saves it to the macOS Keychain or,
with --to file, a private credentials/zernio.key (kept out of git). It is passed to the Keychain on stdin, never
as a command argument, and never printed.

Key lookup, first match wins (the value is never printed):
  --api-key-file PATH, ZERNIO_API_KEY, macOS Keychain (service zernio-api-key),
  credentials/zernio.key

Exit codes: 0 ok, 1 API/platform failure, 2 refused before doing anything, 3 outcome unknown.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import mimetypes
import os
import platform
import pwd
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API = "https://zernio.com/api/v1"
KEYCHAIN_SERVICE = "zernio-api-key"
CREDENTIAL_FILE = Path("credentials/zernio.key")
# sk_ + 64 hex today, zrk_ for restricted keys. The strict alphabet also keeps a key from breaking out of the
# quoted Keychain command it is passed in.
KEY_PATTERN = re.compile(r"(?:sk|zrk)_[A-Za-z0-9]{16,128}")
TIMEOUT_S = 120
MAX_429_RETRIES = 3
TERMINAL = {"published", "partial", "failed", "cancelled"}
WRITE_PREFIXES = ("POST", "PUT", "DELETE", "PATCH")
# Zernio's validate endpoints are dry runs that persist nothing, so read-only mode allows them.
DRY_RUN_PATHS = ("/tools/validate/",)


# --------------------------------------------------------------------------
# auth
# --------------------------------------------------------------------------

def _run(cmd: list[str]) -> str | None:
    if not shutil.which(cmd[0]):
        return None
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def find_key(key_file: str | None = None) -> tuple[str | None, str]:
    """Return (key, where-it-came-from). Never logs the key."""
    if key_file:
        p = Path(key_file)
        if not p.is_file():
            sys.exit("The --api-key-file path doesn't exist (not shown, in case a key was passed by mistake). "
                     "Pass the path of a file that contains the key.")
        return p.read_text().strip(), str(p)
    if os.environ.get("ZERNIO_API_KEY"):
        return os.environ["ZERNIO_API_KEY"].strip(), "ZERNIO_API_KEY environment variable"
    user = _user()
    if platform.system() == "Darwin":
        k = _run(["security", "find-generic-password", "-a", user, "-s", KEYCHAIN_SERVICE, "-w"])
        if k:
            return k, f"macOS Keychain (service {KEYCHAIN_SERVICE})"
    if CREDENTIAL_FILE.is_file():
        return CREDENTIAL_FILE.read_text().strip(), str(CREDENTIAL_FILE)
    return None, ""


def load_key(key_file: str | None = None) -> str:
    key, _ = find_key(key_file)
    if not key:
        sys.exit(
            "No Zernio API key found.\n"
            "Create one at https://zernio.com/dashboard/api-keys. Then either give it to the assistant, which\n"
            "stores it with `zernio_api.py store-key`, or store it yourself in a terminal:\n"
            f"  macOS:  security add-generic-password -a \"$USER\" -s {KEYCHAIN_SERVICE} -w\n"
            f"  any:    save it to {CREDENTIAL_FILE} and chmod 600 it"
        )
    return key


SAFE_ACCOUNT = re.compile(r"[A-Za-z0-9._-]{1,64}")


def _user() -> str:
    """The login name the Keychain item is filed under (from the system, not the environment)."""
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except KeyError:
        return os.environ.get("USER") or ""


def _write_private(path: Path, text: str) -> None:
    """Write a secret so it is never readable by others, even for a moment, and never through a link."""
    parent = path.parent
    if parent.is_symlink() or path.is_symlink():
        sys.exit(f"{path} or its folder is a link; refusing to write the key through it. Nothing stored.")
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(parent, 0o700)
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".zernio-key-")   # created 0600
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)    # replaces a file or link at path itself; never writes through it
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _keep_out_of_git(path: Path) -> str:
    """If path is inside a git repository and not ignored, add its folder to that repository's .gitignore."""
    top = subprocess.run(["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0:
        return ""
    if subprocess.run(["git", "-C", str(path.parent), "check-ignore", "-q", str(path)]).returncode == 0:
        return ""
    root = Path(top.stdout.strip())
    rel = os.path.relpath(path.parent.resolve(), root.resolve())
    with (root / ".gitignore").open("a") as fh:
        fh.write(f"\n# Zernio API key (added by social-publishing)\n/{rel}/\n")
    return f"Added {rel}/ to {root / '.gitignore'} so the key can't be committed."


def store_key(key: str, to: str) -> str:
    """Save the key; return where. Verifies by reading it back. Never prints the key or a tool's raw output."""
    user = _user()
    if to == "auto":
        to = "keychain" if platform.system() == "Darwin" and shutil.which("security") and SAFE_ACCOUNT.fullmatch(user) \
            else "file"
    if to == "keychain":
        if not SAFE_ACCOUNT.fullmatch(user):
            sys.exit("This account name can't be used for a Keychain item; use --to file. Nothing stored.")
        where = f"macOS Keychain (service {KEYCHAIN_SERVICE})"
        # passed on stdin to security's own command line, never as a process argument; KEY_PATTERN and SAFE_ACCOUNT
        # guarantee neither value contains a quote or whitespace
        r = subprocess.run(["/usr/bin/security", "-i"], capture_output=True, text=True,
                           input=f'add-generic-password -U -a "{user}" -s "{KEYCHAIN_SERVICE}" -w "{key}"\n')
        ok = r.returncode == 0 and _run(["/usr/bin/security", "find-generic-password", "-a", user,
                                         "-s", KEYCHAIN_SERVICE, "-w"]) == key
    else:
        _write_private(CREDENTIAL_FILE, key + "\n")
        where = str(CREDENTIAL_FILE.resolve())
        note = _keep_out_of_git(CREDENTIAL_FILE)
        if note:
            print(note.strip())
        ok = CREDENTIAL_FILE.read_text().strip() == key
    if not ok:
        sys.exit(f"Couldn't store the key in {where} (it didn't read back). Try --to file. Nothing else changed.")
    return where


# --------------------------------------------------------------------------
# http
# --------------------------------------------------------------------------

class Unknown(Exception):
    """The request may or may not have reached Zernio (timeout, dropped connection)."""


def readonly() -> bool:
    return os.environ.get("ZERNIO_READONLY") == "1" or os.environ.get("CI", "").lower() in ("1", "true")


def call(key: str, method: str, path: str, body: dict | None = None,
         headers: dict | None = None) -> tuple[int, dict]:
    if method in WRITE_PREFIXES and readonly() and not path.startswith(DRY_RUN_PATHS):
        print(f"Refused {method} {path}: ZERNIO_READONLY/CI is set, so writes are disabled.")
        sys.exit(2)
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"}
    h.update(headers or {})
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(MAX_429_RETRIES + 1):
        req = urllib.request.Request(API + path, method=method, headers=h, data=data)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            raw = e.read()
            if e.code == 429 and attempt < MAX_429_RETRIES:
                wait = int(e.headers.get("Retry-After") or 10)
                print(f"Rate limited by Zernio; waiting {wait}s (attempt {attempt + 1}).", file=sys.stderr)
                time.sleep(wait)
                continue
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, {"error": raw.decode(errors="replace")[:300]}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise Unknown(f"{method} {path}: {e.__class__.__name__}: {e}") from e
    return 429, {"error": "rate limited after retries"}


def fingerprint(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def load_post(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        sys.exit(f"{path} not found.")
    try:
        return json.loads(p.read_text())
    except ValueError as e:
        sys.exit(f"{path} is not valid JSON: {e}")


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_store_key(_key: str, a) -> int:
    if a.from_clipboard:
        # the person copied the key; reading it here keeps it out of the chat, the command and the session log
        clip = subprocess.run(["/usr/bin/pbpaste"], capture_output=True, text=True)
        key = clip.stdout.strip() if clip.returncode == 0 else ""
    elif sys.stdin.isatty():
        key = getpass.getpass("Zernio API key (input hidden): ").strip()
    else:
        key = sys.stdin.read().strip()
    if not KEY_PATTERN.fullmatch(key):
        print("That doesn't look like a Zernio API key (they start with sk_)"
              + (": copy the key again, then retry." if a.from_clipboard else ".") + " Nothing stored.")
        return 2
    count = None
    if not a.no_verify:
        try:
            st, r = call(key, "GET", "/accounts")
        except Unknown:
            print("Couldn't reach Zernio to check the key. Nothing stored; try again, or pass --no-verify.")
            return 3
        if st in (401, 403):
            print("Zernio rejected this key (deleted, or copied incompletely). Nothing stored.")
            return 1
        if st != 200:
            print(f"Zernio returned HTTP {st} while checking the key. Nothing stored.")
            return 1
        count = len(r.get("accounts", []))
    where = store_key(key, a.to)
    print(f"Stored the key ending ...{key[-4:]} in {where}."
          + (f" Zernio accepts it: {count} connected account(s)." if count is not None else " Not verified."))
    env = os.environ.get("ZERNIO_API_KEY", "").strip()
    if env and env != key:
        print("Note: a different key is set in ZERNIO_API_KEY, and that one is used first. Remove or update it in "
              "your shell profile (for example ~/.zshrc), then restart the app.")
    if a.from_clipboard:
        subprocess.run(["/usr/bin/pbcopy"], input="", text=True)   # don't leave the key on the clipboard
        print("Cleared the clipboard.")
    return 0


def cmd_accounts(key: str, _a) -> int:
    st, d = call(key, "GET", "/accounts")
    if st != 200:
        print(f"Zernio returned HTTP {st}: {d.get('error', '')}")
        return 1
    for acc in d.get("accounts", []):
        print(json.dumps({k: acc.get(k) for k in ("platform", "username", "displayName", "isActive", "_id")}))
    return 0


def cmd_upload(key: str, a) -> int:
    f = Path(a.file)
    if not f.is_file():
        sys.exit(f"{a.file} not found.")
    ctype = mimetypes.guess_type(f.name)[0] or ""
    if not ctype.startswith(("video/", "image/")) and ctype != "application/pdf":
        sys.exit(f"Unsupported file type for {f.name} ({ctype or 'unknown'}). Use MP4/MOV video, JPEG/PNG image or PDF.")
    # publicUrl is fetchable by anyone who has it, so make it unguessable.
    name = f"media-{secrets.token_hex(8)}{f.suffix.lower()}"   # the local file name never becomes public
    st, pre = call(key, "POST", "/media/presign", {"filename": name, "contentType": ctype, "size": f.stat().st_size})
    if st != 200 or "uploadUrl" not in pre:
        print(f"Presign failed (HTTP {st}): {pre.get('error', '')}")
        return 1
    put = subprocess.run(["curl", "-sS", "-f", "-o", "/dev/null", "-w", "%{http_code}", "-X", "PUT", pre["uploadUrl"],
                          "-H", f"Content-Type: {ctype}", "--data-binary", f"@{f}"], capture_output=True, text=True)
    if put.returncode != 0 or put.stdout.strip() != "200":
        print(f"Upload failed (HTTP {put.stdout.strip() or '?'}): {put.stderr.strip()[:200]}")
        return 1
    st, v = call(key, "POST", "/tools/validate/media", {"url": pre["publicUrl"]})
    print(json.dumps({"publicUrl": pre["publicUrl"], "valid": v.get("valid"), "size": v.get("sizeFormatted"),
                      "type": v.get("type"), "error": v.get("error"),
                      "platformLimits": v.get("platformLimits")}, indent=1))
    print("Note: uploads expire after 7 days unless a post uses them.")
    return 0 if v.get("valid") else 1


def cmd_validate(key: str, a) -> int:
    body = load_post(a.post)
    st, v = call(key, "POST", "/tools/validate/post", body)
    print(json.dumps(v, indent=1))
    return 0 if st == 200 and v.get("valid") else 1


def cmd_preview(_key: str, a) -> int:
    body = load_post(a.post)
    when = body.get("scheduledFor") or ("now" if body.get("publishNow") else "draft" if body.get("isDraft") else "queue" if body.get("queuedFromProfile") else "draft")
    print(f"When: {when}  timezone: {body.get('timezone', 'UTC (none given)')}")
    print("Media:", ", ".join(m.get("url", "?").rsplit("/", 1)[-1] for m in body.get("mediaItems", [])) or "none")
    for p in body.get("platforms", []):
        psd = p.get("platformSpecificData") or {}
        extra = {k: psd[k] for k in ("title", "visibility", "firstComment") if k in psd}
        print(f"- {p.get('platform')} account {p.get('accountId')} {json.dumps(extra) if extra else ''}"
              f"{' (custom text)' if p.get('customContent') else ''}")
    print("\nText:\n" + (body.get("content") or "(none)"))
    print(f"\nFingerprint: {fingerprint(body)}   (create requires --confirm with exactly this value)")
    return 0


def cmd_create(key: str, a) -> int:
    body = load_post(a.post)
    fp = fingerprint(body)
    if a.confirm != fp:
        print(f"Refused: the post changed or was never previewed. Current fingerprint is {fp}.\n"
              "Run `preview`, show it to the user, and pass --confirm only after they approve.")
        return 2
    state = Path(a.post).with_suffix(".request.json")
    saved = json.loads(state.read_text()) if state.is_file() else {}
    # Reuse the request id only for the same approved body: a retry must not double-post, but an edited and
    # re-approved post is a new request (Zernio could otherwise answer with the earlier post).
    rid = saved["requestId"] if saved.get("fingerprint") == fp and saved.get("requestId") else str(uuid.uuid4())
    state.write_text(json.dumps({"requestId": rid, "fingerprint": fp}))
    try:
        st, r = call(key, "POST", "/posts", body, headers={"x-request-id": rid})
    except Unknown as e:
        print(f"Outcome unknown ({e}). Do NOT create again blindly: run `list --status scheduled` "
              f"or `status` first. A retry with this post file reuses request id {rid}.")
        return 3
    post = r.get("post", {})
    print(json.dumps({"http": st, "postId": post.get("_id"), "status": post.get("status"),
                      "scheduledFor": post.get("scheduledFor"), "warnings": r.get("warnings"), "error": r.get("error"),
                      "platforms": [{k: x.get(k) for k in ("platform", "status", "platformPostUrl", "errorMessage")}
                                    for x in post.get("platforms", [])]}, indent=1))
    if post.get("_id"):
        state.write_text(json.dumps({"requestId": rid, "fingerprint": fp, "postId": post["_id"]}))
    # 207 is a 2xx but means one or more platforms failed.
    return 0 if st in (200, 201) and post.get("status") not in ("failed", "partial") else 1


def _post_summary(r: dict) -> dict:
    p = r.get("post", {})
    return {"status": p.get("status"), "scheduledFor": p.get("scheduledFor"), "publishedAt": p.get("publishedAt"),
            "platforms": [{k: x.get(k) for k in ("platform", "status", "platformPostUrl", "errorMessage", "errorCategory")}
                          for x in p.get("platforms", [])]}


def cmd_status(key: str, a) -> int:
    st, r = call(key, "GET", f"/posts/{a.post_id}")
    if st == 404:
        print("Not found (deleted, or the id is wrong).")
        return 1
    print(json.dumps(_post_summary(r), indent=1))
    return 0 if st == 200 else 1


def cmd_wait(key: str, a) -> int:
    deadline = time.time() + a.minutes * 60
    last = None
    while True:
        st, r = call(key, "GET", f"/posts/{a.post_id}")
        if st == 404:
            print("Post no longer exists (deleted).")
            return 1
        s = _post_summary(r)
        brief = (s["status"], [(p["platform"], p["status"]) for p in s["platforms"]])
        if brief != last:
            print(time.strftime("%H:%M:%S"), brief, flush=True)
            last = brief
        if s["status"] in TERMINAL:
            print(json.dumps(s, indent=1))
            return 0 if s["status"] == "published" else 1
        if time.time() > deadline:
            print(f"Still {s['status']} after {a.minutes} min.")
            return 3
        time.sleep(60)


def cmd_list(key: str, a) -> int:
    st, r = call(key, "GET", f"/posts?status={a.status}&limit={a.limit}")
    if st != 200:
        print(f"Listing failed (HTTP {st}): {r.get('error', '')}")
        return 1
    posts = r.get("posts", [])
    if not posts:
        print(f"No {a.status} posts.")
    for p in posts:
        print(json.dumps({"postId": p.get("_id"), "status": p.get("status"), "scheduledFor": p.get("scheduledFor"),
                          "platforms": [x.get("platform") for x in p.get("platforms", [])]}))
    return 0


def cmd_delete(key: str, a) -> int:
    if not a.yes:
        print("Refused: deleting needs --yes, after the user has confirmed which post.")
        return 2
    st, r = call(key, "DELETE", f"/posts/{a.post_id}")
    if st == 400:
        print(f"Zernio refused: {r.get('error')}. Published posts need unpublish, which Instagram and TikTok don't support.")
        return 1
    st2, _ = call(key, "GET", f"/posts/{a.post_id}")
    print("Deleted (verified: post not found)." if st2 == 404 else f"Delete returned HTTP {st}; post still present (HTTP {st2}).")
    return 0 if st2 == 404 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--api-key-file", help="path to a file containing the key (never the key itself)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("accounts")
    p = sub.add_parser("upload"); p.add_argument("file")
    p = sub.add_parser("validate"); p.add_argument("post")
    p = sub.add_parser("preview"); p.add_argument("post")
    p = sub.add_parser("create"); p.add_argument("post"); p.add_argument("--confirm", required=True)
    p = sub.add_parser("status"); p.add_argument("post_id")
    p = sub.add_parser("wait"); p.add_argument("post_id"); p.add_argument("--minutes", type=int, default=30)
    p = sub.add_parser("list"); p.add_argument("--status", default="scheduled"); p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("delete"); p.add_argument("post_id"); p.add_argument("--yes", action="store_true")
    p = sub.add_parser("store-key", help="read a key on stdin, verify it with Zernio, store it")
    p.add_argument("--to", choices=["auto", "keychain", "file"], default="auto")
    p.add_argument("--from-clipboard", action="store_true", help="read the key the person copied (macOS)")
    p.add_argument("--no-verify", action="store_true", help="store without checking it with Zernio")
    a = ap.parse_args()
    handlers = {"accounts": cmd_accounts, "upload": cmd_upload, "validate": cmd_validate, "preview": cmd_preview,
                "create": cmd_create, "status": cmd_status, "wait": cmd_wait, "list": cmd_list, "delete": cmd_delete,
                "store-key": cmd_store_key}
    key = "" if a.cmd in ("preview", "store-key") else load_key(a.api_key_file)
    try:
        sys.exit(handlers[a.cmd](key, a))
    except Unknown as e:
        print(f"Could not reach Zernio: {e}. Check the network and retry.")
        sys.exit(3)


if __name__ == "__main__":
    main()
