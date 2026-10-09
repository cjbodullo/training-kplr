"""generate six weeks of asterisk queue_log from the true world, plus the plan week forecast.
usage: python3 gen_history.py OUTDIR"""
import datetime as dt
import heapq
import math
import os
import sys

import numpy as np
import world as W

EPOCH0 = dt.datetime(1970, 1, 1)
AGENTS = {"billing": ["PJSIP/%d" % n for n in range(2101, 2171)],
          "moving": ["PJSIP/%d" % n for n in range(2201, 2241)],
          "faults": ["PJSIP/%d" % n for n in range(2301, 2351)]}
XFER_EXT = "6002"
ENTRY_COUNT = {}   # (queue, block) -> [first attempts, repeat attempts] of fresh callers


def ep(d, secs):
    return (dt.datetime(d.year, d.month, d.day) - EPOCH0).total_seconds() + secs


class Log:
    def __init__(self):
        self.rows = []
        self.seq = 0

    def add(self, t, callid, q, agent, ev, *data):
        self.seq += 1
        self.rows.append((int(math.floor(t)), self.seq, "|".join([str(int(math.floor(t))), callid, q, agent, ev] + [str(x) for x in data])))


def callerids(rng, n):
    """caller ids leave pbx01 hashed (gdpr export): a stable token per number"""
    return ["H%010x" % x for x in rng.integers(0, 2 ** 40, n)]


def occ_mean(q, d, h, wrap):
    rng = np.random.default_rng(1)
    qs = W.QUICK_SHARE[q]
    t = qs * W.talk(rng, q, d, h, 4000, "quick").mean() + (1 - qs) * W.talk(rng, q, d, h, 4000, "complex").mean()
    if q == "billing":
        t = (1 - W.TRANSFER_P) * t + W.TRANSFER_P * W.XFER_LEG[0]
    return t + sum(W.RING[q]) / 2 + W.after(rng, q, 4000, wrap).mean()


def sim_queue_day(q, d, arrivals, targets, rng, log, uid):
    """arrivals: list of (t, callid, callerid, kind). targets: list of (t, seats).
    returns list of transfers (t, callid, callerid) for billing."""
    wrap = W.WRAP_HIST[q]
    oh = W.open_hours(d)
    close_t = ep(d, oh[1] * 3600)
    agents = AGENTS[q]
    state = {a: "off" for a in agents}
    last_end = {a: 0.0 for a in agents}
    leaving = set()
    waiting = []          # list of call dicts, fcfs
    ev = []
    n = 0

    def push(t, kind, obj):
        nonlocal n
        n += 1
        heapq.heappush(ev, (t, n, kind, obj))

    for a in arrivals:
        push(a[0], "arr", a)
    for t, s in targets:
        push(t, "staff", s)
    push(close_t, "close", None)
    closed = False
    transfers = []
    target = 0

    def active():
        return [a for a in agents if state[a] in ("idle", "busy") and a not in leaving]

    def dispatch(now):
        while waiting:
            idle = [a for a in agents if state[a] == "idle" and a not in leaving]
            if not idle:
                return
            c = waiting.pop(0)
            a = min(idle, key=lambda x: last_end[x])
            state[a] = "busy"
            r = W.ring(rng, q, 1)[0]
            c["agent"] = a
            c["state"] = "ringing"
            c["ringstart"] = now
            push(now + r, "ringend", (c, a, r, now))

    def staff(now, s):
        nonlocal target
        target = s
        act = active()
        if len(act) < s:
            need = s - len(act)
            for a in list(leaving):
                if need == 0:
                    break
                leaving.discard(a)
                need -= 1
            for pool in ("break", "off"):
                for a in agents:
                    if need == 0:
                        break
                    if state[a] == pool:
                        if pool == "break":
                            log.add(now, "NONE", q, a, "UNPAUSE", "Break")
                        else:
                            log.add(now, "NONE", q, a, "ADDMEMBER", "")
                        state[a] = "idle"
                        need -= 1
        elif len(act) > s:
            extra = len(act) - s
            idle = sorted([a for a in act if state[a] == "idle"], key=lambda x: last_end[x])
            for a in idle:
                if extra == 0:
                    break
                go_off(now, a)
                extra -= 1
            for a in act:
                if extra == 0:
                    break
                if state[a] == "busy":
                    leaving.add(a)
                    extra -= 1
        dispatch(now)

    def go_off(now, a):
        leaving.discard(a)
        if closed or rng.random() < 0.45:
            log.add(now, "NONE", q, a, "REMOVEMEMBER", "")
            state[a] = "off"
        else:
            reason = "Lunch" if 11.5 * 3600 < now - ep(d, 0) < 14.5 * 3600 and rng.random() < 0.6 else "Break"
            log.add(now, "NONE", q, a, "PAUSE", reason)
            state[a] = "break"

    redial_seq = [0]
    now = close_t
    while ev:
        now, _, kind, obj = heapq.heappop(ev)
        if kind == "arr":
            t, callid, cid, ck = obj[:4]
            att = obj[4] if len(obj) > 4 else 1
            p = W.patience(rng, q, 1, ck)[0]
            c = {"id": callid, "t": t, "cid": cid, "kind": ck, "state": "wait", "p": p, "att": att}
            if ck != "xfer_in":
                hh = int((t - ep(d, 0)) // 3600)
                ENTRY_COUNT.setdefault((q, W.block(d, hh)), [0, 0])[0 if att == 1 else 1] += 1
            waiting.append(c)
            c["orig"] = len(waiting)
            log.add(t, callid, q, "NONE", "ENTERQUEUE", "", cid, c["orig"])
            push(t + p, "pat", c)
            if q == "faults":
                push(t + W.FAULTS_TIMEOUT, "tmo", c)
            dispatch(now)
        elif kind in ("pat", "tmo"):
            c = obj
            if c["state"] not in ("wait", "ringing"):
                continue
            w = now - c["t"]
            if c["state"] == "wait":
                pos = waiting.index(c) + 1
                waiting.remove(c)
            else:
                pos = 1
                a = c["agent"]
                log.add(now, c["id"], q, a, "RINGCANCELED", int(round((now - c["ringstart"]) * 1000)))
                state[a] = "idle"
            c["state"] = "gone"
            if kind == "pat":
                log.add(now, c["id"], q, "NONE", "ABANDON", pos, c["orig"], int(round(w)))
            else:
                log.add(now, c["id"], q, "NONE", "EXITWITHTIMEOUT", pos, c["orig"], int(round(w)))
            # a fresh caller who held 10 s or more may ring back later the same day
            if c["kind"] != "xfer_in" and w >= W.GHOST and \
                    rng.random() < W.REDIAL_P[q] * W.REDIAL_DECAY ** (c["att"] - 1):
                t2 = now + W.redial_delay(rng, 1)[0]
                if t2 < close_t:
                    redial_seq[0] += 1
                    nid = "%d.%d" % (int(t2), 9000000 + uid[0] * 7 + redial_seq[0])
                    push(t2, "arr", (t2, nid, c["cid"], c["kind"], c["att"] + 1))
            if c.get("agent") and state[c["agent"]] == "idle" and c["agent"] in leaving:
                go_off(now, c["agent"])
            dispatch(now)
        elif kind == "ringend":
            c, a, r, rs = obj
            c["ringstart"] = rs
            if c["state"] != "ringing":
                continue
            c["state"] = "talk"
            hold = now - c["t"]
            uid[0] += 1
            log.add(now, c["id"], q, a, "CONNECT", int(round(hold)), "%d.%d" % (int(now), uid[0]), int(round(r)))
            if q == "billing" and rng.random() < W.TRANSFER_P:
                tk = W.talk(rng, q, d, 0, 1, "xfer_leg")[0]
                c["xfer"] = True
            else:
                h = int((now - ep(d, 0)) // 3600)
                tk = W.talk(rng, q, d, h, 1, c["kind"])[0]
            push(now + tk, "end", (c, a, hold, tk))
        elif kind == "end":
            c, a, hold, tk = obj
            c["state"] = "done"
            if c.get("xfer"):
                log.add(now, c["id"], q, a, "BLINDTRANSFER", XFER_EXT, "queues", int(round(hold)), int(round(tk)), c["orig"])
                transfers.append((now + 1.0, c["id"], c["cid"]))
            else:
                evn = "COMPLETECALLER" if rng.random() < 0.55 else "COMPLETEAGENT"
                log.add(now, c["id"], q, a, evn, int(round(hold)), int(round(tk)), c["orig"])
            last_end[a] = now
            has, delay, length = W.acw(rng, q, 1)
            free = now + wrap
            if has[0]:
                log.add(now + delay[0], "NONE", q, a, "PAUSE", "ACW")
                log.add(now + delay[0] + length[0], "NONE", q, a, "UNPAUSE", "ACW")
                free = max(free, now + delay[0] + length[0])
            push(free, "avail", a)
        elif kind == "avail":
            a = obj
            state[a] = "idle"
            if a in leaving:
                go_off(now, a)
            elif closed and not waiting:
                log.add(now, "NONE", q, a, "REMOVEMEMBER", "")
                state[a] = "off"
            dispatch(now)
        elif kind == "staff":
            if not closed:
                staff(now, obj)
        elif kind == "close":
            closed = True
            for a in agents:
                if state[a] == "break":
                    log.add(now, "NONE", q, a, "REMOVEMEMBER", "")
                    state[a] = "off"
                elif state[a] == "idle" and not waiting:
                    log.add(now, "NONE", q, a, "REMOVEMEMBER", "")
                    state[a] = "off"
    for a in agents:
        if state[a] != "off":
            log.add(max(now, close_t) + 1, "NONE", q, a, "REMOVEMEMBER", "")
    return transfers


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    rng = np.random.default_rng(20270111)
    log = Log()
    uid = [0]
    callseq = [0]
    log.add(ep(W.HIST_START, 6 * 3600 + 2), "NONE", "NONE", "NONE", "QUEUESTART", "")
    for k in range(W.HIST_WEEKS * 7):
        d = W.HIST_START + dt.timedelta(days=k)
        if not W.open_hours(d):
            continue
        week_f = {q: rng.uniform(0.94, 1.06) for q in W.QUEUES}
        transfers = []
        for q in ["billing", "moving", "faults"]:
            ivs = W.intervals(d)
            lam = W.expected_calls(q, d)
            arrivals = []
            targets = []
            # jan-feb was short staffed most of the time, with some well covered stretches
            c = rng.uniform(-1.4, 1.4)
            for (h, m), l in zip(ivs, lam):
                t0 = ep(d, h * 3600 + m * 60)
                cnt = rng.poisson(l * week_f[q] * math.exp(rng.normal(0, 0.06)))
                ts = np.sort(rng.uniform(t0, t0 + 1800, cnt))
                cids = callerids(rng, cnt)
                kinds = W.caller_type(rng, q, cnt)
                for t, cid, kd in zip(ts, cids, kinds):
                    callseq[0] += 1
                    arrivals.append((t, "%d.%d" % (int(t), callseq[0]), cid, str(kd)))
                a = l * week_f[q] / 1800 * occ_mean(q, d, h, W.WRAP_HIST[q])
                if q == "moving":
                    a += l * 0.35 / 1800 * 600
                s = max(2, int(round((a + c * math.sqrt(a)) * rng.uniform(0.74, 1.06))))
                targets.append((t0 - (60 if (h, m) == ivs[0] else 0), s))
            if q == "moving":
                arrivals += [(t, cidd, cid, "xfer_in") for t, cidd, cid in transfers]
                arrivals.sort()
            tr = sim_queue_day(q, d, arrivals, targets, rng, log, uid)
            if q == "billing":
                transfers = tr
        print(d, len(log.rows), flush=True)
    log.rows.sort()
    with open(os.path.join(out, "queue_log"), "w") as f:
        for r in log.rows:
            f.write(r[2] + "\n")
    # forecast for the plan week
    import json
    json.dump({"%s|%s" % k: v for k, v in sorted(ENTRY_COUNT.items())}, open(os.path.join(out, "entry_counts.json"), "w"), indent=0)
    with open(os.path.join(out, "forecast_2027-03-01.csv"), "w") as f:
        f.write("date,interval_start,queue,calls\n")
        for k in range(6):
            d = W.PLAN_START + dt.timedelta(days=k)
            for q in W.QUEUES:
                # the forecasting team trended jan-feb ENTERQUEUE counts, so their figure
                # carries the repeat attempts that the short staffed history generated
                for (h, m), l in zip(W.intervals(d), W.expected_calls(q, d, W.PLAN_CAMPAIGN)):
                    first, rep = ENTRY_COUNT[(q, W.block(d, h))]
                    l = l * (first + rep) / first
                    f.write("%s,%02d:%02d,%s,%.1f\n" % (d.isoformat(), h, m, q, round(l, 1)))


if __name__ == "__main__":
    main()
