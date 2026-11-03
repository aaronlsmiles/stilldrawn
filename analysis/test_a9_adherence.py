"""Tests for analysis/a9_adherence.py (A9 Test 1). Synthetic fixtures only: no
released value and no rating is read here.

    python -m pytest analysis/test_a9_adherence.py
"""
import ast
import hashlib
import itertools
import json
import math
import os
import platform
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a9_adherence as ad  # noqa: E402


def private_term_hits(text):
    """What in `text` matches a private term (reported by line number in private-terms.txt, never spelled).
    The terms are read from that file, which only the private repo has: in the public tree there is
    nothing to check against and this returns []."""
    import importlib.util
    path = Path(__file__).resolve().parent / "adherence" / "prepare.py"
    spec = importlib.util.spec_from_file_location("_prepare_for_tests", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    terms, problems = mod.load_private_terms(path.parent / mod.PRIVATE_TERMS_NAME)
    assert problems == []
    return mod.find_banned(text, terms or []) + mod.find_banned(mod.deobfuscate(text), terms or [])

ANALYSIS = Path(__file__).resolve().parent

SUFFIX = {"wan22": "wan22", "gen4_turbo": "gen4t", "ltx23": "ltx23", "gen4.5": "gen45", "h3-fal": "h3"}
BASE_DRIFT = {"wan22": 0.8, "gen4_turbo": 2.6, "ltx23": 2.8, "gen4.5": 4.8, "h3-fal": 5.4}
BASE_MOTION = {"wan22": 0.01, "gen4_turbo": 0.03, "ltx23": 0.04, "gen4.5": 0.06, "h3-fal": 0.08}
ROWS = {"burst": ["xyz-act-tank-1", "chain-est-cosmic-1"] + [f"act-b-{i}" for i in range(1, 10)],
        "push": ["xyz-act-tank-1", "chain-est-cosmic-1"] + [f"cu-p-{i}" for i in range(1, 10)]}
MOTION_WORD = {"burst": "burst", "push": "campush"}
QUESTION = {"burst": "burst", "push": "push"}                      # blindpanel question ids = the export keys
LOCK_HASH = {"burst": "a" * 64, "push": "b" * 64}
DELIVERY = {"autoplay": True, "keyboard": False, "duration_s": 1230, "ui": "blindpanel@0.1.0"}


def cell_ids():
    """[(private cell id, public id, engine, study, row index)] for the 110 synthetic cells."""
    out = []
    for study, panels in ROWS.items():
        for i, panel in enumerate(panels):
            for e, suf in SUFFIX.items():
                cid = f"{panel}_{MOTION_WORD[study]}_{suf}"
                out.append((cid, ad.public_id(cid), e, study, i))
    return out


def scores_by_misses(misses, miss_score=1, hit_score=5):
    """Scores where engine e misses on its first misses[e] cells (in id order)."""
    seen, out = {}, {}
    for _cid, pid, e, _s, _i in sorted(cell_ids(), key=lambda t: t[1]):
        k = seen.get(e, 0)
        out[pid] = miss_score if k < misses[e] else hit_score
        seen[e] = k + 1
    return out


SUPPORTED = {"wan22": 18, "gen4_turbo": 12, "ltx23": 8, "gen4.5": 4, "h3-fal": 1}   # steadiest misses most
REVERSED = {"wan22": 1, "gen4_turbo": 4, "ltx23": 8, "gen4.5": 12, "h3-fal": 18}


def write_ratings(adh, rater, scores, received_day="2026-11-03", registered="2026-11-01", deadline="2026-11-15"):
    """Slim files as `slim` writes them: ratings in the order seen (here: reverse id order), with positions."""
    for study in ad.STUDIES:
        ids = sorted(p for _c, p, _e, s, _i in cell_ids() if s == study)[::-1]
        dl = deadline if rater == "R7" else None
        rec = {"schema": ad.SLIM_SCHEMA, "rater": rater, "study": study, "instrument": "A9",
               "question": QUESTION[study], "text_sha256": LOCK_HASH[study], "received_day": received_day,
               "registered_day": registered, "deadline": dl,
               "within_deadline": (received_day <= dl) if dl else None, "flags": [], "delivery": DELIVERY,
               "export_sha256": "0" * 64, "n": 55,
               "ratings": [{"position": k + 1, "clip": p, "score": scores[p]} for k, p in enumerate(ids)]}
        (adh / f"ratings-{study}-{rater}.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")


def fixture(root, aaron=SUPPORTED, r7=None, r7_on="2026-11-03", deadline="2026-11-15", blind=True,
            deadline_passed=False, registered="2026-11-01", aaron_on="2026-11-03"):
    out, mot, adh = root / "analysis" / "out", root / "runs" / "metrics-motion", root / "analysis" / "adherence"
    for d in (out, mot, adh):
        d.mkdir(parents=True, exist_ok=True)
    rows = []
    for cid, _pid, e, study, i in cell_ids():
        rows.append({"cell_id": cid, "engine": e, "panel_id": cid.split("_")[0], "flint_pair": "",
                     "motion": ad.STUDIES[study], "line_chamfer_mean_px": BASE_DRIFT[e] * (1 + 0.01 * i)})
        (mot / f"{cid}.json").write_text(json.dumps({"motion": {"headline_median_norm": BASE_MOTION[e] + 0.001 * i}}), encoding="utf-8", newline="\n")
    rows.append({"cell_id": "act-b-1_idle_wan22", "engine": "wan22", "panel_id": "act-b-1", "flint_pair": "",
                 "motion": "IDLE", "line_chamfer_mean_px": 9.9})
    rows.append({"cell_id": "flint-a--b_h3", "engine": "h3-fal", "panel_id": "a", "flint_pair": "a--b",
                 "motion": "FLINT", "line_chamfer_mean_px": 9.9})
    (out / "results_table.json").write_text(json.dumps(rows), encoding="utf-8", newline="\n")
    (adh / "a9-config.json").write_text(json.dumps({"schema": ad.CONFIG_SCHEMA, "registered_on": registered,
                                                    "r7_deadline": deadline, "r7_blind_to_engine_styles": blind}), encoding="utf-8", newline="\n")
    for study in ad.STUDIES:                                   # study.lock.json: the wording hash the files cite
        (adh / study).mkdir(exist_ok=True)
        (adh / study / "study.lock.json").write_text(json.dumps({"instrument": "A9", "text_sha256": LOCK_HASH[study]}), encoding="utf-8", newline="\n")
    if deadline_passed:
        (adh / "r7-status.json").write_text(json.dumps({"deadline_passed": True, "recorded_on": "2026-11-16"}), encoding="utf-8", newline="\n")
    if aaron is not None:
        write_ratings(adh, "AARON", scores_by_misses(aaron), received_day=aaron_on, registered=registered)
    if r7 is not None:
        write_ratings(adh, "R7", scores_by_misses(r7), received_day=r7_on, registered=registered, deadline=deadline)
    return root


# ---------------------------------------------------------------------- stats
def test_exact_p_at_the_extremes_and_at_minus_0_9():
    assert ad.exact_one_sided_p([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == (pytest.approx(-1.0), 1 / 120)
    rho, p = ad.exact_one_sided_p([1, 2, 3, 4, 5], [5, 4, 3, 1, 2])
    assert rho == pytest.approx(-0.9) and p == 5 / 120
    assert ad.exact_one_sided_p([1, 2, 3, 4, 5], [0.5] * 5) == (None, None)


def test_attainable_p_values_without_ties():
    table = ad.attainable_p_no_ties()
    assert table[0] == [-1.0, 1 / 120] and table[1] == [-0.9, 5 / 120]
    assert table[2][1] > 0.05 and table[-1] == [1.0, 1.0]


def test_midranks_share_ties():
    assert list(ad.midranks([3, 1, 3, 2])) == [3.5, 1.0, 3.5, 2.0]
    assert ad.spearman([1, 2, 3], [1, 1, 1]) is None


def test_wilson_intervals():
    z2 = ad.Z95 ** 2
    lo, hi = ad.wilson(0, 22)
    assert lo == pytest.approx(0.0, abs=1e-12) and hi == pytest.approx(z2 / (22 + z2))
    lo, hi = ad.wilson(11, 22)
    assert lo + hi == pytest.approx(1.0)
    assert ad.wilson(0, 0) is None


def test_weighted_kappa():
    assert ad.weighted_kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == pytest.approx(1.0)
    assert ad.weighted_kappa([1, 1, 2, 2], [1, 2, 1, 2]) == pytest.approx(0.0)
    assert ad.weighted_kappa([3, 3], [3, 3]) is None


def test_auc_and_its_reading():
    assert ad.auc([3.0, 2.0], [1.0]) == 1.0
    assert ad.auc([1.0], [1.0]) == 0.5
    assert ad.auc([], [1.0]) is None
    assert ad.auc_reading(0.75).startswith("corroborates")
    assert ad.auc_reading(0.55) == "the misses are not under-animation"
    assert ad.auc_reading(0.65).startswith("inconclusive")


# ------------------------------------------------------------------ the run
def test_author_only_while_r7_is_pending(tmp_path):
    res = ad.run(fixture(tmp_path), draws=200)
    assert res["label"] == "author-rated; second rater pending"
    assert res["verdict"] == "no verdict (second rater pending)" and res["raters"]["R7"] is None
    assert res["raters"]["AARON"]["provisional"] == "provisional (AARON only)"
    pr = res["raters"]["AARON"]["primary"]
    assert pr["rho"] == pytest.approx(-1.0) and pr["p_one_sided"] == pytest.approx(1 / 120, rel=1e-11)
    w = pr["per_engine"]["wan22"]
    assert (w["n"], w["misses"]) == (22, 18) and w["miss_rate"] == pytest.approx(18 / 22, rel=1e-11)
    assert w["wilson95"] == pytest.approx(ad.wilson(18, 22), rel=1e-11)
    assert list(res["steadiness_px"]) == list(ad.LEAGUE_ORDER)
    assert res["r7_blind_to_engine_styles"] is True
    assert res["r7_declaration"].startswith("R7 is declared blind")
    md = (tmp_path / "analysis" / "out" / "a9_adherence.md").read_text(encoding="utf-8")
    assert "author-rated; second rater pending" in md and "| Wan 2.2 |" in md and "no rank column" in md
    assert "**Verdict: no verdict (second rater pending).**" in md
    assert (tmp_path / "analysis" / "out" / "figures" / "a9_adherence.png").exists()


def test_fallback_when_the_deadline_passes_without_r7(tmp_path):
    res = ad.run(fixture(tmp_path, deadline_passed=True), draws=200)
    assert res["label"] == "author-rated" and "did not export" in res["basis"]
    # registered rule: no two-rater verdict in the fallback; AARON's numbers are still computed and reported
    assert res["verdict"] == "not tested by two raters"
    pr = res["raters"]["AARON"]["primary"]
    assert pr["rho"] == pytest.approx(-1.0) and pr["p_one_sided"] == pytest.approx(1 / 120, rel=1e-11)
    assert res["raters"]["R7"] is None
    md = (tmp_path / "analysis" / "out" / "a9_adherence.md").read_text(encoding="utf-8")
    assert "**Verdict: not tested by two raters.**" in md and "author-rated" in md
    assert "Verdict: supported" not in md and "Verdict: not supported" not in md
    assert "## AARON" in md and "exact one-sided p" in md


def test_fallback_has_no_verdict_even_when_aarons_alone_would_fail(tmp_path):
    res = ad.run(fixture(tmp_path, aaron=REVERSED, deadline_passed=True), draws=200)
    assert res["label"] == "author-rated" and res["verdict"] == "not tested by two raters"


def test_two_raters_both_needed(tmp_path):
    res = ad.run(fixture(tmp_path / "a", r7=SUPPORTED), draws=200)
    assert res["label"] == "two raters" and res["verdict"] == "supported"
    assert res["agreement_quadratic_kappa"]["burst"] == pytest.approx(1.0)
    res = ad.run(fixture(tmp_path / "b", r7=REVERSED), draws=200)
    assert res["label"] == "two raters" and res["verdict"] == "not supported"


def test_r7_on_the_deadline_day_is_in_time(tmp_path):
    res = ad.run(fixture(tmp_path, r7=SUPPORTED, r7_on="2026-11-15"), draws=200)      # inclusive
    assert res["label"] == "two raters"
    assert res["ratings_files"]["R7"]["burst"]["within_deadline"] is True
    assert res["ratings_files"]["R7"]["burst"]["received_day"] == "2026-11-15"
    assert res["ratings_files"]["AARON"]["burst"]["within_deadline"] is None


def test_late_r7_export_keeps_the_author_label(tmp_path):
    res = ad.run(fixture(tmp_path, r7=SUPPORTED, r7_on="2026-11-20"), draws=200)
    assert res["label"] == "author-rated" and "after the deadline" in res["basis"]
    assert res["raters"]["R7"] is not None                     # analysed and printed, but no verdict
    assert res["verdict"] == "not tested by two raters"        # even though both raters would have passed
    assert res["agreement_quadratic_kappa"]["burst"] == pytest.approx(1.0)
    assert "r7_without_a6_overlap" not in res and "a6_overlap_clips" not in res
    md = (tmp_path / "analysis" / "out" / "a9_adherence.md").read_text(encoding="utf-8")
    assert "**Verdict: not tested by two raters.**" in md
    assert "## R7" in md and "## Agreement" in md and "late" in md and "without the" not in md
    assert "Verdict: supported" not in md


def test_r7_without_a_deadline_is_an_error(tmp_path):
    with pytest.raises(SystemExit, match="r7_deadline"):
        ad.run(fixture(tmp_path, r7=SUPPORTED, deadline=None), draws=200)


def test_equal_miss_rates_are_not_supported(tmp_path):
    res = ad.run(fixture(tmp_path, aaron={e: 5 for e in ad.LEAGUE_ORDER}), draws=200)
    assert res["raters"]["AARON"]["primary"]["rho"] is None and res["verdict"] == "no verdict (second rater pending)"
    res = ad.run(fixture(tmp_path / "two", aaron={e: 5 for e in ad.LEAGUE_ORDER}, r7={e: 5 for e in ad.LEAGUE_ORDER}),
                 draws=200)
    assert res["verdict"] == "not supported"                   # the two-rater state still says it


def test_no_statistic_without_aarons_ratings(tmp_path):
    with pytest.raises(SystemExit, match="nothing to analyse"):
        ad.run(fixture(tmp_path, aaron=None), draws=200)


def test_within_row_is_seeded_and_one_sided(tmp_path):
    root = fixture(tmp_path)
    cells = ad.load_cells(root)
    scores = {p: (5 if c["engine"] in ("gen4.5", "h3-fal") else 1) for p, c in cells.items()}
    a = ad.within_row(cells, scores, draws=300)
    b = ad.within_row(cells, scores, draws=300)
    assert a == b and a["n_rows"] == 22 and a["mean_rho"] > 0.8 and a["p_one_sided"] < 0.01


def test_two_runs_are_byte_identical(tmp_path):
    root = fixture(tmp_path, r7=REVERSED)
    ad.run(root, out_dir=tmp_path / "o1", draws=300)
    ad.run(root, out_dir=tmp_path / "o2", draws=300)
    for name in ("a9_adherence.json", "a9_adherence.md", "figures/a9_adherence.png"):
        assert (tmp_path / "o1" / name).read_bytes() == (tmp_path / "o2" / name).read_bytes(), name


# ---------------------------------------------------------------------- slim
# The raw shapes are blindpanel 0.1.0's: `blindpanel export` writes ratings-V0001.json =
# {rater, instrument, ratings: [{clip, <question id>: n}, ...in the order seen], baseline, flags} and no
# day or delivery; the stored row (the file store's .jsonl) carries order, answers, delivery, flags and
# received_day (src/cli/data.ts, src/server/stores/types.ts).
def _seen(study):
    return sorted(p for _c, p, _e, s, _i in cell_ids() if s == study)[::-1]            # the order this rater saw


def _code(k, clip):
    return f"c{k:05d}"


def _codes(study, code=_code):
    """{opaque code: public cell id}: what prepare.py derives from the study seed."""
    return {code(k, p): p for k, p in enumerate(_seen(study))}


def _export(path, study, instrument="A9", drop=0, bad=None, flags=("fast",), shuffle=False):
    q = QUESTION[study]
    ratings = [{"clip": p, q: 1 + k % 5} for k, p in enumerate(_seen(study))]
    if shuffle:                                     # same score sequence, two clip names swapped
        ratings[0]["clip"], ratings[1]["clip"] = ratings[1]["clip"], ratings[0]["clip"]
    ratings = ratings[drop:]
    if bad is not None:
        ratings[0][q] = bad
    path.write_text(json.dumps({"rater": "V0001", "instrument": instrument, "ratings": ratings,
                                "baseline": [], "flags": list(flags)}, indent=1) + "\n", encoding="utf-8", newline="\n")
    return path


def _store(path, study, day="2026-11-02", rows=1, tamper=False, flags=("fast",), study_id=None, rater=None,
           code=_code):
    q = QUESTION[study]
    seen = _seen(study)
    code = {p: code(k, p) for k, p in enumerate(seen)}
    answers = {code[p]: {q: 1 + k % 5} for k, p in enumerate(seen)}
    if tamper:
        answers[code[seen[0]]][q] = 5
    row = {"study": study_id or f"a9-{study}", "instrument": "A9", "session": "s",
           "order": {"baseline": [], "clips": [code[p] for p in seen]},
           "answers": {"baseline": {}, "clips": answers}, "delivery": DELIVERY, "flags": list(flags),
           "received_day": day}
    if rater is not None:
        row["rater"] = rater
    path.write_text("".join(json.dumps(row) + "\n" for _ in range(rows)), encoding="utf-8", newline="\n")
    return path


def _ctx(root, study="burst"):
    adh = root / "analysis" / "adherence"
    return (ad.load_cells(root), ad.load_config(adh), json.loads((adh / study / "study.lock.json").read_text(encoding="utf-8")))


def _slim(tmp_path, rater="AARON", study="burst", store_kw=None, export_kw=None, **kw):
    root = fixture(tmp_path / "repo")
    cells, config, lock = _ctx(root, study)
    e = _export(tmp_path / "e.json", study, **(export_kw or {}))
    s = _store(tmp_path / "s.jsonl", study, **(store_kw or {}))
    kw.setdefault("code_map", _codes(study))
    return ad.slim(e, s, rater, study, cells, config, lock, **kw), e


def test_slim_writes_the_full_record_in_the_order_seen(tmp_path):
    rec, e = _slim(tmp_path)
    assert list(rec) == ["schema", "rater", "study", "instrument", "question", "text_sha256", "received_day",
                         "registered_day", "deadline", "within_deadline", "flags", "delivery", "export_sha256",
                         "n", "ratings"]
    assert rec["schema"] == ad.SLIM_SCHEMA and rec["n"] == 55 and len(rec["ratings"]) == 55
    assert (rec["rater"], rec["study"], rec["instrument"], rec["question"]) == ("AARON", "burst", "A9", "burst")
    assert rec["text_sha256"] == LOCK_HASH["burst"] and rec["flags"] == ["fast"] and rec["delivery"] == DELIVERY
    assert rec["received_day"] == "2026-11-02" and rec["registered_day"] == "2026-11-01"      # the stored row, the config
    assert rec["deadline"] is None and rec["within_deadline"] is None                          # AARON has no deadline
    assert [r["position"] for r in rec["ratings"]] == list(range(1, 56))
    assert [r["clip"] for r in rec["ratings"]] == _seen("burst")                               # order seen, not sorted
    assert rec["ratings"][0] == {"position": 1, "clip": _seen("burst")[0], "score": 1}
    assert rec["export_sha256"] == ad.hashlib.sha256(e.read_bytes()).hexdigest()


def test_slim_for_r7_reads_the_deadline_from_the_config(tmp_path):
    rec, _ = _slim(tmp_path, rater="R7", store_kw={"day": "2026-11-15"})
    assert rec["deadline"] == "2026-11-15" and rec["within_deadline"] is True                  # inclusive
    rec, _ = _slim(tmp_path / "late", rater="R7", store_kw={"day": "2026-11-16"})
    assert rec["within_deadline"] is False                                                     # kept, labelled late


def test_slim_refuses_a_day_not_after_registration(tmp_path):
    for day in ("2026-11-01", "2026-10-31"):
        with pytest.raises(SystemExit, match="not after registration"):
            _slim(tmp_path / day, store_kw={"day": day})


def test_slim_needs_the_registered_config(tmp_path):
    root = fixture(tmp_path / "repo")
    cells, config, lock = _ctx(root)
    e, s = _export(tmp_path / "e.json", "burst"), _store(tmp_path / "s.jsonl", "burst")
    with pytest.raises(SystemExit, match="registered_on"):
        ad.slim(e, s, "AARON", "burst", cells, dict(config, registered_on=None), lock, code_map=_codes("burst"))
    with pytest.raises(SystemExit, match="r7_deadline"):
        ad.slim(e, s, "R7", "burst", cells, dict(config, r7_deadline=None), lock, code_map=_codes("burst"))


def test_slim_exported_on_is_only_a_cross_check(tmp_path):
    rec, _ = _slim(tmp_path, exported_on="2026-11-02")
    assert rec["received_day"] == "2026-11-02"
    with pytest.raises(SystemExit, match="stored day"):
        _slim(tmp_path / "x", exported_on="2026-11-03")
    with pytest.raises(SystemExit, match="YYYY-MM-DD"):
        _slim(tmp_path / "y", exported_on="3 Nov")


def test_slim_refuses_a_second_session_or_a_mismatch(tmp_path):
    with pytest.raises(SystemExit, match="one stored session"):
        _slim(tmp_path / "a", store_kw={"rows": 2})
    with pytest.raises(SystemExit, match="differ"):
        _slim(tmp_path / "b", store_kw={"tamper": True})
    with pytest.raises(SystemExit, match="flags"):
        _slim(tmp_path / "c", store_kw={"flags": ()})
    with pytest.raises(SystemExit, match="study"):
        _slim(tmp_path / "d", store_kw={"study_id": "a9-push"})


def test_slim_rejects_bad_exports(tmp_path):
    with pytest.raises(SystemExit, match="instrument"):
        _slim(tmp_path / "a", export_kw={"instrument": "1"})
    with pytest.raises(SystemExit, match="not the 55 burst cells"):
        _slim(tmp_path / "b", export_kw={"drop": 1})
    with pytest.raises(SystemExit, match="not 1-5"):
        _slim(tmp_path / "c", export_kw={"bad": 7})
    with pytest.raises(SystemExit, match="not 1-5"):
        _slim(tmp_path / "d", export_kw={"bad": True})


def test_slim_output_loads_and_runs(tmp_path):
    """A slim record written by `slim` is accepted by the analysis (positions, order seen, lock hash)."""
    root = fixture(tmp_path / "repo", aaron=None)
    cells, config, _ = _ctx(root)
    for study in ad.STUDIES:
        lock = json.loads((root / "analysis" / "adherence" / study / "study.lock.json").read_text(encoding="utf-8"))
        rec = ad.slim(_export(tmp_path / f"e{study}.json", study), _store(tmp_path / f"s{study}.jsonl", study),
                      "AARON", study, cells, config, lock, code_map=_codes(study))
        (root / "analysis" / "adherence" / f"ratings-{study}-AARON.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    res = ad.run(root, draws=100)
    assert res["label"] == "author-rated; second rater pending"


@pytest.mark.parametrize("edit, message", [
    (lambda d: d["ratings"][3].__setitem__("position", 99), "positions"),
    (lambda d: d["ratings"].reverse(), "positions"),
    (lambda d: d.__setitem__("n", 54), "n is 54"),
    (lambda d: d.__setitem__("text_sha256", "f" * 64), "study.lock.json"),
    (lambda d: d.__setitem__("registered_day", "2026-10-01"), "registered_day"),
    (lambda d: d.__setitem__("received_day", "2026-11-01"), "not after registration"),
    (lambda d: d.__setitem__("received_day", "11/03"), "received_day"),
])
def test_load_ratings_checks_the_slim_fields(tmp_path, edit, message):
    root = fixture(tmp_path)
    _edit_ratings(root, "AARON", "burst", edit)
    with pytest.raises(SystemExit, match=message):
        ad.run(root, draws=100)


def test_load_ratings_checks_r7_deadline_fields(tmp_path):
    root = fixture(tmp_path, r7=SUPPORTED)
    _edit_ratings(root, "R7", "push", lambda d: d.__setitem__("within_deadline", False))
    with pytest.raises(SystemExit, match="within_deadline"):
        ad.run(root, draws=100)
    root = fixture(tmp_path / "b", r7=SUPPORTED)
    _edit_ratings(root, "R7", "push", lambda d: d.__setitem__("deadline", "2026-12-01"))
    with pytest.raises(SystemExit, match="deadline"):
        ad.run(root, draws=100)


# ------------------------------------------------- verdict status and tables
def test_pending_state_gives_no_verdict_and_labels_aarons_numbers_provisional(tmp_path):
    for k, aaron in enumerate((SUPPORTED, REVERSED)):          # whichever way AARON's numbers fall
        root = tmp_path / str(k)
        res = ad.run(fixture(root, aaron=aaron), draws=200)
        assert res["verdict"] == "no verdict (second rater pending)"
        assert res["verdict_status"] == "no verdict (second rater pending)"
        assert res["label"] == "author-rated; second rater pending"
        assert res["raters"]["AARON"]["provisional"] == "provisional (AARON only)"
        md = (root / "analysis" / "out" / "a9_adherence.md").read_text(encoding="utf-8")
        js = (root / "analysis" / "out" / "a9_adherence.json").read_text(encoding="utf-8")
        assert "**Verdict: no verdict (second rater pending).**" in md
        assert "Status: **author-rated; second rater pending**" in md
        assert "- provisional (AARON only): Spearman rho(S, m)" in md and "exact one-sided p" in md
        assert md.count("provisional (AARON only): ") == 3            # primary, sensitivity, within-row lines
        for text in (md, js):                                       # no bare H1 verdict anywhere in pending
            assert "supported" not in text
    assert ad.verdict(ad.LABEL_PENDING, {"AARON": {"primary": {"p_le_0_05": True}}}) == "no verdict (second rater pending)"


def test_verdict_status_two_raters_is_final(tmp_path):
    res = ad.run(fixture(tmp_path, r7=SUPPORTED), draws=200)
    assert res["verdict_status"] == "final"
    md = (tmp_path / "analysis" / "out" / "a9_adherence.md").read_text(encoding="utf-8")
    assert "**Verdict: supported.**" in md and "provisional" not in md


def test_verdict_status_fallback_is_no_verdict(tmp_path):
    res = ad.run(fixture(tmp_path, deadline_passed=True), draws=200)
    assert res["verdict_status"] == "no verdict (author-rated fallback)"
    md = (tmp_path / "analysis" / "out" / "a9_adherence.md").read_text(encoding="utf-8")
    assert "provisional" not in md
    res = ad.run(fixture(tmp_path / "late", r7=SUPPORTED, r7_on="2026-11-20"), draws=200)
    assert res["verdict_status"] == "no verdict (author-rated fallback)"


def test_md_has_engine_by_class_table(tmp_path):
    ad.run(fixture(tmp_path, r7=SUPPORTED), draws=200)
    md = (tmp_path / "analysis" / "out" / "a9_adherence.md").read_text(encoding="utf-8")
    assert md.count("| engine | burst misses / n (Wilson 95%) | push misses / n (Wilson 95%) |") == 2   # one per rater
    lines = md.splitlines()
    i = lines.index("| engine | burst misses / n (Wilson 95%) | push misses / n (Wilson 95%) |")
    rows = lines[i + 2:i + 7]
    assert [r.split("|")[1].strip() for r in rows] == [ad.ENGINE_NAMES[e] for e in ad.LEAGUE_ORDER]
    cls = ad.by_class(ad.load_cells(tmp_path), scores_by_misses(SUPPORTED))
    lo, hi = cls["wan22"]["burst"]["wilson95"]
    assert f"{cls['wan22']['burst']['misses']} / 11 ({lo:.2f} to {hi:.2f})" in rows[0]
    assert "rank" not in "\n".join(rows).lower()


# ------------------------------------------------- ratings validation at analysis time
def _edit_ratings(root, rater, study, fn):
    f = root / "analysis" / "adherence" / f"ratings-{study}-{rater}.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    fn(d)
    f.write_text(json.dumps(d), encoding="utf-8", newline="\n")


@pytest.mark.parametrize("bad", [0, 6, 3.5, "4", None, True])
def test_load_ratings_rejects_scores_outside_int_1_to_5(tmp_path, bad):
    root = fixture(tmp_path)
    _edit_ratings(root, "AARON", "burst", lambda d: d["ratings"][0].__setitem__("score", bad))
    with pytest.raises(SystemExit, match="not an integer 1-5"):
        ad.run(root, draws=200)


def test_load_ratings_rejects_duplicate_clips(tmp_path):
    root = fixture(tmp_path)
    _edit_ratings(root, "AARON", "push", lambda d: d["ratings"].__setitem__(1, dict(d["ratings"][0])))
    with pytest.raises(SystemExit, match="duplicate clip"):
        ad.run(root, draws=200)


def test_load_ratings_rejects_wrong_clip_set(tmp_path):
    root = fixture(tmp_path)
    _edit_ratings(root, "AARON", "burst", lambda d: d["ratings"].pop())
    with pytest.raises(SystemExit, match="not the 55 burst cells"):
        ad.run(root, draws=200)


def test_load_ratings_rejects_wrong_rater_or_instrument(tmp_path):
    root = fixture(tmp_path)
    _edit_ratings(root, "AARON", "burst", lambda d: d.__setitem__("rater", "R7"))
    with pytest.raises(SystemExit, match="rater"):
        ad.run(root, draws=200)
    root = fixture(tmp_path / "i")
    _edit_ratings(root, "AARON", "push", lambda d: d.__setitem__("instrument", "1"))
    with pytest.raises(SystemExit, match="instrument"):
        ad.run(root, draws=200)


def test_md_states_when_each_export_was_received(tmp_path):
    ad.run(fixture(tmp_path, r7=SUPPORTED, r7_on="2026-11-15"), draws=100)
    md = (tmp_path / "analysis" / "out" / "a9_adherence.md").read_text(encoding="utf-8")
    assert "Ratings received: burst 2026-11-03, push 2026-11-03 (deadline: none)." in md
    assert "Ratings received: burst 2026-11-15, push 2026-11-15 (deadline 2026-11-15: in time)." in md
    assert "exported_on" not in md


# ======================================================================== quality pass before freeze
# ------------------------------------------------------------------ exact arithmetic
def _frac_ranks(a):
    order = sorted(range(len(a)), key=lambda i: a[i])
    ranks, i = [None] * len(a), 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and a[order[j + 1]] == a[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = Fraction(i + 1 + j + 1, 2)
        i = j + 1
    return ranks


def _frac_sxy(rx, ry):
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry))


def test_spearman_and_the_exact_test_match_an_independent_fraction_computation():
    x = [1, 2, 3, 4, 5]
    rx = _frac_ranks(x)
    for m in itertools.product(range(3), repeat=5):
        if len(set(m)) == 1:
            continue
        ry = _frac_ranks(m)
        sxy = _frac_sxy(rx, ry)
        want_hits = sum(_frac_sxy(rx, [ry[i] for i in p]) <= sxy for p in itertools.permutations(range(5)))
        rho, p = ad.exact_one_sided_p(x, list(m))
        assert p == want_hits / 120, m
        sxx, syy = _frac_sxy(rx, rx), _frac_sxy(ry, ry)
        assert rho == pytest.approx(float(sxy) / math.sqrt(float(sxx * syy)), abs=1e-15), m


def test_exact_p_has_no_tolerance():
    # rho values 1e-13 apart are different values: only an exact comparison keeps them apart.
    src = Path(ad.__file__).read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "exact_one_sided_p")
    assert not [n for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, float)]


def test_midranks_are_exact_fractions():
    r = ad.midranks([0.1, 0.1 + 0.2, 0.3, 0.1])
    assert all(isinstance(v, Fraction) for v in r)
    assert r == [Fraction(3, 2), Fraction(4), Fraction(3), Fraction(3, 2)]    # 0.1+0.2 != 0.3 as floats: kept apart


def test_r12_and_the_floats_in_the_json(tmp_path):
    assert ad._r12(1 / 3) == 0.333333333333 and ad._r12(None) is None and ad._r12(0.0) == 0.0
    res = ad.run(fixture(tmp_path, r7=REVERSED), draws=100)

    def walk(o):
        if isinstance(o, float):
            yield o
        elif isinstance(o, dict):
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)
    floats = list(walk(res))
    assert floats and all(float(f"{v:.12g}") == v for v in floats)
    on_disk = json.loads((tmp_path / "analysis" / "out" / "a9_adherence.json").read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(res))


def test_weighted_kappa_is_exact():
    x, y = [1, 2, 3, 4, 5, 2, 2], [1, 2, 3, 3, 5, 4, 1]
    k = 5
    O = [[0] * k for _ in range(k)]
    for a, b in zip(x, y):
        O[a - 1][b - 1] += 1
    n = len(x)
    rows, cols = [sum(r) for r in O], [sum(O[i][j] for i in range(k)) for j in range(k)]
    num = sum(Fraction((i - j) ** 2, 16) * O[i][j] for i in range(k) for j in range(k))
    den = sum(Fraction((i - j) ** 2, 16) * Fraction(rows[i] * cols[j], n) for i in range(k) for j in range(k))
    assert ad.weighted_kappa(x, y) == float(1 - num / den)


# ------------------------------------------------------------------ RNG goldens
def test_the_registered_rng_stream_is_pinned():
    rng = np.random.default_rng(ad.SEED)
    assert ad.SEED == 20261030
    assert [rng.permutation(5).tolist() for _ in range(4)] == [[2, 1, 0, 3, 4], [2, 1, 3, 0, 4], [0, 2, 4, 1, 3],
                                                              [1, 0, 2, 4, 3]]


TINY_DRIFT = [[1.0, 2.5, 2.0, 4.0, 3.5], [0.5, 3.0, 3.0, 6.0, 5.0]]        # per row, in league order
TINY_SCORE = [[3, 1, 2, 5, 4], [2, 5, 4, 3, 3]]


def _tiny():
    cells, scores = {}, {}
    for r, (ds, ss) in enumerate(zip(TINY_DRIFT, TINY_SCORE)):
        for e, d, s in zip(ad.LEAGUE_ORDER, ds, ss):
            pid = f"row{r}_burst_{SUFFIX[e]}"
            cells[pid] = {"engine": e, "panel": f"row{r}", "study": "burst", "drift": d}
            scores[pid] = s
    return cells, scores


def test_within_row_golden_on_a_tiny_input():
    # independent reference: scipy.stats.spearmanr per row, mean 67/190; 29 of 200 draws reach it
    cells, scores = _tiny()
    res = ad.within_row(cells, scores, draws=200)
    assert res["n_rows"] == 2 and res["n_rows_defined"] == 2 and res["seed"] == 20261030 and res["draws"] == 200
    assert res["mean_rho"] == pytest.approx(67 / 190, abs=1e-14)
    assert res["p_one_sided"] == 30 / 201


def test_within_row_ignores_rows_with_constant_scores():
    cells, scores = _tiny()
    for p in [p for p in cells if p.startswith("row1")]:
        scores[p] = 3
    res = ad.within_row(cells, scores, draws=100)
    assert res["n_rows_defined"] == 1 and res["mean_rho"] == pytest.approx(0.6, abs=1e-14)


# ------------------------------------------------------------------ figure, environment, processes, locale
def test_environment_is_recorded(tmp_path):
    import matplotlib
    import PIL
    want = {"python": platform.python_version(), "numpy": np.__version__,
            "matplotlib": matplotlib.__version__, "pillow": PIL.__version__}
    assert ad.environment() == want
    res = ad.run(fixture(tmp_path), draws=50)
    assert res["environment"] == want
    on_disk = json.loads((tmp_path / "analysis" / "out" / "a9_adherence.json").read_text(encoding="utf-8"))
    assert on_disk["environment"] == want


def _child(root, out, env_extra=None, draws=300):
    code = ("import sys; sys.path.insert(0, %r); import a9_adherence as a; a.run(sys.argv[1], sys.argv[2], draws=%d); "
            "print('pyplot', 'matplotlib.pyplot' in sys.modules)" % (str(Path(__file__).resolve().parent), draws))
    env = dict(os.environ)
    env.update(env_extra or {})
    r = subprocess.run([sys.executable, "-c", code, str(root), str(out)], env=env, capture_output=True, text=True,
                       encoding="utf-8", cwd=str(root))
    assert r.returncode == 0, r.stderr
    assert "pyplot False" in r.stdout
    return {n: (Path(out) / n).read_bytes() for n in ("a9_adherence.json", "a9_adherence.md",
                                                     "figures/a9_adherence.png")}


def test_outputs_are_identical_across_processes_hash_seeds_and_a_hostile_matplotlibrc(tmp_path):
    root = fixture(tmp_path / "fx", r7=REVERSED)
    hostile = tmp_path / "mplconfig"
    hostile.mkdir()
    (hostile / "matplotlibrc").write_text("font.size: 30\nfont.family: serif\naxes.grid: True\nsavefig.dpi: 72\n"
                                          "figure.facecolor: red\nlines.linewidth: 9\n", encoding="utf-8", newline="\n")
    a = _child(root, tmp_path / "o1", {"PYTHONHASHSEED": "1"})
    b = _child(root, tmp_path / "o2", {"PYTHONHASHSEED": "2", "MPLCONFIGDIR": str(hostile)})
    for name in a:
        assert a[name] == b[name], name
    png = a["figures/a9_adherence.png"]
    assert png.startswith(b"\x89PNG") and b"tEXt" not in png and b"iTXt" not in png and b"atplotlib" not in png


def test_outputs_do_not_depend_on_the_locale(tmp_path):
    root = fixture(tmp_path / "fx", r7=SUPPORTED)
    plain = _child(root, tmp_path / "o1", {"PYTHONHASHSEED": "3"})
    env = {"LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "PYTHONHASHSEED": "4"}
    enc = subprocess.run([sys.executable, "-c", "import locale; print(locale.getpreferredencoding(False))"],
                         env=dict(os.environ, **env), capture_output=True, text=True).stdout.strip().lower()
    assert "utf" not in enc                                         # the child really runs with a non-UTF-8 locale
    c = _child(root, tmp_path / "o2", env)
    for name in plain:
        assert plain[name] == c[name], name
    assert b"\r\n" not in c["a9_adherence.md"]


def test_slim_writes_utf8_under_a_non_utf8_locale(tmp_path):
    root = fixture(tmp_path / "fx", aaron=None)
    adh = root / "analysis" / "adherence"
    (adh / "raw" / "burst-AARON").mkdir(parents=True)
    (adh / ".data" / "AARON").mkdir(parents=True)
    _export(adh / "raw" / "burst-AARON" / "ratings-V0001.json", "burst", flags=("fast", "caf\u00e9"))
    _store(adh / ".data" / "AARON" / "a9-burst.jsonl", "burst", flags=("fast", "caf\u00e9"), code=_hash_code("burst"))
    _fake_prepare(adh)
    code = ("import sys; sys.path.insert(0, %r); import a9_adherence as a; a.ROOT = __import__('pathlib').Path(sys.argv[1]); "
            "sys.exit(a.main(['slim', '--rater', 'AARON', '--study', 'burst']))" % str(Path(__file__).resolve().parent))
    env = dict(os.environ, LC_ALL="C", LANG="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0")
    r = subprocess.run([sys.executable, "-c", code, str(root)], env=env, capture_output=True, text=True,
                       encoding="utf-8", cwd=str(root))
    assert r.returncode == 0, r.stderr
    raw = (adh / "ratings-burst-AARON.json").read_bytes()
    assert json.loads(raw.decode("utf-8"))["flags"] == ["fast", "caf\u00e9"] and raw.endswith(b"\n") and b"\r" not in raw


def test_the_markdown_ends_with_exactly_one_newline(tmp_path):
    ad.run(fixture(tmp_path, r7=SUPPORTED), draws=50)
    md = (tmp_path / "analysis" / "out" / "a9_adherence.md").read_bytes()
    assert md.endswith(b"\n") and not md.endswith(b"\n\n")
    js = (tmp_path / "analysis" / "out" / "a9_adherence.json").read_bytes()
    assert js.endswith(b"\n") and not js.endswith(b"\n\n")


def test_every_text_read_and_write_names_its_encoding():
    for f in (Path(ad.__file__), Path(__file__)):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                kws = {k.arg for k in node.keywords}
                if node.func.attr == "read_text":
                    assert "encoding" in kws, (f.name, node.lineno)
                if node.func.attr == "write_text":
                    assert {"encoding", "newline"} <= kws, (f.name, node.lineno)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
                assert "encoding" in {k.arg for k in node.keywords} or len(node.args) > 1, (f.name, node.lineno)


def test_the_figure_code_is_pyplot_free_and_rc_isolated():
    src = Path(ad.__file__).read_text(encoding="utf-8")
    assert "matplotlib.pyplot" not in src and "plt." not in src and "FigureCanvasAgg" in src and "rc_context" in src and "compress_level" in src


def test_no_temporary_files_are_left_behind(tmp_path):
    ad.run(fixture(tmp_path), draws=50)
    assert not [p for p in tmp_path.rglob("*") if p.name.endswith(".tmp")]


def test_byte_identity_at_the_registered_10000_draws(tmp_path):
    root = fixture(tmp_path / "fx", r7=REVERSED)
    a = _child(root, tmp_path / "o1", {"PYTHONHASHSEED": "5"}, draws=ad.N_WITHIN)
    b = _child(root, tmp_path / "o2", {"PYTHONHASHSEED": "6"}, draws=ad.N_WITHIN)
    for name in a:
        assert a[name] == b[name], name


# ------------------------------------------------------------------ _load_json and the loaders
def test_load_json_names_the_file_and_the_field(tmp_path):
    f = tmp_path / "x.json"
    with pytest.raises(SystemExit, match=r"thing: x\.json not found"):
        ad._load_json(f, "thing")
    f.write_text("{not json", encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match=r"thing: x\.json is not valid JSON"):
        ad._load_json(f, "thing")
    f.write_text("[1]", encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match=r"x\.json must be a JSON object"):
        ad._load_json(f, "thing")
    f.write_text(json.dumps({"a": "s", "b": True}), encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match=r"x\.json.*field 'c' missing"):
        ad._load_json(f, "thing", {"a": str, "c": int})
    with pytest.raises(SystemExit, match=r"x\.json.*field 'b' missing or not"):
        ad._load_json(f, "thing", {"b": int})                     # a bool is not an int
    assert ad._load_json(f, "thing", {"a": str})["a"] == "s"


def test_loaders_report_bad_files_by_name(tmp_path):
    root = fixture(tmp_path)
    adh = root / "analysis" / "adherence"
    (adh / "a9-config.json").write_text("{", encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match=r"a9-config\.json is not valid JSON"):
        ad.run(root, draws=50)
    root = fixture(tmp_path / "c")
    (root / "analysis" / "adherence" / "burst" / "study.lock.json").write_text(json.dumps({"instrument": "A9"}),
                                                                                encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match=r"study\.lock\.json.*field 'text_sha256'"):
        ad.run(root, draws=50)
    root = fixture(tmp_path / "d")
    (root / "analysis" / "out" / "results_table.json").unlink()
    with pytest.raises(SystemExit, match=r"results_table\.json not found"):
        ad.run(root, draws=50)
    root = fixture(tmp_path / "e")
    rows = json.loads((root / "analysis" / "out" / "results_table.json").read_text(encoding="utf-8"))
    del rows[0]["line_chamfer_mean_px"]
    (root / "analysis" / "out" / "results_table.json").write_text(json.dumps(rows), encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match=r"results_table\.json row 0.*line_chamfer_mean_px"):
        ad.run(root, draws=50)
    root = fixture(tmp_path / "f")
    f = next((root / "runs" / "metrics-motion").glob("*.json"))
    f.write_text(json.dumps({"motion": {}}), encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match=r"\.json.*headline_median_norm"):
        ad.run(root, draws=50)
    root = fixture(tmp_path / "g")
    _edit_ratings(root, "AARON", "burst", lambda d: d.pop("received_day"))
    with pytest.raises(SystemExit, match=r"ratings-burst-AARON\.json.*field 'received_day'"):
        ad.run(root, draws=50)


def _edit_results(root, fn):
    f = root / "analysis" / "out" / "results_table.json"
    rows = json.loads(f.read_text(encoding="utf-8"))
    fn(rows)
    f.write_text(json.dumps(rows), encoding="utf-8", newline="\n")


def test_load_cells_refuses_public_id_collisions(tmp_path):
    root = fixture(tmp_path)
    def dup(rows):
        r = dict(next(x for x in rows if x["cell_id"] == "xyz-act-tank-1_burst_wan22"))
        r["cell_id"] = "cip-act-tank-1_burst_wan22"            # the same cell under its public id
        rows.append(r)
    _edit_results(root, dup)
    with pytest.raises(SystemExit, match="cip-act-tank-1_burst_wan22.*twice"):
        ad.load_cells(root)


def test_load_cells_checks_the_design(tmp_path):
    root = fixture(tmp_path / "a")
    _edit_results(root, lambda rows: rows.remove(next(r for r in rows if r["cell_id"] == "act-b-3_burst_h3")))
    with pytest.raises(SystemExit, match="55 burst"):
        ad.load_cells(root)
    root = fixture(tmp_path / "b")
    def swap(rows):                                            # 55 stay 55, but one engine has 12 and another 10
        next(r for r in rows if r["cell_id"] == "act-b-3_burst_h3")["engine"] = "wan22"
    _edit_results(root, swap)
    with pytest.raises(SystemExit, match="11 per engine"):
        ad.load_cells(root)
    root = fixture(tmp_path / "c")
    def row_clash(rows):                                       # engines still 11 each, but two rows are lopsided
        next(r for r in rows if r["cell_id"] == "act-b-3_burst_h3")["engine"] = "wan22"
        next(r for r in rows if r["cell_id"] == "act-b-4_burst_wan22")["engine"] = "h3-fal"
    _edit_results(root, row_clash)
    with pytest.raises(SystemExit, match=r"\(panel, study\)"):
        ad.load_cells(root)
    root = fixture(tmp_path / "d")
    _edit_results(root, lambda rows: next(r for r in rows if r["cell_id"] == "act-b-3_burst_h3").update(engine="nope"))
    with pytest.raises(SystemExit, match="engine"):
        ad.load_cells(root)


def test_load_motion_refuses_public_id_collisions(tmp_path):
    root = fixture(tmp_path)
    cells = ad.load_cells(root)
    mot = root / "runs" / "metrics-motion"
    (mot / "cip-act-tank-1_burst_wan22.json").write_text(
        (mot / "xyz-act-tank-1_burst_wan22.json").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match="two motion files"):
        ad.load_motion(root, cells)


# ------------------------------------------------------------------ dates
def test_day_validation():
    assert ad._day("2026-11-01") and ad._day("2024-02-29")
    for bad in ("2026-13-01", "2026-02-30", "2026-1-1", "20261101", "\uff12\uff10\uff12\uff16-11-01", " 2026-11-01",
                "2026-11-01\n", None, 20261101):
        assert not ad._day(bad), bad


def test_r7_deadline_is_registered_on_plus_14_days(tmp_path):
    with pytest.raises(SystemExit, match=r"r7_deadline.*14 days"):
        ad.run(fixture(tmp_path / "a", r7=SUPPORTED, deadline="2026-11-16"), draws=50)
    with pytest.raises(SystemExit, match="r7_deadline"):
        ad.run(fixture(tmp_path / "b", deadline="2026-02-30"), draws=50)
    root = fixture(tmp_path / "c")
    cfg = root / "analysis" / "adherence" / "a9-config.json"
    d = json.loads(cfg.read_text(encoding="utf-8"))
    d["registered_on"] = None
    cfg.write_text(json.dumps(d), encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match="registered_on"):
        ad.run(root, draws=50)
    root = fixture(tmp_path / "d", r7=SUPPORTED, r7_on="2027-01-08", registered="2026-12-25",
                   deadline="2027-01-08", aaron_on="2026-12-26")                        # across a year end
    assert ad.run(root, draws=50)["label"] == "two raters"


# ------------------------------------------------------------------ half-present files, status echo, inputs
def test_half_of_aarons_files_is_an_error(tmp_path):
    root = fixture(tmp_path)
    (root / "analysis" / "adherence" / "ratings-push-AARON.json").unlink()
    with pytest.raises(SystemExit, match=r"AARON.*partial.*push"):
        ad.run(root, draws=50)


def test_half_of_r7s_files_keeps_the_pending_state_with_a_note(tmp_path):
    root = fixture(tmp_path, r7=SUPPORTED)
    (root / "analysis" / "adherence" / "ratings-push-R7.json").unlink()
    res = ad.run(root, draws=50)
    assert res["label"] == "author-rated; second rater pending" and res["verdict"] == "no verdict (second rater pending)"
    assert res["raters"]["R7"] is None and res["r7_partial_note"] == "R7 partial: push missing"
    assert "R7 partial: push missing" in res["basis"]
    md = (root / "analysis" / "out" / "a9_adherence.md").read_text(encoding="utf-8")
    assert "R7 partial: push missing" in md
    assert "analysis/adherence/ratings-push-R7.json" not in res["inputs"]["files"]
    assert "analysis/adherence/ratings-burst-R7.json" in res["inputs"]["files"]


def test_half_of_r7s_files_after_the_deadline_falls_back(tmp_path):
    root = fixture(tmp_path, r7=SUPPORTED, deadline_passed=True)
    (root / "analysis" / "adherence" / "ratings-burst-R7.json").unlink()
    res = ad.run(root, draws=50)
    assert res["label"] == "author-rated" and "R7 partial: burst missing" in res["basis"]


def test_one_late_r7_file_alone_is_the_fallback_even_without_a_status_file(tmp_path):
    root = fixture(tmp_path, r7=SUPPORTED, r7_on="2026-11-20")            # deadline 2026-11-15
    (root / "analysis" / "adherence" / "ratings-push-R7.json").unlink()
    assert not (root / "analysis" / "adherence" / "r7-status.json").exists()
    res = ad.run(root, draws=50)
    assert res["label"] == "author-rated" and res["verdict"] == "not tested by two raters"
    assert res["verdict_status"] == "no verdict (author-rated fallback)"
    assert "burst export was received after the deadline (2026-11-15)" in res["basis"]
    assert "R7 partial: push missing" in res["basis"] and res["raters"]["R7"] is None
    assert res["raters"]["AARON"]["provisional"] is None
    md = (root / "analysis" / "out" / "a9_adherence.md").read_text(encoding="utf-8")
    assert "**Verdict: not tested by two raters.**" in md and "provisional" not in md
    assert "Verdict: supported" not in md


def test_one_late_r7_file_alone_is_the_fallback_for_either_study(tmp_path):
    root = fixture(tmp_path, r7=SUPPORTED, r7_on="2026-11-16")
    (root / "analysis" / "adherence" / "ratings-burst-R7.json").unlink()
    res = ad.run(root, draws=50)
    assert res["label"] == "author-rated" and "push export was received after the deadline" in res["basis"]


def test_one_in_time_r7_file_alone_stays_pending_until_the_deadline_passes(tmp_path):
    for day in ("2026-11-03", "2026-11-15"):                               # the deadline day itself is in time
        root = fixture(tmp_path / day, r7=SUPPORTED, r7_on=day)
        (root / "analysis" / "adherence" / "ratings-push-R7.json").unlink()
        res = ad.run(root, draws=50)
        assert res["label"] == "author-rated; second rater pending"
        assert res["verdict"] == "no verdict (second rater pending)"


def test_one_r7_file_alone_needs_a_valid_day_and_a_deadline(tmp_path):
    root = fixture(tmp_path / "a", r7=SUPPORTED)
    (root / "analysis" / "adherence" / "ratings-push-R7.json").unlink()
    _edit_ratings(root, "R7", "burst", lambda d: d.__setitem__("received_day", "soon"))
    with pytest.raises(SystemExit, match="received_day"):
        ad.run(root, draws=50)
    root = fixture(tmp_path / "b", r7=SUPPORTED, deadline=None)
    (root / "analysis" / "adherence" / "ratings-push-R7.json").unlink()
    with pytest.raises(SystemExit, match="r7_deadline"):
        ad.run(root, draws=50)


def test_either_late_r7_file_of_two_is_the_fallback(tmp_path):
    root = fixture(tmp_path, r7=SUPPORTED, r7_on="2026-11-03")
    _edit_ratings(root, "R7", "push", lambda d: d.update(received_day="2026-11-16", within_deadline=False))
    res = ad.run(root, draws=50)
    assert res["label"] == "author-rated" and "push export was received after the deadline" in res["basis"]
    assert res["verdict"] == "not tested by two raters" and res["raters"]["R7"] is not None   # still analysed


def test_both_r7_files_in_time_beat_a_status_file(tmp_path):
    root = fixture(tmp_path, r7=SUPPORTED, deadline_passed=True)             # r7-status.json says deadline_passed
    assert (root / "analysis" / "adherence" / "r7-status.json").exists()
    res = ad.run(root, draws=50)
    assert res["label"] == "two raters" and res["verdict"] == "supported"
    assert res["r7_status_file"]["deadline_passed"] is True                 # echoed, but not what decides


def test_r7_status_is_echoed_when_present(tmp_path):
    res = ad.run(fixture(tmp_path / "a", deadline_passed=True), draws=50)
    assert res["r7_status_file"] == {"deadline_passed": True, "recorded_on": "2026-11-16"}
    assert ad.run(fixture(tmp_path / "b"), draws=50)["r7_status_file"] is None
    root = fixture(tmp_path / "c", deadline_passed=True)
    (root / "analysis" / "adherence" / "r7-status.json").write_text(json.dumps({"deadline_passed": "yes"}),
                                                                    encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match=r"r7-status\.json.*deadline_passed"):
        ad.run(root, draws=50)


def test_inputs_record_the_sha256_of_every_input_file(tmp_path):
    root = fixture(tmp_path, r7=SUPPORTED, deadline_passed=True)
    res = ad.run(root, draws=50)
    files = res["inputs"]["files"]
    want = {"analysis/adherence/a9-config.json",
            "analysis/adherence/r7-status.json",
            "analysis/adherence/burst/study.lock.json", "analysis/adherence/push/study.lock.json",
            "analysis/adherence/ratings-burst-AARON.json", "analysis/adherence/ratings-push-AARON.json",
            "analysis/adherence/ratings-burst-R7.json", "analysis/adherence/ratings-push-R7.json"}
    assert set(files) == want and list(files) == sorted(files)
    for rel, h in files.items():
        assert h == hashlib.sha256((root / rel).read_bytes()).hexdigest(), rel
    ex = res["inputs"]["extracted"]
    assert list(ex) == ["results_table.line_chamfer_mean_px", "motion.headline_median_norm"]
    assert all(v["n"] == 110 and len(v["sha256"]) == 64 for v in ex.values())
    assert "tank" not in json.dumps(res["inputs"]).replace("cip-act-tank-1", "")       # public ids only
    # each extracted hash is the sha256 of canonical JSON of {public id: value}
    cells = ad.load_cells(root)
    drift = {p: c["drift"] for p, c in cells.items()}
    canon = json.dumps(drift, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    assert ex["results_table.line_chamfer_mean_px"]["sha256"] == hashlib.sha256(canon).hexdigest()
    # a changed motion value moves its hash; a changed drift value moves the other
    before = json.loads(json.dumps(ex))
    f = next((root / "runs" / "metrics-motion").glob("act-b-1_burst_h3.json"))
    f.write_text(json.dumps({"motion": {"headline_median_norm": 0.5}}), encoding="utf-8", newline="\n")
    after = ad.run(root, draws=50)["inputs"]["extracted"]
    assert after["motion.headline_median_norm"] != before["motion.headline_median_norm"]
    assert after["results_table.line_chamfer_mean_px"] == before["results_table.line_chamfer_mean_px"]
    _edit_results(root, lambda rows: next(r for r in rows if r["cell_id"] == "act-b-1_burst_h3").update(
        line_chamfer_mean_px=9.25))
    assert ad.run(root, draws=50)["inputs"]["extracted"]["results_table.line_chamfer_mean_px"] != \
        before["results_table.line_chamfer_mean_px"]


def test_inputs_do_not_depend_on_the_private_prefix_or_row_order(tmp_path):
    """The release renames the private panel prefix in the results table and the motion file names and
    re-sorts the rows; the recorded input hashes must not move."""
    a = ad.run(fixture(tmp_path / "a"), draws=50)["inputs"]
    root = fixture(tmp_path / "b")
    f = root / "analysis" / "out" / "results_table.json"
    rows = json.loads(f.read_text(encoding="utf-8"))
    for r in rows:
        r["cell_id"] = r["cell_id"].replace("xyz-act-tank-1", "cip-act-tank-1")
        r["panel_id"] = r["panel_id"].replace("xyz-act-tank-1", "cip-act-tank-1")
    rows.sort(key=lambda r: r["cell_id"], reverse=True)
    f.write_text(json.dumps(rows), encoding="utf-8", newline="\n")
    for m in (root / "runs" / "metrics-motion").glob("xyz-act-tank-1_*.json"):
        m.rename(m.with_name(m.name.replace("xyz-act-tank-1", "cip-act-tank-1")))
    assert ad.run(root, draws=50)["inputs"] == a


def test_slim_refuses_shuffled_clip_names_with_an_identical_score_sequence(tmp_path):
    with pytest.raises(SystemExit, match="clip order"):
        _slim(tmp_path, export_kw={"shuffle": True})


def test_slim_needs_the_code_map_to_read_opaque_stored_orders(tmp_path):
    with pytest.raises(SystemExit, match="clip order"):
        _slim(tmp_path, code_map={})


def test_slim_accepts_a_stored_order_that_already_holds_public_ids(tmp_path):
    root = fixture(tmp_path / "repo")
    cells, config, lock = _ctx(root)
    rec = ad.slim(_export(tmp_path / "e.json", "burst"),
                  _store(tmp_path / "s.jsonl", "burst", code=lambda k, p: p), "AARON", "burst", cells, config, lock)
    assert rec["n"] == 55


def test_slim_checks_the_stored_rater_when_one_is_recorded(tmp_path):
    rec, _ = _slim(tmp_path / "a", rater="R7", store_kw={"rater": "R7", "day": "2026-11-05"})
    assert rec["rater"] == "R7"
    with pytest.raises(SystemExit, match="rater"):
        _slim(tmp_path / "b", rater="R7", store_kw={"rater": "AARON"})


def test_slim_validates_rater_and_study_before_reading_any_file(tmp_path):
    root = fixture(tmp_path / "repo")
    cells, config, lock = _ctx(root)
    with pytest.raises(SystemExit, match="rater must be one of"):
        ad.slim(tmp_path / "nope.json", tmp_path / "nope.jsonl", "R3", "burst", cells, config, lock)
    with pytest.raises(SystemExit, match="rater must be one of"):
        ad.slim(tmp_path / "nope.json", tmp_path / "nope.jsonl", "AARON", "pull", cells, config, lock)
    with pytest.raises(SystemExit, match="not found"):
        ad.slim(tmp_path / "nope.json", tmp_path / "nope.jsonl", "AARON", "burst", cells, config, lock)


def test_slim_reports_a_malformed_export_by_name(tmp_path):
    root = fixture(tmp_path / "repo")
    cells, config, lock = _ctx(root)
    e = tmp_path / "e.json"
    e.write_text(json.dumps({"instrument": "A9", "ratings": [{"score": 1}]}), encoding="utf-8", newline="\n")
    s = _store(tmp_path / "s.jsonl", "burst")
    with pytest.raises(SystemExit, match=r"e\.json.*field 'clip'"):
        ad.slim(e, s, "AARON", "burst", cells, config, lock, code_map=_codes("burst"))


def _fake_prepare(adh):
    """A stand-in for prepare.py: the seeded opaque codes the blindpanel build uses."""
    (adh / "prepare.py").write_text(
        "import hashlib\n"
        "STUDIES = {'burst': {'seed': 'seed-burst'}, 'push': {'seed': 'seed-push'}}\n"
        "def opaque_code(seed, kind, ident):\n"
        "    return 'c' + hashlib.sha256(f'{seed}:{kind}:{ident}'.encode()).hexdigest()[:5]\n", encoding="utf-8", newline="\n")


def _hash_code(study):
    return lambda k, p: "c" + hashlib.sha256(f"seed-{study}:clip:{p}".encode()).hexdigest()[:5]


def test_cli_slim_maps_codes_through_prepare_and_keeps_the_old_file_on_force(tmp_path, monkeypatch):
    root = fixture(tmp_path / "repo", aaron=None)
    adh = root / "analysis" / "adherence"
    (adh / "raw" / "burst-AARON").mkdir(parents=True)
    (adh / ".data" / "AARON").mkdir(parents=True)
    _fake_prepare(adh)
    _export(adh / "raw" / "burst-AARON" / "ratings-V0001.json", "burst")
    _store(adh / ".data" / "AARON" / "a9-burst.jsonl", "burst", code=_hash_code("burst"))
    monkeypatch.setattr(ad, "ROOT", root)
    assert ad.main(["slim", "--rater", "AARON", "--study", "burst", "--exported-on", "2026-11-02"]) == 0
    out = adh / "ratings-burst-AARON.json"
    first = out.read_bytes()
    assert json.loads(first.decode("utf-8"))["n"] == 55
    with pytest.raises(SystemExit, match="exists"):
        ad.main(["slim", "--rater", "AARON", "--study", "burst"])
    assert out.read_bytes() == first
    # --force keeps the old file as .prev; a second --force refuses rather than discard it
    assert ad.main(["slim", "--rater", "AARON", "--study", "burst", "--force"]) == 0
    assert (adh / "ratings-burst-AARON.json.prev").read_bytes() == first
    with pytest.raises(SystemExit, match="prev"):
        ad.main(["slim", "--rater", "AARON", "--study", "burst", "--force"])
    assert (adh / "ratings-burst-AARON.json.prev").read_bytes() == first


def test_cli_slim_without_prepare_py_says_so(tmp_path, monkeypatch):
    root = fixture(tmp_path / "repo", aaron=None)
    adh = root / "analysis" / "adherence"
    (adh / "raw" / "burst-AARON").mkdir(parents=True)
    (adh / ".data" / "AARON").mkdir(parents=True)
    _export(adh / "raw" / "burst-AARON" / "ratings-V0001.json", "burst")
    _store(adh / ".data" / "AARON" / "a9-burst.jsonl", "burst")
    monkeypatch.setattr(ad, "ROOT", root)
    with pytest.raises(SystemExit, match="prepare.py"):
        ad.main(["slim", "--rater", "AARON", "--study", "burst"])


# ------------------------------------------------------------------ follow-up minors
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_non_finite_numbers_are_refused_on_input(tmp_path, literal):
    f = tmp_path / "x.json"
    f.write_text('{"a": %s}' % literal, encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match=r"x\.json.*(not valid JSON|field 'a')"):
        ad._load_json(f, "thing", {"a": float})
    assert not ad._is(float("nan"), float) and not ad._is(float("inf"), float) and ad._is(1.5, float)


def test_non_finite_values_in_the_released_tables_are_refused(tmp_path):
    root = fixture(tmp_path / "a")
    f = root / "analysis" / "out" / "results_table.json"
    f.write_text(f.read_text(encoding="utf-8").replace('"line_chamfer_mean_px": 0.8}', '"line_chamfer_mean_px": NaN}', 1),
                 encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match=r"results_table\.json"):
        ad.run(root, draws=20)
    root = fixture(tmp_path / "b")
    m = next((root / "runs" / "metrics-motion").glob("act-b-1_burst_h3.json"))
    m.write_text('{"motion": {"headline_median_norm": Infinity}}', encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match=r"\.json"):
        ad.run(root, draws=20)


def _slim_cli_root(tmp_path, monkeypatch):
    root = fixture(tmp_path / "repo", aaron=None)
    adh = root / "analysis" / "adherence"
    (adh / "raw" / "burst-AARON").mkdir(parents=True)
    (adh / ".data" / "AARON").mkdir(parents=True)
    _fake_prepare(adh)
    _export(adh / "raw" / "burst-AARON" / "ratings-V0001.json", "burst")
    _store(adh / ".data" / "AARON" / "a9-burst.jsonl", "burst", code=_hash_code("burst"))
    monkeypatch.setattr(ad, "ROOT", root)
    return adh


def test_force_never_leaves_only_the_prev_file(tmp_path, monkeypatch):
    adh = _slim_cli_root(tmp_path, monkeypatch)
    argv = ["slim", "--rater", "AARON", "--study", "burst"]
    assert ad.main(argv) == 0
    out = adh / "ratings-burst-AARON.json"
    first = out.read_bytes()
    # (a) the new file cannot be written: the old one stays, no .prev appears
    real_write = Path.write_text

    def boom(self, *a, **k):
        if self.name.endswith(".new"):
            raise OSError("disk full")
        return real_write(self, *a, **k)
    monkeypatch.setattr(Path, "write_text", boom)
    with pytest.raises(OSError, match="disk full"):
        ad.main(argv + ["--force"])
    monkeypatch.setattr(Path, "write_text", real_write)
    assert out.read_bytes() == first and not (adh / "ratings-burst-AARON.json.prev").exists()
    # (b) the final rename fails: the old file is put back
    real_replace = os.replace

    def flaky(src, dst):
        if Path(src).name.endswith(".new"):
            raise OSError("rename failed")
        return real_replace(src, dst)
    monkeypatch.setattr(ad.os, "replace", flaky)
    with pytest.raises(OSError, match="rename failed"):
        ad.main(argv + ["--force"])
    monkeypatch.setattr(ad.os, "replace", real_replace)
    assert out.read_bytes() == first and not (adh / "ratings-burst-AARON.json.prev").exists()
    assert not [p for p in adh.iterdir() if p.name.endswith((".new", ".tmp"))]
    # (c) success: old kept as .prev
    assert ad.main(argv + ["--force"]) == 0
    assert (adh / "ratings-burst-AARON.json.prev").read_bytes() == first and out.exists()
    # the replaced file's hash is published; the first write (no replacement) recorded nothing
    lines = (adh / "sessions.sha256").read_text(encoding="utf-8").splitlines()
    assert lines == [f"{hashlib.sha256(first).hexdigest()}  replaced analysis/adherence/ratings-burst-AARON.json "
                     f"({ad._utc_day()} UTC)"]
    assert "/" not in lines[0].split("  ", 1)[1].replace("analysis/adherence/", "") and private_term_hits(lines[0]) == []
    assert (adh / "sessions.sha256").read_bytes().endswith(b"\n") and b"\r" not in (adh / "sessions.sha256").read_bytes()


def test_r7_status_deadline_passed_needs_a_later_recorded_day(tmp_path):
    def with_status(sub, status, **kw):
        root = fixture(tmp_path / sub, **kw)
        (root / "analysis" / "adherence" / "r7-status.json").write_text(json.dumps(status), encoding="utf-8", newline="\n")
        return root
    res = ad.run(with_status("ok", {"deadline_passed": True, "recorded_on": "2026-11-16"}), draws=20)
    assert res["label"] == "author-rated"
    for sub, day in (("same", "2026-11-15"), ("before", "2026-11-10")):
        with pytest.raises(SystemExit, match=r"recorded_on.*after r7_deadline"):
            ad.run(with_status(sub, {"deadline_passed": True, "recorded_on": day}), draws=20)
    with pytest.raises(SystemExit, match=r"deadline_passed.*r7_deadline"):
        ad.run(with_status("nodl", {"deadline_passed": True, "recorded_on": "2026-11-16"}, deadline=None), draws=20)
    # a status that says the deadline has not passed carries no date constraint
    ad.run(with_status("false", {"deadline_passed": False, "recorded_on": "2026-11-01"}), draws=20)


# ------------------------------------------------------------------ review fixes: rng consumption, declaration
def test_only_rows_with_a_defined_rho_draw_from_the_stream():
    cells, scores = _tiny()
    base = ad.within_row(cells, scores, draws=200)
    # a constant-score row, sorted before, between and after the two real rows, consumes nothing
    for name in ("a_flat", "row0z", "z_flat"):
        c2, s2 = dict(cells), dict(scores)
        for e in ad.LEAGUE_ORDER:
            pid = f"{name}_burst_{SUFFIX[e]}"
            c2[pid] = {"engine": e, "panel": name, "study": "burst", "drift": 1.0 + ad.LEAGUE_ORDER.index(e)}
            s2[pid] = 3
        res = ad.within_row(c2, s2, draws=200)
        assert (res["n_rows"], res["n_rows_defined"]) == (3, 2), name
        assert res["mean_rho"] == base["mean_rho"] and res["p_one_sided"] == base["p_one_sided"], name
    # the stream itself: one rng.permutation(5) per defined row, in sorted row order, per draw
    rng = np.random.default_rng(ad.SEED)
    obs = base["mean_rho"]
    k = 0
    for _ in range(200):
        rhos = []
        for r in range(2):
            idx = rng.permutation(5)
            rhos.append(ad.spearman(TINY_DRIFT[r], np.array(TINY_SCORE[r])[idx].tolist()))
        k += math.fsum(rhos) / 2 >= obs - 1e-12
    assert base["p_one_sided"] == (k + 1) / 201
    doc = " ".join(ad.within_row.__doc__.split())
    assert "(defined or not)" not in doc and "only rows with a defined rho draw" in doc.lower()


def test_the_r7_declaration_attests_only_as_of_registration(tmp_path):
    for blind, text in ((True, "R7 is declared blind to engine styles: R7, a new rater who has never rated for "
                               "StillDrawn, had not seen its explorer, release, clips or results as of 3 Nov 2026 "
                               "(Gate A, revised)."),
                        (False, "R7 is declared NOT blind to engine styles: R7, a new rater who has never rated for "
                                "StillDrawn, had seen its explorer, release, clips or results as of 3 Nov 2026 "
                                "(Gate A, revised).")):
        assert ad.DECLARATION[blind] == text
        res = ad.run(fixture(tmp_path / str(blind), blind=blind), draws=20)
        assert res["r7_declaration"] == text
        assert text in (tmp_path / str(blind) / "analysis" / "out" / "a9_adherence.md").read_text(encoding="utf-8")
    assert "before rating" not in " ".join(ad.DECLARATION.values())
    assert "registration" not in " ".join(ad.DECLARATION.values())


# ------------------------------------------------------------------ the committed config's wording
def test_committed_config_note_matches_the_declaration_and_the_fallback():
    cfg = json.loads((Path(__file__).resolve().parent / "adherence" / "a9-config.json").read_text(encoding="utf-8"))
    assert cfg["registered_on"] == "2026-11-03" and cfg["r7_deadline"] == "2026-11-17"    # filled at registration (+ 14 days)
    note = cfg["note"]
    assert ("r7_blind_to_engine_styles is Aaron's declaration that R7, a new rater who has never rated for "
            "StillDrawn, had not seen its explorer, release, clips or results as of 3 Nov 2026 (Gate A, "
            "revised); a later exposure is recorded in the written record, not here.") in note
    assert "R2" not in note and "A6" not in note and "r7_deadline (registration day + 14 days" in note
    assert "before rating" not in note
    assert "Test 1 then has no verdict and its numbers stay author-rated" in note


# ----------------------------------------------------------------- set-aside
def _row_line(study, session, day="2026-11-02", complete=True, rater=None):
    """One stored row as blindpanel's file store writes it (compact JSON, LF)."""
    q = QUESTION[study]
    seen = _seen(study) if complete else _seen(study)[:10]
    code = {p: _code(k, p) for k, p in enumerate(seen)}
    row = {"study": f"a9-{study}", "instrument": "A9", "session": session,
           "order": {"baseline": [], "clips": [code[p] for p in seen]},
           "answers": {"baseline": {}, "clips": {code[p]: {q: 1 + k % 5} for k, p in enumerate(seen)}},
           "delivery": DELIVERY, "flags": [], "received_day": day}
    if rater:
        row["rater"] = rater
    return (json.dumps(row) + "\n").encode("utf-8")


def _aside_ctx(tmp_path, lines, study="burst", rater="R7", age_s=3600):
    """A repo's adherence folder and a store folder named for the rater (the default layout .data/<RATER>),
    whose store file was last written `age_s` seconds ago."""
    adh = tmp_path / "repo" / "analysis" / "adherence"
    store_dir = tmp_path / "store" / rater
    store_dir.mkdir(parents=True)
    adh.mkdir(parents=True)
    f = store_dir / f"a9-{study}.jsonl"
    f.write_bytes(b"".join(lines))
    t = time.time() - age_s
    os.utime(f, (t, t))
    return adh, store_dir


def _hash_lines(adh):
    return (adh / "sessions.sha256").read_text(encoding="utf-8").splitlines()


def test_set_aside_keeps_the_first_complete_session_and_moves_the_rest_byte_for_byte(tmp_path):
    a, b, c = _row_line("burst", "s1"), _row_line("burst", "s2", "2026-11-03"), _row_line("burst", "s3", "2026-11-04")
    adh, store = _aside_ctx(tmp_path, [a, b, c])
    assert ad.set_aside(store, "burst", "R7", adh, today="2026-11-05") == 2
    assert (store / "a9-burst.jsonl").read_bytes() == a                        # slim now sees one session
    extra = adh / "raw" / "burst-R7" / "extra-sessions.jsonl"
    assert extra.read_bytes() == b + c
    text = (adh / "sessions.sha256").read_text(encoding="utf-8")
    assert text.splitlines() == [f"{hashlib.sha256(b).hexdigest()}  extra session burst-R7 row 1 (2026-11-05 UTC)",
                                 f"{hashlib.sha256(c).hexdigest()}  extra session burst-R7 row 2 (2026-11-05 UTC)"]
    assert text.endswith("\n") and "/" not in text and private_term_hits(text) == [] and "\r" not in text
    assert not [p for p in tmp_path.rglob("*") if p.name.endswith((".new", ".tmp"))]


def test_set_aside_appends_to_earlier_extras_and_hashes_and_is_idempotent(tmp_path):
    a, b, c = _row_line("burst", "s1"), _row_line("burst", "s2"), _row_line("burst", "s3")
    adh, store = _aside_ctx(tmp_path, [a, b], rater="AARON")
    (adh / "sessions.sha256").write_text("0" * 64 + "  earlier line\n", encoding="utf-8", newline="\n")
    assert ad.set_aside(store, "burst", "AARON", adh, today="2026-11-05") == 1
    (store / "a9-burst.jsonl").write_bytes(a + c)                              # a later extra session arrives
    t = time.time() - 3600
    os.utime(store / "a9-burst.jsonl", (t, t))
    assert ad.set_aside(store, "burst", "AARON", adh, today="2026-11-06") == 1
    assert (adh / "raw" / "burst-AARON" / "extra-sessions.jsonl").read_bytes() == b + c
    assert _hash_lines(adh) == ["0" * 64 + "  earlier line",
                                f"{hashlib.sha256(b).hexdigest()}  extra session burst-AARON row 1 (2026-11-05 UTC)",
                                f"{hashlib.sha256(c).hexdigest()}  extra session burst-AARON row 2 (2026-11-06 UTC)"]
    with pytest.raises(SystemExit, match="Stop the blindpanel server"):        # the store was just rewritten
        ad.set_aside(store, "burst", "AARON", adh)
    os.utime(store / "a9-burst.jsonl", (time.time() - 3600,) * 2)
    assert ad.set_aside(store, "burst", "AARON", adh) == 0                      # nothing left to move
    assert len(_hash_lines(adh)) == 3


def test_set_aside_hashes_each_moved_row_as_stored_even_without_a_final_newline_or_with_crlf(tmp_path):
    a, b = _row_line("burst", "s1"), _row_line("burst", "s2")
    crlf = _row_line("burst", "s3").rstrip(b"\n") + b"\r\n"
    last = _row_line("burst", "s4").rstrip(b"\n")                               # no terminator at all
    adh, store = _aside_ctx(tmp_path, [a, b, crlf, last])
    assert ad.set_aside(store, "burst", "R7", adh, today="2026-11-05") == 3
    assert (store / "a9-burst.jsonl").read_bytes() == a
    extra = (adh / "raw" / "burst-R7" / "extra-sessions.jsonl").read_bytes()
    assert extra == b + crlf + last + b"\n"                                    # CRLF kept; separator only after the last
    assert [l.split("  ")[0] for l in _hash_lines(adh)] == [hashlib.sha256(x).hexdigest() for x in (b, crlf, last)]
    assert hashlib.sha256(last).hexdigest() != hashlib.sha256(last + b"\n").hexdigest()
    assert [l.split("  ")[1] for l in _hash_lines(adh)] == [f"extra session burst-R7 row {k} (2026-11-05 UTC)" for k in (1, 2, 3)]


def test_set_aside_treats_json_null_and_other_non_sessions_as_rows_not_blanks(tmp_path):
    a, nul, lst = _row_line("burst", "s1"), b"null\n", b"[1, 2]\n"
    adh, store = _aside_ctx(tmp_path, [nul, a, b"  \n", lst, b"\n"])
    assert ad.set_aside(store, "burst", "R7", adh, today="2026-11-05") == 2
    assert (store / "a9-burst.jsonl").read_bytes() == a + b"  \n" + b"\n"       # only the blank lines stay
    assert (adh / "raw" / "burst-R7" / "extra-sessions.jsonl").read_bytes() == nul + lst
    assert [l.split("  ")[0] for l in _hash_lines(adh)] == [hashlib.sha256(nul).hexdigest(), hashlib.sha256(lst).hexdigest()]


def test_set_aside_skips_an_incomplete_first_row_and_moves_it_too(tmp_path):
    part, full, extra = _row_line("burst", "p", complete=False), _row_line("burst", "f"), _row_line("burst", "x")
    adh, store = _aside_ctx(tmp_path, [part, full, extra])
    assert ad.set_aside(store, "burst", "R7", adh, today="2026-11-05") == 2
    assert (store / "a9-burst.jsonl").read_bytes() == full
    assert (adh / "raw" / "burst-R7" / "extra-sessions.jsonl").read_bytes() == part + extra


def test_set_aside_refuses_without_a_complete_session_and_changes_nothing(tmp_path):
    part = _row_line("burst", "p", complete=False)
    adh, store = _aside_ctx(tmp_path, [part, part])
    with pytest.raises(SystemExit, match="no complete session"):
        ad.set_aside(store, "burst", "R7", adh)
    assert (store / "a9-burst.jsonl").read_bytes() == part + part
    assert not (adh / "raw").exists() and not (adh / "sessions.sha256").exists()
    nowhere = tmp_path / "nowhere" / "R7"
    nowhere.mkdir(parents=True)
    with pytest.raises(SystemExit, match="not found"):
        ad.set_aside(nowhere, "push", "R7", adh)


def test_set_aside_refuses_another_raters_rows(tmp_path):
    adh, store = _aside_ctx(tmp_path, [_row_line("burst", "s1", rater="AARON"), _row_line("burst", "s2")])
    with pytest.raises(SystemExit, match="rater"):
        ad.set_aside(store, "burst", "R7", adh)
    assert not (adh / "raw").exists() and not (adh / "sessions.sha256").exists()


def test_set_aside_needs_the_store_folder_to_be_named_for_the_rater(tmp_path):
    rows = [_row_line("burst", "s1"), _row_line("burst", "s2")]
    adh, store = _aside_ctx(tmp_path, rows, rater="AARON")                     # AARON's store ...
    before = (store / "a9-burst.jsonl").read_bytes()
    with pytest.raises(SystemExit, match=r"named 'AARON', not 'R7'"):          # ... named as R7's run
        ad.set_aside(store, "burst", "R7", adh)
    assert (store / "a9-burst.jsonl").read_bytes() == before
    assert not (adh / "raw").exists() and not (adh / "sessions.sha256").exists()
    with pytest.raises(SystemExit, match="named"):
        ad.set_aside(tmp_path / "store", "burst", "R7", adh)                   # the parent folder is no rater either
    assert ad.set_aside(store, "burst", "AARON", adh) == 1                      # the right name works


def test_set_aside_refuses_a_row_for_another_study_and_does_not_move_it(tmp_path):
    adh, store = _aside_ctx(tmp_path, [_row_line("burst", "s1"), _row_line("push", "s2")], study="burst")
    before = (store / "a9-burst.jsonl").read_bytes()
    with pytest.raises(SystemExit, match=r"study 'a9-push', not a9-burst"):
        ad.set_aside(store, "burst", "R7", adh)
    assert (store / "a9-burst.jsonl").read_bytes() == before
    assert not (adh / "raw").exists() and not (adh / "sessions.sha256").exists()
    adh, store = _aside_ctx(tmp_path / "b", [_row_line("push", "s1")], study="burst")   # only other-study rows
    with pytest.raises(SystemExit, match="not a9-burst"):
        ad.set_aside(store, "burst", "R7", adh)
    row = json.loads(_row_line("burst", "s1"))
    del row["study"]                                                            # a dict without a study is refused too
    adh, store = _aside_ctx(tmp_path / "c", [(json.dumps(row) + "\n").encode()])
    with pytest.raises(SystemExit, match="study None"):
        ad.set_aside(store, "burst", "R7", adh)


@pytest.mark.parametrize("age_s", [0, 30, 119])
def test_set_aside_refuses_a_store_written_in_the_last_two_minutes(tmp_path, age_s):
    rows = [_row_line("burst", "s1"), _row_line("burst", "s2")]
    adh, store = _aside_ctx(tmp_path, rows, age_s=age_s)
    before = (store / "a9-burst.jsonl").read_bytes()
    with pytest.raises(SystemExit, match=r"Stop the blindpanel server"):
        ad.set_aside(store, "burst", "R7", adh)
    assert (store / "a9-burst.jsonl").read_bytes() == before
    assert not (adh / "raw").exists() and not (adh / "sessions.sha256").exists()


def test_set_aside_accepts_a_store_that_has_been_quiet_for_two_minutes(tmp_path):
    adh, store = _aside_ctx(tmp_path, [_row_line("burst", "s1"), _row_line("burst", "s2")], age_s=125)
    assert ad.set_aside(store, "burst", "R7", adh, today="2026-11-05") == 1


def test_set_aside_help_and_readme_say_to_stop_the_server_first():
    r = subprocess.run([sys.executable, str(ANALYSIS / "a9_adherence.py"), "set-aside", "--help"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0 and "STOP THE BLINDPANEL SERVER FIRST" in " ".join(r.stdout.split())
    readme = (ANALYSIS / "adherence" / "README.md").read_text(encoding="utf-8")
    assert "Stop the blindpanel server first" in readme


def test_set_aside_then_slim_sees_one_session(tmp_path):
    root = fixture(tmp_path / "repo", aaron=None)
    cells, config, lock = _ctx(root)
    adh, store = root / "analysis" / "adherence", tmp_path / "store" / "AARON"
    store.mkdir(parents=True)
    keep = _store(tmp_path / "keep.jsonl", "burst").read_bytes()
    (store / "a9-burst.jsonl").write_bytes(keep + keep.replace(b'"session": "s"', b'"session": "t"'))
    os.utime(store / "a9-burst.jsonl", (time.time() - 3600,) * 2)
    e = _export(tmp_path / "e.json", "burst")
    with pytest.raises(SystemExit, match="one stored session"):
        ad.slim(e, store / "a9-burst.jsonl", "AARON", "burst", cells, config, lock, code_map=_codes("burst"))
    assert ad.set_aside(store, "burst", "AARON", adh) == 1
    rec = ad.slim(e, store / "a9-burst.jsonl", "AARON", "burst", cells, config, lock, code_map=_codes("burst"))
    assert rec["n"] == 55


def test_set_aside_command_line(tmp_path, monkeypatch, capsys):
    root = fixture(tmp_path / "repo", aaron=None)
    monkeypatch.setattr(ad, "ROOT", root)
    adh, store = root / "analysis" / "adherence", tmp_path / "store" / "R7"
    store.mkdir(parents=True)
    (store / "a9-push.jsonl").write_bytes(_row_line("push", "s1") + _row_line("push", "s2"))
    os.utime(store / "a9-push.jsonl", (time.time() - 3600,) * 2)
    assert ad.main(["set-aside", "--study", "push", "--rater", "R7", "--store", str(store)]) == 0
    assert "set aside 1 extra" in capsys.readouterr().out
    assert (adh / "raw" / "push-R7" / "extra-sessions.jsonl").exists() and (adh / "sessions.sha256").exists()
    with pytest.raises(SystemExit):
        ad.main(["set-aside", "--study", "push", "--rater", "R3", "--store", str(store)])   # only AARON and R7
