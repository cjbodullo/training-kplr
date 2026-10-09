"""widen the true-model seat bands so they hold every answer a correct method gives.
usage: python3 build_bands.py TRUTH_JSON OUT_BANDS_JSON PLAN_CSV [PLAN_CSV ...]

truth: nstar is the smallest seat count meeting both targets under the true behaviour,
lo/hi already allow one seat either side where the true figure is near a target.
each plan csv is the reference method re-run with fresh seeds and/or a weekday stratified
day bootstrap of the six weeks of history, i.e. what a correct method can produce from data
of this size. the band is the union of nstar +/- 1 (nstar - 2 on the monday, whose factor rests on six
mondays of history) and every such answer."""
import csv
import json
import sys


def main():
    truth = json.load(open(sys.argv[1]))
    band = {(r["date"], r["start"], r["queue"]): dict(r) for r in truth}
    for b in band.values():
        b["seen"] = []
    for p in sys.argv[3:]:
        for r in csv.DictReader(open(p)):
            band[(r["date"], r["interval_start"], r["queue"])]["seen"].append(int(r["seats"]))
    out = []
    widened = 0
    for (d, s, q), b in band.items():
        # monday rows rest on a monday factor estimated from only six mondays of history
        mon = d == "2027-03-01"
        lo = min([b["lo"], b["nstar"] - (2 if mon else 1)] + b["seen"])
        hi = max([b["hi"], b["nstar"] + 1] + b["seen"])
        widened += (lo, hi) != (b["lo"], b["hi"])
        out.append({"date": d, "start": s, "queue": q, "lo": lo, "hi": hi, "nstar": b["nstar"],
                    "true_lo": b["lo"], "true_hi": b["hi"], "sl": round(b["sl"], 4), "ab": round(b["ab"], 4),
                    "replicates_min": min(b["seen"]) if b["seen"] else None,
                    "replicates_max": max(b["seen"]) if b["seen"] else None})
    json.dump(out, open(sys.argv[2], "w"), indent=0)
    exact = sum(1 for r in out if r["lo"] == r["hi"])
    width = sum(r["hi"] - r["lo"] + 1 for r in out) / len(out)
    print(f"rows {len(out)} widened {widened} exact {exact} mean width {width:.2f} from {len(sys.argv) - 3} plans")


if __name__ == "__main__":
    main()
