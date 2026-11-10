"""Tests for analysis/a14_seedance.py (A14). Synthetic fixtures only: no A14 clip exists.

    python -m pytest analysis/test_a14_seedance.py
"""
import json
import sys
from pathlib import Path

import pytest
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "harness"))
import a14_draws as ad  # noqa: E402
import a14_seedance as a14  # noqa: E402

SCOUT = [f"act-black-3_burst_sd2-h{k}" for k in (1, 2, 3)]
H3 = {"cu-line-1_idle_h3": (9, 10), "cu-line-1_burst_h3": (2, 10), "act-black-3_idle_h3": (0, 10),
      "act-black-3_burst_h3": (8, 10)}


@pytest.fixture(autouse=True)
def registered(tmp_path, monkeypatch):
    """A14 public by default: the fixtures record a route check, which comes after registration."""
    p = tmp_path / "public-prereg" / "PREREGISTRATION.md"
    p.parent.mkdir()
    p.write_text("### A14 — 2026-11-20: confirmatory: A5's Seedance hazard replication\n", encoding="utf-8")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(p))


def ink(path, chamfer):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"metrics": {"line_drift": {"vs_frame0": {"chamfer_px": {"mean": chamfer}}},
                                            "edge_decay": {"abs_slope_norm": 0.1}, "style_drift": {"terminal": 0.2}}}))


def mot(path, value=0.004):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"motion": {"headline_median_norm": value}}))


def make(root, verdict="match", chamfer=None, review=None, refused=(), skip=(), model=None, versions=None):
    """A finished A14: clips, manifest lines, metrics and the blind review. `chamfer` and `review`
    map a cell id to its value (defaults: 2.0 px, "held")."""
    (root / "docs").mkdir(parents=True)
    ad.build(root)
    a14.build_codes(root)
    (root / "docs" / "A14-ROUTE.md").write_text("captured\n")
    ad.route(verdict, root)
    out = root / "analysis" / "out"
    (out / "hazard_rates.json").write_text(json.dumps({"a4_per_cell": {
        c: {"n": n, "departed": k, "rate": k / n, "ci95": [0, 1]} for c, (k, n) in H3.items()}}))
    rec = json.loads((out / "a14_cells.json").read_text())
    runway = [c["cell_id"] for c in rec["cells"]]                 # the same 20 on a match and on a mismatch
    lines, codes = [], {cell: code for code, cell in a14.codes_for(root).items()}
    review_rec = {}
    for cid in SCOUT + runway:
        if cid in skip:
            continue
        if cid in refused:
            lines.append({"cell_id": cid, "refused": True, "out": None})
            continue
        folder = "seedance" if cid in SCOUT else "seedance2"
        clip = root / "runs" / folder / f"{cid}.mp4"
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"clip")
        lines.append({"cell_id": cid, "out": f"runs/{folder}/{cid}.mp4", "date": "2026-11-21", "seed": None,
                      "model_version": (versions or {}).get(cid, "seedance2 (Runway dev API, X-Runway-Version "
                                                                     "2024-11-06)" if cid not in SCOUT else "Seedance 2.0 via fal.ai"),
                      "task": {"id": "t", "status": "SUCCEEDED"} | ({"model": model} if model and cid not in SCOUT else {})})
        ink(root / "runs" / "metrics-seedance" / f"{cid}.json", (chamfer or {}).get(cid, 2.0))
        mot(root / "runs" / ("metrics-motion" if cid in SCOUT else "metrics-motion-seedance") / f"{cid}.json")
        review_rec[codes[cid]] = (review or {}).get(cid, "held")
    (root / "runs" / "manifest.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    (out / "a14_review.json").write_text(json.dumps({"reviewer": "blind agent", "codes": review_rec}))
    first = runway[0]                                        # the watched first draw: the model reference
    route = json.loads((out / "a14_route.json").read_text())
    route["task_reference"] = ({"captured_from": first, "fields": {"model": "seedance2"}, "check": "the model field"}
                               if model else {"captured_from": first, "fields": {}, "check": ad.CANNOT_FIRE})
    (out / "a14_route.json").write_text(json.dumps(route))
    if model:                                                # the reference draw names the captured model
        lines = [json.loads(x) for x in (root / "runs" / "manifest.jsonl").read_text().splitlines()]
        for x in lines:
            if x["cell_id"] == first and "task" in x:
                x["task"]["model"] = "seedance2"
        (root / "runs" / "manifest.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    return root


BURST_RUNWAY = [f"act-black-3_burst_sd2r-h{k}" for k in (4, 5, 6, 7, 8)]


def test_one_code_set_opaque_and_shuffled_covers_all_23_strips(tmp_path):
    (tmp_path / "docs").mkdir()
    ad.build(tmp_path)
    rec = a14.build_codes(tmp_path)
    assert set(rec) == {"seed", "rule", "codes"}                               # one set, whatever the route verdict
    codes = rec["codes"]
    assert sorted(codes) == [f"s{i:02d}" for i in range(1, 24)]
    assert set(codes.values()) == set(SCOUT) | {c["cell_id"] for c in ad.cells()}
    assert rec["seed"] == 20261104 and a14.build_codes(tmp_path) == rec          # deterministic
    assert list(codes.values()) != sorted(codes.values())                      # shuffled


def test_the_shipped_codes_are_what_build_codes_writes(tmp_path):
    shipped = a14.ROOT / a14.CODES_JSON
    if not shipped.exists():
        pytest.skip("no analysis/out/a14_codes.json in this tree")
    (tmp_path / "docs").mkdir()
    ad.build(tmp_path)
    a14.build_codes(tmp_path)
    assert (tmp_path / a14.CODES_JSON).read_bytes() == shipped.read_bytes()


def test_four_of_five_departures_hold_the_prediction(tmp_path):
    root = make(tmp_path, chamfer={BURST_RUNWAY[0]: 16.9, BURST_RUNWAY[1]: 12.0, BURST_RUNWAY[2]: 20.0,
                                   BURST_RUNWAY[4]: 11.0})
    p = a14.analyse(root)["prediction"]
    assert p["reading"] == "prediction holds: Seedance's departure rate is no lower than H3's"
    assert (p["k"], p["n"]) == (4, 5) and p["draws"] == BURST_RUNWAY
    assert p["wilson95"] == pytest.approx(list(a14.wilson(4, 5)))
    assert p["h3"] == {"k": 8, "n": 10, "wilson95": pytest.approx(list(a14.wilson(8, 10)))}
    assert p["fisher_p_h3_greater"] == pytest.approx(stats.fisher_exact([[8, 2], [4, 1]], alternative="greater")[1])


def test_three_of_five_refute_it(tmp_path):
    root = make(tmp_path, chamfer={BURST_RUNWAY[0]: 16.9, BURST_RUNWAY[1]: 20.0, BURST_RUNWAY[2]: 11.0})
    assert a14.analyse(root)["prediction"]["reading"] == \
        "prediction refuted: Seedance's departure rate is lower than H3's"


def test_the_scout_never_enters_the_confirmatory_reading(tmp_path):
    """Three of five fresh draws refute it, even with all three scout draws departed (the pooled 6 of 8 would not)."""
    root = make(tmp_path, chamfer={c: 30.0 for c in SCOUT} | {c: 16.9 for c in BURST_RUNWAY[:3]})
    res = a14.analyse(root)
    assert res["prediction"]["reading"].startswith("prediction refuted") and res["prediction"]["draws"] == BURST_RUNWAY
    assert (res["prediction"]["k"], res["prediction"]["n"]) == (3, 5)
    assert res["cells"]["act-black-3_burst"]["draws"] == BURST_RUNWAY
    assert (res["pooled"]["full_rule"]["k"], res["pooled"]["full_rule"]["n"]) == (6, 8)


def test_rule_b_counts_and_the_rule_a_only_reading_is_reported_beside(tmp_path):
    review = {BURST_RUNWAY[1]: "hard graphic cut", BURST_RUNWAY[2]: "subject replacement",
              BURST_RUNWAY[3]: "evacuation"}
    root = make(tmp_path, chamfer={BURST_RUNWAY[0]: 16.9, SCOUT[0]: 16.9}, review=review)
    res = a14.analyse(root)
    assert res["prediction"]["reading"].startswith("prediction holds") and res["prediction"]["k"] == 4
    a_only = res["prediction_rule_a_only"]
    assert a_only["reading"].startswith("prediction refuted") and a_only["k"] == 1
    # rule (b) without (a) on the three reviewed draws, and (a) without (b) on two draws at 16.9 px, held
    assert res["disagreements"]["n"] == 5
    assert res["disagreements"]["draws"] == sorted(list(review) + [BURST_RUNWAY[0], SCOUT[0]])


def test_refusals_leaving_fewer_than_three_draws_are_not_testable(tmp_path):
    root = make(tmp_path, refused=tuple(BURST_RUNWAY[:3]))
    p = a14.analyse(root)["prediction"]
    assert p["reading"] == "not testable: fewer than 3 coded draws" and p["n"] == 2
    assert p["refused"] == BURST_RUNWAY[:3]


def test_a_draw_neither_refused_nor_coded_reads_incomplete_with_its_numbers(tmp_path):
    root = make(tmp_path, skip=(BURST_RUNWAY[1],))
    p = a14.analyse(root)["prediction"]
    assert p["reading"] == "incomplete: 1 draws missing" and p["missing"] == [BURST_RUNWAY[1]]
    assert p["n"] == 4                                                     # its numbers still reported
    review = json.loads((root / a14.REVIEW_JSON).read_text())
    code = {cell: c for c, cell in a14.codes_for(root).items()}[BURST_RUNWAY[0]]
    review["codes"].pop(code)                                              # a strip code missing too
    (root / a14.REVIEW_JSON).write_text(json.dumps(review))
    assert a14.analyse(root)["prediction"]["reading"] == "incomplete: 2 draws missing"


SECONDARY = dict(chamfer={SCOUT[1]: 16.94, BURST_RUNWAY[0]: 15.0, BURST_RUNWAY[3]: 12.0},
                 review={SCOUT[0]: "hard graphic cut"})


def test_on_a_match_the_scout_and_the_pooled_eight_are_reported_beside_under_both_codings(tmp_path):
    res = a14.analyse(make(tmp_path, **SECONDARY))
    s = res["scout"]
    assert s["draws"] == SCOUT and "reading" not in s                       # beside, without a verdict
    assert (s["full_rule"]["k"], s["full_rule"]["n"]) == (2, 3) and (s["rule_a_only"]["k"], s["rule_a_only"]["n"]) == (1, 3)
    pooled = res["pooled"]
    assert pooled["computed"] is True and pooled["draws"] == SCOUT + BURST_RUNWAY and "reading" not in pooled
    full, a_only = pooled["full_rule"], pooled["rule_a_only"]
    assert (full["k"], full["n"], full["rate"]) == (4, 8, 0.5) and full["wilson95"] == pytest.approx(list(a14.wilson(4, 8)))
    assert (a_only["k"], a_only["n"]) == (3, 8) and a_only["wilson95"] == pytest.approx(list(a14.wilson(3, 8)))
    assert (res["prediction"]["k"], res["prediction"]["n"]) == (2, 5)          # the reading stays on the five
    md = a14.markdown(res)
    assert "secondary, without a verdict" in md and "4 of 8" in md and "3 of 8" in md


def test_a_mismatch_reads_the_same_five_reports_the_scout_and_does_not_pool(tmp_path):
    match = a14.analyse(make(tmp_path / "m", **SECONDARY))
    res = a14.analyse(make(tmp_path / "x", verdict="mismatch", **SECONDARY))
    assert res["route"]["verdict"] == "mismatch"
    assert {k: res["prediction"][k] for k in ("reading", "draws", "k", "n")} == \
        {k: match["prediction"][k] for k in ("reading", "draws", "k", "n")}
    assert res["prediction_rule_a_only"]["reading"] == match["prediction_rule_a_only"]["reading"]
    assert res["scout"] == match["scout"]                                   # the scout is still reported beside
    assert res["pooled"] == {"computed": False, "draws": SCOUT + BURST_RUNWAY,
                             "note": "not computed: the route check recorded a mismatch, and A5's fal draws "
                                     "are never pooled with Runway's (A14.3.4)"}
    assert a14.POOLED_NOT_COMPUTED in a14.markdown(res)


def test_a_model_change_found_during_the_run_is_not_testable_and_every_draw_has_no_verdict(tmp_path):
    root = make(tmp_path, model="seedance2_fast", skip=(BURST_RUNWAY[1],))
    res = a14.analyse(root)
    assert res["prediction"]["reading"] == "not testable at five draws: route mismatch found during the run"
    assert res["prediction_rule_a_only"]["reading"] == res["prediction"]["reading"]
    assert res["found_during_run"]["reported"] == "model='seedance2_fast'"
    assert res["found_during_run"]["reference"]["fields"] == {"model": "seedance2"}
    assert all(c["reading"] == "no verdict (route mismatch found during the run)" for c in res["cells"].values())
    assert res["pooled"] == {"computed": False, "draws": SCOUT + BURST_RUNWAY,          # never pooled across a
                             "note": "not computed: a route mismatch was found during the run, and A5's fal "   # model
                                     "draws are never pooled across a model change (A14.3.4)"}                   # change
    assert a14.POOLED_NOT_COMPUTED_RUN in a14.markdown(res)
    assert res["scout"]["draws"] == SCOUT and res["scout"]["full_rule"]["n"] == 3        # the scout still reported


def test_after_both_kinds_of_mismatch_the_check_string_is_printed(tmp_path):
    res = a14.analyse(make(tmp_path, verdict="mismatch", model="seedance2_fast"))
    assert res["found_during_run"] and res["pooled"]["computed"] is False
    assert res["pooled"]["note"] == a14.POOLED_NOT_COMPUTED


def test_the_rule_a_only_reading_can_hold(tmp_path):
    res = a14.analyse(make(tmp_path, chamfer={c: 16.9 for c in BURST_RUNWAY[:4]}))
    a_only = res["prediction_rule_a_only"]
    assert a_only["reading"] == "prediction holds: Seedance's departure rate is no lower than H3's"
    assert (a_only["k"], a_only["n"]) == (4, 5) and res["prediction"]["reading"] == a_only["reading"]


def test_per_cell_rates_beside_h3s_and_a4s_statistic(tmp_path):
    root = make(tmp_path, chamfer={"cu-line-1_idle_sd2r-h1": 12.0, SCOUT[0]: 16.9, BURST_RUNWAY[0]: 13.0,
                                   BURST_RUNWAY[1]: 14.0})
    res = a14.analyse(root)
    c = res["cells"]["act-black-3_burst"]
    assert (c["k"], c["n"]) == (2, 5) and c["h3"] == {"k": 8, "n": 10, "rate": 0.8}      # the scout not in it
    assert res["cells"]["cu-line-1_idle"]["h3"]["k"] == 9 and res["cells"]["cu-line-1_idle"]["k"] == 1
    a4 = res["a4_statistic"]["full_rule"]
    assert a4["burst_black"] == [2, 5] and a4["idle_line"] == [1, 5]
    assert a4["p_one_sided"] == pytest.approx(stats.fisher_exact([[2, 3], [1, 4]], alternative="greater")[1])


def test_model_versions_are_listed_and_flagged_when_more_than_one(tmp_path):
    root = make(tmp_path, versions={"cu-line-1_idle_sd2r-h2": "seedance2 (other)"})
    mv = a14.analyse(root)["model_versions"]
    assert mv["flag_more_than_one"] is True and "seedance2 (other)" in mv["runway"]


def test_a_review_with_an_unknown_label_is_refused(tmp_path):
    root = make(tmp_path)
    rec = json.loads((root / a14.REVIEW_JSON).read_text())
    rec["codes"]["s01"] = "looks off"
    (root / a14.REVIEW_JSON).write_text(json.dumps(rec))
    with pytest.raises(SystemExit) as e:
        a14.analyse(root)
    assert "looks off" in str(e.value)


def test_main_writes_the_same_outputs_twice(tmp_path):
    root = make(tmp_path / "t", chamfer={SCOUT[0]: 16.9})
    a14.main(["--fixtures", str(root)])
    out = root / "analysis" / "out"
    first = {n: (out / n).read_bytes() for n in ("a14_seedance.json", "a14_seedance.md")}
    a14.main(["--fixtures", str(root)])
    assert all((out / n).read_bytes() == b for n, b in first.items())
    assert "prediction refuted" in first["a14_seedance.md"].decode()


def test_real_data_is_refused_until_a14_is_public_and_fixtures_refuse_the_repository(tmp_path, monkeypatch):
    p = tmp_path / "PUBLIC-PREREGISTRATION.md"
    p.write_text("### A10 — 2026-11-20: ladder\n", encoding="utf-8")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(p))
    for argv in ([], ["--strips", str(tmp_path / "blind")]):
        with pytest.raises(SystemExit) as e:
            a14.main(argv)
        assert "A14" in str(e.value)
    with pytest.raises(SystemExit) as e:
        a14.main(["--fixtures", str(a14.ROOT)])
    assert "REFUSING --fixtures" in str(e.value)


def test_strips_are_copied_under_their_codes_only(tmp_path):
    root = make(tmp_path / "t")
    codes = a14.codes_for(root)
    assert len(codes) == 23
    for cid in codes.values():
        s = root / "analysis" / "out" / "frames" / cid / "strip.png"
        s.parent.mkdir(parents=True, exist_ok=True)
        s.write_bytes(cid.encode())
    blind = tmp_path / "blind"
    a14.make_strips(root, blind)
    names = sorted(p.name for p in blind.iterdir())
    assert names == sorted(f"{code}.png" for code in codes)
    code, cid = next(iter(codes.items()))
    assert (blind / f"{code}.png").read_bytes() == cid.encode()



# Kill rule A14.6.3: a cell whose every draw is refused reads "refused", its rate not computed; on
# the predicted cell it precedes "not testable: fewer than 3 coded draws".
def test_a_cell_whose_every_draw_is_refused_reads_refused_with_no_rate(tmp_path):
    idle = [f"cu-line-1_idle_sd2r-h{k}" for k in range(1, 6)]
    c = a14.analyse(make(tmp_path, refused=idle))["cells"]["cu-line-1_idle"]
    assert c["reading"] == "refused" and c["rate"] is None and c["wilson95"] is None and c["n"] == 0


@pytest.mark.parametrize("verdict", ["match", "mismatch"])
def test_the_predicted_cell_all_refused_reads_refused(tmp_path, verdict):
    res = a14.analyse(make(tmp_path, verdict=verdict, refused=tuple(BURST_RUNWAY)))
    assert res["prediction"]["reading"] == "refused" and res["prediction_rule_a_only"]["reading"] == "refused"
    assert res["cells"]["act-black-3_burst"]["reading"] == "refused"



def test_a_review_naming_a_code_outside_the_set_is_refused(tmp_path):
    root = make(tmp_path)
    rec = json.loads((root / a14.REVIEW_JSON).read_text())
    rec["codes"]["s99"] = "held"
    (root / a14.REVIEW_JSON).write_text(json.dumps(rec))
    with pytest.raises(SystemExit) as e:
        a14.analyse(root)
    assert "s99" in str(e.value)


def test_a_draw_lacking_the_captured_field_is_not_the_found_during_the_run_reading(tmp_path):
    root = make(tmp_path, model="seedance2", chamfer={SCOUT[0]: 16.9})
    lines = [json.loads(x) for x in (root / "runs" / "manifest.jsonl").read_text().splitlines()]
    for x in lines:
        if x["cell_id"] == "cu-line-1_burst_sd2r-h2":
            x["task"].pop("model")                                       # a record without the field
    (root / "runs" / "manifest.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    res = a14.analyse(root)
    assert res["found_during_run"] is None and not res["prediction"]["reading"].startswith("not testable at five")
    assert res["absent_fields"] == [{"cell_id": "cu-line-1_burst_sd2r-h2", "fields": ["model"], "note": None}]


def test_the_analysis_and_its_test_carry_no_card_or_call_identifier():
    """They ship with the release and are frozen in A14's manifest: dates, never a private card or log number."""
    import re
    for f in (Path(a14.__file__), Path(__file__)):
        text = f.read_text(encoding="utf-8")
        assert "P" + "69" not in text and not re.search(r"\bcall" + r"s? \d", text), f.name


def strips_for(root, cells):
    for cid in cells:
        st = root / "analysis" / "out" / "frames" / cid / "strip.png"
        st.parent.mkdir(parents=True, exist_ok=True)
        st.write_bytes(cid.encode())


def test_strips_skip_a_refused_draw_and_the_review_reads_without_its_code(tmp_path, capsys):
    root = make(tmp_path / "t", refused=(BURST_RUNWAY[0],))
    codes = a14.codes_for(root)
    strips_for(root, [cid for cid in codes.values() if cid != BURST_RUNWAY[0]])   # no clip, so no strip
    blind = tmp_path / "blind"
    a14.main(["--fixtures", str(root), "--strips", str(blind)])
    gone = {cid: code for code, cid in codes.items()}[BURST_RUNWAY[0]]
    names = sorted(x.name for x in blind.iterdir())
    assert len(names) == 22 and f"{gone}.png" not in names
    assert f"22 coded strips in {blind}; 1 draw skipped (refused, or no clip)" in capsys.readouterr().out
    res = a14.analyse(root)                                   # the record lacks the skipped code: still read
    assert res["prediction"]["refused"] == [BURST_RUNWAY[0]] and res["prediction"]["n"] == 4


def test_strips_refuse_a_draw_with_a_clip_but_no_strip(tmp_path):
    root = make(tmp_path / "t", skip=(BURST_RUNWAY[1],))      # no manifest line and no clip: skipped
    codes = a14.codes_for(root)
    strips_for(root, [cid for cid in codes.values() if cid not in (BURST_RUNWAY[1], SCOUT[2])])
    with pytest.raises(SystemExit) as e:
        a14.make_strips(root, tmp_path / "blind")
    assert SCOUT[2] in str(e.value) and BURST_RUNWAY[1] not in str(e.value)
    assert not (tmp_path / "blind").exists()


def test_the_markdown_flags_refused_and_missing_draws_on_the_secondary_lines(tmp_path):
    root = make(tmp_path, refused=(BURST_RUNWAY[0],))
    rec = json.loads((root / a14.REVIEW_JSON).read_text())
    rec["codes"].pop({cid: code for code, cid in a14.codes_for(root).items()}[SCOUT[0]])   # a scout code missing
    (root / a14.REVIEW_JSON).write_text(json.dumps(rec))
    md = a14.markdown(a14.analyse(root))
    scout = next(ln for ln in md.splitlines() if ln.startswith("- A5's scout"))
    assert scout.endswith(f"; missing: {SCOUT[0]}")
    pooled = [ln for ln in md.splitlines() if ln.startswith("- Pooled")]
    assert len(pooled) == 2 and pooled[0].endswith(f"; refused: {BURST_RUNWAY[0]}; missing: {SCOUT[0]}")
    assert pooled[1].endswith(f"; refused: {BURST_RUNWAY[0]}")           # rule (a) needs no review code
    assert md.startswith("# A14: A5's Seedance prediction at five fresh draws\n")


def test_the_markdown_secondary_lines_carry_no_flag_when_nothing_is_refused_or_missing(tmp_path):
    md = a14.markdown(a14.analyse(make(tmp_path)))
    assert "; refused:" not in md and "; missing:" not in md
