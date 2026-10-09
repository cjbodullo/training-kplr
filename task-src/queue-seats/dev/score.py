import csv, json, sys
tr = {(r["date"], r["start"], r["queue"]): r for r in json.load(open(sys.argv[1]))}
bad = []; n = 0
for r in csv.DictReader(open(sys.argv[2])):
    b = tr[(r["date"], r["interval_start"], r["queue"])]; s = int(r["seats"]); n += 1
    if not (b["lo"] <= s <= b["hi"]): bad.append((r["date"], r["interval_start"], r["queue"], s, b["lo"], b["nstar"], b["hi"], round(b["sl"],3)))
print("rows", n, "out", len(bad))
for x in bad[:25]: print(x)
exact = sum(1 for b in tr.values() if b["lo"] == b["hi"])
print("exact-only intervals", exact, "of", len(tr))
