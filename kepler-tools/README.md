# kepler-tools — AfterQuery Kepler automation

End-to-end automation for the Kepler task pipeline on experts.afterquery.com:
idea check → submit → live status polling → on failure, delete + rebuild + resubmit, looping
until the automated pipeline passes.

## Pieces

| File | Role |
|---|---|
| `token_bridge_extension/` | Chrome extension: captures your AfterQuery session token and POSTs it to the token server. Server URL is set in the popup. |
| `token_write.js` | Node token server. Receives the token, writes `token.txt` (raw JWT) + `token.json` (meta) live. |
| `token.txt` | The live bearer token. Refreshed automatically as you use the site. Read by the client. |
| `kepler_api.py` | Python client for the tRPC API (pitch, issueUpload, put_zip, finalize, get, delete, list_mine). |
| `kepler_run.py` | Orchestrator: `idea`, `submit`, `watch`, `loop`. |
| `bundle.py` | Zips a task source dir into a deliverable (excludes SUBMISSION.md / required_tokens.txt / zips / pyc). |
| `rebuild_aicheck.py` | Default rebuild hook for an ai_check failure: humanize instruction + integrity-check tokens + rezip. |
| `anchor_check.py` | Real-world tool anchoring scan: are the tools the instruction names installed / driven / graded, any version drift, any generic placeholder phrasing. Advisory; run before submit. |

## Topology

The **token server runs on the VPS** (public IP, e.g. `109.199.116.56`); the **extension runs in
your local browser** and pushes captured tokens to the VPS over `http://<vps-ip>:47615`. So the
server binds `0.0.0.0` and is protected by a **shared secret** (a public token endpoint must not be
open). The Python client + loop also run on the VPS and read `token.txt` directly.

## One-time setup

1. **Token server (via PM2, on the VPS)** — bound to all interfaces, secret required:
   ```bash
   npm install -g pm2                     # once
   cd kepler-tools
   # ecosystem.config.js already sets KEPLER_TOKEN_HOST=0.0.0.0 and a KEPLER_TOKEN_SECRET.
   # change the secret if you like:  openssl rand -hex 24
   pm2 start ecosystem.config.js --update-env   # start (127.0.0.1 ⨯ — now 0.0.0.0:47615)
   pm2 save                                       # persist across reboots
   sudo env PATH=$PATH:/usr/bin pm2 startup systemd -u $USER --hp $HOME   # boot on restart
   # pm2 logs kepler-token-server                 # tail (token writes print here)
   ```
2. **Open the port** — this host isn't firewalling it (ufw inactive), but your **VPS provider's
   cloud firewall / security group must allow inbound TCP 47615**. Test from your laptop:
   `curl http://<vps-ip>:47615/ping` → `{"ok":true,"app":"aqbot"}`.
3. **Extension** — `chrome://extensions` → Developer mode → Load unpacked → `token_bridge_extension/`.
   In the popup set **Token server URL** = `http://<vps-ip>:47615` and **Shared secret** = the value
   of `KEPLER_TOKEN_SECRET`, Save. (The VPS IP is also hard-listed in `manifest.json`
   `host_permissions` — update it there if your IP changes.)
4. **Sign in** — open `experts.afterquery.com`, sign in with Google. The extension pushes your token
   on every API call and every minute, so `token.txt` on the VPS stays fresh (~1h JWTs).
5. **Deps (VPS)** — `pip install --user --break-system-packages curl_cffi` (client + humanizer).

Verify (on the VPS): `python3 kepler_api.py whoami` should print your email and minutes-left.

### Security

- The endpoint holds a **live auth token**. Keep the secret non-trivial. `/ping` is open (for
  reachability); `/token` and `/status` require `x-aq-secret`.
- Even better than a public port: an **SSH tunnel** — `ssh -R 47615:localhost:47615 you@vps` (or a
  local `-L` tunnel) — then point the extension at `http://127.0.0.1:47615` and keep the server
  bound to loopback. Avoids exposing the port at all. Use this if you can.
- Never commit `token.txt` / `token.json`.

## Usage

```bash
# idea check (advisory)
python3 kepler_run.py idea "Given a minimal in-memory KV store with a broken transaction layer, ..."

# one-shot submit
python3 kepler_run.py submit --zip ../tasks/mvcc-snapshot-isolation/mvcc-snapshot-isolation.zip \
    --name mvcc-snapshot-isolation --category Software --labels Databases,Systems

# watch a submission's pipeline live
python3 kepler_run.py watch <submissionId>

# full auto loop: submit -> poll -> on fail delete+rebuild+resubmit until it passes
python3 kepler_run.py loop \
    --zip ../tasks/mvcc-snapshot-isolation/mvcc-snapshot-isolation.zip \
    --name mvcc-snapshot-isolation --category Software --labels Databases,Systems \
    --src ../task-src/mvcc-snapshot-isolation \
    --idea "..." --max-rounds 5
```

## What the loop automates (and what it can't)

- **structure / similarity / oracle_nop / quality / cheat_probe / difficulty_probe / run_audit** —
  polled live. On an **infra** failure it just resubmits (no count). On a **verdict** failure it
  prints the reason, deletes the task, runs the rebuild hook, and resubmits.
- **ai_check** — default rebuild hook is `rebuild_aicheck.py` (humanize + integrity check). The
  humanizer can scramble exact tokens or invert meaning, so the hook refuses to ship a bundle whose
  required tokens/suffix don't survive; it writes `instruction.humanized.review.md` for you to
  correct. **Always eyeball an ai_check auto-rebuild.**
- **difficulty / quality / oracle failures need real task redesign** — supply your own `--rebuild-cmd`
  (an agent or script that updates the zip), or the loop stops and hands you the feedback.
- **failed-task handling** — the reason is saved to `<src>/last_failure.md` (+ `failures.log`) before
  any delete. A failed task is deleted when the loop rebuilds+resubmits; if the loop stops it keeps
  the task for inspection unless `--delete-on-fail`. Manual delete: `python3 kepler_api.py delete <id>`.

## Notes

- `token.txt` holds a live credential — do not commit it. The loop reads it fresh on every call and
  refuses to run on an expired token.
- If the upload PUT returns `403 SignatureDoesNotMatch`, set
  `KEPLER_UPLOAD_CONTENT_TYPE=application/x-zip-compressed` (or `application/octet-stream`).
- Keep the task **source** under `task-src/<slug>/` and the **deliverable** zip under
  `tasks/<slug>/` — the loop rebuilds the zip from source.
