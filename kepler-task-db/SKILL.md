---
name: kepler-task-db
description: Persistent data store for Kepler task authoring. Tracks scored ideas, submitted tasks and their pipeline status, and an archive of completed bundles. Update when scoring ideas and after submitting.
---

# Kepler Task DB — SKILL

persistent data across all tasks: idea log, submitted tasks, and an archive of completed bundles.
prevents duplicate ideas (similarity is a pipeline gate) and tracks what shipped.

---

## files

| File | Purpose |
|---|---|
| `ideas.md` | every scored idea. status: candidate / building / dropped / submitted |
| `submitted.md` | slug, domain, task/conversation id, and pipeline status for each submission |
| `completed/` | archived bundle manifest (task.toml + instruction.md) per shipped task, named `<slug>.md` |

## when to update

### after scoring an idea (kepler-idea)
- append a row to `ideas.md`: slug, domain, payout tier, difficulty/verifiability/specificity
  scores, one-sentence verifier shape, status = candidate.
- prefix the verifier-shape cell with the real-tool anchor, so it stays greppable:
  `anchor: memcached 1.6.21 + text protocol | verifier compares ...`. an idea dropped for having no
  real anchor gets `dropped` plus that reason — the same abstract idea comes back otherwise.

### when starting / dropping a build
- flip the idea status to `building` or `dropped` (with a one-line reason if dropped).

### after submitting (kepler-submit)
- add a row to `submitted.md`: slug, domain, task id, submit date, status = submitted.
- copy the final `task.toml` + `instruction.md` into `completed/<slug>.md`.
- flip the idea status to `submitted`.

### as pipeline stages report back
- update the `submitted.md` status (e.g. passed-difficulty, rejected-<stage>, approved-paid) so the
  history stays accurate and rejected angles are not retried blindly.
- live status is available from the API instead of manual tracking — [[kepler-api]]:
  `python3 kepler-tools/kepler_api.py list` (all your tasks) or `status <submissionId>` (one task's
  pipeline). sync `submitted.md` from that.

## why it matters
- similarity is a hard gate — knowing what you've already submitted avoids near-duplicate rejects.
- the archive lets you reuse proven environment scaffolding without copying an existing task's structure.
