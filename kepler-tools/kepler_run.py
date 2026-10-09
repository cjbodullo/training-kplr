#!/usr/bin/env python3
"""
Kepler automation orchestrator.

Drives the full loop against the AfterQuery API: (optional) idea check -> submit
-> poll the validation pipeline live -> on a verdict failure, delete the failed
task, run a rebuild hook that updates the zip, and resubmit. Repeats until the
automated pipeline passes or --max-rounds is hit. Infra flakes are retried without
counting.

Commands:
  idea "<one-sentence pitch>"
  submit  --zip Z --name N --category C --labels a,b
  watch   <submissionId>
  loop    --zip Z --name N --category C --labels a,b --src DIR
          [--idea "..."] [--force] [--rebuild-cmd "..."] [--delete-on-fail] [--max-rounds 5] [--interval 10]

On a verdict failure the reason is always saved to <src>/last_failure.md + <src>/failures.log
BEFORE anything is deleted. A failed task is deleted when the loop rebuilds and resubmits; when the
loop stops (no rebuild path / rebuild failed) the task is kept for inspection unless --delete-on-fail.

The rebuild hook must update --zip in place and exit 0. For an ai_check failure
with no --rebuild-cmd, rebuild_aicheck.py is used automatically (humanize +
integrity check); other stages need a hook you supply (real task redesign), or
the loop stops and hands you the feedback.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kepler_api as api

HERE = Path(__file__).resolve().parent

# (response key, human label)
STAGES = [
    ("structure", "structure"),
    ("aiCheck", "ai_check"),
    ("similarity", "similarity"),
    ("oracleNop", "oracle_nop"),
    ("qualityCheck", "quality"),
    ("cheatProbe", "cheat_probe"),
    ("difficultyProbe", "difficulty_probe"),
    ("trajectoryReview", "run_audit"),
]


def _stage_status(pipeline, key):
    v = pipeline.get(key)
    if v is None:
        return "pending"
    if isinstance(v, dict):
        return v.get("status") or "running"
    return str(v)


def watch(submission_id, interval=10, quiet=False):
    """Poll until terminal.

    Returns {'result': passed|failed|infra, 'stage', 'reason', 'sim_cleared'}.
    sim_cleared says whether the similarity stage ever reached passed on THIS
    submission, which decides how long the infra retry has to wait before it
    may resubmit -- see the note on the infra branch below.
    """
    last = None
    sim_cleared = False
    net_fails = 0
    max_net_fails = 60
    while True:
        try:
            d = api.get(submission_id)
        except api.TokenError as e:
            # long stages (e.g. difficulty probe) can outlast a token; wait for the
            # extension to push a fresh one instead of dying.
            print(f"  (token stale: {e}); waiting for refresh…")
            time.sleep(interval)
            continue
        except Exception as e:  # noqa: BLE001
            # A transient network blip must not kill a watch that has hours of
            # probe time riding on it -- the pipeline keeps running server side,
            # so back off and re-poll rather than dropping the submission.
            net_fails += 1
            if net_fails >= max_net_fails:
                print(f"  ({net_fails} consecutive poll failures; giving up: {e!r})")
                raise
            backoff = min(300, interval * (2 ** min(net_fails, 5)))
            print(f"  (poll failed: {type(e).__name__}; retry {net_fails}/{max_net_fails} "
                  f"in {backoff}s)")
            time.sleep(backoff)
            continue
        net_fails = 0
        p = d.get("pipeline") or {}
        statuses = {key: _stage_status(p, key) for key, _ in STAGES}
        if statuses.get("similarity") == "passed":
            sim_cleared = True
        line = "  ".join(f"{label}:{statuses[key]}" for key, label in STAGES)
        if line != last and not quiet:
            print(line)
            last = line

        if p.get("stage") == "failed":
            kind = p.get("failureKind")
            return {
                "result": "infra" if kind == "infra" else "failed",
                "stage": p.get("failedStage"),
                "reason": p.get("failureReason"),
                "sim_cleared": sim_cleared,
            }
        if d.get("status") == "Approved":
            return {"result": "passed", "stage": None, "reason": "approved"}
        # all automated stages passed -> automated pipeline is green (awaiting human review)
        if all(statuses[key] == "passed" for key, _ in STAGES):
            return {"result": "passed", "stage": None, "reason": "automated pipeline passed"}
        time.sleep(interval)


def cmd_idea(args):
    r = api.pitch(args.idea)
    print("decision:", r.get("decision"))
    print("\n--- review ---\n" + r.get("review", ""))
    return r


def cmd_submit(args):
    fin = api.submit(args.zip, args.name, args.category, args.labels.split(","))
    print("submissionId:", fin.get("submissionId"), "| structureOk:", fin.get("structureOk"))
    for f in fin.get("findings", []):
        print(f"  finding [{f.get('level')}] {f.get('code')}: {f.get('message')}")
    return fin


def cmd_watch(args):
    out = watch(args.submission_id, interval=args.interval)
    print("\noutcome:", out)
    return out


def record_failure(args, submission_id, out, full=None):
    """Persist the failure feedback BEFORE any delete, so it survives task removal.
    Writes <src>/last_failure.md (latest) and appends to <src>/failures.log."""
    if not args.src:
        return
    src = Path(args.src)
    body = (
        f"# last failure\n\n"
        f"- submissionId: {submission_id}\n"
        f"- stage: {out.get('stage')}\n"
        f"- result: {out.get('result')}\n\n"
        f"## reason\n{out.get('reason')}\n"
    )
    if full:
        import json as _json
        body += f"\n## raw pipeline\n```json\n{_json.dumps(full, indent=2)[:4000]}\n```\n"
    try:
        (src / "last_failure.md").write_text(body)
        with open(src / "failures.log", "a") as f:
            f.write(f"{submission_id}\t{out.get('stage')}\t{str(out.get('reason'))[:300]}\n")
        print(f"  feedback saved -> {src/'last_failure.md'}")
    except Exception as e:
        print(f"  (could not save feedback: {e})")


def cmd_loop(args):
    if args.idea:
        r = api.pitch(args.idea)
        print("idea decision:", r.get("decision"))
        if str(r.get("decision", "")).lower() != "accept" and not args.force:
            print("idea not accepted; not submitting (use --force to override).\n\n--- review ---\n" + r.get("review", ""))
            return
    labels = args.labels.split(",")
    # infra flakes must NOT consume a verdict round -- they are the harness
    # failing, not the task. They get their own (generous) ceiling so a
    # permanently sick stage cannot spin forever.
    if getattr(args, "start_delay", 0):
        print(f"holding {args.start_delay}s before the first submit "
              f"(index turnover after a delete).")
        time.sleep(args.start_delay)
    rnd = 0
    sim_retries = 0
    infra_retries = 0
    max_infra_retries = max(12, args.max_rounds * 4)
    while rnd < args.max_rounds:
        rnd += 1
        print(f"\n=== round {rnd}/{args.max_rounds}: submitting {args.zip} ===")
        fin = api.submit(args.zip, args.name, args.category, labels)
        sid = fin.get("submissionId")
        print("submissionId:", sid, "| structureOk:", fin.get("structureOk"))
        for f in fin.get("findings", []):
            print(f"  finding [{f.get('level')}] {f.get('code')}: {f.get('message')}")
        if not sid:
            print("no submissionId returned; aborting."); return

        out = watch(sid, interval=args.interval)
        if out["result"] == "passed":
            print(f"\n✅ PASSED automated pipeline ({out['reason']}). submissionId: {sid}")
            print("now awaiting human review — nothing more to automate.")
            return sid
        if out["result"] == "infra":
            infra_retries += 1
            rnd -= 1  # genuinely does not count against the verdict rounds
            print(f"\n⚙ infra flake at {out['stage']}; deleting and resubmitting "
                  f"(infra retry {infra_retries}/{max_infra_retries}, "
                  f"verdict round still {rnd + 1}/{args.max_rounds}).")
            api.delete(sid)
            if infra_retries >= max_infra_retries:
                print(f"\n{max_infra_retries} infra flakes without a verdict — "
                      f"the harness looks sick. Stopping with nothing submitted; "
                      f"resubmit by hand when it recovers.")
                return
            # back off before hammering a platform that is already struggling
            # measured 2026-07-31 on unwind-order: seven consecutive ai_check
            # errors (runId null) under 60-180s delete-and-resubmit churn, which
            # cleared on the first submit after a 25 minute quiet period. The
            # churn is itself a cause, so the ramp starts slow and stays slow.
            backoff = min(1500, 300 * infra_retries)
            # If similarity had ALREADY passed on the record we just deleted,
            # a short backoff converts a healthy submission into a similarity
            # block: the resubmission is judged against its own freshly deleted
            # predecessor. Measured live on trip-matrix 2026-08-07 -- same zip,
            # five minutes apart, similarity passed and then failed. So when the
            # deleted record had cleared similarity, hold for the similarity gap
            # instead, which is what that gap is for.
            if out.get("sim_cleared"):
                gap = max(backoff, getattr(args, "similarity_gap", 0) or 3600)
                if gap > backoff:
                    print(f"  the deleted record had already passed similarity, "
                          f"so holding {gap}s rather than {backoff}s to avoid "
                          f"blocking against its ghost.")
                backoff = gap
            print(f"  waiting {backoff}s before resubmitting.")
            time.sleep(backoff)
            continue

        print(f"\n❌ FAILED at {out['stage']}: {out['reason']}")
        # always persist feedback first, so it survives if we delete the task.
        record_failure(args, sid, out)

        # A similarity block right after deleting a predecessor is usually the
        # ghost of that predecessor, not a real twin -- measured on
        # theme-resolve 2026-08-04, where v1 PASSED similarity and a near
        # identical v2 was blocked six minutes after v1 was deleted, while four
        # other submissions in the same window passed. The remedy is the gap,
        # not a re-skin: subject, industry, apparatus and skeleton are all
        # measured not to move this gate. So delete, wait for the index to turn
        # over, and resubmit the SAME zip. It does not consume a verdict round.
        if out["stage"] == "similarity" and sim_retries < args.similarity_retries:
            sim_retries += 1
            rnd -= 1
            print(f"deleting {sid} and holding the identical zip for "
                  f"{args.similarity_gap}s (similarity retry {sim_retries}/"
                  f"{args.similarity_retries}, verdict round still "
                  f"{rnd + 1}/{args.max_rounds}).")
            api.delete(sid)
            time.sleep(args.similarity_gap)
            continue

        def maybe_delete(reason_msg):
            """Delete the failed task when told to (--delete-on-fail), else keep it."""
            if args.delete_on_fail:
                print(f"deleting failed task {sid} ({reason_msg}).")
                api.delete(sid)
            else:
                print(f"failed task {sid} left in place ({reason_msg}); --delete-on-fail to remove it.")

        cmd = args.rebuild_cmd
        if not cmd and out["stage"] == "ai_check":
            if not args.src:
                print("ai_check failed but --src not given; cannot auto-rebuild. stopping.")
                maybe_delete("stopping"); return
            cmd = f'python3 "{HERE}/rebuild_aicheck.py" --src "{args.src}" --zip "{args.zip}"'
        if not cmd:
            print("no rebuild hook for this stage (needs real task redesign). feedback saved above.")
            maybe_delete("stopping for manual redesign"); return
        print("running rebuild hook:", cmd)
        rc = subprocess.call(cmd, shell=True)
        if rc != 0:
            print(f"rebuild hook exited {rc} — NOT resubmitting (bundle may be unfixed).")
            maybe_delete("stopping; rebuild failed"); return
        # rebuild succeeded -> always delete the old failed task before resubmitting.
        print(f"rebuild ok; deleting failed task {sid} and resubmitting.")
        api.delete(sid)
    print(f"\nreached max-rounds ({args.max_rounds}) without passing.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("idea"); p.add_argument("idea"); p.set_defaults(fn=cmd_idea)

    p = sub.add_parser("submit")
    p.add_argument("--zip", required=True); p.add_argument("--name", required=True)
    p.add_argument("--category", required=True); p.add_argument("--labels", required=True)
    p.set_defaults(fn=cmd_submit)

    p = sub.add_parser("watch")
    p.add_argument("submission_id"); p.add_argument("--interval", type=int, default=10)
    p.set_defaults(fn=cmd_watch)

    p = sub.add_parser("loop")
    p.add_argument("--zip", required=True); p.add_argument("--name", required=True)
    p.add_argument("--category", required=True); p.add_argument("--labels", required=True)
    p.add_argument("--src", default=None, help="task source dir (for rebuild hooks)")
    p.add_argument("--idea", default=None); p.add_argument("--force", action="store_true")
    p.add_argument("--rebuild-cmd", default=None, dest="rebuild_cmd")
    p.add_argument("--delete-on-fail", action="store_true", dest="delete_on_fail",
                   help="delete the failed task even when stopping (no rebuild). feedback is saved first.")
    p.add_argument("--max-rounds", type=int, default=5); p.add_argument("--interval", type=int, default=10)
    p.add_argument("--similarity-gap", type=int, default=5400,
                   dest="similarity_gap",
                   help="seconds to hold the identical zip after a similarity "
                        "block before resubmitting (index turnover)")
    p.add_argument("--similarity-retries", type=int, default=3,
                   dest="similarity_retries",
                   help="how many times a similarity block may be retried with "
                        "the same zip before it counts as a real twin")
    p.add_argument("--start-delay", type=int, default=0, dest="start_delay",
                   help="seconds to wait before the first submit")
    p.set_defaults(fn=cmd_loop)

    args = ap.parse_args()
    try:
        args.fn(args)
    except api.TokenError as e:
        print("TOKEN ERROR:", e); sys.exit(3)
    except api.KeplerError as e:
        print("API ERROR:", e); sys.exit(4)


if __name__ == "__main__":
    main()
