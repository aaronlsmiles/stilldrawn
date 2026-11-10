"""Tests for analysis/a12_ground_repeats.py (A12). Synthetic fixtures only.

    python -m pytest analysis/test_a12_ground_repeats.py
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a12_ground_repeats as ag  # noqa: E402

NOISE = {1: 0.0, 2: 0.1, 3: -0.1}


def put(p, c):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"metrics": {"line_drift": {"vs_frame0": {"chamfer_px": {"mean": c}}},
                                         "edge_decay": {"abs_slope_norm": c / 10},
                                         "style_drift": {"terminal": c / 100}}}))


def write(root, engine, values):
    """values: {(k, draw): chamfer}; edge and style follow chamfer."""
    for (k, d), c in values.items():
        put(ag.path_for(root, k, engine, d), c)


def write_a3(root, engine, values):
    """A3's unsuffixed local cell: {k: chamfer}."""
    for k, c in values.items():
        put(ag.a3_path(root, k, engine), c)


def readable(tmp_path, engine="gen4_turbo"):
    write(tmp_path, engine, {(k, d): 5 + 20 * (1 - k) + NOISE[d] for k in ag.KS for d in ag.DRAWS})
    return tmp_path


def test_local_draws_carry_d1_to_d3_and_turbo_draw_one_is_a3s_file(tmp_path):
    assert ag.path_for(tmp_path, 0.52, "wan22", 1).name == "ground-cu-line-1-v052_idle_wan22-d1.json"
    assert ag.path_for(tmp_path, 0.80, "ltx23", 3).name == "ground-cu-line-1-v080_idle_ltx23-d3.json"
    assert ag.path_for(tmp_path, 1.0, "gen4_turbo", 1).name == "ground-cu-line-1-v100_idle_gen4t.json"
    assert ag.path_for(tmp_path, 1.0, "gen4_turbo", 3).name == "ground-cu-line-1-v100_idle_gen4t-d3.json"
    assert ag.a3_path(tmp_path, 0.52, "wan22").name == "ground-cu-line-1-v052_idle_wan22.json"
    assert ag.path_for(tmp_path, 0.52, "wan22", 1).parent == tmp_path / "runs" / "metrics-ground"
    assert set(ag.ENGINES) == {"gen4_turbo", "wan22", "ltx23"}       # Gen-4.5 and H3 are not extended


def test_a_dose_response_above_the_noise_floor_is_readable(tmp_path):
    e = ag.analyse(readable(tmp_path))["engines"]["gen4_turbo"]
    assert (e["n_points"], e["n_expected"], e["n_missing"]) == (15, 15, 0)
    r = e["per_metric"]["chamfer"]
    assert r["n_points"] == 15
    assert r["reading"] == "monotone claim allowed (darker ground, more drift)"
    assert r["noise_floor"] == pytest.approx(0.2) and r["dose_effect"] == pytest.approx(9.6)
    assert r["rho_vs_k"] < -0.9 and r["p_perm_two_sided"] < 0.01 and r["rho_agrees"] is True
    edge, style = e["per_metric"]["edge"], e["per_metric"]["style"]
    assert edge["n_points"] == 15 and edge["dose_effect"] == pytest.approx(0.96)
    assert edge["noise_floor"] == pytest.approx(0.02)
    assert style["n_points"] == 15 and style["dose_effect"] == pytest.approx(0.096)
    assert style["noise_floor"] == pytest.approx(0.002)
    assert edge["reading"] == style["reading"] == "monotone claim allowed (darker ground, more drift)"
    assert e["a3"] is None                                           # Turbo: A3's cell is draw 1


def test_a_negative_dose_reads_as_less_drift(tmp_path):
    write(tmp_path, "wan22", {(k, d): 5 + 20 * k + NOISE[d] for k in ag.KS for d in ag.DRAWS})
    r = ag.analyse(tmp_path)["engines"]["wan22"]["per_metric"]["chamfer"]
    assert r["dose_effect"] == pytest.approx(-9.6)
    assert r["reading"] == "monotone claim allowed (darker ground, less drift)"


def spread(base, ranges):
    """{(k, draw): value}: per level, the median `base[k]` and the range `ranges[k]` across draws."""
    return {(k, d): base[k] + {1: 0.0, 2: ranges[k] / 2, 3: -ranges[k] / 2}[d] for k in ag.KS for d in ag.DRAWS}


def test_the_floor_is_the_median_of_the_per_level_ranges(tmp_path):
    ranges = dict(zip(ag.KS, (0.2, 0.4, 0.6, 5.0, 8.0)))             # median 0.6; mean 2.84, max 8
    base = dict(zip(ag.KS, (5.0, 6.0, 7.0, 7.5, 8.0)))               # dose 8 - 5 = 3.0
    write(tmp_path, "wan22", spread(base, ranges))
    r = ag.analyse(tmp_path)["engines"]["wan22"]["per_metric"]["chamfer"]
    assert r["noise_floor"] == pytest.approx(0.6) and r["dose_effect"] == pytest.approx(3.0)
    assert r["reading"] == "monotone claim allowed (darker ground, more drift)"


@pytest.mark.parametrize("dark, reading", [
    (7.0, "not readable at three draws"),                            # dose exactly 2 x floor: not above it
    (7.1, "monotone claim allowed (darker ground, more drift)"),     # dose 2.1
    (6.5, "not readable at three draws"),                            # dose 1.5
])
def test_the_threshold_is_strictly_above_twice_the_floor(tmp_path, dark, reading):
    base = {k: 5.0 for k in ag.KS} | {0.52: dark}
    write(tmp_path, "ltx23", spread(base, {k: 1.0 for k in ag.KS}))
    r = ag.analyse(tmp_path)["engines"]["ltx23"]["per_metric"]["chamfer"]
    assert r["noise_floor"] == pytest.approx(1.0) and r["dose_effect"] == pytest.approx(dark - 5.0)
    assert r["reading"] == reading


def test_rho_disagreeing_with_the_dose_is_flagged(tmp_path):
    base = dict(zip(ag.KS, (5.0, 9.0, 8.0, 1.0, 5.5)))               # dose +0.5, yet rho > 0
    write(tmp_path, "wan22", spread(base, {k: 0.1 for k in ag.KS}))
    r = ag.analyse(tmp_path)["engines"]["wan22"]["per_metric"]["chamfer"]
    assert r["dose_effect"] == pytest.approx(0.5) and r["rho_vs_k"] > 0 and r["rho_agrees"] is False
    assert r["reading"] == "monotone claim allowed (darker ground, more drift)"   # the flag does not change it
    assert "does not agree" in ag.markdown(ag.analyse(tmp_path))


def test_a_nan_value_is_a_missing_point_for_that_metric_only(tmp_path):
    readable(tmp_path)
    p = ag.path_for(tmp_path, 0.80, "gen4_turbo", 3)
    d = json.loads(p.read_text())
    d["metrics"]["line_drift"]["vs_frame0"]["chamfer_px"]["mean"] = float("nan")
    p.write_text(json.dumps(d))
    e = ag.analyse(tmp_path)["engines"]["gen4_turbo"]
    assert e["n_points"] == 15
    assert e["per_metric"]["chamfer"]["n_points"] == 14
    assert e["per_metric"]["chamfer"]["reading"] == "incomplete: 1 point missing"
    assert e["per_metric"]["edge"]["n_points"] == 15
    assert e["per_metric"]["edge"]["reading"].startswith("monotone claim allowed")


def test_a_noise_floor_that_swamps_the_dose_is_not_readable(tmp_path):
    big = {1: 0.0, 2: 3.0, 3: -3.0}
    write(tmp_path, "wan22", {(k, d): 5 + (1 - k) + big[d] for k in ag.KS for d in ag.DRAWS})
    r = ag.analyse(tmp_path)["engines"]["wan22"]["per_metric"]["chamfer"]
    assert r["reading"] == "not readable at three draws" and r["noise_floor"] == pytest.approx(6.0)


def test_a3s_local_cell_is_a_separate_point_never_in_the_floor_or_rho(tmp_path):
    readable(tmp_path, "wan22")
    before = ag.analyse(tmp_path)["engines"]["wan22"]
    write_a3(tmp_path, "wan22", {k: 1000.0 + k for k in ag.KS})      # wild, other hardware
    after = ag.analyse(tmp_path)["engines"]["wan22"]
    assert after["per_metric"] == before["per_metric"]               # series untouched
    assert after["n_points"] == 15
    assert before["a3"]["n_present"] == 0
    a3 = after["a3"]
    assert a3["label"] == "a3" and a3["n_present"] == 5
    assert a3["by_level"]["0.52"]["chamfer"] == pytest.approx(1000.52)


def test_turbo_unsuffixed_cell_counts_as_draw_one(tmp_path):
    write(tmp_path, "gen4_turbo", {(k, d): 5.0 + k + d for k in ag.KS for d in (2, 3)})
    e = ag.analyse(tmp_path)["engines"]["gen4_turbo"]
    assert e["n_points"] == 10 and e["n_missing"] == 5
    write_a3(tmp_path, "gen4_turbo", {k: 5.0 + k for k in ag.KS})     # the same files as draw 1
    e = ag.analyse(tmp_path)["engines"]["gen4_turbo"]
    assert e["n_points"] == 15 and e["n_missing"] == 0 and e["a3"] is None


def test_a_single_draw_has_no_floor_and_is_incomplete(tmp_path):
    write(tmp_path, "ltx23", {(k, 1): 5.0 + k for k in ag.KS})
    e = ag.analyse(tmp_path)["engines"]["ltx23"]
    r = e["per_metric"]["chamfer"]
    assert r["n_points"] == 5 and r["noise_floor"] is None
    assert r["reading"] == "incomplete: 10 points missing" and e["n_missing"] == 10
    assert all(level["n_draws"] == 1 for level in r["by_level"].values())


def test_one_missing_point_makes_the_reading_incomplete(tmp_path):
    readable(tmp_path)
    ag.path_for(tmp_path, 0.65, "gen4_turbo", 2).unlink()
    r = ag.analyse(tmp_path)["engines"]["gen4_turbo"]["per_metric"]["chamfer"]
    assert r["n_points"] == 14 and r["reading"] == "incomplete: 1 point missing"
    assert r["noise_floor"] == pytest.approx(0.2)                    # numbers still reported


def test_an_engine_with_no_files_is_reported_empty(tmp_path):
    e = ag.analyse(readable(tmp_path))["engines"]["ltx23"]
    assert e["n_points"] == 0 and e["per_metric"]["chamfer"]["reading"] == "incomplete: 15 points missing"
    assert e["per_metric"]["chamfer"]["rho_agrees"] is None
    assert "does not agree" not in ag.markdown(ag.analyse(tmp_path))


def test_outputs_are_written_and_reproducible(tmp_path):
    root = readable(tmp_path)
    write_a3(root, "wan22", {k: 77.25 for k in ag.KS})
    ag.main(["--fixtures", str(root)])
    out = root / "analysis" / "out"
    first = (out / "a12_ground.json").read_bytes()
    ag.main(["--fixtures", str(root)])
    assert (out / "a12_ground.json").read_bytes() == first
    md = (out / "a12_ground.md").read_text()
    assert "Gen-4 Turbo" in md and "(15 of 15 files)" in md and "15 points:" in md
    assert "permutation p (descriptive)" in md
    assert "a3 chamfer (other hardware)" in md and "| 77.250 |" in md


def test_real_data_is_refused_until_a12_is_public(tmp_path, monkeypatch):
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(tmp_path / "absent.md"))
    with pytest.raises(SystemExit) as e:
        ag.main([])
    assert "A12" in str(e.value) and "REFUSING" in str(e.value)


def test_fixtures_must_not_be_the_repository_or_inside_it(tmp_path):
    for inside in (ag.ROOT, ag.ROOT / "runs"):
        with pytest.raises(SystemExit) as e:
            ag.main(["--fixtures", str(inside)])
        assert "REFUSING" in str(e.value)
    marked = tmp_path / "copy"
    (marked / "analysis" / "adherence").mkdir(parents=True)
    (marked / "analysis" / "adherence" / "private-terms.txt").write_text("")
    for tree in (marked, marked / "sub"):                            # the marker's folder, or below it
        tree.mkdir(exist_ok=True)
        with pytest.raises(SystemExit) as e:
            ag.main(["--fixtures", str(tree)])
        assert "REFUSING" in str(e.value)
    assert not (marked / "analysis" / "out").exists() and not (marked / "sub" / "analysis").exists()


def test_fixtures_refuse_any_folder_at_or_under_the_root_without_the_marker(tmp_path, monkeypatch):
    """The release tree carries no private marker: the guard must still refuse it and its folders."""
    rel = tmp_path / "release"
    (rel / "runs").mkdir(parents=True)
    monkeypatch.setattr(ag, "ROOT", rel)
    for inside in (rel, rel / "runs", rel / "runs" / "new"):
        with pytest.raises(SystemExit) as e:
            ag.main(["--fixtures", str(inside)])
        assert "REFUSING" in str(e.value)
    assert not (rel / "analysis").exists() and not (rel / "runs" / "analysis").exists()
    assert ag.fixture_root(tmp_path / "beside") == (tmp_path / "beside").resolve()


def manifest(root, lines):
    """runs/manifest.jsonl from (cell_id, model_version) pairs, in order."""
    p = Path(root) / "runs" / "manifest.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps({"cell_id": c, "engine": "x", "model_version": mv, "out": f"runs/x/{c}.mp4"})
                         + "\n" for c, mv in lines))


def test_model_versions_are_read_per_draw_and_mixed_hardware_is_flagged(tmp_path):
    readable(tmp_path, "wan22")
    write_a3(tmp_path, "wan22", {k: 7.0 for k in ag.KS})
    before = ag.analyse(tmp_path)["engines"]["wan22"]["per_metric"]
    cells = [ag.draw_stem(k, "wan22", d) for k in ag.KS for d in ag.DRAWS]
    odd = ag.draw_stem(0.80, "wan22", 2)
    lines = [(odd, "Wan 2.2 [pod-a]")]                               # superseded: the last line wins
    lines += [(c, "Wan 2.2 [pod-b]" if c == odd else "Wan 2.2 [pod-a]") for c in cells]
    lines += [(ag.draw_stem(k, "wan22", None), "Wan 2.2 [old-box]") for k in ag.KS]   # A3's point
    manifest(tmp_path, lines)
    e = ag.analyse(tmp_path)["engines"]["wan22"]
    assert e["per_metric"] == before                                 # no reading changes
    assert len(e["draws"]) == 15 and [d["cell_id"] for d in e["draws"]] == cells
    by_cell = {d["cell_id"]: d["model_version"] for d in e["draws"]}
    assert by_cell[odd] == "Wan 2.2 [pod-b]" and by_cell[cells[0]] == "Wan 2.2 [pod-a]"
    assert e["model_versions"] == ["Wan 2.2 [pod-a]", "Wan 2.2 [pod-b]"]
    assert e["hardware"] == ["pod-a", "pod-b"] and e["hardware_mixed"] is True   # A3's box not counted
    assert e["a3"]["model_version"] == {f"{k:.2f}": "Wan 2.2 [old-box]" for k in ag.KS}
    md = ag.markdown(ag.analyse(tmp_path))
    assert "Wan 2.2 [pod-b]" in md and "hardware mixed" in md and "old-box" in md


def test_one_machine_is_not_mixed_and_turbo_reports_versions_without_hardware(tmp_path):
    readable(tmp_path, "ltx23")
    readable(tmp_path, "gen4_turbo")
    manifest(tmp_path, [(ag.draw_stem(k, "ltx23", d), "LTX-2.3 [pod-a]") for k in ag.KS for d in ag.DRAWS]
             + [(ag.draw_stem(k, "gen4_turbo", d), "gen4_turbo") for k in ag.KS for d in ag.DRAWS])
    res = ag.analyse(tmp_path)["engines"]
    assert res["ltx23"]["hardware"] == ["pod-a"] and res["ltx23"]["hardware_mixed"] is False
    assert res["gen4_turbo"]["model_versions"] == ["gen4_turbo"]
    assert res["gen4_turbo"]["hardware"] is None and res["gen4_turbo"]["hardware_mixed"] is None
    assert res["gen4_turbo"]["a3"] is None
    assert "hardware mixed" not in ag.markdown(ag.analyse(tmp_path))


def test_a_local_draw_without_a_hardware_string_counts_as_unrecorded(tmp_path):
    readable(tmp_path, "wan22")
    cells = [ag.draw_stem(k, "wan22", d) for k in ag.KS for d in ag.DRAWS]
    manifest(tmp_path, [(c, "Wan 2.2" if i == 0 else "Wan 2.2 [pod-a]") for i, c in enumerate(cells)])
    e = ag.analyse(tmp_path)["engines"]["wan22"]
    assert e["hardware"] == ["(not recorded)", "pod-a"] and e["hardware_mixed"] is True


def test_draws_without_a_manifest_line_report_none(tmp_path):
    readable(tmp_path, "wan22")
    e = ag.analyse(tmp_path)["engines"]["wan22"]
    assert all(d["model_version"] is None for d in e["draws"])
    assert e["model_versions"] == [] and e["hardware"] == [] and e["hardware_mixed"] is False
    assert e["n_draws_without_manifest_line"] == 15


def abandoned_lines(root, engine, hw):
    """A12.3.1: the lines ground_series.py abandon writes for a lost machine's series."""
    p = Path(root) / "runs" / "manifest.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        for d in ag.DRAWS:
            for k in ag.KS:
                f.write(json.dumps({"cell_id": ag.draw_stem(k, engine, d), "engine": engine, "draw": d,
                                    "model_version": f"Wan 2.2 [{hw}]", "out": None,
                                    "clip_kept_privately": False, "abandoned": "machine lost"}) + "\n")


def test_a_rerun_series_is_flagged_and_the_abandoned_draws_are_not_draws(tmp_path):
    readable(tmp_path, "wan22")
    readable(tmp_path, "ltx23")
    before = ag.analyse(tmp_path)["engines"]
    abandoned_lines(tmp_path, "wan22", "pod-a")                    # the lost machine
    cells = [ag.draw_stem(k, "wan22", d) for k in ag.KS for d in ag.DRAWS]
    p = tmp_path / "runs" / "manifest.jsonl"
    with p.open("a") as f:                                           # the re-run on one fresh machine
        f.write("".join(json.dumps({"cell_id": c, "model_version": "Wan 2.2 [pod-b]", "out": f"runs/wan22/{c}.mp4"})
                        + "\n" for c in cells))
    res = ag.analyse(tmp_path)["engines"]
    e = res["wan22"]
    assert e["per_metric"] == before["wan22"]["per_metric"]          # no reading changes
    assert e["series_rerun"] is True and res["ltx23"]["series_rerun"] is False
    assert res["gen4_turbo"]["series_rerun"] is None                 # hosted: no machine to lose
    assert e["model_versions"] == ["Wan 2.2 [pod-b]"]               # the abandoned lines are not draws
    assert e["hardware"] == ["pod-b"] and e["hardware_mixed"] is False
    md = ag.markdown(ag.analyse(tmp_path))
    note = ("so the series was re-run, once, on one fresh machine at the same cell ids and seeds (A12.3.1); "
            "if that machine was lost too, the series reads incomplete above.")
    assert md.count(note) == 1 and "re-run whole" not in md


def test_an_abandoned_draw_never_rerun_has_no_manifest_line(tmp_path):
    readable(tmp_path, "wan22")
    manifest(tmp_path, [(ag.draw_stem(k, "wan22", d), "Wan 2.2 [pod-a]") for k in ag.KS for d in ag.DRAWS])
    abandoned_lines(tmp_path, "wan22", "pod-a")                    # an abandoned line cancels an earlier one
    e = ag.analyse(tmp_path)["engines"]["wan22"]
    assert all(d["model_version"] is None for d in e["draws"]) and e["n_draws_without_manifest_line"] == 15
    assert e["series_rerun"] is True and e["hardware"] == []
