#!/usr/bin/env python3
"""Resilient watcher for pane-emit. Survives token expiry and network timeouts:
it logs the problem and keeps retrying instead of exiting, so it resumes on its
own the moment the token bridge pushes a fresh token."""
import sys, time, os
sys.path.insert(0, '/home/osboxes/Downloads/afterquery_kepler/kepler-tools')
import kepler_api as K

SID = 'UcqeNU8AtyFlBCu22Y1t'
LOG = '/home/osboxes/Downloads/afterquery_kepler/task-src/pane-emit/status.log'
TERMINAL = ('Needs Review', 'Approved', 'Validation Failed', 'Rejected')


def say(msg):
    with open(LOG, 'a') as fh:
        fh.write('%s %s\n' % (time.strftime('%H:%M:%S'), msg))


quiet = 0
for _ in range(400):
    try:
        r = K.get(SID)
    except Exception as exc:
        quiet += 1
        if quiet in (1, 4, 12) or quiet % 24 == 0:
            say('unreachable (%s) — will keep retrying' % str(exc)[:90])
        time.sleep(300)
        continue
    quiet = 0
    p = r.get('pipeline') or {}
    st = ' '.join('%s:%s' % (k, v.get('status'))
                  for k, v in p.items() if isinstance(v, dict))
    status = r.get('status')
    say('%s | %s' % (status, st))
    for k, v in p.items():
        if isinstance(v, dict) and v.get('status') == 'failed':
            say('   FAILED %s kind=%s err=%s'
                % (k, v.get('failureKind'), str(v.get('error'))[:300]))
    dp = p.get('difficultyProbe') or {}
    if dp.get('passCount') is not None:
        say('   difficulty passCount=%s of %s applicable'
            % (dp.get('passCount'), dp.get('applicableTrials')))
    if status in TERMINAL:
        say('TERMINAL: %s' % status)
        break
    time.sleep(300)
