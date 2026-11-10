"""Tests for analysis/draw_ladder_panels.py (A10's 12-panel draw). No clip is read.

    python -m pytest analysis/test_draw_ladder_panels.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import draw_ladder_panels as dl  # noqa: E402

METADATA = HERE.parent / "dataset" / "panel-metadata.json"
SHIPPED = HERE / "out" / "a10_panels.json"


def check(panels):
    assert len(panels) == 12 and len(set(panels)) == 12
    assert set(panels) <= set(dl.core_panels())
    cls = Counter(p.split("-")[0] for p in panels)
    trt = Counter(p.split("-")[1] for p in panels)
    cell = Counter(tuple(p.split("-")[:2]) for p in panels)
    assert set(cls.values()) == {4} and set(trt.values()) == {4}
    assert len(cell) == 9 and sorted(cell.values()) == [1] * 6 + [2] * 3
    doubled = [c for c, n in cell.items() if n == 2]
    assert len({c for c, _ in doubled}) == 3 and len({t for _, t in doubled}) == 3


def test_the_pool_is_the_27_core_panels_only():
    pool = dl.core_panels()
    assert len(pool) == 27 and len(set(pool)) == 27
    ids = set(json.loads(METADATA.read_text()))
    assert set(pool) <= ids
    assert len(ids - set(pool)) == 2


def test_the_constraints_hold_for_many_seeds():
    for seed in range(300):
        panels, doubled = dl.draw(seed)
        check(panels)
        cell = Counter("-".join(p.split("-")[:2]) for p in panels)
        assert len(doubled) == 3
        assert doubled == sorted(c for c, n in cell.items() if n == 2)


def test_the_same_seed_gives_the_same_record_and_bytes(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    dl.main(["--out", str(a)])
    dl.main(["--out", str(b)])
    assert a.read_bytes() == b.read_bytes()
    rec = json.loads(a.read_text())
    assert rec["seed"] == dl.SEED == 20261104 and rec["panels"] == dl.draw(dl.SEED)[0]
    check(rec["panels"])


def test_different_seeds_give_different_draws():
    assert len({tuple(dl.draw(s)[0]) for s in range(1, 21)}) > 1


def test_the_shipped_record_matches_the_code():
    shipped, fresh = json.loads(SHIPPED.read_text()), dl.record()
    recorded = shipped.pop("python_version")
    fresh.pop("python_version")
    assert shipped == fresh
    if sys.version.split()[0] == recorded:
        assert SHIPPED.read_text() == json.dumps(dl.record(), indent=1) + "\n"
