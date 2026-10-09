"""grades /app/exceptions.sdc against the proven multicycle table of the frozen cicd netlist."""
import json
import math
import os

import pytest

import grade

SDC = '/app/exceptions.sdc'
HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope='module')
def canon():
    assert os.path.isfile(SDC), f'{SDC} missing'
    text = open(SDC, errors='replace').read()
    assert len(text) < 4_000_000, 'sdc too large'
    return grade.parse(text)


@pytest.fixture(scope='module')
def result(canon):
    return grade.edges(canon)


def test_sdc_grammar(canon):
    assert canon.strip(), 'no exception commands in the file'


def test_every_path_edge_matches(result):
    got, _ = result
    exp = json.load(open(os.path.join(HERE, 'expected.json')))
    got = {f'{a}|{b}|{c}': v for (a, b, c), v in got.items()}
    missing = sorted(k for k in exp if k not in got)
    extra = sorted(k for k in got if k not in exp)
    wrong = sorted(k for k in exp if k in got
                   and not (isinstance(got[k], int) and got[k] == exp[k]))
    msg = []
    if missing:
        msg.append(f'{len(missing)} paths no longer timed, e.g. {missing[:3]}')
    if extra:
        msg.append(f'{len(extra)} unexpected paths, e.g. {extra[:3]}')
    if wrong:
        msg.append(f'{len(wrong)} paths with a wrong capture or hold edge, e.g. '
                   + ', '.join(f'{k}: got {got[k]} want {exp[k]}' for k in wrong[:3]))
    assert not msg, '; '.join(msg)


def test_block_meets_timing(result):
    _, (setup, hold) = result
    assert setup is not None and math.isfinite(setup) and setup >= 0, f'setup wns {setup}'
    assert hold is not None and math.isfinite(hold) and hold >= 0, f'hold wns {hold}'
