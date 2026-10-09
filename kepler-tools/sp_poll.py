import sys, json, datetime
sys.path.insert(0,'/home/osboxes/Downloads/afterquery_kepler/kepler-tools')
import kepler_api as k
d = k.get("H4gFVkSwfc0ONMWVyF4b")
p = d.get("pipeline") or {}
print(datetime.datetime.now().strftime("%H:%M"), "status:", d.get("status"), "| stage:", p.get("stage"))
for name, v in p.items():
    if isinstance(v, dict):
        vd = v.get("verdict") or v.get("status") or v.get("band")
        err = v.get("error")
        if vd or err:
            print("   %-18s %s%s" % (name, vd, (" ERR:"+str(err)[:120]) if err else ""))
