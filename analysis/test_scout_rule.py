"""Tests for analysis/scout_rule.py (A15.5, A16.7). Synthetic fixtures only: no scout clip exists.

    python -m pytest analysis/test_scout_rule.py
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "harness"))
import ladder  # noqa: E402
import scout  # noqa: E402
import scout_rule as sr  # noqa: E402

A15 = "### A15 — 2026-11-20: a Kling scout with a declared decision rule\n"
KLING = ["flint-cu-line-2--cu-line-1_kling4", "flint-act-line-2--act-tone-3_kling4",
         "flint-est-line-2--est-black-3_kling4"] + [f"act-black-3_burst_kling4-h{k}" for k in (1, 2, 3)]
IDLE = {"cu-line-1_idle_wan22": 0.001, "cu-line-1_idle_gen45": 0.003, "act-black-2_idle_h3": 0.002,
        "est-line-1_idle_ltx23": 0.004, "est-line-1_idle_gen4t": 0.005}


def motion_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"motion": {"headline_median_norm": value}}))


def ink_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"metrics": {"line_drift": {"vs_frame0": {"chamfer_px": {"mean": value}}}}}))


def corpus(root):
    """The frozen corpus's metric files: primary IDLE cells plus every kind the floor must leave out."""
    for stem, v in IDLE.items():
        motion_json(root / "runs" / "metrics-motion" / f"{stem}.json", v)
        ink_json(root / "runs" / "metrics" / f"{stem}.json", 1.0)
    for stem, v in (("cu-line-1_idle_wan22-r2", 9.0), ("act-black-3_idle_h3-h1", 9.0),
                    ("cu-line-1_burst_wan22", 9.0), ("flint-cu-line-2--cu-line-1_h3", 9.0),
                    ("ground-cu-line-1-v052_idle_wan22", 9.0), ("act-black-3_burst_sd2-h1", 9.0)):
        motion_json(root / "runs" / "metrics-motion" / f"{stem}.json", v)
        if not stem.startswith("ground-"):
            ink_json(root / "runs" / "metrics" / f"{stem}.json", 1.0)
    return root


def scout_tree(root, arm="kling_4", motions=(0.01, 0.01, 0.01), chamfers=None, refused=(), missing=(),
               record=True, unrecorded=()):
    """A scout that has run: clips, manifest lines, metric files for each cell and the metrics
    step's record (harness/scout.py), less any `unrecorded` cells."""
    corpus(root)
    sr.build_floor(root, out_root=root)
    sr.build_cells(root)
    cells = json.loads((root / sr.CELLS_JSON).read_text())[arm]
    folder = {"kling_4": "kling_4", "midjourney": "midjourney"}[arm]
    lines, bursts = [], iter(motions)
    for c in cells:
        cid = c["cell_id"]
        if cid in refused:
            lines.append({"cell_id": cid, "refused": True, "out": None, "seed": None})
            if c["motion"] == "BURST":
                next(bursts)
            continue
        if cid in missing:
            continue
        clip = root / "runs" / folder / f"{cid}.mp4"
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"clip")
        lines.append({"cell_id": cid, "out": f"runs/{folder}/{cid}.mp4", "seed": None})
        m = next(bursts) if c["motion"] == "BURST" else 0.02
        motion_json(root / "runs" / "metrics-motion-scout" / f"{cid}.json", m)
        ink_json(root / "runs" / "metrics-scout" / f"{cid}.json", (chamfers or {}).get(cid, 2.0))
    (root / "runs" / "manifest.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
    if record:
        rec = scout.metrics_record(arm, root)
        if unrecorded:
            p = root / ladder.ARMS[arm]["scout_metrics"]
            data = json.loads(p.read_text())
            for cid in unrecorded:
                data["cells"].pop(cid)
            p.write_text(json.dumps(data))
    return root


def test_the_floor_is_the_median_of_the_primary_idle_cells_only(tmp_path):
    rec = sr.build_floor(corpus(tmp_path), out_root=tmp_path)
    assert rec["floor"] == pytest.approx(0.003) and rec["n"] == 5
    assert sorted(rec["cells"]) == sorted(IDLE) and rec["engines"] == {"gen45": 1, "gen4t": 1, "h3": 1,
                                                                       "ltx23": 1, "wan22": 1}
    assert json.loads((tmp_path / sr.FLOOR_JSON).read_text()) == rec


def test_the_cell_lists_are_a5s_composition_for_each_arm(tmp_path):
    rec = sr.build_cells(tmp_path)
    assert [c["cell_id"] for c in rec["kling_4"]] == KLING
    assert [c["cell_id"] for c in rec["midjourney"]] == [c.replace("kling4", "mjv") for c in KLING]
    flint = rec["kling_4"][0]
    assert flint == {"cell_id": KLING[0], "motion": "FLINT", "panel": "cu-line-2", "last_panel": "cu-line-1"}
    assert rec["kling_4"][3] == {"cell_id": KLING[3], "motion": "BURST", "panel": "act-black-3", "draw": 1}


def test_the_shipped_files_are_what_the_builders_write(tmp_path):
    for name, builder in ((sr.CELLS_JSON, sr.build_cells), (sr.FLOOR_JSON, sr.build_floor)):
        shipped = sr.ROOT / name
        if not shipped.exists():
            pytest.skip(f"no {name} in this tree")
        if name == sr.FLOOR_JSON:
            # from the released files (A15.5): this tree when it is the public one, else the public
            # tree beside it; the file is then the same bytes in both forms
            src = sr.public_tree() if sr.private_tree(sr.ROOT) else sr.ROOT
            if not (src / "runs" / "metrics-motion").is_dir():
                pytest.skip("no public tree with released motion files beside this one")
            builder(src, out_root=tmp_path)
        else:
            builder(tmp_path)
        assert (tmp_path / name).read_bytes() == shipped.read_bytes(), name


def test_a_scout_that_moves_passes_with_the_registered_reading(tmp_path, capsys):
    root = scout_tree(tmp_path)
    rec = sr.read_scout("kling_4", root, today="2026-11-21")
    assert rec["reading"] == ladder.ARMS["kling_4"]["scout_passed"]
    saved = json.loads((root / "analysis" / "out" / "a15_scout.json").read_text())
    assert saved == rec and saved["floor"] == pytest.approx(0.003) and saved["rule"] == "A15.5"
    assert saved["cells"][KLING[3]] == {"motion": "BURST", "refused": False, "chamfer": 2.0, "motion_value": 0.01,
                                        "above_floor": True, "seed": None, "metrics_file_missing": False,
                                        "failures": []}
    assert "FINDINGS: A15 scout (kling_4), 2026-11-21: " + rec["reading"] in capsys.readouterr().out


@pytest.mark.parametrize("kwargs,reading", [
    ({"refused": (KLING[0], KLING[4])}, "scout failed: refused (2 of 6 cells)"),
    ({"refused": (KLING[0],), "chamfers": {KLING[1]: float("nan")}},
     f"scout failed: not measurable ({KLING[1]})"),
    ({"motions": (0.01, 0.001, 0.003)}, "scout failed: does not move on request (1 of 3 BURST draws above the floor)"),
    ({"refused": (KLING[3],), "motions": (0.01, 0.01, 0.01)},
     "scout failed: does not move on request (2 of 3 BURST draws above the floor)"),
])
def test_each_failure_reading_in_its_declared_order(tmp_path, kwargs, reading):
    if "2 of 3" in reading:                     # a refused BURST draw counts as not above: 2 left, still a pass
        rec = sr.read_scout("kling_4", scout_tree(tmp_path, **kwargs), today="2026-11-21")
        assert rec["reading"] == ladder.ARMS["kling_4"]["scout_passed"]
        return
    rec = sr.read_scout("kling_4", scout_tree(tmp_path, **kwargs), today="2026-11-21")
    assert rec["reading"] == reading and ladder.scout_failed(reading)


def test_a_refused_burst_draw_counts_as_not_above_the_floor(tmp_path):
    root = scout_tree(tmp_path, refused=(KLING[3],), motions=(0.01, 0.01, 0.001))
    assert sr.read_scout("kling_4", root)["reading"] == \
        "scout failed: does not move on request (1 of 3 BURST draws above the floor)"


def test_the_rule_is_read_once_and_only_when_every_cell_has_a_clip_or_a_refusal(tmp_path):
    root = scout_tree(tmp_path, missing=(KLING[2],))
    with pytest.raises(SystemExit) as e:
        sr.read_scout("kling_4", root)
    assert KLING[2] in str(e.value) and "not read" in str(e.value)
    root3 = scout_tree(tmp_path / "c")
    sr.read_scout("kling_4", root3)
    with pytest.raises(SystemExit) as e:
        sr.read_scout("kling_4", root3)
    assert "final" in str(e.value)


def test_the_floor_must_exist(tmp_path):
    root = scout_tree(tmp_path)
    (root / sr.FLOOR_JSON).unlink()
    with pytest.raises(SystemExit) as e:
        sr.read_scout("kling_4", root)
    assert "scout_floor.json" in str(e.value)


def test_a_midjourney_scout_without_an_end_frame_reads_its_three_burst_draws(tmp_path):
    root = scout_tree(tmp_path, arm="midjourney", refused=("act-black-3_burst_mjv-h1", "act-black-3_burst_mjv-h2"))
    with pytest.raises(SystemExit) as e:                          # A16.4.3 not yet answered
        sr.read_scout("midjourney", root)
    assert "a16_setup.json" in str(e.value)
    (root / ladder.ARMS["midjourney"]["setup"]).write_text(json.dumps({"end_frame": False}))
    rec = sr.read_scout("midjourney", root)
    assert rec["reading"] == "scout failed: refused (2 of 3 cells)" and len(rec["cells"]) == 3


def test_real_data_is_refused_until_the_amendment_is_public(tmp_path, monkeypatch):
    p = tmp_path / "PUBLIC-PREREGISTRATION.md"
    p.write_text("### A10 — 2026-11-20: ladder\n", encoding="utf-8")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(p))
    for arm, amendment in (("kling_4", "A15"), ("midjourney", "A16")):
        with pytest.raises(SystemExit) as e:
            sr.main(["--arm", arm])
        assert amendment in str(e.value)


def test_fixtures_refuse_the_repository(tmp_path):
    with pytest.raises(SystemExit) as e:
        sr.main(["--arm", "kling_4", "--fixtures", str(sr.ROOT)])
    assert "REFUSING --fixtures" in str(e.value)
    root = scout_tree(tmp_path / "t")
    assert sr.main(["--arm", "kling_4", "--fixtures", str(root)]) == 0




# The order enforced: the metrics step's record must name every
# delivered clip before a reading is written.
def test_without_the_metrics_record_the_rule_is_not_read(tmp_path):
    root = scout_tree(tmp_path, record=False)
    with pytest.raises(SystemExit) as e:
        sr.read_scout("kling_4", root)
    assert "metrics step not complete" in str(e.value) and "a15_scout_metrics.json" in str(e.value)
    assert not (root / "analysis" / "out" / "a15_scout.json").exists()


def test_a_delivered_clip_absent_from_the_record_means_the_metrics_step_has_not_run(tmp_path):
    root = scout_tree(tmp_path, unrecorded=(KLING[4],))
    with pytest.raises(SystemExit) as e:
        sr.read_scout("kling_4", root)
    assert "metrics step not complete" in str(e.value) and KLING[4] in str(e.value)
    assert not (root / "analysis" / "out" / "a15_scout.json").exists()


def test_a_metric_file_changed_since_the_metrics_step_is_refused(tmp_path):
    root = scout_tree(tmp_path)
    ink_json(root / "runs" / "metrics-scout" / f"{KLING[3]}.json", 99.0)
    with pytest.raises(SystemExit) as e:
        sr.read_scout("kling_4", root)
    assert KLING[3] in str(e.value) and "changed since the metrics step" in str(e.value)



def test_the_floor_refuses_a_private_tree(tmp_path):
    root = corpus(tmp_path / "private")
    (root / "analysis" / "adherence").mkdir(parents=True)
    (root / "analysis" / "adherence" / "private-terms.txt").write_text("x\n")
    with pytest.raises(SystemExit) as e:
        sr.build_floor(root)
    assert "private" in str(e.value) and "released" in str(e.value)


def test_the_shipped_floor_names_public_ids_only(tmp_path):
    shipped = sr.ROOT / sr.FLOOR_JSON
    if not shipped.exists():
        pytest.skip("no scout_floor.json in this tree")
    rec = json.loads(shipped.read_text())
    assert rec["n"] == 54 and rec["floor"] == pytest.approx(0.0016057083117110389)
    # The creator-IP panel's five cells carry the released id and no other (written so that the check
    # reads the same in the release, which rewrites that panel's working id wherever it appears).
    assert sorted(c for c in rec["cells"] if "-act-tank-1_" in c) == [
        f"cip-act-tank-1_idle_{e}" for e in ("gen45", "gen4t", "h3", "ltx23", "wan22")]



# Addendum (8) and (9): a metric file deleted after the record is refused; a tool failure becomes
# "not measurable" only after one confirming re-run of the metrics step has failed again.
FAIL = {"tool": "inkstab.py", "reason": "CalledProcessError: cannot decode"}


def failed_once(tmp_path, cell=KLING[1], again=None):
    """A scout whose metrics step failed on `cell` (no inkstab file); `again`: a confirming re-run
    that fails ("fail") or recovers ("recover")."""
    root = scout_tree(tmp_path, record=False)
    good = (root / "runs" / "metrics-scout" / f"{cell}.json").read_text()
    (root / "runs" / "metrics-scout" / f"{cell}.json").unlink()
    scout.metrics_record("kling_4", root, failures={cell: [FAIL]}, attempted={cell})
    if again == "fail":
        scout.metrics_record("kling_4", root, failures={cell: [FAIL]}, attempted={cell})
    elif again == "recover":
        (root / "runs" / "metrics-scout" / f"{cell}.json").write_text(good)
        scout.metrics_record("kling_4", root, attempted={cell})
    return root


@pytest.mark.parametrize("folder", ["metrics-scout", "metrics-motion-scout"])
def test_a_metric_file_deleted_after_the_record_is_refused(tmp_path, folder):
    root = scout_tree(tmp_path)
    (root / "runs" / folder / f"{KLING[5]}.json").unlink()
    with pytest.raises(SystemExit) as e:
        sr.read_scout("kling_4", root)
    assert KLING[5] in str(e.value) and "deleted since the metrics step" in str(e.value)
    assert not (root / "analysis" / "out" / "a15_scout.json").exists()


def test_a_first_tool_failure_awaits_a_confirming_rerun(tmp_path):
    root = failed_once(tmp_path)
    with pytest.raises(SystemExit) as e:
        sr.read_scout("kling_4", root)
    assert "metrics step not complete: 1 clips await a confirming re-run" in str(e.value) and KLING[1] in str(e.value)
    assert not (root / "analysis" / "out" / "a15_scout.json").exists()


def test_a_confirmed_failure_reads_not_measurable_with_its_reasons(tmp_path, capsys):
    root = failed_once(tmp_path, again="fail")
    rec = sr.read_scout("kling_4", root)
    assert rec["reading"] == f"scout failed: not measurable ({KLING[1]})"
    assert rec["cells"][KLING[1]]["failures"][0]["reason"] == FAIL["reason"]
    out = capsys.readouterr().out
    assert f"{KLING[1]}: inkstab.py: {FAIL['reason']}" in out


def test_a_rerun_that_recovers_lets_the_rule_read(tmp_path):
    root = failed_once(tmp_path, again="recover")
    assert sr.read_scout("kling_4", root)["reading"] == ladder.ARMS["kling_4"]["scout_passed"]


def test_unmeasurable_cells_are_joined_by_comma_and_space(tmp_path):
    root = failed_once(tmp_path, cell=KLING[4], again="fail")
    p = root / "runs" / "metrics-scout" / f"{KLING[0]}.json"            # a non-finite value, recorded as made
    ink_json(p, float("nan"))
    scout.metrics_record("kling_4", root)
    assert sr.read_scout("kling_4", root)["reading"] == f"scout failed: not measurable ({KLING[0]}, {KLING[4]})"


# The release: the metrics record hashes each metric file in its release form (the
# tree's absolute prefix removed, as the release build strips it), and `--rerun` re-derives a shipped
# reading in the release tree, keeping its date, so the build can compare it byte for byte.
def with_absolute_paths(root):
    """Give every scout metric file the tree's absolute paths, as the frozen tools write them."""
    for folder in ("metrics-scout", "metrics-motion-scout"):
        for p in (root / "runs" / folder).iterdir():
            d = json.loads(p.read_text())
            d["clip"] = f"{root}/runs/kling_4/{p.stem}.mp4"
            p.write_text(json.dumps(d))


def release_copy(root, dest):
    """The tree as the release ships it: the absolute prefix stripped from the metric files."""
    import shutil
    shutil.copytree(root, dest)
    for folder in ("metrics-scout", "metrics-motion-scout"):
        for p in (dest / "runs" / folder).iterdir():
            p.write_text(p.read_text().replace(f"{root}/", ""))
    return dest


def test_the_record_hashes_the_release_form_so_the_release_tree_reads_the_same(tmp_path):
    root = scout_tree(tmp_path / "private", record=False)
    with_absolute_paths(root)
    scout.metrics_record("kling_4", root)
    rel = release_copy(root, tmp_path / "release")
    private_reading = sr.read_scout("kling_4", root, today="2026-11-21")
    released_reading = sr.read_scout("kling_4", rel, today="2026-11-21")
    assert private_reading == released_reading
    assert (root / "analysis/out/a15_scout.json").read_bytes() == (rel / "analysis/out/a15_scout.json").read_bytes()


def test_rerun_reproduces_the_shipped_reading_byte_for_byte(tmp_path):
    root = scout_tree(tmp_path / "private", record=False)
    with_absolute_paths(root)
    scout.metrics_record("kling_4", root)
    sr.read_scout("kling_4", root, today="2026-11-21")
    rel = release_copy(root, tmp_path / "release")
    shipped = (rel / "analysis/out/a15_scout.json").read_bytes()
    sr.rerun_scout("kling_4", rel)
    assert (rel / "analysis/out/a15_scout.json").read_bytes() == shipped           # the date kept, the inputs equal
    motion = rel / "runs" / "metrics-motion-scout" / f"{KLING[3]}.json"
    motion.write_text(json.dumps({"motion": {"headline_median_norm": 0.0}}))
    with pytest.raises(SystemExit):                                               # a changed input is caught
        sr.rerun_scout("kling_4", rel)


def test_rerun_refuses_a_private_tree_and_a_tree_without_a_reading(tmp_path):
    root = scout_tree(tmp_path / "t")
    with pytest.raises(SystemExit) as e:
        sr.rerun_scout("kling_4", root)
    assert "no reading" in str(e.value)
    sr.read_scout("kling_4", root)
    (root / "analysis" / "adherence").mkdir(parents=True)
    (root / "analysis" / "adherence" / "private-terms.txt").write_text("x\n")
    with pytest.raises(SystemExit) as e:
        sr.rerun_scout("kling_4", root)
    assert "private" in str(e.value)
