"""true world for queue-seats. nothing here ships to the agent."""
import datetime as dt
import math
import numpy as np

QUEUES = ["billing", "moving", "faults"]
WRAP_HIST = {"billing": 15, "moving": 30, "faults": 20}
WRAP_MARCH = {"billing": 15, "moving": 30, "faults": 60}
TRANSFER_P = 0.12          # billing answered calls blind transferred to moving
FAULTS_TIMEOUT = 600
SLT, GHOST = 20, 10
SL_TARGET, AB_TARGET = 0.80, 0.05

HIST_START = dt.date(2027, 1, 11)   # monday
HIST_WEEKS = 6
PLAN_START = dt.date(2027, 3, 1)    # monday


def open_hours(d):
    wd = d.weekday()
    if wd < 5:
        return 8, 20
    if wd == 5:
        return 9, 17
    return None


def intervals(d):
    oh = open_hours(d)
    if not oh:
        return []
    return [(h, m) for h in range(oh[0], oh[1]) for m in (0, 30)]


def block(d, h):
    if d.weekday() == 5:
        return "sat"
    if h < 12:
        return "am"
    if h < 17:
        return "pm"
    return "eve"


# ---------- caller types ----------
# every fresh caller is either a quick query (short call, little patience) or a complex one
# (long call, patient). the log never says which.
QUICK_SHARE = {"billing": 0.55, "moving": 0.25, "faults": 0.50}
TYPE_TALK = {  # mean seconds at block factor 1, lognormal sigma
    "billing": {"quick": (150, 0.50), "complex": (560, 0.55)},
    "moving": {"quick": (200, 0.50), "complex": (650, 0.50)},
    "faults": {"quick": (120, 0.50), "complex": (500, 0.55)},
}
BLOCK_F = {
    "billing": {"am": 1.0, "pm": 0.90, "eve": 1.08, "sat": 0.85},
    "moving": {"am": 1.0, "pm": 1.0, "eve": 1.0, "sat": 1.08},
    "faults": {"am": 1.0, "pm": 0.93, "eve": 1.45, "sat": 1.12},
}
MONDAY_TALK = {"billing": 1.12, "moving": 1.0, "faults": 1.0}
TYPE_PAT = {  # patience median seconds, lognormal sigma
    "billing": {"quick": (70, 0.8), "complex": (520, 0.9)},
    "moving": {"quick": (90, 0.8), "complex": (620, 0.9)},
    "faults": {"quick": (55, 0.8), "complex": (330, 0.9)},
}
XFER_LEG = (70, 0.45)          # billing leg of a call that gets transferred
XFER_IN_TALK = (470, 0.55)     # moving talk for a call that came in by transfer

RING = {"billing": (2.0, 7.0), "moving": (2.0, 7.0), "faults": (3.0, 11.0)}

# after call: manual ACW pause probability, delay before pause, pause length
ACW = {"billing": (0.35, 50, 0.60), "moving": (0.60, 95, 0.50), "faults": (0.50, 38, 0.55)}
ACW_DELAY = (2.0, 6.0)

# patience
GHOST_P = 0.04
SPIKE = {"billing": 0.08, "moving": 0.05, "faults": 0.10}
XFER_IN_PAT = (700, 0.8)


def lognorm_mean(rng, mean, sig, n):
    mu = math.log(mean) - sig * sig / 2
    return rng.lognormal(mu, sig, n)


def talk(rng, q, d, h, n, kind="complex"):
    if kind == "xfer_leg":
        return lognorm_mean(rng, XFER_LEG[0], XFER_LEG[1], n)
    if kind == "xfer_in":
        return lognorm_mean(rng, XFER_IN_TALK[0], XFER_IN_TALK[1], n)
    m, sig = TYPE_TALK[q][kind]
    m *= BLOCK_F[q][block(d, h)]
    if d.weekday() == 0:
        m *= MONDAY_TALK[q]
    return lognorm_mean(rng, m, sig, n)


def caller_type(rng, q, n):
    return np.where(rng.random(n) < QUICK_SHARE[q], "quick", "complex")


def ring(rng, q, n):
    a, b = RING[q]
    return rng.uniform(a, b, n)


def acw(rng, q, n):
    """returns (has_pause bool array, delay, length)"""
    p, mean, sig = ACW[q]
    has = rng.random(n) < p
    delay = rng.uniform(ACW_DELAY[0], ACW_DELAY[1], n)
    length = lognorm_mean(rng, mean, sig, n)
    return has, delay, length


def after(rng, q, n, wrap):
    has, delay, length = acw(rng, q, n)
    return np.where(has, np.maximum(wrap, delay + length), float(wrap))


def patience(rng, q, n, kind="complex"):
    if kind == "xfer_in":
        med, sig = XFER_IN_PAT
        return rng.lognormal(math.log(med), sig, n)
    med, sig = TYPE_PAT[q][kind]
    base = rng.lognormal(math.log(med), sig, n)
    u = rng.random(n)
    ghost = rng.uniform(1.0, 9.0, n)
    spike = 30.0 + rng.uniform(2.0, 7.0, n)
    out = np.where(u < GHOST_P, ghost, np.where(u < GHOST_P + SPIKE[q], np.minimum(spike, base), base))
    return out


# ---------- arrivals ----------
DAY_VOL = {"billing": 1650, "moving": 520, "faults": 820}
SAT_VOL = {"billing": 520, "moving": 260, "faults": 430}
WD_FACTOR = {0: 1.22, 1: 1.0, 2: 0.97, 3: 0.98, 4: 0.9}


def shape(q, d):
    """relative weight per open interval"""
    ivs = intervals(d)
    w = []
    for h, m in ivs:
        x = h + m / 60 + 0.25
        if q == "billing":
            v = 0.6 + 1.0 * math.exp(-((x - 10.0) / 1.6) ** 2) + 0.55 * math.exp(-((x - 13.8) / 1.2) ** 2) + 0.25 * math.exp(-((x - 18.0) / 1.5) ** 2)
        elif q == "moving":
            v = 0.7 + 0.6 * math.exp(-((x - 12.0) / 2.5) ** 2)
        else:
            v = 0.55 + 0.45 * math.exp(-((x - 9.0) / 1.3) ** 2) + 0.9 * math.exp(-((x - 18.0) / 1.4) ** 2)
        if d.weekday() == 5:
            v = 0.7 + 0.5 * math.exp(-((x - 11.5) / 2.0) ** 2)
        w.append(v)
    s = sum(w)
    return [v / s for v in w]


def expected_calls(q, d, campaign=None):
    """expected fresh ENTERQUEUE count per interval, list aligned with intervals(d)"""
    if d.weekday() == 6:
        return []
    vol = SAT_VOL[q] if d.weekday() == 5 else DAY_VOL[q] * WD_FACTOR[d.weekday()]
    if campaign:
        vol *= campaign.get((q, d), 1.0)
    return [vol * w for w in shape(q, d)]


PLAN_CAMPAIGN = {("billing", dt.date(2027, 3, 2)): 1.55, ("billing", dt.date(2027, 3, 3)): 1.35,
                 ("faults", dt.date(2027, 3, 4)): 1.25}


# ---------- repeat attempts ----------
# a caller who gives up after waiting 10 s or more (or is timed out) rings back with this
# probability, which shrinks by REDIAL_DECAY with every further attempt. same caller, same kind.
REDIAL_P = {"billing": 0.55, "moving": 0.60, "faults": 0.70}
REDIAL_DECAY = 0.7
REDIAL_DELAY = (240.0, 0.8)   # lognormal median seconds, sigma


def redial_delay(rng, n):
    return rng.lognormal(math.log(REDIAL_DELAY[0]), REDIAL_DELAY[1], n)
