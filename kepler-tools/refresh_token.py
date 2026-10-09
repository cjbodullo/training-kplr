#!/usr/bin/env python3
"""
mint a fresh Firebase ID token from the refresh token in credentials.md and write it to
token.txt, so the API client works without the browser extension.

reads credentials.md, never prints the secrets.
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREDS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "credentials.md"
OUT = Path(__file__).with_name("token.txt")


def field(text, name):
    m = re.search(rf"^\s*{name}\s*=\s*(\S+)\s*$", text, re.M)
    if not m:
        raise SystemExit("credentials file has no %s" % name)
    return m.group(1)


def main():
    text = CREDS.read_text()
    api_key = field(text, "apiKey")
    refresh = field(text, "refreshToken")
    email = field(text, "email")

    url = "https://securetoken.googleapis.com/v1/token?key=" + urllib.parse.quote(api_key)
    body = urllib.parse.urlencode({"grant_type": "refresh_token",
                                   "refresh_token": refresh}).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type":
                                          "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise SystemExit("token exchange failed (%s): %s" % (exc.code, detail))

    tok = data.get("id_token") or data.get("access_token")
    if not tok:
        raise SystemExit("no id_token in the response: %s" % sorted(data))
    OUT.write_text(tok)
    OUT.chmod(0o600)
    print("wrote %s (%d chars), expires in %ss, for %s"
          % (OUT, len(tok), data.get("expires_in", "?"), email))


if __name__ == "__main__":
    main()
