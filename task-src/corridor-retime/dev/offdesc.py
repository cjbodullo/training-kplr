"""coordinate descent on offsets. score = blocking back s + 10 x max depart delay + 1000 x teleports."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demand, design, evalplan, sumolib


def true_movs(net, term=True):
    movs = {}
    for a, b, v, prof in demand.streams(term, phase2=os.environ.get("P2") == "1"):
        path, _ = net.getShortestPath(net.getEdge(a), net.getEdge(b))
        ids = [e.getID() for e in path]
        for x, y in zip(ids, ids[1:]):
            k = (net.getEdge(x).getToNode().getID(), x)
            movs.setdefault(k, {}).setdefault(y, 0)
            movs[k][y] += v
    return movs


def score(res):
    return sum(sum(m["bb_seconds"].values()) + 10 * m["depart_delay_max"] + 1000 * m["teleports"] for m in res.values())


if __name__ == "__main__":
    evalplan.prep()
    net = sumolib.net.readNet(os.path.join(evalplan.BASE, "corridor.net.xml"))
    movs = true_movs(net)
    C = int(sys.argv[1]); seeds = [int(x) for x in sys.argv[2].split(",")]
    offs = json.loads(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else {"J1": 0, "J2": 0, "J3": 0, "J4": 0}
    match = int(sys.argv[4]) if len(sys.argv) > 4 else None
    cache = {}
    def ev(o):
        key = tuple(o[j] % C for j in ["J2", "J3", "J4"])
        if key not in cache:
            plan = design.design(movs, C, o, j4_match=match)
            cache[key] = score(evalplan.evaluate(plan, seeds, tag="d" + "_".join(map(str, key))))
            print(cache[key], key, flush=True)
        return cache[key]
    best = ev(offs)
    for rnd in range(2):
        for j in ["J2", "J3", "J4"]:
            for v in range(0, C, 8):
                o = dict(offs); o[j] = v
                s = ev(o)
                if s < best:
                    best, offs = s, o
        print("ROUND", rnd, best, offs, flush=True)
    plan = design.design(movs, C, offs, j4_match=match)
    print("PLAN", json.dumps(plan))
