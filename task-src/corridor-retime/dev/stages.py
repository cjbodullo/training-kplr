"""controller specification: stage contents per junction, interstage design, minimum greens.

a stage is a dict {(from_edge, to_edge): 'G' or 'g'}; every other link at the junction is red.
'g' is a filtering (opposed) right turn, it gives way to the opposing flow.
"""
STAGES = {
    "J1": [
        ("1", "main road", {("a_w_in", "j1n_out"): "G", ("a_w_in", "a_12"): "G", ("a_w_in", "j1s_out"): "g",
                            ("a_21", "j1s_out"): "G", ("a_21", "a_w_out"): "G", ("a_21", "j1n_out"): "g"}),
        ("2", "side roads", {("j1n_in", "a_12"): "G", ("j1n_in", "j1s_out"): "G", ("j1n_in", "a_w_out"): "g",
                             ("j1s_in", "a_w_out"): "G", ("j1s_in", "j1n_out"): "G", ("j1s_in", "a_12"): "g"}),
        ("3", "pedestrian", {}),
    ],
    "J2": [
        ("1", "main road", {("a_12", "a_23"): "G", ("a_12", "j2s_out"): "g",
                            ("a_32", "j2s_out"): "G", ("a_32", "a_21"): "G"}),
        ("2", "estate road", {("j2s_in", "a_21"): "G", ("j2s_in", "a_23"): "G"}),
        ("3", "pedestrian", {}),
    ],
    "J3": [
        ("1", "main road", {("a_23", "j3n_out"): "G", ("a_23", "a_34"): "G", ("a_43", "a_32"): "G"}),
        ("2", "school road", {("j3n_in", "a_34"): "G", ("j3n_in", "a_32"): "G"}),
        ("3", "pedestrian", {}),
    ],
    "J4": [
        ("1", "main road", {("a_34", "j4n_out"): "G", ("a_34", "a_e_out"): "G", ("a_34", "j4s_out"): "g",
                            ("a_e_in", "j4s_out"): "G", ("a_e_in", "a_43"): "G", ("a_e_in", "j4n_out"): "g"}),
        ("2", "side roads", {("j4n_in", "a_e_out"): "G", ("j4n_in", "j4s_out"): "G", ("j4n_in", "a_43"): "g",
                             ("j4s_in", "a_43"): "G", ("j4s_in", "j4n_out"): "G", ("j4s_in", "a_e_out"): "g"}),
    ],
}
MIN_GREEN = {"J1": [10, 7, 9], "J2": [10, 7, 9], "J3": [10, 7, 9], "J4": [10, 7]}
AMBER, ALL_RED, RED_AMBER = 3, 2, 2
MAX_CYCLE = 120


def link_movements(net, tls_id):
    """link index -> (from_edge, to_edge) for one signal."""
    out = {}
    for in_lane, out_lane, idx in net.getTLSSecure(tls_id).getConnections():
        key = (in_lane.getEdge().getID(), out_lane.getEdge().getID())
        if idx in out and out[idx] != key:
            raise ValueError(f"link {idx} of {tls_id} serves two movements")
        out[idx] = key
    return out


def stage_state(moves, stage):
    n = max(moves) + 1
    return "".join(stage.get(moves[i], "r") for i in range(n))


def interstage(moves, a, b):
    """phase list [(state, dur)] between stage dicts a and b (amber, all red, red+amber)."""
    n = max(moves) + 1
    seq = []
    amber, red, ra = [], [], []
    for i in range(n):
        m = moves[i]
        ga, gb = a.get(m), b.get(m)
        if ga and gb:          # runs through the change; take the stronger of the two
            s = "G" if "G" in (ga, gb) else "g"
            amber.append(ga); red.append(ga); ra.append(ga)
        elif ga:
            amber.append("y"); red.append("r"); ra.append("r")
        elif gb:
            amber.append("r"); red.append("r"); ra.append("u")
        else:
            amber.append("r"); red.append("r"); ra.append("r")
    return [("".join(amber), AMBER), ("".join(red), ALL_RED), ("".join(ra), RED_AMBER)]


def program_phases(moves, stages, greens):
    """full cycle phase list for a junction given stage greens (fixed stage order)."""
    ph = []
    k = len(stages)
    for i in range(k):
        ph.append((stage_state(moves, stages[i][2]), greens[i]))
        ph.extend(interstage(moves, stages[i][2], stages[(i + 1) % k][2]))
    return ph


def cycle_of(greens):
    return sum(greens) + len(greens) * (AMBER + ALL_RED + RED_AMBER)


def write_tls(path, net, plan, program_id="am_peak"):
    """plan: {tls: {"greens": [...], "offset": int}}"""
    with open(path, "w") as f:
        f.write("<additional>\n")
        for tls in sorted(plan):
            moves = link_movements(net, tls)
            ph = program_phases(moves, STAGES[tls], plan[tls]["greens"])
            f.write(f'    <tlLogic id="{tls}" type="static" programID="{program_id}" offset="{plan[tls]["offset"]}">\n')
            for st, d in ph:
                f.write(f'        <phase duration="{d}" state="{st}"/>\n')
            f.write("    </tlLogic>\n")
        f.write("</additional>\n")
