for f in dev/abl/*.sdc; do python3 - "$f" <<'PY'
import json,sys; sys.path.insert(0,'tests'); import grade
exp=json.load(open('tests/expected.json'))
try: c=grade.parse(open(sys.argv[1]).read())
except grade.SdcError as e: print(sys.argv[1],'REJECTED',e); sys.exit()
got,w=grade.edges(c); got={f'{a}|{b}|{c}':v for (a,b,c),v in got.items()}
bad=[k for k in set(exp)|set(got) if exp.get(k)!=got.get(k)]
print(sys.argv[1],'mismatches',len(bad),'wns',w)
PY
done
