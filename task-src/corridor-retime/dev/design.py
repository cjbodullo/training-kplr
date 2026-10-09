"""plan designer: critical lane flows -> stage greens for a common cycle."""
import stages

SAT = 1950.0          # veh/h per lane, unopposed
SAT_SIDE = 1750.0     # single lane side arm with turning traffic
SAT_ESTATE = 1600.0   # orchard way turning lanes, measured from saturated discharge

LANES = {  # approach -> list of lanes, each a set of exit edges it serves
    "a_w_in": [{"j1n_out", "a_12"}, {"a_12"}],
    "a_21": [{"j1s_out", "a_w_out"}, {"a_w_out"}],
    "a_12": [{"a_23"}, {"a_23"}],
    "a_32": [{"j2s_out", "a_21"}, {"a_21"}],
    "j2s_in": [{"a_21"}, {"a_23"}],
    "a_23": [{"j3n_out", "a_34"}, {"a_34"}],
    "a_43": [{"a_32"}, {"a_32"}],
    "a_34": [{"j4n_out", "a_e_out"}, {"a_e_out"}],
    "a_e_in": [{"j4s_out", "a_43"}, {"a_43"}],
}


def lane_flows(app, mov):
    """mov: {exit: flow}. returns the critical (largest) lane flow, assuming drivers balance lanes."""
    lanes = LANES.get(app)
    tot = sum(mov.values())
    if not lanes:
        return tot
    # forced: flow that can only use one lane
    forced = [0.0] * len(lanes)
    shared = 0.0
    for ex, v in mov.items():
        idx = [i for i, l in enumerate(lanes) if ex in l]
        if len(idx) == 1:
            forced[idx[0]] += v
        else:
            shared += v
    # water filling of the shared flow
    lo = sorted(forced)
    level = max(forced)
    need = sum(level - f for f in forced)
    if shared > need:
        level += (shared - need) / len(lanes)
    return level


def stage_y(movs):
    """movs: {(junction, approach): {exit: flow}} -> {junction: [y per stage]} plus J3 extras."""
    def y(j, a, sat=SAT):
        return lane_flows(a, movs.get((j, a), {})) / sat
    out = {}
    out["J1"] = [max(y("J1", "a_w_in"), y("J1", "a_21")), max(y("J1", "j1n_in", SAT_SIDE), y("J1", "j1s_in", SAT_SIDE))]
    out["J2"] = [max(y("J2", "a_12"), y("J2", "a_32")), y("J2", "j2s_in", SAT_ESTATE)]
    out["J3"] = [max(y("J3", "a_23"), y("J3", "a_43")), y("J3", "j3n_in", SAT_SIDE)]
    out["J4"] = [max(y("J4", "a_34"), y("J4", "a_e_in")), max(y("J4", "j4n_in", SAT_SIDE), y("J4", "j4s_in", SAT_SIDE))]
    return out


def split(C, ys, mins, fixed_extra=0):
    """webster style: share the usable green in proportion to y, respecting minimum greens."""
    k = len(ys)
    usable = C - k * (stages.AMBER + stages.ALL_RED + stages.RED_AMBER) - fixed_extra
    g = [0.0] * k
    free = list(range(k))
    rem = usable
    while True:
        ys_free = sum(ys[i] for i in free)
        changed = False
        for i in list(free):
            gi = rem * ys[i] / ys_free if ys_free > 0 else rem / len(free)
            if gi < mins[i]:
                g[i] = mins[i]
                free.remove(i)
                rem -= mins[i]
                changed = True
        if not changed:
            break
    ys_free = sum(ys[i] for i in free)
    for i in free:
        g[i] = rem * ys[i] / ys_free
    gi = [int(round(x)) for x in g]
    # fix rounding so the cycle is exact
    diff = usable - sum(gi)
    order = sorted(range(k), key=lambda i: -ys[i])
    j = 0
    while diff != 0:
        i = order[j % k]
        step = 1 if diff > 0 else -1
        if gi[i] + step >= mins[i]:
            gi[i] += step
            diff -= step
        j += 1
    return gi


def design(movs, C, offsets, ped=9, rt_margin=1.6, j4_match=None):
    ys = stage_y(movs)
    plan = {}
    plan["J1"] = {"greens": split(C, ys["J1"], stages.MIN_GREEN["J1"][:2], fixed_extra=ped + 7) + [ped]}
    plan["J2"] = {"greens": split(C, ys["J2"], stages.MIN_GREEN["J2"][:2], fixed_extra=ped + 7) + [ped]}
    plan["J3"] = {"greens": split(C, ys["J3"], stages.MIN_GREEN["J3"][:2], fixed_extra=ped + 7) + [ped]}
    plan["J4"] = {"greens": split(C, ys["J4"], stages.MIN_GREEN["J4"])}
    if j4_match is not None:
        # linked pair: j4 main road green follows j3's so the 60 m link is never fed into a red
        g1 = plan["J3"]["greens"][0] + j4_match
        plan["J4"] = {"greens": [g1, C - 14 - g1]}
    for j in plan:
        plan[j]["offset"] = int(offsets.get(j, 0)) % C
        assert stages.cycle_of(plan[j]["greens"]) == C, (j, plan[j], C)
    return plan
