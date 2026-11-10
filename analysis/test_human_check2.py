"""Tests for A11's human check (analysis/human_check2/): the opaque codes and the
analysis. Synthetic fixtures, plus A6's released ratings re-pointed.

    python -m pytest analysis/test_human_check2.py
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ANALYSIS = Path(__file__).resolve().parent
HC2 = ANALYSIS / "human_check2"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cells40(prefix="cip"):
    tags = ["gen4t", "h3", "gen45", "wan22", "ltx23"]
    base = [f"{c}-{t}-{n}" for c in ("cu", "act", "est") for t in ("line", "tone", "black") for n in (1, 2, 3)]
    cells = [f"{p}_idle_{tags[i % 5]}" for i, p in enumerate(base)]
    cells += [f"{p}_burst_{tags[(i + 1) % 5]}" for i, p in enumerate(base[:10])]
    cells += [f"{prefix}-act-tank-1_burst_gen45", f"{prefix}-act-tank-1_idle_wan22", "chain-est-cosmic-1_idle_h3"]
    return cells


# ------------------------------------------------------------------ codes
def test_codes_follow_a6s_and_cover_every_cell_once():
    bm = load("hc2_build_mapping", HC2 / "build_mapping.py")
    cells = cells40()
    mapping, baseline = bm.build(cells)
    codes = list(mapping["opaque_to_cell"])
    assert codes == [f"c{i}" for i in range(21, 61)] and sorted(mapping["opaque_to_cell"].values()) == sorted(cells)
    panels = {c.rsplit("_", 2)[0] for c in cells}
    pcodes = list(baseline["panel_opaque_to_name"])
    assert pcodes == [f"p{i}" for i in range(15, 15 + len(panels))]
    assert set(baseline["panel_opaque_to_name"].values()) == panels
    for code, cell in mapping["opaque_to_cell"].items():
        assert baseline["panel_opaque_to_name"][baseline["clip_to_panel"][code]] == cell.rsplit("_", 2)[0]
    att = mapping["attention_clips"]
    assert len(att) == 2 == len(set(att)) and set(att) <= set(codes)


def test_codes_are_deterministic_and_reproduce_in_the_release_form():
    bm = load("hc2_build_mapping", HC2 / "build_mapping.py")
    private = json.dumps(bm.build(cells40("xyz"))).replace("xyz-act-tank-1", "cip-act-tank-1")
    assert private == json.dumps(bm.build(cells40("cip"))) == json.dumps(bm.build(cells40("cip")))


def test_a_wrong_count_is_refused():
    bm = load("hc2_build_mapping", HC2 / "build_mapping.py")
    with pytest.raises(SystemExit):
        bm.build(cells40()[:39])


# --------------------------------------------------------------- analysis
FAIL_BOTH = [{"clip": "c21", "register": 2, "sameness": 2}, {"clip": "c22", "register": 1, "sameness": 2}]
FAIL_ONE = [{"clip": "c21", "register": 2, "sameness": 5}, {"clip": "c22", "register": 4, "sameness": 5}]


def load_hc2():
    return load("hc2_collect", HC2 / "collect.py")


def rater(name, same=(5, 5, 4, 3, 2, 1), reg=(5, 4, 4, 3, 3, 2), attention=None, drop=None, baseline=(4, 2)):
    codes = [f"c{21 + i}" for i in range(6)]
    att = attention if attention is not None else [{"clip": "c21", "register": reg[0], "sameness": same[0]},
                                                   {"clip": "c22", "register": reg[1], "sameness": same[1]}]
    return {"rater": name, "instrument": "A11",
            "ratings": [{"clip": c, "register": r, "sameness": s} for c, r, s in zip(codes, reg, same) if c != drop],
            "attention": att,
            "baseline": [{"panel": "p15", "hand_drawn": baseline[0]}, {"panel": "p16", "hand_drawn": baseline[1]}]}


def hc2_tree(tmp_path, raters, constant=None):
    here, out = tmp_path / "analysis" / "human_check2", tmp_path / "analysis" / "out"
    (here / "ratings").mkdir(parents=True)
    out.mkdir(parents=True)
    codes = [f"c{21 + i}" for i in range(6)]
    cells = [f"cu-line-{i}_idle_wan22" for i in range(1, 7)]
    (here / "mapping.json").write_text(json.dumps({"instrument": "A11", "opaque_to_cell": dict(zip(codes, cells)),
                                                   "attention_clips": ["c21", "c22"]}))
    (here / "baseline_mapping.json").write_text(json.dumps({
        "panel_opaque_to_name": {"p15": "panel-a", "p16": "panel-b"},
        "clip_to_panel": {c: ("p15" if i < 3 else "p16") for i, c in enumerate(codes)}}))
    rows = [{"cell_id": c, "line_chamfer_mean_px": 1.0 + i, "tone_variance": None, "edge_abs_slope": 0.1 * (i + 1),
             "style_terminal": 0.05 * (i + 1), "closure_abs_terminal": 0.01 * (i + 1)} for i, c in enumerate(cells)]
    for r in rows:
        if constant:
            r[constant] = 0.5
    (out / "results_table.json").write_text(json.dumps(rows))
    for name, d in raters.items():
        (here / "ratings" / f"ratings-{name}.json").write_text(json.dumps(d))
    return here, out


def test_a6s_ratings_re_pointed_reproduce_the_released_numbers():
    hc2 = load_hc2()
    a6dir = ANALYSIS / "human_check"
    res = hc2.run(here=a6dir, out_dir=ANALYSIS / "out", seed=20260813, instrument="A6", write=False)
    shipped = json.loads((a6dir / "human_check_results.json").read_text())
    assert res["per_axis"] == shipped["per_axis"] and res["raters"] == shipped["raters"]
    assert res["excluded_attention"] == [] and res["excluded_incomplete"] == []
    edge = shipped["per_axis"]["sameness"]["per_metric"]["edge_abs_slope"]
    assert res["h3"]["rho"] == pytest.approx(edge["spearman_rho"], abs=1e-12) and res["h3"]["n"] == edge["n_cells"]


def test_the_completeness_and_attention_rules_exclude_before_any_correlation(tmp_path):
    hc2 = load_hc2()
    here, out = hc2_tree(tmp_path, {"R8": rater("R8"), "R9": rater("R9"), "R10": rater("R10", same=(5, 4, 4, 3, 2, 2)),
                                    "R11": rater("R11", attention=FAIL_BOTH), "R12": rater("R12", drop="c26")})
    res = hc2.run(here=here, out_dir=out, fixtures=True, b=500, write=False)
    assert res["excluded_attention"] == ["R11"] and res["excluded_incomplete"] == ["R12"]
    assert res["n_excluded_attention"] == 1 and res["n_excluded_incomplete"] == 1
    assert res["raters"] == ["R10", "R8", "R9"] and res["n_raters"] == 3 and res["n_rating_files"] == 5
    assert res["attention"]["R11"] == {"items": 2, "failed": 2}
    assert res["flags"]["fewer_than_10_raters"] is True
    f = res["register_baseline_filtered"]
    assert f["n_clips"] == 3 and f["excluded_panels"] == ["p16"] and f["status"].startswith("secondary")
    assert list(res["baseline"]["mean_by_panel"]) == ["p15", "p16"]


def test_one_failed_attention_item_keeps_the_rater(tmp_path):
    hc2 = load_hc2()
    here, out = hc2_tree(tmp_path, {"R8": rater("R8"), "R9": rater("R9", attention=FAIL_ONE),
                                    "R10": rater("R10", same=(5, 4, 4, 3, 2, 2))})
    res = hc2.run(here=here, out_dir=out, fixtures=True, b=500, write=False)
    assert res["excluded_attention"] == [] and res["attention"]["R9"] == {"items": 2, "failed": 1}


def test_h3_reads_supported_only_when_rho_is_credibly_below_the_registered_bound():
    hc2 = load_hc2()
    rng = np.random.default_rng(3)
    x = rng.random(40)
    strong = hc2.h3(x, -x + rng.normal(0, 0.05, 40), b=2000)
    null = hc2.h3(x, rng.normal(0, 1, 40), b=2000)
    assert strong["bound"] == -0.4 and strong["secondary"]["bound"] == -0.5
    assert strong["rho"] < -0.9 and strong["reading"] == "supported" and strong["p_bootstrap_one_sided"] < 0.01
    assert strong["secondary"]["reading"] == "supported"
    assert null["reading"] == "not supported" and null["p_bootstrap_one_sided"] > 0.05
    assert null["secondary"]["reading"] == "not supported"


def test_the_outputs_are_written_and_reproducible(tmp_path):
    hc2 = load_hc2()
    here, out = hc2_tree(tmp_path, {"R8": rater("R8"), "R9": rater("R9"), "R10": rater("R10", same=(5, 4, 4, 3, 2, 2))})
    hc2.run(here=here, out_dir=out, fixtures=True, b=500)
    j, m = here / "human_check2_results.json", here / "human_check2_results.md"
    first = j.read_bytes()
    hc2.run(here=here, out_dir=out, fixtures=True, b=500)
    assert j.read_bytes() == first and "H3" in m.read_text()


def test_a_rater_slot_in_two_files_is_refused(tmp_path):
    hc2 = load_hc2()
    here, out = hc2_tree(tmp_path, {"R8": rater("R8"), "R9": rater("R8")})
    with pytest.raises(SystemExit, match="R8"):
        hc2.run(here=here, out_dir=out, fixtures=True, b=500, write=False)


def test_a_bootstrap_with_no_finite_resample_gives_no_interval(tmp_path, monkeypatch):
    hc2 = load_hc2()
    here, out = hc2_tree(tmp_path, {"R8": rater("R8"), "R9": rater("R9"), "R10": rater("R10", same=(5, 4, 4, 3, 2, 2))},
                         constant="closure_abs_terminal")
    res = hc2.run(here=here, out_dir=out, fixtures=True, b=500)
    v = res["per_axis"]["sameness"]["per_metric"]["closure_abs_terminal"]
    assert v["ci95"] is None and v["spearman_rho"] is None and v["bootstrap_n"] == 0
    assert res["per_axis"]["sameness"]["per_metric"]["edge_abs_slope"]["ci95"] is not None
    monkeypatch.setattr(hc2.rs, "bootstrap", lambda *a, **k: np.array([]))
    h = hc2.h3(np.arange(10.0), -np.arange(10.0), b=100)
    assert h["ci95"] is None and h["p_bootstrap_one_sided"] is None and h["reading"].startswith("undefined")


def test_the_tolerant_path_matches_a6s_code_on_regular_data(tmp_path):
    hc2 = load_hc2()
    here, out = hc2_tree(tmp_path, {"R8": rater("R8"), "R9": rater("R9"), "R10": rater("R10", same=(5, 4, 4, 3, 2, 2))})
    files = sorted((here / "ratings").glob("ratings-*.json"))
    codes = [f"c{21 + i}" for i in range(6)]
    _, mats = hc2.a6.load_matrices(files, codes)
    cells = json.loads((here / "mapping.json").read_text())["opaque_to_cell"]
    rows = {r["cell_id"]: r for r in json.loads((out / "results_table.json").read_text())}
    args = (mats, [cells[c] for c in codes], rows)
    assert hc2._analyse_tolerant(*args, seed=7, b=300) == hc2.a6.analyse(*args, seed=7, b=300)


def test_the_live_run_refuses_until_a11_is_public(tmp_path, monkeypatch):
    hc2 = load_hc2()
    prereg = tmp_path / "PREREGISTRATION.md"
    prereg.write_text("### A10 — something\n")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(prereg))
    for call in (lambda: hc2.main([]), lambda: hc2.run(here=HC2)):
        with pytest.raises(SystemExit, match="REFUSING.*A11"):
            call()


def test_fixtures_refuse_the_repository_and_private_trees(tmp_path):
    hc2 = load_hc2()
    (tmp_path / "analysis" / "adherence").mkdir(parents=True)
    (tmp_path / "analysis" / "adherence" / "private-terms.txt").write_text("")
    for root in (ANALYSIS.parent, tmp_path, tmp_path / "analysis"):
        with pytest.raises(SystemExit, match="REFUSING --fixtures"):
            hc2.main(["--fixtures", str(root)])


def test_fixtures_refuse_any_folder_at_or_under_the_root_without_the_marker(tmp_path, monkeypatch):
    """The release tree carries no private marker: the guard must still refuse it and its folders."""
    hc2 = load_hc2()
    rel = tmp_path / "release"
    (rel / "analysis" / "human_check2").mkdir(parents=True)
    monkeypatch.setattr(hc2, "ROOT", rel)
    for root in (rel, rel / "analysis", rel / "analysis" / "human_check2" / "new"):
        with pytest.raises(SystemExit, match="REFUSING --fixtures"):
            hc2.main(["--fixtures", str(root)])
    assert hc2.check_fixtures(tmp_path / "beside") == (tmp_path / "beside").resolve()


def test_a_missing_attention_repeat_answer_excludes_the_rater_as_incomplete(tmp_path):
    hc2 = load_hc2()
    half = [{"clip": "c21", "register": 5, "sameness": 5}, {"clip": "c22", "register": 4}]
    here, out = hc2_tree(tmp_path, {"R8": rater("R8"), "R9": rater("R9", attention=half[:1]),
                                    "R10": rater("R10", same=(5, 4, 4, 3, 2, 2)), "R11": rater("R11", attention=half)})
    res = hc2.run(here=here, out_dir=out, fixtures=True, b=500, write=False)
    assert res["excluded_incomplete"] == ["R11", "R9"] and res["n_excluded_incomplete"] == 2
    assert res["excluded_attention"] == [] and res["raters"] == ["R10", "R8"]


def test_the_committed_mapping_files_are_the_real_draw():
    bm = load("hc2_build_mapping", HC2 / "build_mapping.py")
    subset = json.loads((ANALYSIS / "out" / "a11_subset.json").read_text())["cells"]
    mapping, baseline = json.loads(json.dumps(bm.build(subset)))
    assert mapping == json.loads((HC2 / "mapping.json").read_text())
    assert baseline == json.loads((HC2 / "baseline_mapping.json").read_text())
    assert len(mapping["opaque_to_cell"]) == 40 and set(mapping["opaque_to_cell"].values()) == set(subset)


# ----------------------------------------------------- review fixes (boundaries)
def test_attention_boundaries_two_points_fail_and_one_point_passes(tmp_path):
    hc2 = load_hc2()
    two = [{"clip": "c21", "register": 3, "sameness": 5}, {"clip": "c22", "register": 4, "sameness": 3}]
    one = [{"clip": "c21", "register": 4, "sameness": 4}, {"clip": "c22", "register": 5, "sameness": 4}]
    here, out = hc2_tree(tmp_path, {"R8": rater("R8"), "R9": rater("R9", attention=two), "R10": rater("R10"),
                                    "R11": rater("R11", attention=one), "R12": rater("R12", same=(5, 4, 4, 3, 2, 2))})
    res = hc2.run(here=here, out_dir=out, fixtures=True, b=500, write=False)
    assert res["excluded_attention"] == ["R9"] and res["attention"]["R9"] == {"items": 2, "failed": 2}
    assert res["attention"]["R11"] == {"items": 2, "failed": 0} and "R11" in res["raters"]


@pytest.mark.parametrize("boots, p, reading, p2, reading2", [
    (np.full(99, -0.45), 0.01, "supported", 1.0, "not supported"),
    (np.full(99, -0.4), 1.0, "not supported", 1.0, "not supported"),        # ties count against
    (np.array([-0.41] * 94 + [-0.4] * 5), 0.06, "not supported", 1.0, "not supported"),
])
def test_h3_counts_against_the_registered_bound_and_not_the_secondary(monkeypatch, boots, p, reading, p2, reading2):
    hc2 = load_hc2()
    monkeypatch.setattr(hc2.rs, "bootstrap", lambda *a, **k: boots)
    h = hc2.h3(np.arange(10.0), -np.arange(10.0), b=99)
    assert h["bound"] == -0.4 and h["secondary"]["bound"] == -0.5
    assert h["p_bootstrap_one_sided"] == pytest.approx(p) and h["reading"] == reading
    assert h["secondary"]["p_bootstrap_one_sided"] == pytest.approx(p2) and h["secondary"]["reading"] == reading2


def _three(**r9):
    return {"R8": rater("R8"), "R9": {**rater("R9"), **r9}, "R10": rater("R10", same=(5, 4, 4, 3, 2, 2))}


@pytest.mark.parametrize("r9, message", [
    ({"ratings": rater("R9")["ratings"] + [{"clip": "c99", "register": 3, "sameness": 3}]}, "outside"),
    ({"ratings": rater("R9")["ratings"] + [{"clip": "c23", "register": 3, "sameness": 3}]}, "twice"),
    ({"attention": [{"clip": "c21", "register": 5, "sameness": 5}, {"clip": "c23", "register": 4, "sameness": 4}]},
     "outside"),
    ({"attention": rater("R9")["attention"] + [{"clip": "c21", "register": 5, "sameness": 5}]}, "twice"),
    ({"instrument": "A6"}, "instrument"),
])
def test_a_rating_file_that_breaks_the_contract_is_refused_by_name(tmp_path, r9, message):
    hc2 = load_hc2()
    here, out = hc2_tree(tmp_path, _three(**r9))
    with pytest.raises(SystemExit, match=rf"ratings-R9\.json.*{message}"):
        hc2.run(here=here, out_dir=out, fixtures=True, b=500, write=False)


@pytest.mark.parametrize("attention", [["c21"], ["c21", "c99"], ["c21", "c21"], ["c21", "c22", "c23"]])
def test_the_attention_clips_must_be_two_codes_of_the_mapping(tmp_path, attention):
    hc2 = load_hc2()
    here, out = hc2_tree(tmp_path, _three())
    m = json.loads((here / "mapping.json").read_text())
    (here / "mapping.json").write_text(json.dumps({**m, "attention_clips": attention}))
    with pytest.raises(SystemExit, match="attention_clips"):
        hc2.run(here=here, out_dir=out, fixtures=True, b=500, write=False)


def test_a11_needs_its_baseline_mapping_and_reports_answers_per_panel(tmp_path):
    hc2 = load_hc2()
    here, out = hc2_tree(tmp_path, _three())
    res = hc2.run(here=here, out_dir=out, fixtures=True, b=500, write=False)
    assert res["baseline"]["n_by_panel"] == {"p15": 3, "p16": 3}
    (here / "baseline_mapping.json").unlink()
    with pytest.raises(SystemExit, match="baseline_mapping.json is missing"):
        hc2.run(here=here, out_dir=out, fixtures=True, b=500, write=False)


def test_an_a11_mapping_outside_the_repository_still_trips_without_the_fixtures_escape(tmp_path, monkeypatch):
    hc2 = load_hc2()
    here, out = hc2_tree(tmp_path, _three())
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(tmp_path / "absent.md"))
    with pytest.raises(SystemExit, match="REFUSING.*A11"):
        hc2.run(here=here, out_dir=out, b=500, write=False)


def test_the_tolerant_copy_re_raises_a_failure_that_is_not_an_empty_bootstrap(tmp_path, monkeypatch):
    hc2 = load_hc2()
    here, out = hc2_tree(tmp_path, _three())

    def boom(*a, **k):
        raise IndexError("not an empty bootstrap")
    monkeypatch.setattr(hc2.a6, "analyse", boom)
    with pytest.raises(IndexError, match="not an empty bootstrap"):
        hc2.run(here=here, out_dir=out, fixtures=True, b=200, write=False)
