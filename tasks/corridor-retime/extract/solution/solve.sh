#!/usr/bin/env bash
# reference: clean the loop export (half term, stuck loop, crossed feeders, double counting loop),
# recover the estate road's demand by conservation, size the stages at a 120 s common cycle with
# J4 following J3 across the 60 m link, and write am_peak with the controller's own phase structure.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sumo --version | head -1
python3 "$HERE/retime.py" /app/utc /app/model/existing.add.xml /app/am_peak.add.xml
