#!/usr/bin/env python3
"""
Client for the AfterQuery Kepler tRPC API (experts.afterquery.com).

Reads a live bearer token from token.txt (written by token_write.js, fed by the
browser extension) so calls always use the freshest session token.

Endpoints wrapped:
  pitch(idea)                          -> kepler.tasks.pitch        (idea check)
  issue_upload()                       -> kepler.tasks.issueUpload  (get signed upload URL)
  put_zip(upload_url, zip_path)        -> PUT the bundle to GCS
  finalize(upload_id, name, cat, lbls) -> kepler.tasks.finalize     (submit for validation)
  get(submission_id)                   -> kepler.tasks.get          (status + pipeline)
  delete(submission_id)                -> kepler.tasks.delete
  list_mine()                          -> kepler.tasks.listMine

CLI:
  python3 kepler_api.py pitch "my idea sentence"
  python3 kepler_api.py list
  python3 kepler_api.py status <submissionId>
  python3 kepler_api.py delete <submissionId>
  python3 kepler_api.py submit <zip> <taskName> <Category> <label1,label2>
  python3 kepler_api.py whoami        # decode token.txt (email + minutes left)
"""

import json
import os
import sys
import time
import base64
from pathlib import Path
from urllib.parse import quote

from curl_cffi import requests

BASE = "https://experts.afterquery.com/api/trpc"
TOKEN_FILE = os.environ.get("KEPLER_TOKEN_FILE", str(Path(__file__).with_name("token.txt")))
COOKIE_FILE = os.environ.get("KEPLER_COOKIE_FILE", str(Path(__file__).with_name("cookies.txt")))
UPLOAD_CT = os.environ.get("KEPLER_UPLOAD_CONTENT_TYPE", "application/zip")


def read_cookies():
    """Browser cookies (incl. the Vercel challenge cookie) captured by the extension,
    so headless requests can pass the Vercel Security Checkpoint. Optional."""
    try:
        return Path(COOKIE_FILE).read_text().strip()
    except FileNotFoundError:
        return ""


class KeplerError(RuntimeError):
    pass


class TokenError(KeplerError):
    pass


def read_token():
    try:
        tok = Path(TOKEN_FILE).read_text().strip()
    except FileNotFoundError:
        raise TokenError(f"token file not found: {TOKEN_FILE} — start token_write.js and sign in via the extension")
    if not tok or tok.count(".") != 2:
        raise TokenError(f"no valid token in {TOKEN_FILE} yet — sign in on experts.afterquery.com so the extension pushes one")
    return tok


def token_meta():
    """Decode the JWT payload (email + exp) without verifying."""
    tok = read_token()
    payload = tok.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    data = json.loads(base64.urlsafe_b64decode(payload))
    exp = int(data.get("exp", 0))
    return {"email": data.get("email"), "exp": exp, "minutes_left": round((exp - time.time()) / 60) if exp else None}


def _headers(json_body=True):
    h = {
        "authorization": f"Bearer {read_token()}",
        "accept": "*/*",
        "origin": "https://experts.afterquery.com",
        "referer": "https://experts.afterquery.com/projects/kepler/submit",
    }
    if json_body:
        h["content-type"] = "application/json"
    cookies = read_cookies()
    if cookies:
        h["cookie"] = cookies
    return h


def _session():
    return requests.Session(impersonate="chrome136")


def _check_token_fresh():
    m = token_meta()
    if m["exp"] and m["minutes_left"] is not None and m["minutes_left"] <= 0:
        raise TokenError(f"token expired {abs(m['minutes_left'])}m ago — refocus experts.afterquery.com so the extension pushes a fresh one")


def _unwrap(resp, index=0):
    """Pull the json payload out of a tRPC batch response, raising on tRPC error."""
    try:
        data = resp.json()
    except Exception:
        raise KeplerError(f"non-JSON response (HTTP {resp.status_code}): {resp.text[:300]}")
    if isinstance(data, dict) and data.get("error"):
        raise KeplerError(f"tRPC error: {json.dumps(data['error'])[:300]}")
    if not isinstance(data, list) or index >= len(data):
        raise KeplerError(f"unexpected response shape: {json.dumps(data)[:300]}")
    item = data[index]
    if "error" in item:
        err = item["error"].get("json", item["error"])
        raise KeplerError(f"tRPC error: {json.dumps(err)[:400]}")
    return item["result"]["data"]["json"]


def _envelope(json_input):
    # superjson: an explicit `undefined`/no-input procedure needs the meta marker,
    # otherwise the server sees `null`. Procedures with a real payload send json only.
    if json_input is None:
        return {"json": None, "meta": {"values": ["undefined"], "v": 1}}
    return {"json": json_input}


def _retry_net(fn, *a, **kw):
    """Retry a request through transient network faults.

    The platform is reachable but the link to it is not always: connection
    timeouts and SSL recv failures both showed up mid-run and killed a submit
    that had hours of validation riding on it. Auth and protocol errors are
    NOT retried -- only transport-level faults.
    """
    import time as _t
    last = None
    for attempt in range(6):
        try:
            return fn(*a, **kw)
        except (TokenError, KeplerError):
            raise
        except Exception as e:  # noqa: BLE001
            name = type(e).__name__
            msg = str(e)
            # curl_cffi raises HTTPError for transport faults too: (16) is an
            # HTTP/2 framing error and (56)/(52) are truncated reads.  Those are
            # the link, not the platform, and a submit must ride them out.
            transport = any(t in name for t in
                            ("Timeout", "ConnectionError", "SSLError", "ConnectTimeout"))
            transport = transport or ("curl: (" in msg and any(
                f"curl: ({c})" in msg for c in (16, 52, 55, 56, 92)))
            if not transport:
                raise
            last = e
            wait = min(60, 5 * (2 ** attempt))
            print(f"  (network {name}; retry {attempt + 1}/6 in {wait}s)")
            _t.sleep(wait)
    raise last


def _post(procedure, json_input, session=None):
    """POST a tRPC procedure, riding out the submit rate limit.

    finalize is rate limited to one send every ~20s and a delete counts, so an
    unlucky loop round dies on a 429 with a whole validation run riding on it.
    That is an infra flake, not a verdict, and it must not consume a round.
    """
    import time as _t
    _check_token_fresh()
    s = session or _session()
    body = {"0": _envelope(json_input)}
    for attempt in range(5):
        r = _retry_net(s.post, f"{BASE}/{procedure}?batch=1", data=json.dumps(body, separators=(",", ":")), headers=_headers(), timeout=120)
        if r.status_code == 401:
            raise TokenError("401 unauthorized — token rejected (expired or wrong account)")
        try:
            return _unwrap(r)
        except KeplerError as e:
            if "TOO_MANY_REQUESTS" not in str(e) or attempt == 4:
                raise
            wait = 30 * (attempt + 1)
            print(f"  (rate limited; retry {attempt + 1}/4 in {wait}s)")
            _t.sleep(wait)
    raise KeplerError("rate limited five times running")


def _get(procedure, json_input, session=None, index=0):
    _check_token_fresh()
    s = session or _session()
    inp = {"0": _envelope(json_input)}
    url = f"{BASE}/{procedure}?batch=1&input={quote(json.dumps(inp, separators=(",", ":")))}"
    r = _retry_net(s.get, url, headers=_headers(json_body=False), timeout=120)
    if r.status_code == 401:
        raise TokenError("401 unauthorized — token rejected (expired or wrong account)")
    return _unwrap(r, index)


# ---- public API -----------------------------------------------------------

def pitch(idea):
    """Idea check. Returns {'decision': 'Accept'|..., 'review': '...'}."""
    return _post("kepler.tasks.pitch", {"idea": idea})


def issue_upload():
    """Returns {'uploadId', 'uploadUrl', 'maxBytes'}."""
    return _post("kepler.tasks.issueUpload", None)


def put_zip(upload_url, zip_path):
    """PUT the bundle to the signed GCS URL. The Content-Type must match what the
    server signed with (SignedHeaders=content-type;host). Default application/zip;
    override with KEPLER_UPLOAD_CONTENT_TYPE if you get 403 SignatureDoesNotMatch."""
    data = Path(zip_path).read_bytes()
    s = _session()
    r = _retry_net(s.put, upload_url, data=data, headers={"Content-Type": UPLOAD_CT}, timeout=300)
    if r.status_code not in (200, 201):
        raise KeplerError(f"upload PUT failed HTTP {r.status_code}: {r.text[:300]}")
    return r.status_code


def finalize(upload_id, task_name, category, labels):
    """Submit for validation. Returns {'submissionId', 'structureOk', 'findings'}."""
    return _post("kepler.tasks.finalize", {
        "uploadId": upload_id,
        "taskName": task_name,
        "category": category,
        "labels": labels,
    })


def submit(zip_path, task_name, category, labels):
    """Full submit flow: issueUpload -> PUT zip -> finalize. Returns finalize result."""
    up = issue_upload()
    max_bytes = up.get("maxBytes")
    size = Path(zip_path).stat().st_size
    if max_bytes and size > max_bytes:
        raise KeplerError(f"zip {size} bytes exceeds maxBytes {max_bytes}")
    put_zip(up["uploadUrl"], zip_path)
    return finalize(up["uploadId"], task_name, category, labels)


def get(submission_id, view_as_expert=False):
    """Full task record incl pipeline stages and status."""
    return _get("kepler.tasks.get", {"submissionId": submission_id, "viewAsExpert": view_as_expert})


def delete(submission_id):
    return _post("kepler.tasks.delete", {"submissionId": submission_id})


def list_mine():
    """List the caller's tasks. Batched with kepler.me; listMine is index 1."""
    _check_token_fresh()
    s = _session()
    inp = {
        "0": {"json": None, "meta": {"values": ["undefined"], "v": 1}},
        "1": {"json": None, "meta": {"values": ["undefined"], "v": 1}},
    }
    url = f"{BASE}/kepler.me,kepler.tasks.listMine?batch=1&input={quote(json.dumps(inp, separators=(",", ":")))}"
    r = _retry_net(s.get, url, headers=_headers(json_body=False), timeout=120)
    if r.status_code == 401:
        raise TokenError("401 unauthorized")
    return _unwrap(r, index=1)


# ---- CLI ------------------------------------------------------------------

def _main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "whoami":
        print(json.dumps(token_meta(), indent=2))
    elif cmd == "pitch":
        print(json.dumps(pitch(sys.argv[2]), indent=2))
    elif cmd == "list":
        print(json.dumps(list_mine(), indent=2))
    elif cmd == "status":
        print(json.dumps(get(sys.argv[2]), indent=2))
    elif cmd == "delete":
        print(json.dumps(delete(sys.argv[2]), indent=2))
    elif cmd == "submit":
        zip_path, name, category, labels = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5].split(",")
        print(json.dumps(submit(zip_path, name, category, labels), indent=2))
    else:
        print(f"unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    _main()
