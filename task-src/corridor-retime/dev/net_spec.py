"""corridor geometry: four signalled junctions on a west-east arterial (uk, left hand traffic)."""
# node id -> (x, y, type)
NODES = {
    "w_fringe": (-450, 0, "priority"),
    "J1": (0, 0, "traffic_light"),
    "j1_n": (0, 320, "priority"),
    "j1_s": (0, -320, "priority"),
    "J2": (330, 0, "traffic_light"),
    "j2_s": (330, -380, "priority"),
    "J3": (560, 0, "traffic_light"),
    "j3_n": (560, 320, "priority"),
    "J4": (620, 0, "traffic_light"),
    "j4_n": (620, 320, "priority"),
    "j4_s": (620, -320, "priority"),
    "e_fringe": (1060, 0, "priority"),
}
ART_SPEED = 13.41   # 30 mph
SIDE_SPEED = 13.41
# (edge id, from, to, lanes, speed)
EDGES = [
    ("a_w_in", "w_fringe", "J1", 2, ART_SPEED), ("a_w_out", "J1", "w_fringe", 2, ART_SPEED),
    ("a_12", "J1", "J2", 2, ART_SPEED), ("a_21", "J2", "J1", 2, ART_SPEED),
    ("a_23", "J2", "J3", 2, ART_SPEED), ("a_32", "J3", "J2", 2, ART_SPEED),
    ("a_34", "J3", "J4", 2, ART_SPEED), ("a_43", "J4", "J3", 2, ART_SPEED),
    ("a_e_in", "e_fringe", "J4", 2, ART_SPEED), ("a_e_out", "J4", "e_fringe", 2, ART_SPEED),
    ("j1n_in", "j1_n", "J1", 1, SIDE_SPEED), ("j1n_out", "J1", "j1_n", 1, SIDE_SPEED),
    ("j1s_in", "j1_s", "J1", 1, SIDE_SPEED), ("j1s_out", "J1", "j1_s", 1, SIDE_SPEED),
    ("j2s_in", "j2_s", "J2", 2, SIDE_SPEED), ("j2s_out", "J2", "j2_s", 1, SIDE_SPEED),
    ("j3n_in", "j3_n", "J3", 1, SIDE_SPEED), ("j3n_out", "J3", "j3_n", 1, SIDE_SPEED),
    ("j4n_in", "j4_n", "J4", 1, SIDE_SPEED), ("j4n_out", "J4", "j4_n", 1, SIDE_SPEED),
    ("j4s_in", "j4_s", "J4", 1, SIDE_SPEED), ("j4s_out", "J4", "j4_s", 1, SIDE_SPEED),
]
# explicit lane connections (from edge, from lane, to edge, to lane). lefthand network:
# lane 0 is the nearside (kerb) lane, lane 1 the offside lane.
CONNS = [
    # J1 eastbound: nearside left (north) + ahead, offside ahead + right (south)
    ("a_w_in", 0, "j1n_out", 0), ("a_w_in", 0, "a_12", 0),
    ("a_w_in", 1, "a_12", 1),
    # J1 westbound: nearside left (south) + ahead, offside ahead + right (north)
    ("a_21", 0, "j1s_out", 0), ("a_21", 0, "a_w_out", 0),
    ("a_21", 1, "a_w_out", 1),
    # J1 north arm (southbound): left = east, ahead = south, right = west
    ("j1n_in", 0, "a_12", 0), ("j1n_in", 0, "j1s_out", 0), ("j1n_in", 0, "a_w_out", 1),
    # J1 south arm (northbound): left = west, ahead = north, right = east
    ("j1s_in", 0, "a_w_out", 0), ("j1s_in", 0, "j1n_out", 0), ("j1s_in", 0, "a_12", 1),
    # J2 eastbound: both lanes ahead, offside also right into the estate (south)
    ("a_12", 0, "a_23", 0), ("a_12", 1, "a_23", 1),
    # J2 westbound: nearside ahead + left into the estate, offside ahead
    ("a_32", 0, "j2s_out", 0), ("a_32", 0, "a_21", 0), ("a_32", 1, "a_21", 1),
    # J2 estate arm (northbound): lane 0 left = west, lane 1 right = east
    ("j2s_in", 0, "a_21", 0), ("j2s_in", 1, "a_23", 1),
    # J3 eastbound: nearside left (school road, north) + ahead, offside ahead
    ("a_23", 0, "j3n_out", 0), ("a_23", 0, "a_34", 0), ("a_23", 1, "a_34", 1),
    # J3 westbound: both lanes ahead (no right turn into the school road)
    ("a_43", 0, "a_32", 0), ("a_43", 1, "a_32", 1),
    # J3 school road (southbound): left = east, right = west
    ("j3n_in", 0, "a_34", 0), ("j3n_in", 0, "a_32", 1),
    # J4 eastbound: nearside left (north) + ahead, offside ahead + right (south)
    ("a_34", 0, "j4n_out", 0), ("a_34", 0, "a_e_out", 0),
    ("a_34", 1, "a_e_out", 1),
    # J4 westbound: nearside left (south) + ahead, offside ahead + right (north)
    ("a_e_in", 0, "j4s_out", 0), ("a_e_in", 0, "a_43", 0),
    ("a_e_in", 1, "a_43", 1),
    # J4 north arm: left = east, ahead = south, right = west
    ("j4n_in", 0, "a_e_out", 0), ("j4n_in", 0, "j4s_out", 0), ("j4n_in", 0, "a_43", 1),
    # J4 south arm: left = west, ahead = north, right = east
    ("j4s_in", 0, "a_43", 0), ("j4s_in", 0, "j4n_out", 0), ("j4s_in", 0, "a_e_out", 1),
]


def write_plain(prefix):
    with open(prefix + ".nod.xml", "w") as f:
        f.write("<nodes>\n")
        for nid, (x, y, t) in NODES.items():
            f.write(f'  <node id="{nid}" x="{x}" y="{y}" type="{t}"/>\n')
        f.write("</nodes>\n")
    with open(prefix + ".edg.xml", "w") as f:
        f.write("<edges>\n")
        for eid, a, b, n, v in EDGES:
            f.write(f'  <edge id="{eid}" from="{a}" to="{b}" numLanes="{n}" speed="{v}" priority="{3 if eid.startswith("a_") else 1}"/>\n')
        f.write("</edges>\n")
    with open(prefix + ".con.xml", "w") as f:
        f.write("<connections>\n")
        for a, al, b, bl in CONNS:
            f.write(f'  <connection from="{a}" to="{b}" fromLane="{al}" toLane="{bl}"/>\n')
        f.write("</connections>\n")


if __name__ == "__main__":
    import sys
    write_plain(sys.argv[1])
