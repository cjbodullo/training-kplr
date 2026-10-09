"""vendor prints -> STEP: each submitted model must match the sealed original solid"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_models  # noqa: E402

TRUTH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "truth")
PARTS = ["BRK-2210", "FLG-0417", "HSG-3305", "SHF-1150", "CVR-5120", "BKT-3302"]


@pytest.mark.parametrize("part", PARTS)
def test_model_matches_print(part):
    path = f"/app/models/{part}.step"
    assert os.path.isfile(path), f"{path} missing"
    try:
        msg = check_models.compare(path, os.path.join(TRUTH, f"{part}.step"))
    except check_models.Bad as e:
        pytest.fail(f"{part}: {e}")
    print(part, msg)
