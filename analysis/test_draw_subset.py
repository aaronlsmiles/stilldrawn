"""Tests for analysis/draw_subset.py: §6's frozen draw reproduces byte for byte; A11's draw
meets its strata; both reproduce in the release form. The A11 draw reads this repository's
results table (analysis/out/results_table.json, private ids) for its strata labels only
(engine, class, motion), never a metric value.

    python -m pytest analysis/test_draw_subset.py
"""
import dataclasses
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draw_subset as ds  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
A11 = ["--protocol", "a11", "--n", "40", "--seed", "20261104", "--min-engine", "6",
       "--min-class", "12", "--min-motion", "12"]
# Pinned, not recomputed: the committed §6 record (frozen since August 2026) and A11's draw (4 Nov 2026),
# in both forms. The release renames the creator-IP panel inside the records, so their bytes differ
# there; the draws (the cells, in the same order) are the same. The tests pick the form by whether the
# results table carries the public id.
PUBLIC_ID = "cip-act-tank-1"
PINNED = {"private": {"s6": "6b0803174b12d817e018827af2a68edf0260fb93fd0e67ec5a33ccef23dd7d6f",
                      "a11": "e2d72c62d09ce9935b406cff6f0da44f9597953108e7635bb2cc160ee87d8ab6"},
          "release": {"s6": "3a13934ba3565c6b1d377dbb0693760c7a66a392280b0b1b24595167f6798311",
                      "a11": "b0a38b527c92955b65bc2e10c537e9904382eb38af298fd19ad9eb754883e7cd"}}


def tree_form(table=OUT / "results_table.json"):
    """The tree's form: "release" when the results table carries the creator-IP panel's
    public id, else "private"."""
    ids = [r["cell_id"] for r in json.loads(Path(table).read_text())]
    return "release" if any(i.startswith(PUBLIC_ID + "_") for i in ids) else "private"


FORM = tree_form()
S6_SHA256 = PINNED[FORM]["s6"]
A11_SHA256 = PINNED[FORM]["a11"]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def synthetic_rows(tank):
    """164 standard cells laid out like the real table (5 engines x 33, one cell refused) plus FLINT."""
    tags = {"gen4_turbo": "gen4t", "h3-fal": "h3", "gen4.5": "gen45", "wan22": "wan22", "ltx23": "ltx23"}
    rows = []
    for engine, tag in tags.items():
        panels = [(f"{c}-{t}-{n}", c) for c in ds.CLASSES for t in ("line", "tone", "black") for n in (1, 2, 3)]
        cells = [(p, c, ds.MOTIONS[i % 3]) for i, (p, c) in enumerate(panels)]
        cells += [(tank, "act", m) for m in ds.MOTIONS] + [("chain-est-cosmic-1", "est", m) for m in ds.MOTIONS]
        rows += [{"cell_id": f"{p}_{m.lower()}_{tag}", "engine": engine, "content_class": c, "motion": m}
                 for p, c, m in cells]
    rows = [r for r in rows if r["cell_id"] != "cu-tone-3_campush_gen4t"]
    rows.append({"cell_id": "flint-a--b_h3", "engine": "h3-fal", "content_class": "cu", "motion": "FLINT"})
    return rows


def real_pool():
    return [r for r in json.loads((OUT / "results_table.json").read_text()) if r["motion"] != "FLINT"]


def test_the_committed_records_match_their_pinned_hashes():
    assert sha256(OUT / "human_subset.json") == S6_SHA256
    assert sha256(OUT / "a11_subset.json") == A11_SHA256


def test_the_default_invocation_reproduces_the_frozen_subset_byte_for_byte(tmp_path):
    out = tmp_path / "human_subset.json"
    ds.main(["--out", str(out)])
    assert sha256(out) == S6_SHA256


def test_the_protocol_name_alone_reproduces_the_a11_draw(tmp_path):
    out = tmp_path / "a11.json"
    ds.main(["--protocol", "a11", "--out", str(out)])
    assert sha256(out) == A11_SHA256


def test_the_long_registered_command_gives_the_same_a11_draw(tmp_path):
    out = tmp_path / "a11.json"
    ds.main(A11 + ["--exclude", str(OUT / "human_subset.json"), "--out", str(out)])
    assert sha256(out) == A11_SHA256


def test_each_protocol_writes_to_its_own_default_output():
    assert ds.PROTOCOLS["s6"].out == OUT / "human_subset.json"
    assert ds.PROTOCOLS["a11"].out == OUT / "a11_subset.json"
    assert ds.PROTOCOLS["a11"].exclude == OUT / "human_subset.json"


def test_the_a11_draw_meets_its_strata_and_excludes_the_a6_clips(tmp_path):
    out = tmp_path / "a11.json"
    ds.main(["--protocol", "a11", "--out", str(out)])
    rec = json.loads(out.read_text())
    cells = rec["cells"]
    a6 = set(json.loads((OUT / "human_subset.json").read_text())["cells"])
    rows = {r["cell_id"]: r for r in json.loads((OUT / "results_table.json").read_text())}
    assert len(cells) == 40 == len(set(cells)) and not (set(cells) & a6)
    assert all(rows[c]["motion"] != "FLINT" for c in cells)
    for dim, need, groups in (("engine", 6, 5), ("content_class", 12, 3), ("motion", 12, 3)):
        counts = Counter(rows[c][dim] for c in cells)
        assert len(counts) == groups and min(counts.values()) >= need, (dim, counts)
    assert rec["seed_declared"] == 20261104 and rec["n"] == 40 and rec["n_excluded"] == 20
    assert rec["protocol"] == "docs/PREREGISTRATION.md A11" and rec["excluded_from"] == "human_subset.json"


def test_the_a11_draw_is_deterministic(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    for out in (a, b):
        ds.main(["--protocol", "a11", "--out", str(out)])
    assert a.read_bytes() == b.read_bytes()


def test_frozen_key_keeps_the_order_of_the_frozen_draw():
    """§6 sorted the private ids plainly, which put the creator-IP cells last. In the private tree
    the frozen key moves no cell; in the release (public ids, which sort elsewhere) it puts the
    creator-IP cells last and every other cell in its plain order."""
    ids = [r["cell_id"] for r in real_pool()]
    keyed = sorted(ids, key=ds.frozen_key)
    if FORM == "private":
        assert keyed == sorted(ids)
    else:
        tank = sorted(i for i in ids if i.startswith(PUBLIC_ID + "_"))
        assert tank and keyed == sorted(set(ids) - set(tank)) + tank
        assert keyed != sorted(ids)                       # the plain sort would start the shuffle elsewhere


def test_the_tree_form_follows_the_creator_ip_id(tmp_path):
    for prefix, form in (("xyz", "private"), ("cip", "release")):
        table = tmp_path / f"{prefix}.json"
        table.write_text(json.dumps(synthetic_rows(f"{prefix}-act-tank-1")))
        assert tree_form(table) == form


@pytest.mark.parametrize("protocol", ["s6", "a11"])
def test_both_draws_reproduce_in_the_release_form(tmp_path, protocol):
    """The release renames the creator-IP panel's three-letter prefix to `cip`. Both protocols
    must give the same draw once the private output is renamed the same way. A11 excludes the
    §6 record drawn from the same table."""
    outs = {}
    for prefix in ("xyz", "cip"):
        tree = tmp_path / prefix  # one folder per tree, so the recorded file names match
        tree.mkdir()
        table = tree / "results_table.json"
        table.write_text(json.dumps(synthetic_rows(f"{prefix}-act-tank-1")))
        s6 = tree / "human_subset.json"
        ds.main(["--table", str(table), "--out", str(s6)])
        out = s6
        if protocol == "a11":
            out = tree / "a11_subset.json"
            ds.main(["--protocol", "a11", "--table", str(table), "--exclude", str(s6), "--out", str(out)])
        outs[prefix] = out.read_text()
    assert outs["xyz"].replace("xyz-act-tank-1", "cip-act-tank-1") == outs["cip"]


def test_exclude_refuses_ids_that_are_not_standard_cells(tmp_path):
    table = tmp_path / "t.json"
    table.write_text(json.dumps(synthetic_rows("cip-act-tank-1")))
    ex = tmp_path / "ex.json"
    ex.write_text(json.dumps(["not-a-cell_idle_h3"]))
    with pytest.raises(SystemExit):
        ds.main(["--protocol", "a11", "--table", str(table), "--exclude", str(ex),
                 "--out", str(tmp_path / "o.json")])


def test_a_same_named_exclusion_listing_other_cells_is_refused(tmp_path):
    a6 = set(json.loads((OUT / "human_subset.json").read_text())["cells"])
    others = sorted(r["cell_id"] for r in real_pool() if r["cell_id"] not in a6)[:20]
    fake = tmp_path / "human_subset.json"
    fake.write_text(json.dumps({"cells": others}))
    with pytest.raises(SystemExit, match="not §6's draw"):
        ds.main(["--protocol", "a11", "--exclude", str(fake), "--out", str(tmp_path / "o.json")])
    assert not (tmp_path / "o.json").exists()


@pytest.mark.parametrize("args", [
    ["--n", "21"],
    ["--seed", "1"],
    ["--min-engine", "9"],
    ["--protocol", "a11", "--min-class", "11"],
    ["--protocol", "a11", "--n", "20"],
    ["--exclude", str(OUT / "human_subset.json")],   # §6 excludes nothing
])
def test_values_other_than_the_preset_are_refused(tmp_path, args):
    with pytest.raises(SystemExit):
        ds.main(args + ["--out", str(tmp_path / "o.json")])
    assert not (tmp_path / "o.json").exists()


def test_a_protocol_refuses_to_write_another_protocols_record():
    before = sha256(OUT / "human_subset.json")
    with pytest.raises(SystemExit):
        ds.main(["--protocol", "a11", "--out", str(OUT / "human_subset.json")])
    with pytest.raises(SystemExit):
        ds.main(["--out", str(OUT / "a11_subset.json")])
    assert sha256(OUT / "human_subset.json") == before == S6_SHA256


@pytest.mark.parametrize("mins", [(9, 12, 12), (6, 14, 12), (6, 12, 14)])
def test_impossible_minimums_are_refused_before_drawing(mins):
    proto = dataclasses.replace(ds.PROTOCOLS["a11"], mins=mins)
    with pytest.raises(SystemExit):
        ds.select(real_pool(), proto)


def test_a_stratum_smaller_than_its_minimum_is_refused():
    pool = real_pool()
    proto = dataclasses.replace(ds.PROTOCOLS["s6"], mins=(34, 6, 6), n=170)
    with pytest.raises(SystemExit):
        ds.check_feasible(pool, 164, (34, 6, 6))
    with pytest.raises(SystemExit):
        ds.select(pool, proto)


def test_the_reseed_loop_stops_and_names_the_seeds(monkeypatch):
    monkeypatch.setattr(ds, "draw", lambda *a, **k: None)
    with pytest.raises(SystemExit) as e:
        ds.select(real_pool(), ds.PROTOCOLS["s6"])
    assert f"{ds.SEED}..{ds.SEED + ds.MAX_RESEEDS - 1}" in str(e.value)
