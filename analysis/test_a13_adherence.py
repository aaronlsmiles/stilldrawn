"""Tests for analysis/a13_adherence.py, on synthetic trees only (no A13 rating exists before registration).

    python -m pytest analysis/test_a13_adherence.py
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a13_adherence as A  # noqa: E402
import a9_adherence as a9  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent / "adherence_a13"))
import build_a13 as BA13  # noqa: E402

B_TEST = 1999


def make_tree(tmp_path, scores, n_raters=10, repeat=None):
    """A synthetic tree in A9's design: per study 11 panels x the five engines (22 rows, 110 cells),
    drift 1 + 0.5 k + 0.3 e (k the panel, e the engine). scores(cell, n) gives rater n's first score;
    repeat(slot, study, k, first) gives the k-th repeat's score (default: the same as the first)."""
    root = tmp_path / "tree"
    (root / "analysis" / "out").mkdir(parents=True)
    rows, cells = [], {}
    for study, motion, tok in (("burst", "BURST", "burst"), ("push", "CAMPUSH", "campush")):
        for k in range(11):
            panel = f"{study}-panel-{k:02d}"
            for e, eng in enumerate(a9.LEAGUE_ORDER):
                cid = f"{panel}_{tok}_{eng}"
                rows.append({"cell_id": cid, "motion": motion, "engine": eng, "panel_id": panel,
                             "line_chamfer_mean_px": 1.0 + 0.5 * k + 0.3 * e})
                cells[cid] = {"study": study, "k": k, "e": e}
    (root / "analysis" / "out" / "results_table.json").write_text(json.dumps(rows))
    motion_dir = root / "runs" / "metrics-motion"                  # released motion, read by the AUC
    motion_dir.mkdir(parents=True)
    for cid, c in cells.items():
        (motion_dir / f"{cid}.json").write_text(json.dumps({"motion": {"headline_median_norm": 0.001 * (1 + c["e"])}}))
    folder = root / "analysis" / "adherence_a13"
    (folder / "ratings").mkdir(parents=True)
    studies, att = {}, {}
    for study in A.STUDIES:
        ids = sorted(c for c in cells if cells[c]["study"] == study)
        c2c = {f"c{study[0]}{i:03d}": cid for i, cid in enumerate(ids)}
        reps = [{"alias": f"r{study[0]}{j}", "of": sorted(c2c)[j], "position": (30, 52)[j]} for j in range(2)]
        studies[study] = {"id": f"a13-{study}", "code_to_cell": c2c, "repeats": reps, "min_gap": 5}
        att[study] = [r["of"] for r in reps]
    (folder / "mapping.json").write_text(json.dumps(
        {"instrument": "A13", "seed": 20261104, "studies": studies, "attention_clips": att}))
    same = lambda slot, study, k, first: first  # noqa: E731
    for n in range(n_raters):
        slot = f"R{24 + n}"
        doc = {"rater": slot, "instrument": "A13", "delivery": "hosted-A13", "studies": {}}
        for study in A.STUDIES:
            c2c = studies[study]["code_to_cell"]
            first = {code: scores(cells[cid], n) for code, cid in c2c.items()}
            doc["studies"][study] = {
                "ratings": [{"clip": c, "score": v} for c, v in first.items()],
                "attention": [{"clip": c, "score": (repeat or same)(slot, study, k, first[c])}
                              for k, c in enumerate(att[study])],
                "order": sorted(c2c)}
        (folder / "ratings" / f"ratings-{slot}.json").write_text(json.dumps(doc))
    return root


def run(root, **kw):
    return A.run(root, fixtures=True, b=B_TEST, **kw)


def off_by_two(first):
    return first + 2 if first <= 3 else first - 2


def test_a_planted_within_row_effect_is_supported(tmp_path):
    h = run(make_tree(tmp_path, lambda c, n: 1 + c["e"]))["A13-H4"]
    assert (h["n_clips"], h["n_rows"]) == (110, 22)
    assert h["rho"] > 0 and h["p_one_sided"] <= 0.05 and h["reading"] == "supported"


def test_scores_that_differ_only_between_rows_are_not_supported(tmp_path):
    h = run(make_tree(tmp_path, lambda c, n: 1 + c["k"] % 5))["A13-H4"]     # constant within every row
    assert h["p_one_sided"] == 1.0 and h["reading"] == "not supported"


def test_the_reading_needs_rho_above_zero():
    assert A.h4_reading(0.2, 0.01, True) == "supported"
    assert A.h4_reading(-0.1, 0.01, True) == "not supported (p <= 0.05 but rho <= 0)"
    assert A.h4_reading(-0.1, 0.01, False) == "supported"
    assert A.h4_reading(0.2, 0.06, True) == "not supported"
    assert A.h4_reading(None, None, True).startswith("undefined")


def test_both_items_of_one_study_exclude_a_rater_one_item_does_not(tmp_path):
    def rep(slot, study, k, first):
        if slot == "R24" and study == "push":
            return off_by_two(first)
        if slot == "R25" and study == "burst" and k == 0:
            return off_by_two(first)
        return first
    r = run(make_tree(tmp_path, lambda c, n: 1 + c["e"], repeat=rep))
    assert r["excluded_attention"] == ["R24"] and "R25" in r["included"]
    assert r["attention"]["R24"]["push"] == {"items": 2, "failed": 2}


def test_the_any_item_rule_excludes_a_single_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "EXCLUDE_IF", "any_item")
    def rep(slot, study, k, first):
        return off_by_two(first) if (slot == "R25" and study == "burst" and k == 0) else first
    r = run(make_tree(tmp_path, lambda c, n: 1 + c["e"], repeat=rep))
    assert r["excluded_attention"] == ["R25"]


def test_an_incomplete_rater_is_excluded_before_any_statistic(tmp_path):
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"])
    f = root / "analysis" / "adherence_a13" / "ratings" / "ratings-R30.json"
    d = json.loads(f.read_text())
    d["studies"]["push"]["ratings"].pop()
    f.write_text(json.dumps(d))
    r = run(root)
    assert r["incomplete"] == ["R30"] and r["n_included"] == 9


def test_fewer_than_eight_raters_is_flagged_and_still_analysed(tmp_path):
    r = run(make_tree(tmp_path, lambda c, n: 1 + c["e"], n_raters=5))
    assert r["n_included"] == 5 and any("fewer than 8" in x for x in r["flags"])
    assert r["A13-H4"]["reading"] == "supported"


@pytest.mark.parametrize("edit, msg", [
    (lambda d: d.update(rater="AARON"), "not R followed by digits"),
    (lambda d: d.update(instrument="A9"), "instrument is not A13"),
    (lambda d: d["studies"]["burst"]["ratings"].append({"clip": "cb000", "score": 3}), "a code twice"),
    (lambda d: d["studies"]["push"]["attention"].append({"clip": "cp010", "score": 3}), "outside the mapping"),
])
def test_a_broken_contract_refuses_the_run(tmp_path, edit, msg):
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"])
    f = root / "analysis" / "adherence_a13" / "ratings" / "ratings-R24.json"
    d = json.loads(f.read_text())
    edit(d)
    f.write_text(json.dumps(d))
    with pytest.raises(SystemExit, match=msg):
        run(root)


def test_one_slot_in_two_files_refuses(tmp_path):
    rd = make_tree(tmp_path, lambda c, n: 1 + c["e"]) / "analysis" / "adherence_a13" / "ratings"
    (rd / "ratings-R99.json").write_text((rd / "ratings-R24.json").read_text())
    with pytest.raises(SystemExit, match="two files"):
        run(tmp_path / "tree")


def test_fixtures_refuse_the_repository_and_the_real_run_is_tripwired(monkeypatch, tmp_path):
    with pytest.raises(SystemExit, match="repository itself"):
        A.check_fixtures(A.ROOT)
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(tmp_path / "absent.md"))
    with pytest.raises(SystemExit, match="REFUSING to analyse the A13 ratings"):
        A.run()


def test_count_only_applies_only_the_two_rules(tmp_path):
    c = A.count_only(make_tree(tmp_path, lambda c, n: 1 + c["e"], n_raters=3), fixtures=True)
    assert c == {"included": 3, "incomplete": [], "excluded_attention": [], "top_up_due": True}


def test_outputs_are_written_and_byte_stable(tmp_path):
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"])
    out = root / "analysis" / "out"
    run(root)
    first = (out / "a13_adherence.json").read_bytes(), (out / "a13_adherence.md").read_bytes()
    run(root)
    assert ((out / "a13_adherence.json").read_bytes(), (out / "a13_adherence.md").read_bytes()) == first
    assert "A13-H4" in (out / "a13_adherence.md").read_text()


def test_engine_level_miss_rates_with_wilson_intervals(tmp_path):
    e = run(make_tree(tmp_path, lambda c, n: 1 + c["e"]))["secondary"]["engine_level"]
    per = e["per_engine"]
    assert [per[k]["miss_rate"] for k in a9.LEAGUE_ORDER] == [1.0, 1.0, 0.0, 0.0, 0.0]
    assert all(per[k]["n_ratings"] == 220 for k in a9.LEAGUE_ORDER)        # 22 clips x 10 raters
    lo, hi = per["wan22"]["wilson95"]
    assert lo < 1.0 and hi == pytest.approx(1.0)
    assert e["rho"] is not None and e["p_exact_one_sided"] is not None


def test_alpha_is_one_when_raters_agree_and_flagged_when_they_do_not(tmp_path):
    r = run(make_tree(tmp_path / "agree", lambda c, n: 1 + c["e"]))
    assert r["secondary"]["alpha"]["all_clips"] == pytest.approx(1.0)
    assert not any("alpha" in x for x in r["flags"])
    r = run(make_tree(tmp_path / "split", lambda c, n: 1 + (c["e"] + c["k"] + n) % 5))   # every clip gets each score twice
    assert r["secondary"]["alpha"]["all_clips"] < 0.3
    assert any("alpha" in x for x in r["flags"])
    assert r["A13-H4"]["reading"].startswith("undefined")       # every clip's mean is 3: tested, and undefined


def test_the_motion_auc_on_these_clips_uses_the_clip_level_miss(tmp_path):
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"])
    t = run(root)["secondary"]["motion_auc"]
    assert t["miss"].startswith("mean score")
    for s in ("burst", "push"):
        b = t["by_class"][s]
        assert (b["n_miss"], b["n_nonmiss"]) == (22, 33) and b["auc"] == 1.0    # misses move least here
    assert "A9's motion AUC" in (root / "analysis" / "out" / "a13_adherence.md").read_text()


def test_weighted_kappa_is_the_mean_over_pairs_of_complete_raters(tmp_path):
    def rep(slot, study, k, first):
        return off_by_two(first) if (slot == "R24" and study == "push") else first
    r = run(make_tree(tmp_path, lambda c, n: 1 + c["e"], n_raters=4, repeat=rep))
    assert r["excluded_attention"] == ["R24"] and r["n_included"] == 3
    assert r["secondary"]["weighted_kappa"]["burst"] == {"n_raters": 4, "n_pairs": 6, "n_pairs_defined": 6,
                                                         "mean_kappa": 1.0}


# Hardenings from review of the A13 analysis code.

def test_an_attention_excluded_rater_enters_kappa_and_nothing_else(tmp_path):
    def rep(slot, study, k, first):
        return off_by_two(first) if (slot == "R24" and study == "push") else first
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"], n_raters=4, repeat=rep)
    f = root / "analysis" / "adherence_a13" / "ratings" / "ratings-R27.json"
    d = json.loads(f.read_text())
    d["studies"]["burst"]["ratings"].pop()
    f.write_text(json.dumps(d))
    r = run(root)
    assert (r["included"], r["excluded_attention"], r["incomplete"]) == (["R25", "R26"], ["R24"], ["R27"])
    assert all(v["n_ratings"] == 22 * 2 for v in r["secondary"]["engine_level"]["per_engine"].values())
    assert {s: k["n_raters"] for s, k in r["secondary"]["weighted_kappa"].items()} == {"burst": 3, "push": 3}


def test_every_a13_slot_from_r24_to_r39_is_analysed(tmp_path):
    r = run(make_tree(tmp_path, lambda c, n: 1 + c["e"], n_raters=16))
    assert r["included"] == [f"R{n}" for n in range(24, 40)]


@pytest.mark.parametrize("slot", ["R23", "R40", "R7", "R024"])
def test_a_slot_outside_r24_to_r39_refuses_the_run(tmp_path, slot):
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"])
    f = root / "analysis" / "adherence_a13" / "ratings" / "ratings-R24.json"
    d = json.loads(f.read_text())
    d["rater"] = slot
    f.write_text(json.dumps(d))
    msg = f"ratings-R24.json: rater slot {slot} is outside A13's slots R24 to R39"
    with pytest.raises(SystemExit, match=msg):
        run(root)
    with pytest.raises(SystemExit, match=msg):
        A.count_only(root, fixtures=True)


@pytest.mark.parametrize("where", ["answers/ratings-R40.json", "ratings-R24.json", "ratings/old/ratings-R24.json"])
def test_a_rating_file_outside_ratings_stops_the_run(tmp_path, where):
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"])
    folder = root / "analysis" / "adherence_a13"
    stray = folder / where
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text((folder / "ratings" / "ratings-R25.json").read_text())
    for call in (lambda: run(root), lambda: A.count_only(root, fixtures=True)):
        with pytest.raises(SystemExit) as e:
            call()
        assert "outside ratings/" in str(e.value) and f"analysis/adherence_a13/{where}" in str(e.value)


@pytest.mark.parametrize("level", ["the tree", "a folder above it"])
def test_fixtures_refuse_a_tree_in_or_under_the_private_repository(tmp_path, level):
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"])
    marker = (root if level == "the tree" else tmp_path) / A.PRIVATE_MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("marker\n")
    with pytest.raises(SystemExit, match="refuses a private tree"):
        A.check_fixtures(root)
    with pytest.raises(SystemExit, match="refuses a private tree"):
        run(root)


import os  # noqa: E402
import shutil  # noqa: E402

import numpy as np  # noqa: E402


def test_mixed_rows_are_one_line_per_included_first_showing(tmp_path):
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"], n_raters=4)
    _root, rows = A.mixed_rows(root, fixtures=True)
    assert len(rows) == 4 * 110 and set(rows[0]) == {"rating", "drift", "study", "row", "rater"}
    assert len({r["row"] for r in rows}) == 22 and {r["rater"] for r in rows} == {"R24", "R25", "R26", "R27"}
    assert {r["study"] for r in rows} == {"burst", "push"}


def test_mixed_refuses_without_the_pinned_library(tmp_path, monkeypatch):
    monkeypatch.delenv("A13_R_LIBS", raising=False)
    with pytest.raises(SystemExit, match="A13_R_LIBS"):
        A.run_mixed(make_tree(tmp_path, lambda c, n: 1 + c["e"]), fixtures=True)


NEEDS_R = pytest.mark.skipif(not (shutil.which("Rscript") and os.environ.get("A13_R_LIBS")),
                             reason="R and the pinned ordinal are needed")


def defeating_scores():
    """Scores that follow only the engine step within a row: the non-convergence fixture (see below)."""
    rng = np.random.default_rng(1)
    return lambda c, n: int(np.clip(1 + c["e"] + rng.integers(-1, 2), 1, 5))


def planted_scores():
    """Scores that follow drift itself, within and between rows: the planted fixture (see below)."""
    rng = np.random.default_rng(1)
    return lambda c, n: int(np.clip(1 + round((0.5 * c["k"] + 0.3 * c["e"]) / 1.55) + rng.integers(-1, 2), 1, 5))


LOCK = A.ROOT / "analysis" / "a13-r-lock.txt"
CONVERGED_SENTENCE = "is in `a13_mixed.json`"


def locked_versions():
    """{"R": ..., "ordinal": ..., ...} as analysis/a13-r-lock.txt pins them."""
    out = {}
    for line in LOCK.read_text().splitlines():
        if line.startswith("R version "):
            out["R"] = line[len("R version "):]
        elif line.split(" ")[0] in ("ordinal", "ucminf", "numDeriv", "Matrix"):
            out[line.split(" ")[0]] = line.split(" ", 1)[1]
    return out


@NEEDS_R
def test_the_mixed_model_finds_a_planted_drift_effect(tmp_path):
    """The effect is planted in drift itself, within and between rows. The first draft planted it in the
    engine step only, while drift also rises 0.5 px per panel between rows with no change in score: the
    row effects then had to cancel a large drift coefficient and nlminb did not converge. That data is
    now the non-convergence fixture, defeating_scores(); do not put it back here."""
    root = make_tree(tmp_path, planted_scores(), n_raters=6)
    mx = A.run_mixed(root, fixtures=True)
    assert mx["n_ratings"] == 660 and mx["drift"]["estimate"] > 0 and "study_push" in mx
    assert mx["formula"] == "rating ~ drift + study + (1 | row) + (1 | rater)"
    assert mx["converged"] is True and mx["optimizer"] == "nlminb" and mx["condition_number_hessian"] > 0
    assert mx["convergence_code"] == 0 and 0 <= mx["max_abs_gradient"] < 0.1 and mx["warnings"] == []
    assert mx["test_control"] is None and mx["raters"] == [f"R{n}" for n in range(24, 30)]
    v = locked_versions()
    assert mx["r"] == f"R version {v.pop('R')}" and mx["packages"] == v      # as loaded, as locked


@NEEDS_R
def test_non_convergence_is_a_recorded_outcome_not_a_failure(tmp_path, capsys):
    root = make_tree(tmp_path, defeating_scores(), n_raters=6)
    mx = A.run_mixed(root, fixtures=True)
    assert mx["converged"] is False and mx["optimizer"] == "nlminb" and "converge" in mx["error"]
    assert mx["convergence_code"] is None and mx["max_abs_gradient"] is None and isinstance(mx["warnings"], list)
    assert not {"drift", "study_push", "thresholds", "random_sd", "log_likelihood"} & set(mx)
    A.main(["--fixtures", str(root), "--mixed"])                  # exits 0; the report reads the outcome
    assert "did not converge" in capsys.readouterr().out
    md = (root / "analysis" / "out" / "a13_adherence.md").read_text()
    assert "ordinal mixed model: did not converge (no verdict; error recorded)" in md


@NEEDS_R
def test_an_optimizer_limit_is_not_converged_though_clmm_returns(tmp_path):
    """clmm raises only when nlminb throws; a limit (here a test-only iter.max = 2) returns a fit with a
    non-zero convergence code, which is recorded as not converged, with the optimizer's message."""
    root = make_tree(tmp_path, planted_scores(), n_raters=6)
    mx = A.run_mixed(root, fixtures=True, test_control={"iter.max": 2})
    assert mx["converged"] is False and mx["convergence_code"] == 1 and "iteration limit" in mx["error"]
    assert mx["max_abs_gradient"] > 1 and mx["warnings"] == [] and mx["test_control"] == "iter.max=2"
    assert not {"drift", "study_push", "thresholds", "random_sd", "log_likelihood"} & set(mx)
    with pytest.raises(SystemExit, match="test-only optimizer control"):
        run(root)                                                  # such a file never reaches a report


@NEEDS_R
@pytest.mark.parametrize("item, how", [("R", "change"), ("ordinal", "change"), ("ucminf", "change"),
                                       ("numDeriv", "change"), ("Matrix", "change"), ("Matrix", "drop")])
def test_a_version_other_than_the_lock_refuses_the_mixed_model(tmp_path, item, how):
    prefix = "R version " if item == "R" else f"{item} "
    lines = [x if not x.startswith(prefix) else (x + "9" if how == "change" else None)
             for x in LOCK.read_text().splitlines()]
    lock = tmp_path / "lock.txt"
    lock.write_text("\n".join(x for x in lines if x is not None) + "\n")
    msg = f"{item} .* is pinned by the lock file; found" if how == "change" else f"{item}: the lock file names no single"
    with pytest.raises(SystemExit, match=msg):
        A.run_mixed(make_tree(tmp_path, planted_scores(), n_raters=6), fixtures=True, lock=lock)


@NEEDS_R
def test_a_mixed_model_fitted_before_a_rater_was_added_is_stale(tmp_path):
    root = make_tree(tmp_path, planted_scores(), n_raters=7)
    late = root / "analysis" / "adherence_a13" / "ratings" / "ratings-R30.json"
    held = tmp_path / "held-ratings-R30.json"                     # outside the tree: the stray guard stays quiet
    late.rename(held)
    mx = A.run_mixed(root, fixtures=True)
    assert mx["converged"] is True and (mx["n_raters"], mx["n_ratings"]) == (6, 660)
    held.rename(late)
    r = run(root)
    assert r["n_included"] == 7 and r["secondary"]["mixed_model"] == "stale (re-run --mixed)"
    md = (root / "analysis" / "out" / "a13_adherence.md").read_text()
    assert "stale (re-run --mixed)" in md and CONVERGED_SENTENCE not in md


@NEEDS_R
def test_a_mixed_model_fitted_on_other_raters_of_the_same_number_is_stale(tmp_path):
    """Counts alone miss a swap: one rater out and another in leaves n_raters and n_ratings equal (ruled 9 Nov 2026)."""
    root = make_tree(tmp_path, planted_scores(), n_raters=7)
    rd = root / "analysis" / "adherence_a13" / "ratings"
    (rd / "ratings-R30.json").rename(tmp_path / "held-ratings-R30.json")    # outside the tree
    assert A.run_mixed(root, fixtures=True)["raters"] == [f"R{n}" for n in range(24, 30)]
    (rd / "ratings-R29.json").rename(tmp_path / "held-ratings-R29.json")
    (tmp_path / "held-ratings-R30.json").rename(rd / "ratings-R30.json")
    r = run(root)
    assert r["included"] == ["R24", "R25", "R26", "R27", "R28", "R30"]
    assert r["secondary"]["mixed_model"] == "stale (re-run --mixed)"


FITTED_ON_10 = {"n_raters": 10, "n_ratings": 1100, "raters": [f"R{n}" for n in range(24, 34)]}


@pytest.mark.parametrize("mixed, status, line", [
    (None, "not run", "has not been run"),
    ({"converged": True, **FITTED_ON_10}, "converged", CONVERGED_SENTENCE),
    ({"converged": False, "optimizer": "nlminb", "error": "optimizer nlminb failed to converge", **FITTED_ON_10},
     "did not converge", "ordinal mixed model: did not converge (no verdict; error recorded)"),
    ({"converged": True, "n_raters": 9, "n_ratings": 990}, "stale (re-run --mixed)", "stale (re-run --mixed)"),
    ({"converged": True, "n_raters": 10, "n_ratings": 1099}, "stale (re-run --mixed)", "stale (re-run --mixed)"),
    ({"converged": True}, "stale (re-run --mixed)", "stale (re-run --mixed)"),
    ({"converged": True, **FITTED_ON_10, "raters": [f"R{n}" for n in range(24, 33)] + ["R39"]},
     "stale (re-run --mixed)", "stale (re-run --mixed)"),                    # same counts, another rater
    ({"converged": True, "n_raters": 10, "n_ratings": 1100}, "stale (re-run --mixed)", "stale (re-run --mixed)"),
])
def test_the_report_states_the_mixed_model_outcome(tmp_path, mixed, status, line):
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"])
    if mixed is not None:
        (root / "analysis" / "out" / "a13_mixed.json").write_text(json.dumps(mixed))
    r = run(root)
    assert r["secondary"]["mixed_model"] == status
    md = (root / "analysis" / "out" / "a13_adherence.md").read_text()
    assert line in md
    assert (CONVERGED_SENTENCE in md) == (status == "converged")


def test_a_mixed_model_fitted_with_a_test_only_control_never_reaches_a_report(tmp_path):
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"])
    (root / "analysis" / "out" / "a13_mixed.json").write_text(json.dumps(
        {"converged": True, "test_control": "iter.max=2", **FITTED_ON_10}))
    with pytest.raises(SystemExit, match="test-only optimizer control"):
        run(root)


def test_mixed_rows_apply_the_slot_and_stray_file_guards(tmp_path):
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"], n_raters=4)
    folder = root / "analysis" / "adherence_a13"
    stray = folder / "answers" / "ratings-R25.json"
    stray.parent.mkdir()
    stray.write_text((folder / "ratings" / "ratings-R25.json").read_text())
    with pytest.raises(SystemExit, match="outside ratings/"):
        A.mixed_rows(root, fixtures=True)
    stray.unlink()
    f = folder / "ratings" / "ratings-R24.json"
    d = json.loads(f.read_text())
    d["rater"] = "R40"
    f.write_text(json.dumps(d))
    with pytest.raises(SystemExit, match="outside A13's slots R24 to R39"):
        A.mixed_rows(root, fixtures=True)


def test_the_report_names_the_studies_the_same_way_everywhere(tmp_path):
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"])
    run(root)
    md = (root / "analysis" / "out" / "a13_adherence.md").read_text()
    assert "| burst | 22 | 33 |" in md and "| camera push | 22 | 33 |" in md and "| push |" not in md
    assert "; burst 1.000; camera push 1.000." in md


KAPPA_EXCEPTION = ("is excluded from every statistic except the κ of A13.4.4(c), which measures the instrument "
                   "over all complete raters")


def test_the_attention_rule_names_the_kappa_exception(tmp_path):
    """An attention-excluded rater still enters A9's kappa (kappas() reads every complete rater), so the rule the
    report prints says so in the registered words (ruled 9 Nov 2026)."""
    assert A.ATTENTION_RULE[A.EXCLUDE_IF] == (
        "per study, an attention item fails when the repeat's score differs from the first showing's by 2 or "
        "more points; a rater who fails both items of either study " + KAPPA_EXCEPTION)
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"])
    r = run(root)
    md = " ".join((root / "analysis" / "out" / "a13_adherence.md").read_text().split())
    assert r["attention_rule"].endswith(KAPPA_EXCEPTION) and KAPPA_EXCEPTION in md


def test_the_registered_text_quotes_the_rule_in_the_same_words():
    """The draft before registration, the pre-registration after it; skipped where neither carries A13 (the release
    before registration)."""
    texts = [p.read_text() for p in (A.ROOT / "docs" / "A13-DRAFT.md", A.ROOT / "docs" / "PREREGISTRATION.md")
             if p.is_file()]
    texts = [t for t in texts if "### A13 — " in t]
    if not texts:
        pytest.skip("no A13 text in this tree yet")
    assert all(KAPPA_EXCEPTION in " ".join(t.split()) for t in texts)


READINGS = {
    "stale mixed fit": "ordinal mixed model: stale (re-run --mixed)",
    "H4, significant the wrong way": "not supported (p <= 0.05 but rho <= 0)",
    "A9's motion AUC, a class without misses or non-misses": "undefined (no misses or no non-misses in this class)",
}


def test_the_code_emits_the_three_readings_the_registered_text_quotes(tmp_path):
    root = make_tree(tmp_path, lambda c, n: 1 + c["e"])
    (root / "analysis" / "out" / "a13_mixed.json").write_text(json.dumps({"converged": True}))     # stale
    assert run(root)["secondary"]["mixed_model"] == A.STALE
    md = (root / "analysis" / "out" / "a13_adherence.md").read_text().splitlines()
    stale = [x for x in md if A.STALE in x]
    assert len(stale) == 1 and stale[0].startswith(READINGS["stale mixed fit"])     # the report's own sentence
    assert A.h4_reading(-0.2, 0.01, True) == READINGS["H4, significant the wrong way"]
    assert a9.auc_reading(None) == READINGS["A9's motion AUC, a class without misses or non-misses"]


def test_the_registered_text_quotes_the_three_readings_in_the_code_s_words():
    """As the attention rule above (ruled 9 Nov 2026): the draft before registration, the pre-registration after it."""
    texts = [p.read_text() for p in (A.ROOT / "docs" / "A13-DRAFT.md", A.ROOT / "docs" / "PREREGISTRATION.md")
             if p.is_file()]
    texts = [" ".join(t.split()) for t in texts if "### A13 — " in t]
    if not texts:
        pytest.skip("no A13 text in this tree yet")
    assert all(f'"{r}"' in t for t in texts for r in READINGS.values())


def test_the_registered_text_quotes_the_built_privacy_line():
    """A13.3.6 item 8 quotes the privacy line the build sets (build_a13.PRIVACY), word for word."""
    texts = [p.read_text() for p in (A.ROOT / "docs" / "A13-DRAFT.md", A.ROOT / "docs" / "PREREGISTRATION.md")
             if p.is_file()]
    texts = [" ".join(t.split()) for t in texts if "### A13 — " in t]
    if not texts:
        pytest.skip("no A13 text in this tree yet")
    assert all(f'in place of A9\'s: "{BA13.PRIVACY}"' in t for t in texts)
