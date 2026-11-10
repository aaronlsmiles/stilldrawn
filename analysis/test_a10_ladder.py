"""Tests for analysis/a10_ladder.py (A10). Synthetic fixtures only: no ladder clip exists.

    python -m pytest analysis/test_a10_ladder.py
"""
import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a10_ladder as al  # noqa: E402

PANELS = [f"{c}-{t}-1" for c in ("cu", "act", "est") for t in ("line", "tone", "black")] + \
         ["cu-line-2", "act-tone-2", "est-black-2"]


def levels(*vals):
    return dict(zip(al.LEVELS, vals))


BASE_MOTION = {"wan22": levels(0.001, 0.002, 0.003, 0.004),
               "gen45": levels(0.002, 0.003, 0.004, 0.008),
               "ltx23": levels(0.002, 0.003, 0.005, 0.009)}


def linear(m, lv, i):
    return 1 + 100 * m


def write_tree(root, motion, chamfer, refused=(), cells_file=False):
    if cells_file:                                    # the registered list: 48 ids per engine
        (root / "analysis" / "out").mkdir(parents=True, exist_ok=True)
        (root / "analysis" / "out" / "a10_cells.json").write_text(json.dumps({"cells": {
            tag: [f"ladder-{p}_{lv.lower()}_{tag}" for p in PANELS for lv in al.LEVELS] for tag in motion}}))
    for d in ("metrics-ladder", "metrics-motion-ladder"):
        (root / "runs" / d).mkdir(parents=True, exist_ok=True)
    for tag, by_level in motion.items():
        for lv, mv in by_level.items():
            for i, panel in enumerate(PANELS):
                cell = f"ladder-{panel}_{lv.lower()}_{tag}"
                m = mv(i) if callable(mv) else mv         # a level's motion may vary by panel
                c = chamfer[tag](m, lv, i)
                (root / "runs" / "metrics-motion-ladder" / f"{cell}.json").write_text(
                    json.dumps({"motion": {"headline_median_norm": m}}))
                (root / "runs" / "metrics-ladder" / f"{cell}.json").write_text(json.dumps({"metrics": {
                    "line_drift": {"vs_frame0": {"chamfer_px": {"mean": c}}},
                    "edge_decay": {"abs_slope_norm": c / 10}, "style_drift": {"terminal": c / 100}}}))
    (root / "runs" / "manifest.jsonl").write_text(
        "".join(json.dumps({"cell_id": c, "refused": True, "out": None}) + "\n" for c in refused))
    return root


def make(tmp_path, motion=None, chamfer=None, refused=(), cells_file=False):
    motion = {**BASE_MOTION, **(motion or {})}
    chamfer = {**{t: linear for t in motion}, **(chamfer or {})}
    return write_tree(tmp_path, motion, chamfer, refused, cells_file)


def drop(root, cells, which=("metrics-ladder",)):
    for c in cells:
        for d in which:
            (root / "runs" / d / f"{c}.json").unlink()
    return root


def cell(panel, lv, tag):
    return f"ladder-{panel}_{lv.lower()}_{tag}"


def test_parse_cell_reads_the_registered_ids_only():
    assert al.parse_cell("ladder-cu-line-1_still_wan22") == ("cu-line-1", "STILL", "wan22")
    assert al.parse_cell("ladder-est-black-2_high_gen45") == ("est-black-2", "HIGH", "gen45")
    assert al.parse_cell("cu-line-1_idle_wan22") is None
    assert al.parse_cell("ladder-cu-line-1_burst_wan22") is None


def test_a_planted_positive_supports_h1_on_every_engine_and_h2(tmp_path):
    res = al.analyse(make(tmp_path))
    for e in al.ENGINES:
        eng = res["engines"][e]
        c = eng["A10-H1"]["per_metric"]["chamfer"]
        assert eng["manipulation"]["passed"] and eng["A10-H1"]["reading"] == "supported"
        assert c["rho"] == pytest.approx(1.0) and c["p_perm_one_sided"] < 0.001 and c["n"] == 48
    h2 = res["A10-H2"]
    assert h2["reading"] == "supported" and h2["n_band"] == {"Gen-4.5": 12, "Wan 2.2": 12}
    assert h2["g_band"] == pytest.approx(0.0, abs=1e-12)
    assert h2["g_whole"] == pytest.approx(math.log2(1.35 / 1.25))


def test_a_planted_null_reads_null(tmp_path):
    def falling(m, lv, i):
        return 10 - 1000 * m
    res = al.analyse(make(tmp_path, chamfer={t: falling for t in BASE_MOTION}))
    for e in al.ENGINES:
        h = res["engines"][e]["A10-H1"]
        assert h["reading"] == "null" and h["per_metric"]["chamfer"]["p_perm_one_sided"] > 0.5


def test_h2_is_not_supported_when_the_gap_survives_in_the_band(tmp_path):
    def doubled(m, lv, i):
        return 2 * (1 + 100 * m)
    res = al.analyse(make(tmp_path, chamfer={"gen45": doubled}))
    assert res["A10-H2"]["reading"] == "not supported"
    assert res["A10-H2"]["g_band"] == pytest.approx(1.0) and res["A10-H2"]["g_whole"] > 1.0


def test_a_still_wan_gives_the_kill_reading(tmp_path):
    res = al.analyse(make(tmp_path, motion={"wan22": levels(0.0005, 0.0006, 0.0007, 0.0008)}))
    assert res["A10-H2"]["reading"] == "not testable: Wan 2.2 does not move on request"
    assert res["A10-H2"]["wan_high_q75"] < min(res["A10-H2"]["other_still_medians"].values())


def test_a_thin_band_is_not_testable(tmp_path):
    res = al.analyse(make(tmp_path, motion={"gen45": levels(0.0035, 0.006, 0.009, 0.012)}))
    assert res["A10-H2"]["reading"].startswith("not testable: band too thin") and res["A10-H2"]["band"] is None


def test_a_failed_manipulation_is_reported_and_carries_no_verdict(tmp_path):
    res = al.analyse(make(tmp_path, motion={"ltx23": levels(0.004, 0.003, 0.002, 0.001)}))
    ltx = res["engines"]["ltx23"]
    assert not ltx["manipulation"]["passed"] and ltx["manipulation"]["rising_steps"] == 0
    assert ltx["A10-H1"]["reading"] == "manipulation failed"
    assert res["engines"]["wan22"]["A10-H1"]["reading"] == "supported"


def test_refused_cells_are_listed(tmp_path):
    res = al.analyse(make(tmp_path, refused=["ladder-cu-line-1_high_gen45", "cu-tone-3_idle_gen4t"]))
    assert res["refused"] == ["ladder-cu-line-1_high_gen45"]
    assert "ladder-cu-line-1_high_gen45" in al.markdown(res)


def test_main_writes_identical_outputs_twice(tmp_path):
    root = make(tmp_path)
    al.main(["--fixtures", str(root)])
    out = root / "analysis" / "out"
    first = {n: (out / n).read_bytes() for n in ("a10_ladder.json", "a10_ladder.md")}
    al.main(["--fixtures", str(root)])
    assert all((out / n).read_bytes() == b for n, b in first.items())
    assert (out / "figures" / "a10_ladder.png").stat().st_size > 0
    assert "Confirmatory (amendment A10)" in first["a10_ladder.md"].decode()


def test_manipulation_only_prints_the_medians_and_writes_nothing(tmp_path, capsys):
    root = make(tmp_path)
    al.main(["--fixtures", str(root), "--manipulation-only"])
    printed = capsys.readouterr().out
    assert "Wan 2.2: STILL 0.00100" in printed and "passed" in printed
    assert not (root / "analysis" / "out" / "a10_ladder.json").exists()


def test_real_data_is_refused_until_a10_is_public(tmp_path, monkeypatch):
    p = tmp_path / "PUBLIC-PREREGISTRATION.md"
    p.write_text("### A9 — 2026-11-03: exploratory\n", encoding="utf-8")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(p))
    for argv in ([], ["--manipulation-only"]):
        with pytest.raises(SystemExit) as e:
            al.main(argv)
        assert "A10" in str(e.value)


@pytest.mark.parametrize("cells_file", [False, True])
def test_a_missing_inkstab_file_withholds_the_verdict(tmp_path, capsys, cells_file):
    gone = cell("cu-line-1", "MID", "wan22")
    root = drop(make(tmp_path, cells_file=cells_file), [gone])
    res = al.analyse(root)
    wan = res["engines"]["wan22"]
    assert wan["A10-H1"]["reading"] == "incomplete: 1 cell missing"
    assert wan["cells"]["missing_inkstab"] == [gone] and wan["cells"]["complete"] == 47
    assert res["A10-H2"]["reading"] == "incomplete: 1 cell missing (Gen-4.5 and Wan 2.2)"
    assert res["engines"]["ltx23"]["A10-H1"]["reading"] == "supported"
    assert gone in al.markdown(res)
    assert "Missing cells: Wan 2.2 (1 cell missing). These rows use the cells present" in al.markdown(res)
    assert res["engines"]["wan22"]["A10-H1-within-panel"]["stratified_by"] == "panel"
    # the full run's manipulation check reads the same rows as --manipulation-only
    assert wan["manipulation"]["n"] == 48
    al.main(["--fixtures", str(root), "--manipulation-only"])
    med = wan["manipulation"]["median_motion_by_level"]
    assert "Wan 2.2: " + "  ".join(f"{lv} {med[lv]:.5f}" for lv in al.LEVELS) in capsys.readouterr().out


def test_a_cell_with_no_files_is_missing_against_the_registered_list(tmp_path, capsys):
    gone = cell("est-tone-1", "HIGH", "gen45")
    root = drop(make(tmp_path, cells_file=True), [gone], ("metrics-ladder", "metrics-motion-ladder"))
    res = al.analyse(root)
    gen = res["engines"]["gen45"]
    assert gen["cells"]["missing_motion"] == [gone] and gen["A10-H1"]["reading"] == "incomplete: 1 cell missing"
    assert res["A10-H2"]["reading"].startswith("incomplete: 1 cell missing")
    al.main(["--fixtures", str(root), "--manipulation-only"])
    assert "Gen-4.5: incomplete, 1 cell missing" in capsys.readouterr().out


def test_refused_cells_are_not_missing(tmp_path):
    ref = [cell(p, "HIGH", "gen45") for p in PANELS[:3]]
    root = drop(make(tmp_path, refused=ref, cells_file=True), ref, ("metrics-ladder", "metrics-motion-ladder"))
    gen = al.analyse(root)["engines"]["gen45"]
    assert gen["cells"]["refused"] == sorted(ref) and gen["cells"]["missing"] == 0
    assert gen["A10-H1"]["reading"] == "supported" and gen["A10-H1"]["per_metric"]["chamfer"]["n"] == 45


def test_fixtures_refuses_the_repository_and_private_trees(tmp_path):
    with pytest.raises(SystemExit) as e:
        al.main(["--fixtures", str(al.ROOT)])
    assert "REFUSING --fixtures" in str(e.value)
    root = make(tmp_path / "copy")
    (root / "analysis" / "adherence").mkdir(parents=True)
    (root / "analysis" / "adherence" / "private-terms.txt").write_text("")
    for target in (root, root / "runs"):
        with pytest.raises(SystemExit) as e:
            al.main(["--fixtures", str(target)])
        assert "REFUSING --fixtures" in str(e.value)
    assert not (root / "analysis" / "out").exists()


def test_fixtures_refuse_any_folder_at_or_under_the_root_without_the_marker(tmp_path, monkeypatch):
    """The release tree carries no private marker: the guard must still refuse it and its folders."""
    rel = make(tmp_path / "release")
    monkeypatch.setattr(al, "ROOT", rel)
    for target in (rel, rel / "runs", rel / "runs" / "new"):
        with pytest.raises(SystemExit) as e:
            al.main(["--fixtures", str(target)])
        assert "REFUSING --fixtures" in str(e.value)
    assert not (rel / "analysis" / "out").exists()
    assert al.check_fixtures(tmp_path / "beside") == (tmp_path / "beside").resolve()


def test_no_whole_ladder_gap_is_read_before_the_support_rule(tmp_path):
    def halved(m, lv, i):
        return (1 + 100 * m) / 2
    h = al.analyse(make(tmp_path, chamfer={"gen45": halved}))["A10-H2"]
    assert h["reading"] == "not testable: no whole-ladder gap (g_whole <= 0)"
    assert h["g_whole"] < 0 and h["n_band"] == {"Gen-4.5": 12, "Wan 2.2": 12}
    assert h["g_band"] <= 0.5 * h["g_whole"]          # the support rule alone would have said "supported"


def test_fewer_than_8_cells_of_an_engine_is_not_testable(tmp_path):
    keep = {cell(p, "STILL", "gen45") for p in PANELS[:7]}
    ref = [cell(p, lv, "gen45") for p in PANELS for lv in al.LEVELS if cell(p, lv, "gen45") not in keep]
    root = drop(make(tmp_path, refused=ref, cells_file=True), ref, ("metrics-ladder", "metrics-motion-ladder"))
    h = al.analyse(root)["A10-H2"]
    assert h["reading"] == "not testable: fewer than 8 cells of an engine"
    assert h["n_whole"] == {"Gen-4.5": 7, "Wan 2.2": 48} and "band" not in h


def test_seven_cells_by_lost_files_reads_incomplete(tmp_path):
    keep = {cell(p, "STILL", "gen45") for p in PANELS[:7]}
    gone = [cell(p, lv, "gen45") for p in PANELS for lv in al.LEVELS if cell(p, lv, "gen45") not in keep]
    res = al.analyse(drop(make(tmp_path), gone))
    assert res["engines"]["gen45"]["A10-H1"]["reading"] == "incomplete: 41 cells missing"
    assert res["A10-H2"]["reading"] == "incomplete: 41 cells missing (Gen-4.5 and Wan 2.2)"


def test_the_band_is_inclusive_at_its_edge(tmp_path):
    # Gen-4.5's lower quartile falls on its own value 0.003 (24 cells), which is the band's lower edge
    h = al.analyse(make(tmp_path, motion={"gen45": levels(0.003, 0.003, 0.004, 0.008)}))["A10-H2"]
    assert h["band"][0] == 0.003
    assert h["n_band"] == {"Gen-4.5": 24, "Wan 2.2": 12}
    assert h["band_panels"] == {"Gen-4.5": {p: 2 for p in sorted(PANELS)}, "Wan 2.2": {p: 1 for p in sorted(PANELS)}}


def test_an_undefined_g_band_reads_undefined_and_zeros_are_counted_in_the_figure(tmp_path):
    def zero_mid(m, lv, i):
        return 0.0 if lv == "MID" else 1 + 100 * m
    root = make(tmp_path, chamfer={"wan22": zero_mid})
    res = al.analyse(root)
    assert res["A10-H2"]["g_whole"] > 0 and res["A10-H2"]["g_band"] is None
    assert res["A10-H2"]["reading"] == "undefined: g_band (a median chamfer in the band is not positive)"
    assert res["figure_not_plotted_nonpositive"] == 12
    al.main(["--fixtures", str(root)])
    assert "12 cells with a motion or chamfer value of 0 or below" in \
        (root / "analysis" / "out" / "a10_ladder.md").read_text()


def test_the_wan_check_records_its_comparison_and_is_undefined_without_stills(tmp_path):
    h = al.analyse(make(tmp_path))["A10-H2"]
    assert h["wan_compared_with"] == ["Gen-4.5", "LTX-2.3"] and h["wan_check_lacking_still"] == []
    ref = [cell(p, "STILL", "ltx23") for p in PANELS]
    root = drop(make(tmp_path / "b", refused=ref), ref, ("metrics-ladder", "metrics-motion-ladder"))
    h = al.analyse(root)["A10-H2"]
    assert h["wan_compared_with"] == ["Gen-4.5"] and h["wan_check_lacking_still"] == ["LTX-2.3"]
    assert h["reading"] == "undefined: the Wan 2.2 motion check cannot be made (no STILL cells for LTX-2.3)"


def test_a_between_panel_only_effect_is_pooled_not_within(tmp_path):
    # motion: panel-major ((i + 1) / 1000), rising a little with the level inside each panel;
    # chamfer: the panel (1 + i) plus a within-panel pattern unrelated to the level (within rho exactly 0)
    def by_panel(k):
        return lambda i: (i + 1) * 0.001 * (1 + 0.1 * k)

    def panel_only(m, lv, i):
        return 1 + i + 0.01 * ((3 * i + 3 * al.LEVELS.index(lv)) % 4)
    motion = {t: levels(*(by_panel(k) for k in range(4))) for t in al.ENGINES}
    res = al.analyse(make(tmp_path, motion=motion, chamfer={t: panel_only for t in al.ENGINES}))
    for e in al.ENGINES:
        pooled = res["engines"][e]["A10-H1"]
        w = res["engines"][e]["A10-H1-within-panel"]
        assert pooled["reading"] == "supported" and pooled["per_metric"]["chamfer"]["rho"] > 0.95
        assert w["rho"] == pooled["per_metric"]["chamfer"]["rho"] and w["n"] == 48 and w["strata"] == 12
        assert w["rho_within"] == pytest.approx(0.0, abs=1e-12)
        assert w["p_pooled_within_strata_perm"] > 0.2 and w["p_within"] > 0.2
        assert w["verdict"] == "none (secondary)" and w["permutations"] == al.B
    assert "Missing cells:" not in al.markdown(res)


def test_a_within_panel_effect_survives_the_within_panel_permutation(tmp_path):
    w = al.analyse(make(tmp_path))["engines"]["wan22"]["A10-H1-within-panel"]
    assert w["rho_within"] == pytest.approx(1.0) and w["p_within"] == pytest.approx(1 / (al.B + 1))


def test_the_labels_are_a10_h1_and_a10_h2(tmp_path):
    res = al.analyse(make(tmp_path))
    assert "A10-H2" in res and "h2" not in res
    assert all({"A10-H1", "A10-H1-within-panel"} <= set(res["engines"][e]) and "h1" not in res["engines"][e]
               for e in al.ENGINES)
    assert res["A10-H2"]["band_panels"]["Wan 2.2"] == {p: 1 for p in sorted(PANELS)}
    md = al.markdown(res)
    for heading in ("## A10-H1: rho(realised motion, drift), per engine",
                    "### A10-H1 within panel (secondary, no verdict)",
                    "## A10-H2: the Gen-4.5 / Wan 2.2 gap on motion-matched cells"):
        assert heading in md.splitlines()
    assert "| 95% CI | A10-H1 |" in md
    assert not any(line.startswith(("## H1", "## H2")) for line in md.splitlines())


def add_manifest(root, versions):
    """Append a manifest line per expected cell: versions = {tag: fn(cell index) -> model_version}."""
    m = root / "runs" / "manifest.jsonl"
    lines = [json.dumps({"cell_id": f"ladder-{p}_{lv.lower()}_{tag}", "engine": tag,
                         "model_version": fn(i * len(al.LEVELS) + j), "out": "x"}) + "\n"
             for tag, fn in versions.items() for i, p in enumerate(PANELS) for j, lv in enumerate(al.LEVELS)]
    m.write_text(m.read_text() + "".join(lines))


def test_model_versions_per_engine_and_mixed_hardware_flag_change_no_verdict(tmp_path):
    root = make(tmp_path / "t", cells_file=True)
    before = al.analyse(root, b=200)
    add_manifest(root, {"wan22": lambda n: "Wan 2.2 [pod-b]" if n == 5 else "Wan 2.2 [pod-a]",
                        "ltx23": lambda n: "LTX-2.3 [pod-a]",
                        "gen45": lambda n: "gen4.5 (Runway)"})
    res = al.analyse(root, b=200)
    for e in al.ENGINES:
        assert res["engines"][e]["A10-H1"] == before["engines"][e]["A10-H1"]
        assert res["engines"][e]["manipulation"] == before["engines"][e]["manipulation"]
    assert res["A10-H2"] == before["A10-H2"]
    w, l, g = (res["engines"][e] for e in ("wan22", "ltx23", "gen45"))
    assert w["model_versions"] == ["Wan 2.2 [pod-a]", "Wan 2.2 [pod-b]"]
    assert w["hardware"] == ["pod-a", "pod-b"] and w["hardware_mixed"] is True
    assert l["hardware"] == ["pod-a"] and l["hardware_mixed"] is False
    assert g["model_versions"] == ["gen4.5 (Runway)"] and g["hardware"] is None and g["hardware_mixed"] is None
    assert w["n_cells_without_manifest_line"] == 0
    md = al.markdown(res)
    assert "Wan 2.2 [pod-b]" in md and "hardware mixed" in md


def test_the_last_manifest_line_of_a_cell_wins_and_refused_cells_are_not_counted(tmp_path):
    root = make(tmp_path / "t", cells_file=True, refused=["ladder-cu-line-1_high_gen45"])
    add_manifest(root, {"wan22": lambda n: "Wan 2.2 [pod-b]", "gen45": lambda n: "gen4.5 (Runway)"})
    add_manifest(root, {"wan22": lambda n: "Wan 2.2 [pod-a]"})          # a later line supersedes
    res = al.analyse(root, b=200)
    assert res["engines"]["wan22"]["hardware"] == ["pod-a"] and res["engines"]["wan22"]["hardware_mixed"] is False
    assert res["engines"]["ltx23"]["model_versions"] == [] and res["engines"]["ltx23"]["hardware_mixed"] is False
    assert res["engines"]["ltx23"]["n_cells_without_manifest_line"] == 48
    assert res["engines"]["gen45"]["n_cells_without_manifest_line"] == 0      # 47 clips + 1 refused
    assert "hardware mixed" not in al.markdown(res)


# --------------------- further engines (A15 Kling, A16 Midjourney): A10-H1 only, under their own
# amendments (ruled 8 Nov 2026). They never enter A10's summary, A10-H2 or its kill rules.
KLING_MOTION = levels(0.002, 0.003, 0.005, 0.009)
ENGINE_OF = {"kling4": "kling_4", "mjv": "midjourney"}


def add_arm(root, tag="kling4", motion=None, chamfer=linear, cell_list=True, scout=None, refused=()):
    """An arm's ladder cells in the tree (metrics only), its cell list and scout reading if asked,
    and refused lines appended to the manifest."""
    m = root / "runs" / "manifest.jsonl"
    kept = m.read_text() if m.exists() else ""
    write_tree(root, {tag: motion or KLING_MOTION}, {tag: chamfer})          # rewrites the manifest
    m.write_text(kept + "".join(json.dumps({"cell_id": c, "refused": True, "out": None}) + "\n" for c in refused))
    for c in refused:
        for d in ("metrics-ladder", "metrics-motion-ladder"):
            (root / "runs" / d / f"{c}.json").unlink(missing_ok=True)
    if cell_list:
        f = root / al.ARMS[tag]["cells"]
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"amendment": al.ARMS[tag]["amendment"], "cells": {
            ENGINE_OF[tag]: [cell(p, lv, tag) for p in PANELS for lv in al.LEVELS]}}))
    if scout is not None:
        (root / al.ARMS[tag]["scout"]).write_text(json.dumps({"reading": scout}))
    return root


def a10_part(res):
    return {k: v for k, v in res.items() if k not in ("arms", "not_analysed_no_cell_list")}


def a10_md(md):
    return md.split("\n## Further engines")[0]


@pytest.mark.parametrize("cells_file", [False, True])
def test_a10s_outputs_are_identical_with_and_without_an_arm(tmp_path, cells_file):
    base = make(tmp_path / "a", cells_file=cells_file)
    plain = al.analyse(base, b=500)
    kling_ref = cell("cu-line-1", "HIGH", "kling4")
    arm = add_arm(make(tmp_path / "b", cells_file=cells_file), refused=[kling_ref])
    with_arm = al.analyse(arm, b=500)
    assert a10_part(with_arm) == plain and "arms" not in plain
    assert a10_md(al.markdown(with_arm)) == al.markdown(plain)
    assert kling_ref not in with_arm["refused"]                      # an arm's refusal stays in its own section
    k = with_arm["arms"]["kling4"]
    assert k["status"] == "analysed" and k["reading"] == "supported" and k["manipulation"]["passed"]
    assert k["label"] == "A10-H1 (Kling, A15)" and k["in_A10_H2"] is False and k["amendment"] == "A15"
    assert k["cells"]["expected"] == 48 and k["cells"]["refused"] == [kling_ref] and k["A10-H1"]["per_metric"][
        "chamfer"]["n"] == 47
    assert "kling4" not in with_arm["engines"]


def test_without_its_cell_list_an_arms_cells_are_listed_not_analysed(tmp_path):
    res = al.analyse(add_arm(make(tmp_path), cell_list=False), b=200)
    assert "arms" not in res
    assert res["not_analysed_no_cell_list"] == sorted(cell(p, lv, "kling4") for p in PANELS for lv in al.LEVELS)
    assert "Cells of a further engine without its cell list (not analysed)" in al.markdown(res)


def test_kill_rule_2_compares_a10s_engines_only(tmp_path):
    # Wan barely moves: its HIGH upper quartile is below Gen-4.5's and LTX-2.3's STILL medians (the
    # kill reading). Kling's STILL median is lower still: counted among "every other engine", it
    # would lift the kill. It must not.
    still_wan = {"wan22": levels(0.0005, 0.0006, 0.0007, 0.0008)}
    root = add_arm(make(tmp_path, motion=still_wan), motion=levels(0.0001, 0.003, 0.005, 0.009))
    res = al.analyse(root, b=500)
    h = res["A10-H2"]
    assert h["reading"] == "not testable: Wan 2.2 does not move on request"
    assert h["wan_compared_with"] == ["Gen-4.5", "LTX-2.3"] and "Kling" not in h["other_still_medians"]
    assert res["arms"]["kling4"]["manipulation"]["median_motion_by_level"]["STILL"] < h["wan_high_q75"]


def test_an_arm_cell_missing_withholds_its_own_reading_only(tmp_path):
    gone = cell("cu-line-1", "HIGH", "kling4")
    root = drop(add_arm(make(tmp_path, cells_file=True)), [gone])
    res = al.analyse(root, b=500)
    assert res["arms"]["kling4"]["reading"] == "incomplete: 1 cell missing"
    assert res["A10-H2"]["reading"] == "supported"
    assert all(res["engines"][e]["A10-H1"]["reading"] == "supported" for e in al.ENGINES)


def test_a_midjourney_arm_is_read_the_same_way(tmp_path):
    def falling(m, lv, i):
        return 10 - 1000 * m
    res = al.analyse(add_arm(make(tmp_path), tag="mjv", chamfer=falling), b=500)
    m = res["arms"]["mjv"]
    assert m["reading"] == "null" and m["label"] == "A10-H1 (Midjourney, A16)"
    assert res["A10-H2"]["reading"] == "supported"


def test_an_arm_list_naming_another_engines_cell_is_refused(tmp_path):
    root = add_arm(make(tmp_path))
    (root / al.ARMS["kling4"]["cells"]).write_text(json.dumps({"cells": {"kling_4": [cell("cu-line-1", "LOW", "gen45")]}}))
    with pytest.raises(SystemExit) as e:
        al.analyse(root, b=50)
    assert "a15_cells.json" in str(e.value)


# Outside --fixtures an arm is analysed only once its amendment is public.
@pytest.mark.parametrize("tag,amendment", [("kling4", "A15"), ("mjv", "A16")])
def test_an_arm_is_analysed_only_when_its_amendment_is_public(tmp_path, tag, amendment):
    root = add_arm(make(tmp_path, cells_file=True), tag=tag)
    shut = al.analyse(root, b=200, public=lambda a: a == "A10")
    arm = shut["arms"][tag]
    assert arm["status"] == arm["reading"] == f"not analysed: {amendment} not public"
    assert "A10-H1" not in arm and "manipulation" not in arm and len(arm["cells_found_not_analysed"]) == 48
    opened = al.analyse(root, b=200, public=lambda a: a in ("A10", amendment))
    assert opened["arms"][tag]["status"] == "analysed" and opened["arms"][tag]["reading"] == "supported"
    assert a10_part(shut) == a10_part(opened)


def test_main_outside_fixtures_reads_the_arm_only_once_a15_is_public(tmp_path, monkeypatch):
    root = add_arm(make(tmp_path / "tree", cells_file=True))
    monkeypatch.setattr(al, "ROOT", root)                            # main's real path, on a synthetic tree
    prereg = tmp_path / "public" / "PREREGISTRATION.md"
    prereg.parent.mkdir()
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(prereg))
    prereg.write_text("### A10 — 2026-11-20: motion by construction\n", encoding="utf-8")
    al.main([])
    res = json.loads((root / "analysis" / "out" / "a10_ladder.json").read_text())
    assert res["arms"]["kling4"]["reading"] == "not analysed: A15 not public"
    assert "not analysed: A15 not public" in (root / "analysis" / "out" / "a10_ladder.md").read_text()
    prereg.write_text("### A10 — 2026-11-20: motion\n### A15 — 2026-11-20: a Kling scout\n", encoding="utf-8")
    al.main([])
    res = json.loads((root / "analysis" / "out" / "a10_ladder.json").read_text())
    assert res["arms"]["kling4"]["reading"] == "supported"


# A failed scout labels the arm by its logged reading.
FAILED_SCOUT = "scout failed: does not move on request (1 of 3 BURST draws above the floor)"


def test_a_failed_scout_labels_the_arm_not_run_with_the_scouts_reading(tmp_path):
    root = add_arm(make(tmp_path, cells_file=True), cell_list=True, scout=FAILED_SCOUT)
    for d in ("metrics-ladder", "metrics-motion-ladder"):             # the arm never ran: no arm clip exists
        for p in PANELS:
            for lv in al.LEVELS:
                (root / "runs" / d / f"{cell(p, lv, 'kling4')}.json").unlink()
    res = al.analyse(root, b=200)
    k = res["arms"]["kling4"]
    assert k["reading"] == "not run: scout failed: does not move on request (1 of 3 BURST draws above the floor)"
    assert k["scout_reading"] == FAILED_SCOUT and "A10-H1" not in k and k["cells_found_not_analysed"] == []
    md = al.markdown(res)
    assert "**not run: scout failed: does not move on request" in md and "incomplete: 48 cells missing" not in md


def test_a_passed_scout_or_none_yet_lets_the_arm_be_read(tmp_path):
    root = add_arm(make(tmp_path, cells_file=True),
                   scout="scout passed: Kling joins A10's motion test as a further engine")
    k = al.analyse(root, b=200)["arms"]["kling4"]
    assert k["reading"] == "supported" and k["scout_reading"].startswith("scout passed: ")
    (root / al.ARMS["kling4"]["scout"]).unlink()
    assert al.analyse(root, b=200)["arms"]["kling4"]["scout_reading"] is None


def test_an_unrecognised_scout_reading_is_refused(tmp_path):
    root = add_arm(make(tmp_path), scout="scout maybe")
    with pytest.raises(SystemExit) as e:
        al.analyse(root, b=50)
    assert "a15_scout.json" in str(e.value) and "scout maybe" in str(e.value)


def test_the_outputs_report_the_arm_under_its_own_heading(tmp_path, capsys):
    root = add_arm(make(tmp_path, cells_file=True))
    al.main(["--fixtures", str(root)])
    md = (root / "analysis" / "out" / "a10_ladder.md").read_text()
    a10, arms = md.split("\n## Further engines", 1)
    assert "Kling" not in a10
    assert "### A10-H1 (Kling, A15)" in arms and "- Reading: **supported**" in arms
    assert "| mean chamfer vs frame 0 (px) | 48 |" in arms
    capsys.readouterr()
    al.main(["--fixtures", str(root), "--manipulation-only"])
    out = capsys.readouterr().out
    assert "Kling (A15): STILL 0.00200" in out and out.index("Gen-4.5:") < out.index("Kling (A15):")


# The registered readings, one source with harness/ladder.py's run gate (exact, not a prefix).
def test_the_analysis_and_the_run_gate_share_the_registered_readings():
    import ladder
    for tag, engine in (("kling4", "kling_4"), ("mjv", "midjourney")):
        assert al.ARMS[tag]["scout_passed"] is ladder.ARMS[engine]["scout_passed"]
        assert str(al.ARMS[tag]["scout"]) == ladder.ARMS[engine]["scout"]


@pytest.mark.parametrize("reading", [
    "scout failed: refused (2 of 6 cells)", "scout failed: not measurable (act-black-3_burst_kling4-h2)",
    "scout failed: does not move on request (0 of 3 BURST draws above the floor)"])
def test_each_registered_failure_reads_not_run(tmp_path, reading):
    k = al.analyse(add_arm(make(tmp_path), scout=reading), b=50)["arms"]["kling4"]
    assert k["reading"] == f"not run: {reading}" and "A10-H1" not in k


@pytest.mark.parametrize("reading", [
    "scout passed: Kling joins A10's motion test",                                  # a prefix only
    "scout passed: Midjourney joins A10's motion test as a further engine",         # the other arm's pass
    "scout failed: does not move", "scout failed: does not move on request (2 of 3 BURST draws above the floor)"])
def test_any_other_scout_reading_is_refused(tmp_path, reading):
    with pytest.raises(SystemExit) as e:
        al.analyse(add_arm(make(tmp_path), scout=reading), b=50)
    assert repr(reading) in str(e.value)
