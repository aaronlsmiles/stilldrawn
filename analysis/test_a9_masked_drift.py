"""Tests for analysis/a9_masked_drift.py (A9 Test 2). Synthetic fixtures only: no
masked value and no released value is read here.

    python -m pytest analysis/test_a9_masked_drift.py
"""
import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a9_masked_drift as md  # noqa: E402

A1 = ["cip-act-tank-1", "chain-est-cosmic-1"]               # each carries an idle and a burst row
IDLE_ONLY = ["cu-i-1", "cu-i-2", "cu-tone-3"] + [f"cu-i-{i}" for i in range(4, 10)]
ROWS = [(p, "idle") for p in A1 + IDLE_ONLY] + \
       [(p, "burst") for p in A1 + [f"act-b-{i}" for i in range(1, 10)]]
WHOLE = {"wan22": 1.0, "gen4_turbo": 2.6, "ltx23": 2.8, "gen4.5": 8.0, "h3-fal": 9.0}


def cid(panel, motion, engine):
    """The public cell id: <panel>_<motion>_<short engine suffix>, as metrics/masked.py forms it."""
    return f"{panel}_{motion}_{md.SUFFIX[engine]}"


def write_clip(d, panel, motion, engine, whole, masked, f0=5000, no_score=False, m_empty=None):
    # whole=None writes a null whole-frame value (read as +inf)
    rec = {"cell_id": cid(panel, motion, engine), "panel": panel, "motion": motion, "engine": engine,
           "whole_frame": {"chamfer_px": whole},
           "m_empty": {s: bool((m_empty or {}).get(s, False)) for s in md.SETS},
           "masked": {s: {f"m{m}": {"chamfer_px": None if no_score else masked[s],
                                    "no_scorable_frame": no_score, "f0_line_px_in_R": f0[s] if isinstance(f0, dict) else f0,
                                    "region_frac": 0.5, "chamfer_series": []} for m in md.MARGINS}
                      for s in md.SETS}}
    (d / f"{rec['cell_id']}.json").write_text(json.dumps(rec))


def fixture(root, masked_ratio=None, whole=WHOLE, eligible=None, f0=None, no_score=(), whole_null=(), m_empty=None):
    """masked_ratio: {set: Gen-4.5 / Wan ratio of the masked medians}; other engines keep
    the whole-frame order. m_empty: {cell_id: {set: True}}; f0: {cell_id: f0 line px, or {set: px}}; no_score: cell ids with no scorable frame."""
    masked_ratio = masked_ratio or {"aaron": 2.0, "agent": 2.0}
    d = root / "runs" / "metrics-masked"
    d.mkdir(parents=True, exist_ok=True)
    for i, (panel, motion) in enumerate(ROWS):
        for e, w in whole.items():
            if (panel, motion, e) == ("cu-tone-3", "idle", "gen4_turbo"):
                continue                                      # Turbo's refused idle cell stays missing
            noise = 1 + 0.001 * i
            masked = {}
            for s, r in masked_ratio.items():
                base = {"wan22": 1.0, "gen4_turbo": 1.1, "ltx23": 1.2, "gen4.5": r, "h3-fal": r + 0.5}[e]
                masked[s] = base * noise
            cell = cid(panel, motion, e)
            write_clip(d, panel, motion, e, None if cell in whole_null else w * noise, masked, f0=(f0 or {}).get(cell, 5000),
                       no_score=cell in no_score, m_empty=(m_empty or {}).get(cell))
    out = root / "analysis" / "out"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "a9_eligible.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["row", "eligible"])
        for panel, motion in ROWS:
            key = f"{panel}_{motion}"
            w.writerow([key, "true" if eligible is None or key in eligible else "false"])
    return root


# --------------------------------------------------------------------- numbers
def test_gap_shrink_and_delta():
    D = {"wan22": 1.0, "gen4.5": 8.0}
    assert md.gap(D) == 3.0
    assert md.shrink(3.0, 1.0) == pytest.approx(2 / 3)
    assert math.isnan(md.shrink(0.0, 1.0)) and math.isnan(md.shrink(math.inf, 1.0))


def test_kendall_tau_b():
    assert md.kendall_tau_b([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == 1.0
    assert md.kendall_tau_b([1, 2, 3, 4, 5], [1, 3, 2, 4, 5]) == pytest.approx(0.8)
    assert md.kendall_tau_b([1, 2, 2, 3], [1, 2, 3, 4]) == pytest.approx(5 / math.sqrt(30))
    assert md.kendall_tau_b([1, 2], [1, math.inf]) is None


def _cond(g_whole, s, tau=1.0, ci=(0.4, 0.9)):
    return {"g_whole": g_whole, "s": s, "kendall_tau_b": tau, "bootstrap": {"s_ci95": list(ci) if ci else None}}


def test_verdict_rules():
    assert md.verdict(_cond(2.6, 0.6), _cond(2.6, 0.55)) == "supported"
    assert md.verdict(_cond(2.6, 0.6, ci=(-0.1, 0.9)), _cond(2.6, 0.6)) == "not supported"
    assert md.verdict(_cond(2.6, 0.6), _cond(2.6, 0.3)) == "mask-dependent"
    assert md.verdict(_cond(2.6, 0.2), _cond(2.6, 0.6)) == "mask-dependent"
    assert md.verdict(_cond(2.6, 0.1), _cond(2.6, 0.2)) == "killed"
    assert md.verdict(_cond(2.6, 0.1, tau=0.8), _cond(2.6, 0.2)) == "not supported"
    assert md.verdict(_cond(2.6, 0.3), _cond(2.6, 0.2)) == "not supported"
    assert md.verdict(_cond(0.9, 0.9), _cond(2.6, 0.9)) == "not testable"
    assert md.verdict(_cond(None, None), _cond(2.6, 0.9)) == "not testable"


def test_condition_clips_exclude_small_frame0_from_both_columns(tmp_path):
    root = fixture(tmp_path, f0={"cu-i-1_idle_wan22": 499})
    clips = md.load_clips(root)
    eligible = md.load_eligible(root / "analysis" / "out" / "a9_eligible.csv")
    kept, excluded = md.condition_clips(clips, eligible, "aaron", 32, ("idle", "burst"))
    assert [c["cell_id"] for c in excluded] == ["cu-i-1_idle_wan22"]
    assert len(kept) == 108 and all(c["cell_id"] != "cu-i-1_idle_wan22" for c in kept)
    kept_idle, _ = md.condition_clips(clips, eligible, "aaron", 32, ("idle",))
    assert {c["cell_id"].split("_")[1] for c in kept_idle} == {"idle"}


def test_replicate_brings_both_rows_of_an_a1_panel():
    kept = [{"cell_id": "a", "panel": "cip-act-tank-1", "engine": "wan22", "whole": 1.0, "masked": 1.0},
            {"cell_id": "b", "panel": "cip-act-tank-1", "engine": "wan22", "whole": 3.0, "masked": 5.0},
            {"cell_id": "c", "panel": "p", "engine": "wan22", "whole": 100.0, "masked": 100.0}]
    arrays = md.per_engine_arrays(kept, ["cip-act-tank-1", "p"])
    Dw, Dm = md.replicate(arrays, np.array([2, 0]))
    assert Dw["wan22"] == 2.0 and Dm["wan22"] == 3.0
    assert math.isnan(Dw["gen4.5"])


def test_panel_draws_golden():
    """Literal values of numpy.random.default_rng(20261030).integers(0, 5, size=(2, 5)) on the
    stack recorded in a9_masked_drift.py's docstring; a numpy that changes them must not go unnoticed."""
    assert np.random.default_rng(20261030).integers(0, 5, size=(2, 5)).tolist() == [[3, 2, 0, 3, 1], [0, 1, 2, 3, 4]]
    assert md.panel_draws(list("abcde"), b=2).tolist() == [[3, 2, 0, 3, 1], [0, 1, 2, 3, 4]]
    assert md.panel_draws(list("abcde"), b=50).shape == (50, 5)


# ------------------------------------------------------------------- the run
def test_supported_when_the_gap_halves_under_both_sets(tmp_path):
    res = md.run(fixture(tmp_path), b=200)
    c = {(x["mask_set"], x["margin_px"]): x for x in res["grid"]["all"]}[("aaron", 32)]
    assert c["g_whole"] == pytest.approx(3.0, abs=0.01) and c["g_masked"] == pytest.approx(1.0, abs=0.01)
    assert c["s"] == pytest.approx(2 / 3, abs=0.01) and c["n_clips"]["gen4_turbo"] == 21
    assert res["verdict"] == "supported"


def test_mask_dependent_when_one_set_disagrees(tmp_path):
    res = md.run(fixture(tmp_path, masked_ratio={"aaron": 2.0, "agent": 8.0}), b=200)
    assert res["verdict"] == "mask-dependent"


def test_killed_when_order_and_gap_survive(tmp_path):
    res = md.run(fixture(tmp_path, masked_ratio={"aaron": 7.0, "agent": 7.5}), b=200)
    assert res["verdict"] == "killed"


def test_not_testable_when_the_whole_frame_gap_is_small(tmp_path):
    res = md.run(fixture(tmp_path, whole=dict(WHOLE, **{"gen4.5": 1.5, "h3-fal": 1.6})), b=200)
    assert res["verdict"] == "not testable"


def test_full_grid_and_splits(tmp_path):
    res = md.run(fixture(tmp_path), b=100)
    assert set(res["grid"]) == {"all", "idle", "burst"}
    for split, conds in res["grid"].items():
        assert [(c["mask_set"], c["margin_px"]) for c in conds] == [(s, m) for s in md.SETS for m in md.MARGINS]
    idle = res["grid"]["idle"][0]
    assert sum(idle["n_clips"].values()) == 11 * 5 - 1


def test_ineligible_rows_drop_out(tmp_path):
    keep = {f"{p}_{m}" for p, m in ROWS[:15]}
    res = md.run(fixture(tmp_path, eligible=keep), b=100)
    assert res["n_eligible_rows"] == 15
    assert sum(res["grid"]["all"][0]["n_clips"].values()) == 15 * 5 - 1


def test_no_scorable_frame_counts_as_infinite_and_json_stays_finite(tmp_path):
    root = fixture(tmp_path, no_score={"cu-i-1_idle_gen45", "cu-i-2_idle_gen45"})
    res = md.run(root, b=100)
    text = (tmp_path / "analysis" / "out" / "a9_masked_drift.json").read_text()
    assert "Infinity" not in text and "NaN" not in text
    clips = {c["cell_id"]: c for c in md.load_clips(root)}
    assert clips["cu-i-1_idle_gen45"]["masked"][("aaron", 32)][0] == math.inf
    assert res["grid"]["all"][1]["D_masked_px"]["gen4.5"] is not None     # two infinities do not move the median far


def test_eligibility_file_is_checked(tmp_path):
    root = fixture(tmp_path)
    p = root / "analysis" / "out" / "a9_eligible.csv"
    p.write_text("row,eligible\n" + "".join(f"{a}_{b},true\n" for a, b in ROWS[:21]))
    with pytest.raises(SystemExit, match="expected 22 rows"):
        md.run(root, b=10)
    p.write_text("row,eligible\n" + "".join(f"{a}_{b},yes\n" for a, b in ROWS))
    with pytest.raises(SystemExit, match="true or false"):
        md.run(root, b=10)


def test_nothing_to_analyse_before_the_registered_run(tmp_path):
    with pytest.raises(SystemExit, match="a9-run"):
        md.run(tmp_path, b=10)


def test_two_runs_are_byte_identical(tmp_path):
    root = fixture(tmp_path, masked_ratio={"aaron": 3.0, "agent": 4.0})
    md.run(root, out_dir=tmp_path / "o1", b=300)
    md.run(root, out_dir=tmp_path / "o2", b=300)
    for name in ("a9_masked_drift.json", "a9_masked_drift.md", "figures/a9_masked_drift.png"):
        assert (tmp_path / "o1" / name).read_bytes() == (tmp_path / "o2" / name).read_bytes(), name


def test_markdown_wording(tmp_path):
    md.run(fixture(tmp_path), b=100)
    text = (tmp_path / "analysis" / "out" / "a9_masked_drift.md").read_text()
    assert "Post-hoc (A9): on 109 cells, Gen-4.5/Wan falls from 8.0× to 2.0×" in text
    assert "The frozen league is unchanged; this qualifies how its gap is read." in text
    assert "no rank column" in text and "doublings" not in text


# ------------------------------------------------- verdict boundaries (frozen with the file)
def test_s_exactly_one_half_counts_as_high():
    assert md.verdict(_cond(2.6, 0.5), _cond(2.6, 0.5)) == "supported"
    assert md.verdict(_cond(2.6, 0.5), _cond(2.6, 0.4999999)) == "mask-dependent"
    assert md.verdict(_cond(2.6, 0.4999999), _cond(2.6, 0.5)) == "mask-dependent"


def test_s_exactly_a_quarter_is_not_killed():
    assert md.verdict(_cond(2.6, 0.25), _cond(2.6, 0.25)) == "not supported"
    assert md.verdict(_cond(2.6, 0.25), _cond(2.6, 0.1)) == "not supported"
    assert md.verdict(_cond(2.6, 0.2499999), _cond(2.6, 0.2499999)) == "killed"


def test_g_whole_exactly_one_is_testable():
    assert md.verdict(_cond(1.0, 0.6), _cond(1.0, 0.6)) == "supported"
    assert md.verdict(_cond(0.9999999, 0.6), _cond(1.0, 0.6)) == "not testable"
    assert md.verdict(_cond(1.0, 0.6), _cond(0.9999999, 0.6)) == "not testable"


def test_not_testable_from_the_agent_set_alone():
    assert md.verdict(_cond(2.6, 0.9), _cond(0.5, 0.9)) == "not testable"
    assert md.verdict(_cond(2.6, 0.9), _cond(None, None)) == "not testable"


def test_ci_lower_endpoint_must_be_strictly_positive():
    # registered rule: the lower endpoint of the bootstrap 95% interval for s (Aaron's masks) is > 0
    assert md.verdict(_cond(2.6, 0.6, ci=(0.0, 0.9)), _cond(2.6, 0.6)) == "not supported"     # exactly 0 fails
    assert md.verdict(_cond(2.6, 0.6, ci=(-0.9, 0.0)), _cond(2.6, 0.6)) == "not supported"
    assert md.verdict(_cond(2.6, 0.6, ci=(1e-9, 0.9)), _cond(2.6, 0.6)) == "supported"        # tiny positive passes
    assert md.verdict(_cond(2.6, 0.6, ci=None), _cond(2.6, 0.6)) == "not supported"


def test_ci_entirely_below_zero_is_not_supported():
    # an interval wholly below 0 is not evidence of shrinkage, whatever the point estimates say
    assert md.verdict(_cond(2.6, 0.6, ci=(-0.9, -1e-9)), _cond(2.6, 0.6)) == "not supported"
    assert md.verdict(_cond(2.6, 0.6, ci=(-0.9, -0.1)), _cond(2.6, 0.6)) == "not supported"


def test_ci_non_finite_or_missing_fails():
    nan, inf = float("nan"), float("inf")
    for ci in ((nan, 0.9), (0.2, nan), (nan, nan), (inf, inf), (0.2, inf)):
        assert md.verdict(_cond(2.6, 0.6, ci=ci), _cond(2.6, 0.6)) == "not supported", ci
    assert md.verdict(_cond(2.6, 0.6, ci=[0.2]), _cond(2.6, 0.6)) == "not supported"
    c = _cond(2.6, 0.6)
    del c["bootstrap"]["s_ci95"]
    assert md.verdict(c, _cond(2.6, 0.6)) == "not supported"


def test_rule_text_names_the_lower_endpoint():
    assert "lower endpoint" in md.RULES["supported"] and "strictly" in md.RULES["supported"]


def test_tau_just_under_one_is_not_killed():
    tau = md.kendall_tau_b([1, 2, 3, 4, 5], [1, 2, 4, 3, 5])          # one adjacent swap
    assert tau == pytest.approx(0.8) and tau < 1
    assert md.verdict(_cond(2.6, 0.1, tau=tau), _cond(2.6, 0.1)) == "not supported"
    assert md.verdict(_cond(2.6, 0.1), _cond(2.6, 0.1, tau=tau)) == "not supported"
    assert md.verdict(_cond(2.6, 0.1, tau=1 - 1e-9), _cond(2.6, 0.1)) == "not supported"
    assert md.verdict(_cond(2.6, 0.1, tau=None), _cond(2.6, 0.1)) == "not supported"
    assert md.verdict(_cond(2.6, 0.1, tau=1.0), _cond(2.6, 0.1, tau=1.0)) == "killed"


def test_s_none_under_both_sets():
    assert md.verdict(_cond(2.6, None), _cond(2.6, None)) == "not supported"
    assert md.verdict(_cond(2.6, None), _cond(2.6, 0.6)) == "mask-dependent"
    assert md.verdict(_cond(2.6, 0.6), _cond(2.6, None)) == "mask-dependent"


def test_frame0_threshold_500_is_kept_and_499_dropped(tmp_path):
    root = fixture(tmp_path, f0={"cu-i-1_idle_wan22": 500, "cu-i-2_idle_wan22": 499})
    clips = md.load_clips(root)
    eligible = md.load_eligible(root / "analysis" / "out" / "a9_eligible.csv")
    kept, excluded = md.condition_clips(clips, eligible, "aaron", 32, ("idle", "burst"))
    ids = {c["cell_id"] for c in kept}
    assert "cu-i-1_idle_wan22" in ids and "cu-i-2_idle_wan22" not in ids
    assert [c["cell_id"] for c in excluded] == ["cu-i-2_idle_wan22"]


def test_g_whole_differs_between_mask_sets_when_exclusions_differ(tmp_path):
    f0 = {f"{p}_idle_wan22": {"aaron": 5000, "agent": 100} for p in IDLE_ONLY}
    res = md.run(fixture(tmp_path, f0=f0), b=100)
    pick = {(c["mask_set"], c["margin_px"]): c for c in res["grid"]["all"]}
    a, g = pick[("aaron", 32)], pick[("agent", 32)]
    assert a["n_clips"]["wan22"] == 22 and g["n_clips"]["wan22"] == 13
    assert len(g["excluded_lt500"]) == 9 and a["excluded_lt500"] == []
    assert a["g_whole"] != g["g_whole"]
    assert res["verdict"] == "supported"                              # each set judged on its own g_whole


# ------------------------------------------------------------------ bootstrap output
def test_bootstrap_intervals_are_present_and_ordered(tmp_path):
    res = md.run(fixture(tmp_path), b=200)
    for conds in res["grid"].values():
        for c in conds:
            bs = c["bootstrap"]
            assert bs["B"] == 200 and bs["seed"] == 20261030
            for key in ("s_ci95", "delta_g_ci95"):
                lo, hi = bs[key]
                assert math.isfinite(lo) and math.isfinite(hi) and lo <= hi
            assert bs["n_s_finite"] == 200 and bs["n_delta_g_finite"] == 200 and bs["n_g_whole_le_0"] == 0


def test_bootstrap_counts_replicates_with_g_whole_not_positive():
    panels = ["p0", "p1"]
    kept = [{"cell_id": "a", "panel": "p0", "engine": "wan22", "whole": 1.0, "masked": 1.0},
            {"cell_id": "b", "panel": "p0", "engine": "gen4.5", "whole": 2.0, "masked": 2.0},
            {"cell_id": "c", "panel": "p1", "engine": "wan22", "whole": 2.0, "masked": 2.0},
            {"cell_id": "d", "panel": "p1", "engine": "gen4.5", "whole": 1.0, "masked": 1.0}]
    draws = np.array([[0, 0], [1, 1], [0, 1]])        # g_whole = 1, -1, 0
    bs = md.bootstrap(kept, panels, draws)
    assert bs["B"] == 3 and bs["n_g_whole_le_0"] == 2 and bs["n_s_finite"] == 2
    assert bs["s_ci95"] == [0.0, 0.0]


def test_bootstrap_with_no_positive_gap_has_no_interval_and_json_stays_finite(tmp_path):
    root = fixture(tmp_path, whole=dict(WHOLE, **{"gen4.5": 1.0, "h3-fal": 1.0}))
    res = md.run(root, b=100)
    c = res["grid"]["all"][1]
    assert c["bootstrap"]["n_g_whole_le_0"] == 100 and c["bootstrap"]["n_s_finite"] == 0
    assert c["bootstrap"]["s_ci95"] is None and c["s"] is None
    assert res["verdict"] == "not testable"
    text = (tmp_path / "analysis" / "out" / "a9_masked_drift.json").read_text()
    assert "NaN" not in text and "Infinity" not in text


def test_all_six_conditions_of_a_split_share_the_same_draws(tmp_path, monkeypatch):
    calls, orig = [], md.bootstrap

    def spy(kept, panels, draws):
        calls.append((list(panels), draws.copy()))
        return orig(kept, panels, draws)

    monkeypatch.setattr(md, "bootstrap", spy)
    md.run(fixture(tmp_path), b=40)
    assert len(calls) == 18
    for k, n_panels in enumerate((20, 11, 11)):              # all, idle, burst; 2 A1 panels count once
        group = calls[6 * k: 6 * k + 6]
        panels, first = group[0]
        assert len(panels) == n_panels and first.shape == (40, n_panels)
        assert np.array_equal(first, md.panel_draws(panels, b=40))
        for p, d in group[1:]:
            assert p == panels and np.array_equal(d, first)


# ----------------------------------------------------------------- input validation
def _refuses(root, pattern):
    with pytest.raises(SystemExit, match=pattern):
        md.run(root, b=10)
    assert not (root / "analysis" / "out" / "a9_masked_drift.json").exists()      # nothing was computed


def _edit(root, name, **changes):
    p = root / "runs" / "metrics-masked" / f"{name}.json"
    d = json.loads(p.read_text())
    d.update(changes)
    p.write_text(json.dumps(d))


def test_refuses_a_wrong_number_of_clip_files(tmp_path):
    root = fixture(tmp_path)
    (root / "runs" / "metrics-masked" / "cu-i-1_idle_wan22.json").unlink()
    _refuses(root, "expected 109 clip files, found 108")


def test_refuses_too_many_clip_files(tmp_path):
    root = fixture(tmp_path)
    d = root / "runs" / "metrics-masked"
    (d / "extra.json").write_text((d / "cu-i-2_idle_wan22.json").read_text())
    _refuses(root, "expected 109 clip files, found 110")


def test_refuses_duplicate_cell_ids(tmp_path):
    root = fixture(tmp_path)
    _edit(root, "cu-i-1_idle_wan22", cell_id="cu-i-2_idle_wan22")
    _refuses(root, "duplicate cell ids")


def test_refuses_a_missing_or_unknown_engine(tmp_path):
    root = fixture(tmp_path)
    for panel, motion in ROWS:
        _edit(root, cid(panel, motion, "h3-fal"), engine="h3")
    _refuses(root, r"missing \['h3-fal'\], unexpected \['h3'\]")


def test_refuses_a_motion_other_than_idle_or_burst(tmp_path):
    root = fixture(tmp_path)
    _edit(root, "cu-i-1_idle_wan22", motion="push")
    _refuses(root, "motion must be idle or burst")


def test_refuses_a_clip_row_missing_from_the_csv(tmp_path):
    root = fixture(tmp_path)
    _edit(root, "cu-i-1_idle_wan22", panel="zz-unknown", cell_id="zz-unknown_idle_wan22")
    _refuses(root, r"zz-unknown_idle.*not in a9_eligible\.csv")


def test_refuses_a_csv_row_with_no_clips(tmp_path):
    root = fixture(tmp_path)
    for e in WHOLE:                                      # every clip of one row now claims another row
        _edit(root, cid("cu-i-9", "idle", e), panel="cu-i-8")
    _refuses(root, r"rows without clips: \['cu-i-9_idle'\]")


def test_refuses_duplicate_csv_rows(tmp_path):
    root = fixture(tmp_path)
    p = root / "analysis" / "out" / "a9_eligible.csv"
    lines = p.read_text().splitlines()
    lines[2] = lines[1]
    p.write_text("\n".join(lines) + "\n")
    _refuses(root, "duplicate rows")


# ---------------------------------------------------- input validation, part 2 (the registered 109)
def test_refuses_a_duplicate_row_engine_pair(tmp_path):
    root = fixture(tmp_path)
    _edit(root, "cu-i-9_idle_ltx23", panel="cu-i-8")           # row cu-i-8_idle now has two LTX clips
    _refuses(root, r"duplicate \(row, engine\).*cu-i-8_idle")


def test_refuses_a_cell_id_that_does_not_name_its_panel_motion_and_engine(tmp_path):
    root = fixture(tmp_path)
    _edit(root, "cu-i-1_idle_wan22", cell_id="cu-i-1_idle_wan23")
    _refuses(root, "cell_id 'cu-i-1_idle_wan23' should be 'cu-i-1_idle_wan22'")
    root2 = fixture(tmp_path / "b")
    _edit(root2, "cu-i-2_idle_gen45", cell_id="cu-i-2_idle_gen4.5")      # the long engine id is not the suffix
    _refuses(root2, "should be 'cu-i-2_idle_gen45'")


def test_refuses_when_the_missing_cell_is_not_the_refused_turbo_idle_cell(tmp_path):
    root = fixture(tmp_path)
    d = root / "runs" / "metrics-masked"
    write_clip(d, "cu-tone-3", "idle", "gen4_turbo", 2.6, {s: 1.1 for s in md.SETS})   # the refused cell is present
    (d / "cu-i-1_idle_wan22.json").unlink()                                              # another one is gone
    _refuses(root, r"cu-i-1_idle x wan22.*cu-tone-3_idle x gen4_turbo")


def test_the_refused_turbo_idle_cell_is_cu_tone_3_idle():
    assert md.REFUSED_CELL == ("cu-tone-3_idle", "gen4_turbo")


# ------------------------------------------------------------- reading a malformed clip file
def test_a_malformed_clip_file_exits_naming_the_file_and_the_field(tmp_path):
    root = fixture(tmp_path)
    d = root / "runs" / "metrics-masked"
    p = d / "cu-i-1_idle_wan22.json"
    good = json.loads(p.read_text())

    def damage(fn):
        rec = json.loads(json.dumps(good))
        fn(rec)
        p.write_text(json.dumps(rec))

    p.write_text("{not json")
    with pytest.raises(SystemExit, match=r"cu-i-1_idle_wan22\.json: not valid JSON"):
        md.load_clips(root)
    damage(lambda r: r["masked"]["agent"]["m64"].pop("f0_line_px_in_R"))
    with pytest.raises(SystemExit, match=r"cu-i-1_idle_wan22\.json: missing field masked\.agent\.m64\.f0_line_px_in_R"):
        md.load_clips(root)
    damage(lambda r: r.pop("whole_frame"))
    with pytest.raises(SystemExit, match=r"cu-i-1_idle_wan22\.json: missing field whole_frame\.chamfer_px"):
        md.load_clips(root)
    damage(lambda r: r["masked"]["aaron"]["m16"].update(chamfer_px="abc"))
    with pytest.raises(SystemExit, match=r"cu-i-1_idle_wan22\.json: .*masked\.aaron\.m16\.chamfer_px"):
        md.load_clips(root)
    damage(lambda r: r["masked"]["aaron"]["m16"].update(chamfer_px=None))          # null without no_scorable_frame
    with pytest.raises(SystemExit, match=r"masked\.aaron\.m16\.chamfer_px"):
        md.load_clips(root)
    damage(lambda r: r["masked"]["aaron"]["m16"].update(chamfer_px=-1.0))
    with pytest.raises(SystemExit, match=r"masked\.aaron\.m16\.chamfer_px"):
        md.load_clips(root)
    damage(lambda r: r.update(whole_frame={"chamfer_px": [1]}))
    with pytest.raises(SystemExit, match=r"whole_frame\.chamfer_px"):
        md.load_clips(root)
    damage(lambda r: r.update(masked=[]))
    with pytest.raises(SystemExit, match=r"cu-i-1_idle_wan22\.json: missing field masked\.aaron\.m16"):
        md.load_clips(root)
    p.write_text(json.dumps(good))
    assert len(md.load_clips(root)) == 109


def test_a_non_finite_number_in_a_clip_file_is_refused(tmp_path):
    root = fixture(tmp_path)
    p = root / "runs" / "metrics-masked" / "cu-i-1_idle_wan22.json"
    p.write_text(p.read_text().replace('"whole_frame": {"chamfer_px": ', '"whole_frame": {"chamfer_px": Infinity, "x": ', 1))
    with pytest.raises(SystemExit, match=r"cu-i-1_idle_wan22\.json: whole_frame\.chamfer_px"):
        md.load_clips(root)


# --------------------------------------------------------------------- infinities reported
def test_a_median_that_is_infinite_is_reported_and_json_stays_finite(tmp_path):
    inf_cells = {cid(p, m, "gen4.5") for p, m in ROWS[:12]}                     # 12 of 22 > half
    res = md.run(fixture(tmp_path, no_score=inf_cells), b=100)
    c = {(x["mask_set"], x["margin_px"]): x for x in res["grid"]["all"]}[("aaron", 32)]
    assert c["D_masked_px"]["gen4.5"] is None and c["D_masked_px"]["wan22"] is not None
    assert c["n_unscorable_masked"] == {"wan22": 0, "gen4_turbo": 0, "ltx23": 0, "gen4.5": 12, "h3-fal": 0}
    assert all(v == 0 for v in c["n_unscorable_whole"].values())
    assert c["g_masked"] is None and c["s"] is None and c["ratio_masked"] is None
    assert c["kendall_tau_b"] is None and res["verdict"] == "not supported"
    text = (tmp_path / "analysis" / "out" / "a9_masked_drift.json").read_text()
    assert "Infinity" not in text and "NaN" not in text
    report = (tmp_path / "analysis" / "out" / "a9_masked_drift.md").read_text()
    assert "no scorable frame" in report and "Gen-4.5: masked 12" in report


def test_a_null_whole_frame_value_is_read_as_infinity_and_counted(tmp_path):
    null_cells = {cid(p, m, "gen4.5") for p, m in ROWS[:12]}
    root = fixture(tmp_path, whole_null=null_cells)
    clips = {c["cell_id"]: c for c in md.load_clips(root)}
    assert clips[cid("cu-i-1", "idle", "gen4.5")]["whole"] == math.inf
    res = md.run(root, b=100)
    c = res["grid"]["all"][1]
    assert c["n_unscorable_whole"]["gen4.5"] == 12 and c["D_whole_px"]["gen4.5"] is None
    assert c["g_whole"] is None and res["verdict"] == "not testable"


def test_no_unscorable_line_when_every_clip_scores(tmp_path):
    md.run(fixture(tmp_path), b=50)
    assert "no scorable frame" not in (tmp_path / "analysis" / "out" / "a9_masked_drift.md").read_text()


# ---------------------------------------------------------------- numerics, guards, goldens
def test_gap_guards_zero_infinite_and_nan_medians():
    nan = math.nan
    assert md.gap({"wan22": 1.0, "gen4.5": 8.0}) == 3.0
    assert md.gap({"wan22": 1.0, "gen4.5": 0.0}) == -math.inf
    assert md.gap({"wan22": 0.0, "gen4.5": 1.0}) == math.inf
    assert md.gap({"wan22": 1.0, "gen4.5": math.inf}) == math.inf
    assert md.gap({"wan22": math.inf, "gen4.5": 1.0}) == -math.inf
    for w, g in ((0.0, 0.0), (math.inf, math.inf), (nan, 1.0), (1.0, nan)):
        assert math.isnan(md.gap({"wan22": w, "gen4.5": g}))
    assert md.gap({"wan22": 1e-300, "gen4.5": 1e300}) == pytest.approx(1993.0, abs=1)   # 1e600 overflows a float


def test_pow2_does_not_overflow():
    assert md._pow2(3.0) == 8.0 and md._pow2(-1.0) == 0.5
    assert md._pow2(2000.0) is None and md._pow2(math.nan) is None and md._pow2(math.inf) is None


def test_an_enormous_ratio_does_not_crash_the_report(tmp_path):
    res = md.run(fixture(tmp_path, whole={"wan22": 1e-160, "gen4_turbo": 1e-159, "ltx23": 1e-158,
                                          "gen4.5": 1e160, "h3-fal": 1e161}), b=20)
    c = res["grid"]["all"][1]
    assert c["g_whole"] > 1000 and c["ratio_whole"] is None


def test_tau_b_is_exactly_one_for_a_monotone_pair_and_the_verdict_uses_exact_equality():
    for xs in ([0.1, 0.7, 0.3 + 0.4, 1.1, 1e-3 + 2], [1e-9, 1.0, 17.3, 1e6, 1e9 + 0.1]):
        ys = [v * 3.3 + 0.1 for v in sorted(xs)]
        assert md.kendall_tau_b(sorted(xs), ys) == 1.0
    assert md.verdict(_cond(2.6, 0.1, tau=1 - 1e-13), _cond(2.6, 0.1)) == "not supported"


def test_the_seed_is_not_a_parameter_so_the_reported_seed_is_the_one_used():
    import inspect
    assert list(inspect.signature(md.panel_draws).parameters) == ["panels", "b"]
    assert list(inspect.signature(md.bootstrap).parameters) == ["kept", "panels", "draws"]
    assert md.SEED == 20261030


def test_golden_bootstrap_on_a_tiny_fixture():
    panels = [f"p{i}" for i in range(5)]
    wan_w, wan_m = [1.0, 1.2, 1.1, 1.4, 1.3], [1.0, 1.1, 1.0, 1.2, 1.1]
    gen_w, gen_m = [4.0, 5.0, 4.5, 6.0, 5.5], [2.0, 2.4, 2.2, 2.6, 2.5]
    kept = [{"cell_id": f"{e}{i}", "panel": f"p{i}", "engine": e, "whole": w[i], "masked": m[i]}
            for e, w, m in (("wan22", wan_w, wan_m), ("gen4.5", gen_w, gen_m)) for i in range(5)]
    bs = md.bootstrap(kept, panels, md.panel_draws(panels, b=200))
    assert bs["B"] == 200 and bs["seed"] == 20261030
    assert bs["s_ci95"] == pytest.approx([0.4308168628467106, 0.5], rel=1e-9)
    assert bs["delta_g_ci95"] == pytest.approx([0.8949179539424423, 1.0], rel=1e-9)
    assert bs["n_g_whole_le_0"] == 0 and bs["n_s_finite"] == 200 and bs["n_delta_g_finite"] == 200


# --------------------------------------------------- environment, figure, encoding, processes
def test_environment_is_recorded_and_the_docstring_names_it(tmp_path):
    import matplotlib
    import numpy
    import PIL
    want = {"python": platform.python_version(), "numpy": numpy.__version__,
            "matplotlib": matplotlib.__version__, "pillow": PIL.__version__}
    assert md.environment() == want
    res = md.run(fixture(tmp_path), b=20)
    assert res["environment"] == want
    assert json.loads((tmp_path / "analysis" / "out" / "a9_masked_drift.json").read_text())["environment"] == want
    line = next(x for x in md.__doc__.splitlines() if "reproducible under" in x)
    for v in want.values():
        assert v in line, (v, line)


def test_the_docstring_states_the_registered_edge_behaviour():
    doc = " ".join(md.__doc__.split())
    assert "g_whole < 0" in doc and "stay in the s and delta_g intervals" in doc and "n_g_whole_le_0" in doc
    assert "s = None counts as neither high nor low" in doc
    assert "null is +inf" in doc


def test_run_prints_the_output_paths_and_their_sha256(tmp_path, capsys):
    md.run(fixture(tmp_path), b=20)
    out = capsys.readouterr().out
    for rel in ("a9_masked_drift.json", "a9_masked_drift.md", "figures/a9_masked_drift.png"):
        f = tmp_path / "analysis" / "out" / rel
        assert f"{hashlib.sha256(f.read_bytes()).hexdigest()}  " in out and rel in out


def _child(root, out, env_extra=None, b=300):
    code = ("import sys; sys.path.insert(0, %r); import a9_masked_drift as m; m.run(sys.argv[1], sys.argv[2], b=%d); "
            "print('pyplot', 'matplotlib.pyplot' in sys.modules)" % (str(Path(__file__).resolve().parent), b))
    env = dict(os.environ)
    env.update(env_extra or {})
    r = subprocess.run([sys.executable, "-c", code, str(root), str(out)], env=env, capture_output=True, text=True,
                       encoding="utf-8", cwd=str(root))
    assert r.returncode == 0, r.stderr
    assert "pyplot False" in r.stdout
    return {n: (Path(out) / n).read_bytes() for n in ("a9_masked_drift.json", "a9_masked_drift.md",
                                                     "figures/a9_masked_drift.png")}


def test_outputs_are_identical_across_processes_hash_seeds_and_a_hostile_matplotlibrc(tmp_path):
    root = fixture(tmp_path / "fx", masked_ratio={"aaron": 3.0, "agent": 4.0})
    hostile = tmp_path / "mplconfig"
    hostile.mkdir()
    (hostile / "matplotlibrc").write_text("font.size: 30\nfont.family: serif\naxes.grid: True\nsavefig.dpi: 72\n"
                                          "figure.facecolor: red\n")
    a = _child(root, tmp_path / "o1", {"PYTHONHASHSEED": "1"})
    b = _child(root, tmp_path / "o2", {"PYTHONHASHSEED": "2", "MPLCONFIGDIR": str(hostile)})
    for name in a:
        assert a[name] == b[name], name
    png = a["figures/a9_masked_drift.png"]
    assert png.startswith(b"\x89PNG") and b"tEXt" not in png and b"iTXt" not in png and b"atplotlib" not in png


def test_outputs_do_not_depend_on_the_locale(tmp_path):
    root = fixture(tmp_path / "fx")
    plain = _child(root, tmp_path / "o1", {"PYTHONHASHSEED": "3"})
    env = {"LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "PYTHONHASHSEED": "4"}
    enc = subprocess.run([sys.executable, "-c", "import locale; print(locale.getpreferredencoding(False))"],
                         env=dict(os.environ, **env), capture_output=True, text=True).stdout.strip().lower()
    assert "utf" not in enc                                         # the child really runs with a non-UTF-8 locale
    c = _child(root, tmp_path / "o2", env)
    for name in plain:
        assert plain[name] == c[name], name
    assert "\u00d7".encode("utf-8") in c["a9_masked_drift.md"] and b"\r\n" not in c["a9_masked_drift.md"]


# ------------------------------------------------------------------------ m_empty
def test_a_missing_or_non_bool_m_empty_is_refused_naming_the_file(tmp_path):
    root = fixture(tmp_path)
    p = root / "runs" / "metrics-masked" / "cu-i-1_idle_wan22.json"
    good = json.loads(p.read_text())

    def damage(fn):
        rec = json.loads(json.dumps(good))
        fn(rec)
        p.write_text(json.dumps(rec))

    damage(lambda r: r.pop("m_empty"))
    with pytest.raises(SystemExit, match=r"cu-i-1_idle_wan22\.json: missing field m_empty\.aaron"):
        md.load_clips(root)
    damage(lambda r: r["m_empty"].pop("agent"))
    with pytest.raises(SystemExit, match=r"cu-i-1_idle_wan22\.json: missing field m_empty\.agent"):
        md.load_clips(root)
    for bad in (1, "false", None):
        damage(lambda r: r["m_empty"].update(aaron=bad))
        with pytest.raises(SystemExit, match=r"cu-i-1_idle_wan22\.json: m_empty\.aaron must be true or false"):
            md.load_clips(root)
    p.write_text(json.dumps(good))
    assert {c["cell_id"]: c["m_empty"] for c in md.load_clips(root)}["cu-i-1_idle_wan22"] == {"aaron": False, "agent": False}


def test_n_m_empty_counts_kept_clips_per_engine_and_mask_set(tmp_path):
    m_empty = {cid("cu-i-1", "idle", "wan22"): {"aaron": True},
               cid("cu-i-2", "idle", "wan22"): {"aaron": True, "agent": True},
               cid("cu-i-4", "idle", "gen4.5"): {"agent": True},
               cid("cu-i-5", "idle", "wan22"): {"aaron": True}}
    f0 = {cid("cu-i-5", "idle", "wan22"): 100}                      # excluded (< 500), so not counted
    res = md.run(fixture(tmp_path, m_empty=m_empty, f0=f0), b=50)
    for split_conds in res["grid"].values():
        for c in split_conds:
            assert set(c["n_m_empty"]) == set(md.LEAGUE_ORDER)
    pick = {(c["mask_set"], c["margin_px"]): c for c in res["grid"]["all"]}
    for m in md.MARGINS:
        assert pick[("aaron", m)]["n_m_empty"] == {"wan22": 2, "gen4_turbo": 0, "ltx23": 0, "gen4.5": 0, "h3-fal": 0}
        assert pick[("agent", m)]["n_m_empty"] == {"wan22": 1, "gen4_turbo": 0, "ltx23": 0, "gen4.5": 1, "h3-fal": 0}
    idle = {(c["mask_set"], c["margin_px"]): c for c in res["grid"]["burst"]}
    assert all(v == 0 for c in idle.values() for v in c["n_m_empty"].values())   # burst split has none of them
    report = (tmp_path / "analysis" / "out" / "a9_masked_drift.md").read_text()
    assert "mask fills no pixel (R is the whole grid; kept" in report and "Wan 2.2: 2" in report
    assert "Gen-4.5: 1" in report


def test_no_m_empty_line_when_no_mask_is_empty(tmp_path):
    md.run(fixture(tmp_path), b=50)
    text = (tmp_path / "analysis" / "out" / "a9_masked_drift.md").read_text()
    assert "fills no pixel" not in text
