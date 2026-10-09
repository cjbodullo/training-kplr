"""build the corridor, run sumo days, compute the grading metrics."""
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.append("/usr/share/sumo/tools")
import sumolib  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import net_spec  # noqa: E402

INTERNAL = ["a_12", "a_21", "a_23", "a_32", "a_34", "a_43"]
ENTRY = ["a_w_in", "a_e_in", "j1n_in", "j1s_in", "j2s_in", "j3n_in", "j4n_in", "j4s_in"]
APPROACH = ENTRY + INTERNAL
BB_GAP = 8.0       # a queue reaching within this of the upstream stop line blocks back


LANE_LEN = {}


def build_net(outdir):
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, "corridor")
    net_spec.write_plain(p)
    subprocess.run(["netconvert", "--lefthand", "--node-files", p + ".nod.xml", "--edge-files", p + ".edg.xml",
                    "--connection-files", p + ".con.xml", "--tls.default-type", "static",
                    "--no-turnarounds", "true", "--junctions.join", "false",
                    "--output-file", p + ".net.xml"], check=True, capture_output=True)
    load_lengths(p + ".net.xml")
    return p + ".net.xml"


def load_lengths(netfile):
    net = sumolib.net.readNet(netfile)
    for e in net.getEdges():
        for ln in e.getLanes():
            LANE_LEN[ln.getID()] = ln.getLength()


def write_detectors(path, net, loop_period=300, out_prefix="loops"):
    """e1 stop line loops on every approach lane + e1 upstream loops on the entries, e2 blocking back zones."""
    with open(path, "w") as f:
        f.write("<additional>\n")
        for eid in APPROACH:
            e = net.getEdge(eid)
            for ln in e.getLanes():
                L = ln.getLength()
                f.write(f'    <inductionLoop id="sl_{ln.getID()}" lane="{ln.getID()}" pos="{L - 2.0:.2f}" '
                        f'period="{loop_period}" file="{out_prefix}.xml"/>\n')
                if eid in ENTRY:
                    pos = max(5.0, L - 160.0)
                    f.write(f'    <inductionLoop id="up_{ln.getID()}" lane="{ln.getID()}" pos="{pos:.2f}" '
                            f'period="{loop_period}" file="{out_prefix}.xml"/>\n')
        for eid in INTERNAL:
            for ln in net.getEdge(eid).getLanes():
                f.write(f'    <laneAreaDetector id="bb_{ln.getID()}" lane="{ln.getID()}" pos="0.1" '
                        f'endPos="{ln.getLength() - 0.1:.2f}" period="1" file="bb.xml" timeThreshold="1.0" speedThreshold="1.4" jamThreshold="10.0"/>\n')
        f.write("</additional>\n")


def run_day(netfile, routes, tls_files, det_file, workdir, begin=6.75 * 3600, end=10.5 * 3600, seed=1, extra=()):
    os.makedirs(workdir, exist_ok=True)
    # detector outputs are relative to the additional file, so each run gets its own copy
    local_det = os.path.join(workdir, "det.add.xml")
    with open(det_file) as src, open(local_det, "w") as dst:
        dst.write(src.read())
    adds = ",".join(list(tls_files) + [local_det])
    cmd = ["sumo", "-n", netfile, "-r", routes, "-a", adds,
           "--begin", str(int(begin)), "--end", str(int(end)), "--seed", str(seed),
           "--tripinfo-output", os.path.join(workdir, "trips.xml"),
           "--statistic-output", os.path.join(workdir, "stats.xml"),
           "--time-to-teleport", "300", "--no-step-log", "true", "--duration-log.disable", "true",
           "--ignore-route-errors", "false"] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=workdir, env=dict(os.environ, SUMO_HOME="/usr/share/sumo"))
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2000:])
    return r


def metrics(workdir, n_vehicles, netfile=None):
    st = ET.parse(os.path.join(workdir, "stats.xml")).getroot()
    tele = int(st.find("teleports").get("total"))
    veh = st.find("vehicles")
    arrived = 0
    dd_max = 0.0
    waits = {}
    dd_by = {}
    for tr in ET.parse(os.path.join(workdir, "trips.xml")).getroot():
        arrived += 1
        dd = float(tr.get("departDelay"))
        dd_max = max(dd_max, dd)
        a = tr.get("departLane").rsplit("_", 1)[0]
        dd_by.setdefault(a, 0.0)
        dd_by[a] = max(dd_by[a], dd)
        waits.setdefault(a, []).append(float(tr.get("waitingTime")))
    bb = {}
    bbf = os.path.join(workdir, "bb.xml")
    for iv in ET.parse(bbf).getroot():
        lid = iv.get("id")[3:]
        if float(iv.get("maxJamLengthInMeters", "0")) >= LANE_LEN[lid] - BB_GAP:
            bb[lid] = bb.get(lid, 0) + 1
    p95 = {}
    for a, w in waits.items():
        w.sort()
        p95[a] = (w[int(0.95 * (len(w) - 1))], w[-1], sum(w) / len(w))
    return {"teleports": tele, "inserted": int(veh.get("inserted")), "loaded": int(veh.get("loaded")),
            "arrived": arrived, "n": n_vehicles, "depart_delay_max": dd_max, "bb_seconds": bb, "waits": p95, "dd_by": dd_by}
