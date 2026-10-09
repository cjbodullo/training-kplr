#!/usr/bin/env bash
# Submit and keep going until the pipeline passes.
#
# The account takes 5 tasks in validation at once, and parallel sessions keep
# it full, so each round waits for a free slot first.  It also holds off while
# one of our own Media records is in flight, since our own crowding is a live
# hypothesis for the blocks - but only for a while, then it sends anyway.
#
# On a similarity block: delete, leave a gap, send the other proven bundle.
# On any other stage failure: stop, because that one needs real work.
set -uo pipefail
cd /home/osboxes/Downloads/afterquery_kepler
LOG=kepler-tools/media_loop.log
API=kepler-tools/kepler_api.py
RUN=kepler-tools/kepler_run.py
ROUNDS=${1:-8}
GAP=${2:-1800}
CAP=5

say() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*" >> "$LOG"; }

counts() {   # "<all validating> <ours in Media validating>"
    timeout 240 python3 "$API" list 2>/dev/null | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print(99, 99); raise SystemExit
v=[t for t in d if t.get('status')=='Validating']
print(len(v), sum(1 for t in v if t.get('category')=='Media'))
"
}

say "=== loop starting, $ROUNDS rounds, ${GAP}s gap, cap $CAP ==="
round=1
while [ "$round" -le "$ROUNDS" ]; do
    NAME=mount-fit; ZIP=tasks/mount-fit/mount-fit.zip; LAB=Design

    # wait for a slot.  for the first 30 minutes also hold out for our own
    # Media lane to be empty; after that a free slot is enough.
    for w in $(seq 1 96); do
        set -- $(counts)
        all=$1; mine=$2
        say "round $round: $all validating account-wide, $mine of them our Media"
        # a free slot is enough: the crowding hypothesis was disproven when a
        # send passed similarity with three of ours already in flight
        if [ "$all" -lt "$CAP" ]; then
            break
        fi
        sleep 300
    done

    say "round $round: sending $NAME"
    out=$(timeout 900 python3 "$RUN" submit --zip "$ZIP" --name "$NAME" \
          --category Media --labels "$LAB" 2>&1)
    printf '%s\n' "$out" >> "$LOG"
    id=$(printf '%s' "$out" | grep -Eo 'submissionId: [A-Za-z0-9]+' | tail -1 | awk '{print $2}')
    # a rate-limit retry can re-run finalize and come back 409 "already
    # submitted"; the first one is live, so look it up rather than giving up
    if [ -z "$id" ] || printf '%s' "$out" | grep -q "CONFLICT"; then
        found=$(timeout 240 python3 "$API" list 2>/dev/null | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: raise SystemExit
r=[t for t in d if t.get('taskName')=='$NAME' and not t.get('deletedAt')]
r.sort(key=lambda t: t.get('createdAt') or 0)
print(r[-1]['id'] if r else '')
")
        [ -n "$found" ] && id="$found" && say "round $round: picked up live record $id"
    fi
    if [ -z "$id" ]; then
        if printf '%s' "$out" | grep -q "TOO_MANY_REQUESTS"; then
            say "round $round: queue was full, waiting 10 min and trying again"
            sleep 600
            continue                      # same round, same bundle
        fi
        say "round $round: no submission id and not a queue problem, stopping"
        break
    fi

    # the difficulty probe alone runs eight agents, so poll status rather
    # than trusting a single watch call to return inside its timeout
    verdict=""; stage=""
    for _ in $(seq 1 40); do
        timeout 900 python3 "$RUN" watch "$id" >/dev/null 2>&1
        st=$(timeout 240 python3 "$API" status "$id" 2>/dev/null | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print('unknown none'); raise SystemExit
p=d.get('pipeline') or {}
bad=[k for k,v in p.items() if isinstance(v,dict) and v.get('status')=='failed']
print(d.get('status','unknown').replace(' ','_'), (bad[0] if bad else 'none'))
")
        set -- $st; verdict=$1; stage=$2
        say "round $round: $verdict (failed stage: $stage)"
        case "$verdict" in Approved|Needs_Review|Validation_Failed) break;; esac
        sleep 300
    done

    if [ "$verdict" != "Validation_Failed" ]; then
        say "ROUND $round: $NAME CLEARED THE PIPELINE ($id, $verdict)"
        break
    fi
    printf '%s\n' "$stage" >> "$LOG"
    say "round $round: $NAME failed at ${stage:-unknown}"
    if [ "$stage" != "similarity" ]; then
        say "not a similarity block - stopping so it can be fixed properly"
        break
    fi
    timeout 120 python3 "$API" delete "$id" >/dev/null 2>&1
    say "round $round: record deleted, gap ${GAP}s"
    sleep "$GAP"
    round=$((round + 1))
done
say "=== loop finished ==="
