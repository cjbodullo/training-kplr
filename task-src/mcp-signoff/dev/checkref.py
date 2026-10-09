import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tests'))
import grade
exp = json.load(open(sys.argv[1]))
got, wns = grade.edges(grade.parse(open(sys.argv[2]).read()))
got = {f'{a}|{b}|{c}': v for (a, b, c), v in got.items()}
bad = [k for k in set(exp) | set(got) if exp.get(k) != got.get(k)]
print(sys.argv[2], 'mismatches', len(bad), 'wns', wns, sorted(bad)[:5])
