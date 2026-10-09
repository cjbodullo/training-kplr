import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evalplan
plan = json.loads(sys.argv[1]); seeds = [int(x) for x in sys.argv[2].split(",")]
print(evalplan.summarize(evalplan.evaluate(plan, seeds, tag=sys.argv[3] if len(sys.argv) > 3 else "rp")))
