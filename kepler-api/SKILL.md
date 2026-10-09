---
name: kepler-api
description: Automate the AfterQuery Kepler pipeline via the tRPC API — idea check, submit, live status polling, and the delete+rebuild+resubmit loop until a task passes. Uses a live token from the browser-extension token bridge in kepler-tools/.
---

# Kepler API — SKILL

**pipeline position:** wraps submit/track/iterate. used by kepler-submit for the actual API calls,
and for the automated loop. tooling lives in `kepler-tools/`.

automate the whole submit → validate → iterate cycle instead of clicking the web UI.

## auth (live token bridge)
the API uses a short-lived (~1h) Firebase bearer token, captured automatically. server runs on the
**VPS** (public IP), extension runs in the **local browser** and pushes to the VPS.
1. run the token server under **PM2** (always-on, autorestart, boot; binds 0.0.0.0 + shared secret):
   `cd kepler-tools && pm2 start ecosystem.config.js --update-env && pm2 save`
   (writes `kepler-tools/token.txt` live; `pm2 logs kepler-token-server` to watch writes).
   open inbound TCP 47615 in the VPS provider's cloud firewall (host ufw is inactive).
2. load `kepler-tools/token_bridge_extension/` as an unpacked chrome extension; in the popup set the
   server URL to `http://<vps-ip>:47615` and the **shared secret** = `KEPLER_TOKEN_SECRET`, save.
   the VPS IP is also hard-listed in `manifest.json` host_permissions — update there if it changes.
   (more secure alternative: an SSH tunnel + loopback bind instead of a public port.)
3. sign in on experts.afterquery.com — the extension pushes fresh tokens on every call + each minute.
- check it: `python3 kepler-tools/kepler_api.py whoami` prints email + minutes-left.
- the client refuses to run on an expired token. `token.txt` is a live credential — never commit it.

## the endpoints (client: `kepler-tools/kepler_api.py`)
- `pitch(idea)` → `kepler.tasks.pitch` — idea check, returns `{decision, review}` (advisory).
- `issue_upload()` → `kepler.tasks.issueUpload` — signed GCS upload URL `{uploadId, uploadUrl, maxBytes}`.
- `put_zip(url, zip)` — PUT the bundle. content-type must match the signed one (default `application/zip`;
  override `KEPLER_UPLOAD_CONTENT_TYPE` on `403 SignatureDoesNotMatch`).
- `finalize(uploadId, name, category, labels)` → `kepler.tasks.finalize` — submit; returns `{submissionId, structureOk, findings}`.
- `get(submissionId)` → `kepler.tasks.get` — full record incl `pipeline` stages + `status`.
- `delete(submissionId)` → `kepler.tasks.delete`.
- `list_mine()` → `kepler.tasks.listMine`.
tRPC batch envelope: `{"0":{"json":<payload>}}`; a no-input procedure needs superjson
`{"json":null,"meta":{"values":["undefined"],"v":1}}`. responses unwrap at `[0].result.data.json`.

## the loop (orchestrator: `kepler-tools/kepler_run.py`)
```bash
python3 kepler-tools/kepler_run.py loop \
  --zip tasks/<slug>/<slug>.zip --name <slug> --category <Cat> --labels a,b \
  --src task-src/<slug> [--idea "..."] [--rebuild-cmd "..."] [--max-rounds 5] [--interval 10]
```
per round: submit → poll pipeline live (structure, ai_check, similarity, oracle_nop, quality,
cheat_probe, difficulty_probe, run_audit) → on pass stop (awaiting human review) → on **infra**
failure resubmit (no count) → on **verdict** failure save the reason, run rebuild hook, delete failed
task, resubmit.

**status-check cadence (required): schedule the status check every 5 minutes (300s), not faster.**
report a compact stage summary to the user on each 5-min tick, and immediately on any terminal state
(pass/fail). don't poll every 30s (wastes the session token) and don't go silent until done. the
`--interval` flag is the loop's internal retry cadence and is separate from this user-facing 5-min
report cadence. implement with a background 300s poller (e.g. `poll_status.py` on a sleep-300 loop)
or ScheduleWakeup/CronCreate at 300s; stop once terminal. see [[report-interval-5min]].

**failed-task handling:** the reason is always written to `<src>/last_failure.md` (+ appended to
`<src>/failures.log`) BEFORE any delete, so feedback survives removal. a failed task is deleted when
the loop rebuilds and resubmits; if the loop stops (no rebuild path or the hook failed) it keeps the
task for inspection unless you pass `--delete-on-fail`. delete one manually with
`python3 kepler_api.py delete <submissionId>`.

## rebuild hooks
- **ai_check** (default `rebuild_aicheck.py`): humanize instruction + integrity-check that the exact
  tokens and suffix survived (the humanizer scrambles placeholders and can invert meaning). refuses
  to ship a corrupted bundle; writes `instruction.humanized.review.md` for manual correction.
  ALWAYS eyeball an ai_check auto-rebuild — see [[kepler-instruction]].
- **oracle_nop / quality / difficulty / cheat_probe**: need real task redesign. supply `--rebuild-cmd`
  (an agent or script that updates the zip) or the loop stops and hands you the feedback — route it
  back through [[kepler-verifier]] / [[kepler-idea]] / [[kepler-instruction]] as the failure maps.
- **anchoring is not a loop-fixable failure.** if the feedback says the task reads as synthetic,
  simulated, or not real work, do not resubmit a patched zip — the loop will burn rounds on a task
  aimed at an invented world. stop it, go to [[kepler-idea]] step 1b, re-aim at a real tool.
  cheapest insurance is running `anchor_check.py` before the first submit, not after a verdict:
  ```bash
  python3 kepler-tools/anchor_check.py task-src/<slug> --tools <comma,separated,tools>
  ```

## layout convention
- editable bundle source: `task-src/<slug>/` (+ optional `required_tokens.txt` guard for the ai_check hook).
- deliverable: `tasks/<slug>/<slug>.zip` + `SUBMISSION.md`. the loop rebuilds the zip from source.
