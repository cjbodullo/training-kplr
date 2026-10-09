"""quick grader for iteration: grade.py truth.json outdir -> prints diffs, exit 0 iff pass."""
import hashlib, json, sys, tarfile
truth = json.load(open(sys.argv[1])); out = sys.argv[2]
files, lost = truth["files"], set(truth["lost"])
got = {}
with tarfile.open(out + "/recovered.tar") as t:
    for m in t.getmembers():
        if m.isdir():
            continue
        p = "/" + m.name.lstrip("./").lstrip("/") if not m.name.startswith("./") else m.name[1:]
        got[p] = hashlib.sha256(t.extractfile(m).read()).hexdigest()
gl = {l for l in open(out + "/lost.txt").read().split("\n") if l}
bad_content = sorted(p for p in got if p in files and files[p]["sha256"] != got[p])
extra = sorted(set(got) - set(files)); missing = sorted(set(files) - set(got) - gl)
print(f"wrong bytes {len(bad_content)} {bad_content[:6]}")
print(f"lost: should-be-lost-but-given {sorted(lost & set(got))}")
print(f"lost: listed-but-recoverable {sorted(gl - lost)}  missed-lost {sorted(lost - gl)}")
print(f"extra {extra[:5]} missing {missing[:5]}")
ok = not bad_content and not extra and not missing and gl == lost and not (lost & set(got))
print("PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
