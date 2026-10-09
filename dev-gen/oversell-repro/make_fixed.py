#!/usr/bin/env python3
"""Build the patched service tree from the shipped one.

The fix: the read path's publish must count the fast lane's open intents, not
only the committed ledger, so a record republished while an admission is in
flight cannot hand those units out a second time.
"""
import pathlib, shutil, sys

SRC = pathlib.Path(sys.argv[1])
DST = pathlib.Path(sys.argv[2])

OLD = """    stock = ledger.stock_rows(conn, skus)
    reserved = ledger.committed_reserved_many(conn, skus)"""
NEW = """    stock = ledger.stock_rows(conn, skus)
    reserved = admissions.pledged_reserved_many(conn, skus)"""

if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST, ignore=shutil.ignore_patterns("__pycache__"))
path = DST / "reservesvc" / "availability.py"
text = path.read_text()
if OLD not in text:
    raise SystemExit("publish_missing no longer matches the patch anchor")
path.write_text(text.replace(OLD, NEW, 1))
print(f"patched {path}")
