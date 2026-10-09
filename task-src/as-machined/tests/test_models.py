"""as-machined STEP models: each submitted solid must match what the stored programs cut"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_models  # noqa: E402

TRUTH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "truth")
PARTS = ["MNF-0610", "BRG-1140", "LVR-2205"]


@pytest.mark.parametrize("part", PARTS)
def test_model_matches_machined_part(part):
    path = f"/app/models/{part}.step"
    assert os.path.isfile(path), f"{path} missing"
    try:
        msg = check_models.compare(path, os.path.join(TRUTH, f"{part}.step"))
    except check_models.Bad as e:
        pytest.fail(f"{part}: {e}")
    print(part, msg)
