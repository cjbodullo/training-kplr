#!/usr/bin/env python3
"""Gap-aware resubmit for pane-emit v2.

v1 (ADxL19tAxDDrme8U36uf) failed difficulty_probe too_hard and was deleted at
~23:02 on 2026-07-30. A rebuild is ~90% identical to the version it replaces, so
resubmitting soon after a delete gets blocked at similarity by the deleted task
itself -- 20 minutes was measured as not enough. So this waits hours, not
minutes, then submits and watches.

It also survives the token bridge being asleep: the bearer token lasts about an
hour and is only refreshed while a browser is signed in on experts.afterquery.com,
so after the target time this keeps retrying until a usable token appears.

Deliberately does NOT auto delete-and-resubmit on a verdict failure. That is the
exact move the similarity gap forbids; a v3 needs its own long gap and its own
decision about what to change.
"""

import os
import sys
import time

sys.path.insert(0, '/home/osboxes/Downloads/afterquery_kepler/kepler-tools')
os.chdir('/home/osboxes/Downloads/afterquery_kepler')
import kepler_api as K

TARGET = 1785483337                      # 2026-07-31 03:35 local
ZIP = 'tasks/pane-emit/pane-emit.zip'
NAME = 'pane-emit'
CATEGORY = 'Software'
LABELS = ['Systems', 'Algorithms']
LOG = 'task-src/pane-emit/status.log'
SID_FILE = 'task-src/pane-emit/v2_submission_id.txt'
TERMINAL = ('Needs Review', 'Approved', 'Validation Failed', 'Rejected')


def say(msg):
    with open(LOG, 'a') as fh:
        fh.write('%s [v2] %s\n' % (time.strftime('%m-%d %H:%M:%S'), msg))


def submit():
    """Upload and finalize through the client's own flow. Returns a submissionId."""
    res = K.submit(ZIP, NAME, CATEGORY, LABELS)
    sid = res.get('submissionId')
    say('submitted %s structureOk=%s findings=%s'
        % (sid, res.get('structureOk'), res.get('findings')))
    return sid


def main():
    wait = TARGET - time.time()
    if wait > 0:
        say('holding %d min for the similarity gap after deleting v1' % (wait / 60))
        time.sleep(wait)

    sid = None
    for attempt in range(96):            # up to ~8h of retrying on auth
        try:
            sid = submit()
            break
        except Exception as exc:
            if attempt % 6 == 0:
                say('submit blocked (%s) - retrying' % str(exc)[:90])
            time.sleep(300)
    if not sid:
        say('gave up trying to submit')
        return 1
    with open(SID_FILE, 'w') as fh:
        fh.write(sid)

    quiet = 0
    for _ in range(400):
        try:
            r = K.get(sid)
        except Exception as exc:
            quiet += 1
            if quiet in (1, 6) or quiet % 24 == 0:
                say('unreachable (%s) - still retrying' % str(exc)[:80])
            time.sleep(300)
            continue
        quiet = 0
        p = r.get('pipeline') or {}
        st = ' '.join('%s:%s' % (k, v.get('status'))
                      for k, v in p.items() if isinstance(v, dict))
        say('%s | %s' % (r.get('status'), st))
        for k, v in p.items():
            if isinstance(v, dict) and v.get('status') == 'failed':
                say('   FAILED %s kind=%s err=%s'
                    % (k, v.get('failureKind'), str(v.get('error'))[:200]))
        dp = p.get('difficultyProbe') or {}
        if dp.get('passCount') is not None:
            say('   difficulty band=%s passCount=%s of %s'
                % (dp.get('band'), dp.get('passCount'), dp.get('nAttempts')))
        if r.get('status') in TERMINAL:
            say('TERMINAL: %s' % r.get('status'))
            break
        time.sleep(300)
    return 0


if __name__ == '__main__':
    sys.exit(main())
