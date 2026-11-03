"""Tests for metrics/masked.py (A9). Synthetic data only: no clip, no line map,
no released value is read here.

    python -m pytest metrics/test_masked.py
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inkstab  # noqa: E402
import masked as mk  # noqa: E402

RNG = np.random.default_rng(7)


def lines(h, w, rows=(), cols=()):
    m = np.zeros((h, w), dtype=bool)
    for r in rows:
        m[r, :] = True
    for c in cols:
        m[:, c] = True
    return m


def random_maps(n, h=36, w=64, p=0.04):
    return [RNG.random((h, w)) < p for _ in range(n)]


def png(path, arr):
    import imageio.v3 as iio
    path.parent.mkdir(parents=True, exist_ok=True)
    iio.imwrite(path, arr)


def fake_tree(root, clip_hw=(36, 64), panel_wh=(84, 48)):
    """A minimal repo: manifest, released metrics JSONs, panels and line-art layers."""
    pw, ph = panel_wh
    cells = [
        # (cell_id, motion line, refused, has metrics json)
        ("act-line-1_idle_wan22", "IDLE", False, True),
        ("act-line-1_idle_wan22", "IDLE", False, True),            # repeated: last line wins
        ("xyz-act-tank-1_burst_gen45", "BURST", False, True),       # private creator-IP id
        ("act-line-1_idle_gen45-r2", "IDLE", False, True),          # replicate: excluded
        ("cu-tone-3_idle_gen4t", "IDLE", True, False),              # refused: excluded
        ("ground-cu-line-1-v052_idle_gen4t", "IDLE", False, True),  # ground series: excluded
        ("flint-a--b_h3", "FLINT", False, True),                    # FLINT: excluded
        ("act-line-1_campush_wan22", "CAMPUSH", False, True),       # not a Test 2 class
        ("est-line-9_burst_h3", "BURST", False, False),             # no released metrics: excluded
    ]
    lines_out = []
    for i, (cid, motion, refused, has_json) in enumerate(cells):
        rec = {"cell_id": cid, "motion_class": motion, "out": f"runs/x/{cid}-take{i}.mp4"}
        if refused:
            rec["refused"] = True
        lines_out.append(json.dumps(rec))
        if has_json:
            mj = root / "runs" / "metrics" / f"{cid}.json"
            mj.parent.mkdir(parents=True, exist_ok=True)
            mj.write_text(json.dumps({"n_frames": 5, "resolution": list(clip_hw), "metrics": {"line_drift": {
                "vs_frame0": {"chamfer_px": {"mean": 1.0}}}}}))
    (root / "runs" / "manifest.jsonl").write_text("\n".join(lines_out) + "\n")
    for panel in ("act-line-1", "xyz-act-tank-1"):
        png(root / "dataset" / "panels" / f"{panel}.png", np.full((ph, pw, 3), 255, np.uint8))
        art = np.full((ph * 2, pw * 2), 255, np.uint8)           # black-on-white, twice the panel size
        art[ph // 2: ph // 2 + 2, :] = 0
        art[:, pw: pw + 2] = 0
        png(root / "dataset" / "lineart" / f"{panel}-lines.png", art)
    return root


# ----------------------------------------------------------------- ids, cells
def test_public_id_maps_only_the_creator_ip_prefix():
    assert mk.public_id("xyz-act-tank-1_burst_gen45") == "cip-act-tank-1_burst_gen45"
    assert mk.public_id("cip-act-tank-1_idle_h3") == "cip-act-tank-1_idle_h3"
    assert mk.public_id("act-line-1_idle_wan22") == "act-line-1_idle_wan22"
    assert mk.public_id("chain-est-cosmic-1_burst_ltx23") == "chain-est-cosmic-1_burst_ltx23"


def test_a9_cells_keeps_primary_idle_and_burst_only(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    assert [c["public_id"] for c in cells] == ["act-line-1_idle_wan22", "cip-act-tank-1_burst_gen45"]
    first = cells[0]
    assert first["clip"] == "runs/x/act-line-1_idle_wan22-take1.mp4"      # the last manifest line wins
    assert first["engine"] == "wan22" and first["motion"] == "idle"
    assert first["released_px"] == 1.0 and first["released_n_frames"] == 5
    tank = cells[1]
    assert tank["cell_id"] == "xyz-act-tank-1_burst_gen45" and tank["panel"] == "xyz-act-tank-1"
    assert tank["public_panel"] == "cip-act-tank-1" and tank["engine"] == "gen4.5"


# -------------------------------------------------------------------- mapping
def test_crop_geometry():
    assert mk.crop_geometry((1344, 768), (704, 1280), "stretch") == (704, 1280, 0, 0)
    assert mk.crop_geometry((1344, 768), (704, 1280), "centre-crop") == (731, 1280, 13, 0)
    assert mk.crop_geometry((1024, 1792), (1280, 720), "centre-crop") == (1280, 731, 0, 5)
    assert mk.crop_geometry((1280, 720), (720, 1280), "centre-crop") == (720, 1280, 0, 0)
    with pytest.raises(ValueError):
        mk.crop_geometry((10, 10), (10, 10), "letterbox")


def test_stretch_is_inkstabs_resize():
    from skimage.transform import resize
    img = RNG.random((48, 84))
    assert np.array_equal(mk.map_to_grid(img, (36, 64), "stretch"), resize(img, (36, 64), anti_aliasing=True))


def test_centre_crop_keeps_the_centre_column_centred():
    img = np.zeros((48, 96))
    img[:, 47:49] = 1.0                       # a bar at the panel's centre
    out = mk.map_to_grid(img, (40, 40), "centre-crop")
    assert out.shape == (40, 40)
    assert abs(int(np.argmax(out.sum(axis=0))) - 19.5) <= 1


def test_lineart_reference_finds_the_layer_lines(tmp_path):
    root = fake_tree(tmp_path)
    ref = mk.lineart_reference(root, "act-line-1", (36, 64), "stretch")
    assert ref.shape == (36, 64) and ref.any() and ref.mean() < 0.2


# ----------------------------------------------------------------------- gate
def test_whole_frame_series_is_the_frozen_series():
    maps = random_maps(6)
    maps[3] = np.zeros_like(maps[3])          # an empty frame stays None
    expect = [inkstab._chamfer(m, maps[0]) for m in maps[1:]]
    got = mk.whole_frame_series(maps)
    assert got == expect and got[2] is None


def _fake_io(maps):
    frames = np.zeros((len(maps),) + maps[0].shape + (3,), np.uint8)
    return (lambda path: (frames, 24.0)), (lambda fr, device: [m.copy() for m in maps])


def _gate_cell(root, released):
    cell = dict(mk.a9_cells(root)[0])
    cell["released_px"] = released
    return cell


def test_gate_clip_pass_and_each_fail_reason(tmp_path):
    root = fake_tree(tmp_path)
    maps = random_maps(5)
    value = inkstab._stats(mk.whole_frame_series(maps))["mean"]
    load, extract = _fake_io(maps)
    rec = mk.gate_clip(_gate_cell(root, value), root, "mps", "mps", load=load, extract=extract)
    assert rec["pass"] and rec["chamfer_px"] == value and rec["abs_diff_px"] == 0.0
    assert rec["tolerance_px"] == max(0.01, 0.005 * value)
    assert set(rec["geometry"]) == {"stretch", "centre-crop"} and rec["panel_px"] == [84, 48]
    assert not mk.gate_clip(_gate_cell(root, value + 0.5), root, "mps", "mps", load=load, extract=extract)["pass"]
    assert not mk.gate_clip(_gate_cell(root, value), root, "cpu", "mps", load=load, extract=extract)["pass"]
    cell = _gate_cell(root, value)
    cell["released_n_frames"] = 6
    assert not mk.gate_clip(cell, root, "mps", "mps", load=load, extract=extract)["pass"]
    cell = _gate_cell(root, value)
    cell["released_grid"] = [64, 36]
    assert not mk.gate_clip(cell, root, "mps", "mps", load=load, extract=extract)["pass"]


def test_within_tolerance_boundaries_are_inclusive():
    # absolute floor: 0.01 px up to a released value of 2 px (0.5 % of 2 = 0.01)
    assert mk.within_tolerance(0.01, 0.0) and not mk.within_tolerance(0.0100001, 0.0)
    assert mk.within_tolerance(1.0 + 0.0099, 1.0) and not mk.within_tolerance(1.0 + 0.0101, 1.0)
    assert mk.within_tolerance(1.0 - 0.0099, 1.0) and not mk.within_tolerance(1.0 - 0.0101, 1.0)
    # relative above 2 px: 0.5 % of 4 px is 0.02 px
    assert mk.gate_tolerance(1.0) == 0.01 and mk.gate_tolerance(4.0) == 0.02
    assert mk.within_tolerance(4.0199, 4.0) and not mk.within_tolerance(4.0201, 4.0)
    # missing values never pass
    assert not mk.within_tolerance(None, 1.0) and not mk.within_tolerance(1.0, None)


def test_gate_clip_with_no_released_value_fails_instead_of_raising(tmp_path):
    root = fake_tree(tmp_path)
    maps = random_maps(5)
    load, extract = _fake_io(maps)
    for released in (None, "missing"):
        cell = _gate_cell(root, released)
        if released == "missing":
            del cell["released_px"]
        rec = mk.gate_clip(cell, root, "mps", "mps", load=load, extract=extract)
        assert rec["pass"] is False and "no released value" in rec["reason"]
        assert rec["chamfer_px_released"] is None and rec["tolerance_px"] is None
        assert rec["abs_diff_px"] is None


def test_gate_clip_pass_has_empty_reason_and_fail_names_its_reason(tmp_path):
    root = fake_tree(tmp_path)
    maps = random_maps(5)
    value = inkstab._stats(mk.whole_frame_series(maps))["mean"]
    load, extract = _fake_io(maps)
    assert mk.gate_clip(_gate_cell(root, value), root, "mps", "mps", load=load, extract=extract)["reason"] == ""
    assert "device" in mk.gate_clip(_gate_cell(root, value), root, "cpu", "mps", load=load, extract=extract)["reason"]
    assert "value" in mk.gate_clip(_gate_cell(root, value + 0.5), root, "mps", "mps", load=load, extract=extract)["reason"]


def test_gate_leaves_no_spatial_data_on_disk(tmp_path):
    """D3: the gate writes its part JSON (and the parts folder's own .gitignore) and nothing else."""
    root = fake_tree(tmp_path)
    maps = random_maps(5)
    value = inkstab._stats(mk.whole_frame_series(maps))["mean"]
    load, extract = _fake_io(maps)
    cells = [_gate_cell(root, value)]

    def real_gate(cell, root_, device, expect):
        return mk.gate_clip(cell, root_, device, expect, load=load, extract=extract)

    before = {p.relative_to(root) for p in root.rglob("*") if p.is_file()}
    mk.run_gate(root, cells, "mps", ENV, gate_one=real_gate, log=lambda s: None)
    after = {p.relative_to(root) for p in root.rglob("*") if p.is_file()}
    parts = Path(mk.PARTS)
    assert after - before == {parts / ".gitignore", parts / f"{cells[0]['public_id']}.json"}
    assert before - after == set()
    part = root / mk.PARTS / f"{cells[0]['public_id']}.json"
    assert part.stat().st_size < 4096 and json.loads(part.read_text())["pass"] is True


def test_gate_refuses_once_any_mask_file_exists(tmp_path, monkeypatch):
    import argparse
    monkeypatch.setattr(mk, "ROOT", tmp_path)
    args = argparse.Namespace(first=None, expect_device="mps", redo=False)
    mk.refuse_if_masks_exist(tmp_path)                       # no masks folder: fine
    (tmp_path / "dataset" / "masks").mkdir(parents=True)
    mk.refuse_if_masks_exist(tmp_path)                       # empty folder: fine
    (tmp_path / "dataset" / "masks" / "allowed-agent.json").write_text("{}")
    with pytest.raises(SystemExit, match="mask"):
        mk.refuse_if_masks_exist(tmp_path)
    with pytest.raises(SystemExit, match="allowed-agent.json"):
        mk.cmd_gate(args)                                    # refuses before reading a single clip


def test_code_identity_hashes_the_two_files_and_survives_a_missing_git(tmp_path):
    ident = mk.code_identity(root=tmp_path / "no-such-repo")
    here = Path(mk.__file__).resolve().parent
    assert ident["inkstab_sha256"] == mk.sha256_file(here / "inkstab.py")
    assert ident["masked_sha256"] == mk.sha256_file(here / "masked.py")
    assert ident["git_commit"] == "unknown"


def _fake_record(cell, root, device, expect_device):
    return {"cell_id": cell["public_id"], "engine": cell["engine"], "motion": cell["motion"],
            "n_frames": 5, "n_frames_released": 5, "grid": [36, 64], "grid_released": [36, 64],
            "device": device, "chamfer_px": 1.0, "chamfer_px_released": 1.0, "abs_diff_px": 0.0,
            "tolerance_px": 0.01, "pass": True, "panel_px": [84, 48],
            "geometry": {"stretch": 2.0, "centre-crop": 3.0}}


ENV = {"netG_sha256": "0" * 64, "torch": "x", "device": "mps", "python": "3.12", "numpy": "x",
       "scipy": "x", "scikit_image": "x", "inkstab_sha256": "1" * 64, "masked_sha256": "2" * 64,
       "git_commit": "3" * 40, "expect_device": "mps"}


def test_run_gate_resumes_and_writes_only_small_scalar_parts(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    calls = []

    def counting(cell, root_, device, expect):
        calls.append(cell["public_id"])
        return _fake_record(cell, root_, device, expect)

    mk.run_gate(root, cells, "mps", ENV, gate_one=counting, log=lambda s: None)
    mk.run_gate(root, cells, "mps", ENV, gate_one=counting, log=lambda s: None)
    assert calls == [c["public_id"] for c in cells]          # second run skipped both
    parts = root / mk.PARTS
    names = sorted(p.name for p in parts.iterdir())
    assert names == [".gitignore", "act-line-1_idle_wan22.json", "cip-act-tank-1_burst_gen45.json"]
    assert (parts / ".gitignore").read_text() == "*\n"
    for p in parts.glob("*.json"):
        assert p.stat().st_size < 4096                       # scalars only: no line map, no series
    mk.run_gate(root, cells[:1], "mps", ENV, redo=True, gate_one=counting, log=lambda s: None)
    assert calls[-1] == cells[0]["public_id"]


def test_finalise_gate_writes_sorted_csvs_and_summary(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    assert mk.finalise_gate(root, cells) is None             # nothing scored yet
    mk.run_gate(root, cells, "mps", ENV, gate_one=_fake_record, log=lambda s: None)
    assert mk.finalise_gate(root, cells) == 2
    with open(root / mk.GATE_CSV) as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == mk.GATE_FIELDS
    assert [r["cell_id"] for r in rows] == ["act-line-1_idle_wan22", "cip-act-tank-1_burst_gen45"]
    assert rows[0]["grid"] == "36x64" and rows[0]["pass"] == "true" and rows[0]["chamfer_px"] == "1.0"
    with open(root / mk.GEOM_CSV) as f:
        geo = list(csv.DictReader(f))
    assert list(geo[0]) == mk.GEOM_FIELDS and geo[0]["chamfer_centre_crop_px"] == "3.0"
    md = (root / mk.GATE_MD).read_text()
    assert "PASS (2 of 2 clips pass)" in md and "netG_sha256" in md and '"version": "inkstab 1.0' in md
    first = (root / mk.GATE_CSV).read_bytes()
    mk.finalise_gate(root, cells)
    assert (root / mk.GATE_CSV).read_bytes() == first        # deterministic


def test_finalise_gate_refuses_mixed_environments(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    mk.run_gate(root, cells, "mps", ENV, gate_one=_fake_record, log=lambda s: None)
    p = root / mk.PARTS / f"{cells[1]['public_id']}.json"
    rec = json.loads(p.read_text())
    rec["env"]["torch"] = "other"
    p.write_text(json.dumps(rec))
    with pytest.raises(SystemExit, match="different environments"):
        mk.finalise_gate(root, cells)


def _set_env(root, cell, **changes):
    p = root / mk.PARTS / f"{cell['public_id']}.json"
    rec = json.loads(p.read_text())
    rec["env"].update(changes)
    p.write_text(json.dumps(rec))


def test_finalise_gate_tolerates_changed_masked_code_and_commit_but_not_inkstab(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    mk.run_gate(root, cells, "mps", ENV, gate_one=_fake_record, log=lambda s: None)
    _set_env(root, cells[1], masked_sha256="9" * 64, git_commit="8" * 40)
    assert mk.finalise_gate(root, cells) == 2                # resumed run, only non-gate code moved
    md = (root / mk.GATE_MD).read_text()
    assert "9" * 64 in md and "2" * 64 in md                 # both masked.py hashes are shown
    for key in ("inkstab_sha256", "masked_sha256", "git_commit", "expect_device"):
        assert key in md
    _set_env(root, cells[1], inkstab_sha256="7" * 64)
    with pytest.raises(SystemExit, match="different environments"):
        mk.finalise_gate(root, cells)


def test_choose_mappings_lower_median_wins_and_ties_stretch():
    rows = [
        {"engine": "wan22", "chamfer_stretch_px": "3.0", "chamfer_centre_crop_px": "1.0"},
        {"engine": "wan22", "chamfer_stretch_px": "3.0", "chamfer_centre_crop_px": "2.0"},
        {"engine": "h3-fal", "chamfer_stretch_px": "1.5", "chamfer_centre_crop_px": "1.5"},
        {"engine": "gen4.5", "chamfer_stretch_px": "1.0", "chamfer_centre_crop_px": "2.0"},
    ]
    assert mk.choose_mappings(rows) == {"wan22": "centre-crop", "h3-fal": "stretch", "gen4.5": "stretch"}


# ------------------------------------------------- robustness (pre-run hardening)
def _log():
    lines = []
    return lines, lines.append


def test_run_gate_logs_start_continues_after_an_error_and_reports_it(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)

    def flaky(cell, root_, device, expect):
        if cell["public_id"] == cells[0]["public_id"]:
            raise RuntimeError("boom")
        return _fake_record(cell, root_, device, expect)

    lines, log = _log()
    failed = mk.run_gate(root, cells, "mps", ENV, gate_one=flaky, log=log)
    assert failed and failed[0][0] == cells[0]["public_id"] and "boom" in failed[0][1]
    parts = root / mk.PARTS
    assert not (parts / f"{cells[0]['public_id']}.json").exists()           # no part for the failure
    assert (parts / f"{cells[1]['public_id']}.json").exists()               # the run went on
    text = "\n".join(lines)
    assert f"[gate 1/2] start {cells[0]['public_id']}" in text and f"[gate 2/2] start {cells[1]['public_id']}" in text
    assert "boom" in text and "1 clip(s) failed" in text
    assert mk.finalise_gate(root, cells) is None                           # still refuses while a part is missing


def test_run_gate_does_not_swallow_keyboard_interrupt(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)

    def interrupted(cell, root_, device, expect):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        mk.run_gate(root, cells, "mps", ENV, gate_one=interrupted, log=lambda s: None)


def test_run_gate_logs_resume_count_rss_and_eta(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    mk.run_gate(root, cells[:1], "mps", ENV, gate_one=_fake_record, log=lambda s: None)
    lines, log = _log()
    mk.run_gate(root, cells, "mps", ENV, gate_one=_fake_record, log=log)
    text = "\n".join(lines)
    assert "resuming: 1 of 2 done" in text and "MB" in text and "eta" in text
    assert mk.max_rss_mb() > 0


def _part(root, cell):
    return root / mk.PARTS / f"{cell['public_id']}.json"


@pytest.mark.parametrize("damage", ["empty", "truncated", "other-env", "other-released", "other-cell", "missing-keys"])
def test_resume_reruns_stale_or_damaged_parts(tmp_path, damage):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    mk.run_gate(root, cells, "mps", ENV, gate_one=_fake_record, log=lambda s: None)
    p = _part(root, cells[0])
    rec = json.loads(p.read_text())
    if damage == "empty":
        p.write_text("")
    elif damage == "truncated":
        p.write_text(p.read_text()[:60])
    elif damage == "other-env":
        rec["env"]["inkstab_sha256"] = "f" * 64
        p.write_text(json.dumps(rec))
    elif damage == "other-released":
        rec["chamfer_px_released"] = 9.9
        p.write_text(json.dumps(rec))
    elif damage == "other-cell":
        rec["cell_id"] = "somebody-else"
        p.write_text(json.dumps(rec))
    else:
        del rec["geometry"]
        p.write_text(json.dumps(rec))
    calls = []

    def counting(cell, root_, device, expect):
        calls.append(cell["public_id"])
        return _fake_record(cell, root_, device, expect)

    lines, log = _log()
    mk.run_gate(root, cells, "mps", ENV, gate_one=counting, log=log)
    assert calls == [cells[0]["public_id"]]                                # only the damaged one reran
    assert any("stale part, re-running" in s for s in lines)
    assert json.loads(p.read_text())["cell_id"] == cells[0]["public_id"]


def test_resume_ignores_a_changed_masked_hash_and_commit(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    mk.run_gate(root, cells, "mps", ENV, gate_one=_fake_record, log=lambda s: None)
    newer = dict(ENV, masked_sha256="a" * 64, git_commit="b" * 40, git_dirty=True)
    calls = []
    mk.run_gate(root, cells, "mps", newer, gate_one=lambda *a: calls.append(a) or _fake_record(*a),
                log=lambda s: None)
    assert calls == []


def test_leftover_tmp_file_is_harmless_and_cleaned_up(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    parts = root / mk.PARTS
    parts.mkdir(parents=True)
    (parts / f"{cells[0]['public_id']}.json.tmp").write_text('{"half": ')
    mk.run_gate(root, cells, "mps", ENV, gate_one=_fake_record, log=lambda s: None)
    assert sorted(p.name for p in parts.iterdir()) == [".gitignore", "act-line-1_idle_wan22.json",
                                                      "cip-act-tank-1_burst_gen45.json"]
    assert mk.finalise_gate(root, cells) == 2


def test_write_atomic_fsyncs_before_replacing(tmp_path, monkeypatch):
    order = []
    real_fsync, real_replace = mk.os.fsync, mk.os.replace
    monkeypatch.setattr(mk.os, "fsync", lambda fd: (order.append("fsync"), real_fsync(fd))[1])
    monkeypatch.setattr(mk.os, "replace", lambda a, b: (order.append("replace"), real_replace(a, b))[1])
    mk.write_atomic(tmp_path / "x.json", "{}")
    assert order == ["fsync", "replace"] and (tmp_path / "x.json").read_text() == "{}"


def test_cmd_gate_aborts_on_the_wrong_device_before_any_work(tmp_path, monkeypatch):
    import argparse
    monkeypatch.setattr(mk, "ROOT", tmp_path)
    monkeypatch.setattr(mk.inkstab, "_device", lambda: "cpu")
    monkeypatch.setattr(mk, "environment", lambda *a, **k: pytest.fail("environment() must not be reached"))
    with pytest.raises(SystemExit, match="device"):
        mk.cmd_gate(argparse.Namespace(first=None, expect_device="mps", redo=False))


def _patched_cmd_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(mk, "ROOT", fake_tree(tmp_path))
    monkeypatch.setattr(mk, "A9_N_CLIPS", 2)
    monkeypatch.setattr(mk.inkstab, "_device", lambda: "mps")
    monkeypatch.setattr(mk, "environment", lambda device, expect="mps": dict(ENV))
    return mk.ROOT


def test_cmd_gate_returns_one_on_failing_clips_and_zero_on_a_clean_run(tmp_path, monkeypatch):
    import argparse
    root = _patched_cmd_gate(tmp_path, monkeypatch)
    cells = mk.a9_cells(root)

    def one_bad(cell, root_, device, expect):
        rec = _fake_record(cell, root_, device, expect)
        if cell["public_id"] == cells[1]["public_id"]:
            rec.update({"chamfer_px": 2.0, "abs_diff_px": 1.0, "pass": False, "reason": "value outside tolerance"})
        return rec

    mk.run_gate(root, cells, "mps", ENV, gate_one=one_bad, log=lambda s: None)
    args = argparse.Namespace(first=None, expect_device="mps", redo=False)
    assert mk.cmd_gate(args) == 1
    assert "FAIL (1 of 2 clips pass)" in (root / mk.GATE_MD).read_text()
    mk.run_gate(root, cells, "mps", ENV, gate_one=_fake_record, redo=True, log=lambda s: None)
    assert mk.cmd_gate(args) == 0


def test_cmd_gate_first_says_finalise_was_skipped(tmp_path, monkeypatch, capsys):
    import argparse
    root = _patched_cmd_gate(tmp_path, monkeypatch)
    mk.run_gate(root, mk.a9_cells(root), "mps", ENV, gate_one=_fake_record, log=lambda s: None)
    assert mk.cmd_gate(argparse.Namespace(first=1, expect_device="mps", redo=False)) == 0
    assert "finalise skipped" in capsys.readouterr().err


def test_cmd_gate_returns_one_when_a_clip_errors(tmp_path, monkeypatch):
    import argparse
    root = _patched_cmd_gate(tmp_path, monkeypatch)       # clips do not exist: every clip errors
    assert mk.cmd_gate(argparse.Namespace(first=None, expect_device="mps", redo=False)) == 1
    assert not (root / mk.GATE_CSV).exists()


def test_finalise_gate_fail_branch(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)

    def one_bad(cell, root_, device, expect):
        rec = _fake_record(cell, root_, device, expect)
        if cell["public_id"] == cells[1]["public_id"]:
            rec.update({"chamfer_px": 2.0, "abs_diff_px": 1.0, "pass": False, "reason": "value outside tolerance"})
        return rec

    mk.run_gate(root, cells, "mps", ENV, gate_one=one_bad, log=lambda s: None)
    assert mk.finalise_gate(root, cells) == 1
    md = (root / mk.GATE_MD).read_text()
    assert "FAIL (1 of 2 clips pass)" in md and "## Failing clips" in md
    assert f"`{cells[1]['public_id']}`" in md and "value outside tolerance" in md
    with open(root / mk.GATE_CSV) as f:
        assert [r["pass"] for r in csv.DictReader(f)] == ["true", "false"]


def test_finalise_gate_refuses_a_stored_flag_that_disagrees_with_the_numbers(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    mk.run_gate(root, cells, "mps", ENV, gate_one=_fake_record, log=lambda s: None)
    rec = json.loads(_part(root, cells[0]).read_text())
    rec["chamfer_px"] = 5.0                                  # released is 1.0, flag still says pass
    _part(root, cells[0]).write_text(json.dumps(rec))
    with pytest.raises(SystemExit, match="pass flag"):
        mk.finalise_gate(root, cells)


def test_finalise_gate_refuses_a_part_for_the_wrong_cell(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    mk.run_gate(root, cells, "mps", ENV, gate_one=_fake_record, log=lambda s: None)
    rec = json.loads(_part(root, cells[0]).read_text())
    rec["cell_id"] = cells[1]["public_id"]
    _part(root, cells[0]).write_text(json.dumps(rec))
    with pytest.raises(SystemExit, match="cell"):
        mk.finalise_gate(root, cells)


def test_gate_clip_with_all_empty_maps_fails_with_a_reason_and_blank_geometry(tmp_path):
    root = fake_tree(tmp_path)
    maps = [np.zeros((36, 64), bool) for _ in range(5)]
    load, extract = _fake_io(maps)
    rec = mk.gate_clip(_gate_cell(root, 1.0), root, "mps", "mps", load=load, extract=extract)
    assert rec["pass"] is False and rec["chamfer_px"] is None and "no recomputed value" in rec["reason"]
    assert rec["geometry"] == {"stretch": None, "centre-crop": None}


def test_a9_cells_names_the_cell_with_a_missing_field(tmp_path):
    root = fake_tree(tmp_path)
    bad = root / "runs" / "metrics" / "act-line-1_idle_wan22.json"
    bad.write_text(json.dumps({"n_frames": 5}))
    with pytest.raises(ValueError, match="act-line-1_idle_wan22"):
        mk.a9_cells(root)


def test_code_identity_records_git_dirty(tmp_path):
    import subprocess
    assert mk.code_identity(root=tmp_path / "no-such-repo")["git_dirty"] == "unknown"
    git = ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(git + ["init", "-q"], check=True)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(git + ["add", "f.txt"], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "m"], check=True)
    clean = mk.code_identity(root=tmp_path)
    assert clean["git_dirty"] is False and len(clean["git_commit"]) == 40
    (tmp_path / "f.txt").write_text("y")
    assert mk.code_identity(root=tmp_path)["git_dirty"] is True


def test_a_stale_part_does_not_survive_a_failed_rerun(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    mk.run_gate(root, cells, "mps", ENV, gate_one=_fake_record, log=lambda s: None)
    newer = dict(ENV, inkstab_sha256="e" * 64)

    def broken(cell, root_, device, expect):
        raise RuntimeError("boom")

    failed = mk.run_gate(root, cells, "mps", newer, gate_one=broken, log=lambda s: None)
    assert len(failed) == 2 and not any(_part(root, c).exists() for c in cells)
    assert mk.finalise_gate(root, cells) is None


# ============================================================ masked drift
import subprocess  # noqa: E402
import warnings  # noqa: E402

FULL = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
LEFT = [[0.0, 0.0], [0.5, 0.0], [0.5, 1.0], [0.0, 1.0]]
RULE_TEXT = "the drawing rule"


def test_all_true_region_equals_frozen_chamfer_bit_for_bit():
    for h, w in ((36, 64), (64, 36), (45, 80)):
        for _ in range(20):
            a, b = RNG.random((h, w)) < 0.05, RNG.random((h, w)) < 0.05
            R = np.ones((h, w), dtype=bool)
            assert mk.masked_chamfer(a, b, R) == inkstab._chamfer(a, b)   # exact, not approx
    maps = random_maps(8)
    maps[4] = np.zeros_like(maps[4])
    R = np.ones(maps[0].shape, dtype=bool)
    assert mk.masked_series(maps, {"all": R})["all"] == mk.whole_frame_series(maps)


def test_motion_only_inside_M_scores_zero():
    b = lines(36, 64, cols=(50,))                     # frame 0: a stroke at the top left, a line at the right
    b[5, 5:30] = True
    a = lines(36, 64, cols=(50,))                     # the stroke moved; the right line held
    a[9, 5:30] = True
    M = np.zeros((36, 64), dtype=bool)
    M[:16, :40] = True                                # the top-left may move
    R = mk.region(M, 4)
    assert inkstab._chamfer(a, b) > 0
    assert mk.masked_chamfer(a, b, R) == 0.0


def test_vanished_lines_score_the_one_sided_term():
    from scipy.ndimage import distance_transform_edt
    b = lines(36, 64, cols=(10, 50))                  # frame 0 has a line inside R (col 50)
    a = lines(36, 64, cols=(10,))                     # it vanished; only the allowed line is left
    M = np.zeros((36, 64), dtype=bool)
    M[:, :20] = True
    R = mk.region(M, 4)
    assert not (a & R).any() and (b & R).any()
    expect = float(distance_transform_edt(~a)[b & R].mean())
    assert mk.masked_chamfer(a, b, R) == expect == 40.0


def test_appeared_lines_score_the_mirror_term():
    from scipy.ndimage import distance_transform_edt
    b = lines(36, 64, cols=(10,))
    a = lines(36, 64, cols=(10, 50))
    M = np.zeros((36, 64), dtype=bool)
    M[:, :20] = True
    R = mk.region(M, 4)
    assert mk.masked_chamfer(a, b, R) == float(distance_transform_edt(~b)[a & R].mean()) == 40.0


def test_empty_frames_and_empty_region_give_none():
    z, b = np.zeros((36, 64), bool), lines(36, 64, cols=(10,))
    R = np.ones((36, 64), bool)
    assert mk.masked_chamfer(z, b, R) is None and mk.masked_chamfer(b, z, R) is None
    M = np.zeros((36, 64), bool)
    M[:, :20] = True
    assert mk.masked_chamfer(b, b, mk.region(M, 4)) is None      # no line of either frame in R
    assert mk.masked_series([z, b, b], {"r": R})["r"] == [None, None]   # empty frame 0: nothing scorable


# ---- masked_frame: the one per-frame implementation of MASKED_DEFS["masked_chamfer"]
def _left_allowed_region():
    M = np.zeros((36, 64), dtype=bool)
    M[:, :20] = True
    return mk.region(M, 4)


def test_masked_frame_both_terms_branch():
    from scipy.ndimage import distance_transform_edt as edt
    b = lines(36, 64, cols=(10, 50))
    a = lines(36, 64, cols=(10, 54))                  # the line in R moved 4 px
    R = _left_allowed_region()
    assert (a & R).any() and (b & R).any()
    got = mk.masked_frame(a, b, R)
    assert got == float(0.5 * (edt(~b)[a & R].mean() + edt(~a)[b & R].mean())) == 4.0
    assert type(got) is float


def test_masked_frame_only_b_in_R_branch():
    from scipy.ndimage import distance_transform_edt as edt
    b = lines(36, 64, cols=(10, 50))
    a = lines(36, 64, cols=(10,))                     # the line in R vanished
    R = _left_allowed_region()
    assert not (a & R).any() and (b & R).any()
    got = mk.masked_frame(a, b, R)
    assert got == float(edt(~a)[b & R].mean()) == 40.0 and type(got) is float


def test_masked_frame_only_a_in_R_branch():
    from scipy.ndimage import distance_transform_edt as edt
    b = lines(36, 64, cols=(10,))
    a = lines(36, 64, cols=(10, 50))                  # a line appeared in R
    R = _left_allowed_region()
    assert (a & R).any() and not (b & R).any()
    got = mk.masked_frame(a, b, R)
    assert got == float(edt(~b)[a & R].mean()) == 40.0 and type(got) is float


def test_masked_frame_none_branches():
    z, b = np.zeros((36, 64), bool), lines(36, 64, cols=(10,))
    R = np.ones((36, 64), bool)
    assert mk.masked_frame(z, b, R) is None           # frame t empty
    assert mk.masked_frame(b, z, R) is None           # frame 0 empty
    assert mk.masked_frame(z, z, R) is None           # both empty
    assert mk.masked_frame(b, b, _left_allowed_region()) is None   # lines exist, none in R


def test_masked_frame_all_true_region_is_the_frozen_chamfer_bit_for_bit():
    for _ in range(20):
        a, b = RNG.random((36, 64)) < 0.05, RNG.random((36, 64)) < 0.05
        assert mk.masked_frame(a, b, np.ones((36, 64), bool)) == inkstab._chamfer(a, b)


def test_masked_chamfer_is_masked_frame():
    assert mk.masked_chamfer is mk.masked_frame


def test_masked_series_and_score_line_maps_use_masked_frame_exactly(monkeypatch):
    maps = random_maps(6)
    maps[3] = np.zeros_like(maps[3])
    M = np.zeros(maps[0].shape, dtype=bool)
    M[:, :20] = True
    regions = {m: mk.region(M, m) for m in (4, 8)}
    calls = []
    real = mk.masked_frame

    def spy(a, b, R, *args, **kw):
        calls.append(1)
        return real(a, b, R, *args, **kw)

    monkeypatch.setattr(mk, "masked_frame", spy)
    series = mk.masked_series(maps, regions)
    n_scored = sum(1 for a in maps[1:] if a.any()) * len(regions)
    assert len(calls) == n_scored
    monkeypatch.setattr(mk, "masked_frame", real)
    for m, R in regions.items():                      # the shared-EDT series equals the one-frame function, exactly
        assert series[m] == [real(a, maps[0], R) for a in maps[1:]]
    row = {"allowed": [LEFT], "panel_px": [64, 36], "status": "drawn"}
    monkeypatch.setattr(mk, "masked_frame", spy)
    calls.clear()
    res = mk.score_line_maps(maps, {"aaron": row}, "stretch")
    assert len(calls) == sum(1 for a in maps[1:] if a.any()) * len(mk.MARGINS)
    monkeypatch.setattr(mk, "masked_frame", real)
    Rs = mk.regions(mk.rasterise(row["allowed"], (64, 36), maps[0].shape, "stretch"), mk.MARGINS)
    for m in mk.MARGINS:
        assert res["masked"]["aaron"][f"m{m}"]["chamfer_series"] == [real(a, maps[0], Rs[m]) for a in maps[1:]]


def test_no_scorable_frame_is_plus_infinity():
    assert mk.clip_value([None, None]) == (None, True)
    assert mk.clip_value([]) == (None, True)
    assert mk.clip_value([1.0, None, 3.0]) == (2.0, False)
    b = lines(36, 64, cols=(10,))
    maps = [b, np.zeros_like(b), np.zeros_like(b)]
    row = {"allowed": [], "panel_px": [64, 36], "status": "nothing-allowed"}
    res = mk.score_line_maps(maps, {"aaron": row}, "stretch")
    cond = res["masked"]["aaron"]["m32"]
    assert cond["chamfer_px"] is None and cond["no_scorable_frame"] is True
    assert res["whole_frame"]["chamfer_px"] is None


def test_region_is_the_disk_dilation_of_sub_plan_b():
    from scipy.ndimage import binary_dilation as nd_dilation
    from skimage.morphology import binary_dilation, disk
    for m in mk.MARGINS:
        for _ in range(3):
            M = RNG.random((150, 260)) > 0.9995
            M[0, 3] = True                            # a pixel on the border
            M[149, 259] = True                        # and one in a corner
            expect = ~nd_dilation(M, structure=disk(m))        # sub-plan B's definition
            assert np.array_equal(mk.region(M, m), expect)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                assert np.array_equal(mk.region(M, m), ~binary_dilation(M, disk(m)))
    dot = np.zeros((720, 1280), bool)
    dot[360, 640] = True
    r = mk.region(dot, 32)
    assert not r[360, 672] and r[360, 673] and (~r).sum() == disk(32).sum()
    assert mk.region(np.zeros((10, 10), bool), 32).all()
    assert mk.region(np.ones((10, 10), bool), 32).sum() == 0


def test_a_larger_margin_never_adds_pixels_to_R():
    for _ in range(5):
        M = RNG.random((120, 200)) > 0.999
        r16, r32, r64 = (mk.region(M, m) for m in (16, 32, 64))
        assert not (r32 & ~r16).any() and not (r64 & ~r32).any()


def test_full_panel_polygon_covers_every_grid():
    for panel_wh, clip_hw in (((1344, 768), (704, 1280)), ((1344, 768), (768, 1344)),
                              ((1024, 1792), (1280, 720)), ((1024, 1792), (1280, 704))):
        for mapping in mk.MAPPINGS:
            assert mk.rasterise([FULL], panel_wh, clip_hw, mapping).all()


def test_stretch_is_sub_plan_bs_fill_exactly():
    """Contract with B: polygon(r = y*H, c = x*W, shape=(H, W)), boundary pixels included."""
    from skimage.draw import polygon
    for H, W in ((720, 1280), (1280, 720), (36, 64)):
        for _ in range(10):
            polys = [RNG.random((int(RNG.integers(3, 9)), 2)).tolist() for _ in range(2)]
            expect = np.zeros((H, W), bool)
            for p in polys:
                pts = np.asarray(p)
                rr, cc = polygon(pts[:, 1] * H, pts[:, 0] * W, shape=(H, W))
                expect[rr, cc] = True
            assert np.array_equal(mk.rasterise(polys, (1344, 768), (H, W), "stretch"), expect)


def test_left_half_under_stretch_includes_the_boundary_column():
    M = mk.rasterise([LEFT], (128, 72), (36, 64), "stretch")
    assert M[:, :33].all() and not M[:, 33:].any()            # c = 0.5 * 64 = 32 lies on the edge
    q = mk.rasterise([[[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]]], (1344, 768), (720, 1280),
                     "stretch")
    assert q.sum() == 361 * 641 and q[180, 320] and q[540, 960] and not q[179, 320]   # B's own test
    assert not mk.rasterise([], (1344, 768), (720, 1280), "stretch").any()


def test_centre_crop_offsets_landscape_and_portrait():
    top_half = [[[0, 0], [1, 0], [1, 0.5], [0, 0.5]]]
    M = mk.rasterise(top_half, (1344, 768), (704, 1280), "centre-crop")   # 13 rows cropped off the top
    assert M[0].all() and M[352].all() and not M[353:].any()             # 0.5 * 731 - 13 = 352.5
    P = mk.rasterise([LEFT], (1024, 1792), (1280, 720), "centre-crop")    # 5 columns cropped off the left
    assert P[:, 360].all() and not P[:, 361:].any()                      # 0.5 * 731 - 5 = 360.5
    S = mk.rasterise([LEFT], (1024, 1792), (1280, 720), "stretch")
    assert S[:, 360].all() and not S[:, 361:].any()                      # 0.5 * 720 = 360, edge included


def _doc(rows, set_name="aaron", top=None):
    d = {"schema": "stilldrawn-allowed-regions/1", "set": set_name, "drawn_by": "AARON", "rule": RULE_TEXT,
         "notes": "", "rows": rows}
    d.update(top or {})
    return d


def _mask_file(path, rows, set_name="aaron", top=None):
    path.write_text(json.dumps(_doc(rows, set_name, top)), encoding="utf-8")
    return path


def _row(panel="act-line-1", motion="idle", panel_px=(1344, 768), allowed=(FULL,), status="drawn"):
    return {"panel": panel, "motion": motion, "panel_px": list(panel_px), "allowed": list(allowed), "status": status}


def test_load_masks_accepts_good_rows(tmp_path):
    good = {"act-line-1_idle": _row(),
            "cip-act-tank-1_burst": _row("cip-act-tank-1", "burst", (1024, 1792), [], "nothing-allowed")}
    d = mk.load_masks(_mask_file(tmp_path / "ok.json", good))
    assert d["set"] == "aaron" and set(d["rows"]) == set(good)
    d = mk.load_masks(_mask_file(tmp_path / "ok2.json", good, top={"notes": "row x unreadable"}))
    assert d["notes"] == "row x unreadable"


@pytest.mark.parametrize("bad", [
    {"status": "maybe"},
    {"allowed": [[[0, 0], [1, 1]]]},                         # two points
    {"allowed": [[[0, 0], [1.2, 0], [1, 1]]]},               # out of range
    {"allowed": [[[0, 0], [-0.01, 0], [1, 1]]]},
    {"allowed": [[[0, 0], [True, 0], [1, 1]]]},              # a bool is not a number
    {"allowed": [[[0, 0], ["0.5", 0], [1, 1]]]},
    {"allowed": [[[0, 0], [0.5, 0, 0], [1, 1]]]},
    {"allowed": [FULL], "status": "nothing-allowed"},
    {"allowed": [], "status": "drawn"},
    {"allowed": "everything"},
    {"panel_px": [1344]},
    {"panel_px": [1344, 0]},
    {"panel_px": [1344.0, 768]},
    {"panel_px": [True, 768]},
    {"panel": "act-line-2"},                                 # the row id names act-line-1
    {"motion": "burst"},
    {"extra": 1},
])
def test_load_masks_rejects_bad_rows(tmp_path, bad):
    row = _row()
    row.update(bad)
    with pytest.raises(ValueError):
        mk.load_masks(_mask_file(tmp_path / "bad.json", {"act-line-1_idle": row}))


def test_load_masks_rejects_missing_keys_and_non_finite_numbers(tmp_path):
    row = _row()
    del row["status"]
    with pytest.raises(ValueError):
        mk.load_masks(_mask_file(tmp_path / "a.json", {"act-line-1_idle": row}))
    p = tmp_path / "nan.json"
    p.write_text(json.dumps(_doc({"act-line-1_idle": _row()})).replace("[1.0, 1.0]", "[NaN, 1.0]"),
                 encoding="utf-8")
    with pytest.raises(ValueError):
        mk.load_masks(p)


@pytest.mark.parametrize("top", [
    {"schema": "stilldrawn-allowed-regions/2"},
    {"set": ""},
    {"drawn_by": 3},
    {"rule": None},
    {"notes": None},
    {"rows": []},
    {"extra": "x"},
])
def test_load_masks_rejects_bad_headers(tmp_path, top):
    with pytest.raises(ValueError):
        mk.load_masks(_mask_file(tmp_path / "bad.json", {"act-line-1_idle": _row()}, top=top))
    d = _doc({"act-line-1_idle": _row()})
    d.pop("notes")
    (tmp_path / "nonotes.json").write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError):
        mk.load_masks(tmp_path / "nonotes.json")


def test_score_line_maps_structure_and_nothing_allowed_equals_whole_frame():
    maps = random_maps(6)
    rows = {"aaron": {"allowed": [], "panel_px": [64, 36], "status": "nothing-allowed"},
            "agent": {"allowed": [LEFT], "panel_px": [64, 36], "status": "drawn"}}
    res = mk.score_line_maps(maps, rows, "stretch")
    assert set(res["masked"]) == {"aaron", "agent"}
    assert set(res["masked"]["agent"]) == {"m16", "m32", "m64"}
    whole = res["whole_frame"]
    assert whole["chamfer_px"] == inkstab._stats(mk.whole_frame_series(maps))["mean"]
    for m in ("m16", "m32", "m64"):
        c = res["masked"]["aaron"][m]
        assert c["chamfer_px"] == whole["chamfer_px"] and c["chamfer_series"] == whole["chamfer_series"]
        assert c["region_frac"] == 1.0 and c["f0_line_px_in_R"] == int(maps[0].sum())
        assert type(c["f0_line_px_in_R"]) is int and type(c["no_scorable_frame"]) is bool
    assert res["masked"]["agent"]["m64"]["region_frac"] <= res["masked"]["agent"]["m16"]["region_frac"]


# ------------------------------------------------------------------- guard
REAL_ORIGIN_URL = mk._origin_url


@pytest.fixture(autouse=True)
def _pinned_bare_origin(monkeypatch):
    """Test-only: a local bare repo named origin.git stands in for the pinned GitHub repo, so the
    guard can fetch without a network. `git remote get-url` applies insteadOf rewrites, so a real
    rewrite cannot keep the effective URL pinned; the integration tests below use the real reader."""
    def url(repo):
        real = REAL_ORIGIN_URL(repo)
        return PINNED if real.endswith("/origin.git") and Path(real).is_dir() else real
    monkeypatch.setattr(mk, "_origin_url", url)


def _sh(*args, cwd):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
                    *args], cwd=cwd, check=True, capture_output=True)


GUARD_FILES = {
    "metrics/masked.py": "print('registered')\n",
    "metrics/inkstab.py": "print('frozen')\n",
    "dataset/masks/allowed-aaron.json": '{"set": "aaron"}\n',
    "dataset/masks/allowed-agent.json": '{"set": "agent"}\n',
    "analysis/out/a9_repro_gate.csv": "cell_id\n",
    "analysis/out/a9_geometry.csv": "cell_id\n",
}
PINNED = "https://github.com/aaronlsmiles/stilldrawn.git"
REGISTERED_ON = "2026-11-01"


def _write(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def _manifest(files):
    return "".join(f"{mk.sha256_bytes(t.encode())}  {p}\n" for p, t in sorted(files.items()))


def _slim(study, received_day="2026-11-02"):
    return json.dumps({"schema": "stilldrawn-a9-ratings/1", "rater": "AARON", "study": study,
                       "instrument": "A9", "received_day": received_day, "registered_day": REGISTERED_ON,
                       "ratings": []}) + "\n"


def _config(registered_on=REGISTERED_ON):
    return json.dumps({"schema": "stilldrawn-a9-config/1", "registered_on": registered_on,
                       "r7_deadline": None, "r7_blind_to_engine_styles": True}) + "\n"


GUARD_FILES["analysis/adherence/a9-config.json"] = _config()          # registered_on, manifest-verified


def guard_repos(tmp_path, heading="### A9 \u2014 2026-11-01: exploratory follow-up\n", ratings=True, tag=True,
                public_ratings=True):
    """origin (bare) <- pub (the public checkout); priv (the private working repo). The guard
    sees the bare repo's URL as the pinned GitHub URL through the _pinned_bare_origin fixture."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    origin, pub, priv = tmp_path / "origin.git", tmp_path / "pub", tmp_path / "priv"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(pub)], check=True, capture_output=True)
    files = dict(GUARD_FILES)
    files["docs/PREREGISTRATION.md"] = "# Pre-registration\n\n" + heading
    manifest = _manifest({k: v for k, v in files.items() if k != "docs/PREREGISTRATION.md"})
    _write(pub, {**files, mk.MANIFEST: manifest})
    _sh("symbolic-ref", "HEAD", "refs/heads/main", cwd=pub)
    _sh("add", "-A", cwd=pub)
    _sh("commit", "-q", "-m", "register", cwd=pub)
    _sh("push", "-q", "origin", "main", cwd=pub)
    if tag:
        _sh("tag", "-a", "-m", "A9 registered", mk.A9_TAG, cwd=pub)
        _sh("push", "-q", "origin", mk.A9_TAG, cwd=pub)
    if ratings and public_ratings:        # AARON rates after registration: a later commit on origin/main
        _write(pub, {p: _slim(s) for p, s in zip(mk.AARON_RATINGS, ("burst", "push"))})
        _sh("add", "-A", cwd=pub)
        _sh("commit", "-q", "-m", "AARON's ratings", cwd=pub)
        _sh("push", "-q", "origin", "main", cwd=pub)
    priv.mkdir()
    _sh("init", "-q", "-b", "main", cwd=priv)
    _write(priv, {**GUARD_FILES, mk.MANIFEST: manifest, mk.A9_CONFIG: _config()})
    if ratings:
        _write(priv, {p: _slim(s) for p, s in zip(mk.AARON_RATINGS, ("burst", "push"))})
    _sh("add", "-A", cwd=priv)
    _sh("commit", "-q", "-m", "work", cwd=priv)
    return pub, priv


def test_guard_passes_when_a9_is_public_and_inputs_match(tmp_path):
    pub, priv = guard_repos(tmp_path)
    entries = mk.registration_guard(pub, priv)
    assert set(entries) == set(GUARD_FILES)


def test_guard_requires_a_public_repo():
    for empty in (None, ""):
        with pytest.raises(mk.GuardError, match="public-repo"):
            mk.registration_guard(empty)


def test_guard_refuses_without_the_a9_heading(tmp_path):
    for heading in ("### A8 \u2014 2026-08-17: something else\n", "Mentions ### A9 \u2014 inline only\n",
                    "### A9 - 2026-11-01: plain hyphen\n"):
        pub, priv = guard_repos(tmp_path / str(abs(hash(heading))), heading=heading)
        with pytest.raises(mk.GuardError, match="not registered"):
            mk.registration_guard(pub, priv)


def test_guard_refuses_a_heading_that_is_only_local(tmp_path):
    pub, priv = guard_repos(tmp_path, heading="### A8 \u2014 old\n")
    (pub / "docs" / "PREREGISTRATION.md").write_text("### A9 \u2014 local only\n", encoding="utf-8")
    _sh("commit", "-q", "-am", "not pushed", cwd=pub)               # committed but never pushed
    with pytest.raises(mk.GuardError, match="not registered"):
        mk.registration_guard(pub, priv)


def test_guard_fetches_so_a_push_from_elsewhere_counts(tmp_path):
    pub, priv = guard_repos(tmp_path, heading="### A8 \u2014 old\n", tag=False)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(tmp_path / "origin.git"), str(other)], check=True, capture_output=True)
    (other / "docs" / "PREREGISTRATION.md").write_text("### A9 \u2014 2026-11-01: x\n", encoding="utf-8")
    _sh("commit", "-q", "-am", "register elsewhere", cwd=other)
    _sh("tag", "-f", "-a", "-m", "A9", mk.A9_TAG, cwd=other)
    _sh("push", "-q", "origin", "main", cwd=other)
    _sh("push", "-q", "-f", "origin", mk.A9_TAG, cwd=other)
    assert set(mk.registration_guard(pub, priv)) == set(GUARD_FILES)


def test_guard_refuses_a_local_manifest_that_differs(tmp_path):
    pub, priv = guard_repos(tmp_path)
    (priv / mk.MANIFEST).write_text("0" * 64 + "  metrics/masked.py\n", encoding="utf-8")
    with pytest.raises(mk.GuardError, match="differs"):
        mk.registration_guard(pub, priv)


def test_guard_refuses_a_changed_local_input(tmp_path):
    pub, priv = guard_repos(tmp_path)
    (priv / "metrics" / "masked.py").write_text("print('edited after registration')\n", encoding="utf-8")
    with pytest.raises(mk.GuardError, match="metrics/masked.py: the local file is not the registered one"):
        mk.registration_guard(pub, priv)


def test_guard_refuses_a_missing_local_input(tmp_path):
    pub, priv = guard_repos(tmp_path)
    (priv / "dataset" / "masks" / "allowed-agent.json").unlink()
    with pytest.raises(mk.GuardError, match="allowed-agent.json: the local file is not the registered one"):
        mk.registration_guard(pub, priv)


def test_guard_refuses_a_public_file_that_no_longer_matches(tmp_path):
    pub, priv = guard_repos(tmp_path)
    (pub / "analysis" / "out" / "a9_geometry.csv").write_text("changed\n", encoding="utf-8")
    _sh("commit", "-q", "-am", "edit after registration", cwd=pub)
    _sh("push", "-q", "origin", "main", cwd=pub)
    with pytest.raises(mk.GuardError, match="a9_geometry.csv: origin/main's bytes"):
        mk.registration_guard(pub, priv)


def test_guard_refuses_a_manifest_without_an_input(tmp_path):
    pub, priv = guard_repos(tmp_path)
    text = "".join(l for l in (priv / mk.MANIFEST).read_text(encoding="utf-8").splitlines(True)
                   if "a9_geometry.csv" not in l)
    for repo in (pub, priv):
        (repo / mk.MANIFEST).write_text(text, encoding="utf-8")
    _sh("commit", "-q", "-am", "drop a line", cwd=pub)
    _sh("tag", "-f", "-a", "-m", "A9", mk.A9_TAG, cwd=pub)
    _sh("push", "-q", "origin", "main", cwd=pub)
    _sh("push", "-q", "-f", "origin", mk.A9_TAG, cwd=pub)
    with pytest.raises(mk.GuardError, match="a9_geometry.csv: not in the manifest"):
        mk.registration_guard(pub, priv)


def test_parse_manifest_reads_sha256sum_lines_and_refuses_junk():
    h = "a" * 64
    assert mk.parse_manifest(f"{h}  a/b.csv\n{h} *c.json\n\n") == {"a/b.csv": h, "c.json": h}
    for junk in ("nonsense\n", f"{h[:-1]}  x\n", f"{h}  x\n{h}  x\n"):
        with pytest.raises(mk.GuardError):
            mk.parse_manifest(junk)


def test_guard_refuses_before_aaron_has_rated(tmp_path):
    pub, priv = guard_repos(tmp_path, ratings=False)
    with pytest.raises(mk.GuardError, match="AARON's ratings"):
        mk.registration_guard(pub, priv)


def test_guard_refuses_uncommitted_ratings(tmp_path):
    pub, priv = guard_repos(tmp_path)
    (priv / mk.AARON_RATINGS[0]).write_text(_slim("burst").replace("[]", "[ ]"), encoding="utf-8")
    with pytest.raises(mk.GuardError, match="uncommitted"):
        mk.registration_guard(pub, priv)


def test_guard_refuses_untracked_ratings(tmp_path):
    pub, priv = guard_repos(tmp_path, ratings=False)
    _write(priv, {p: _slim(s) for p, s in zip(mk.AARON_RATINGS, ("burst", "push"))})
    with pytest.raises(mk.GuardError, match="not committed"):
        mk.registration_guard(pub, priv)


def test_guard_refuses_ratings_that_are_not_aarons_slim_files(tmp_path):
    pub, priv = guard_repos(tmp_path)
    (priv / mk.AARON_RATINGS[1]).write_text(_slim("burst"), encoding="utf-8")   # wrong study
    _sh("commit", "-q", "-am", "swap", cwd=priv)
    with pytest.raises(mk.GuardError, match="not AARON's slim push ratings"):
        mk.registration_guard(pub, priv)


def _pub_push(pub, message="ratings"):
    _sh("add", "-A", cwd=pub)
    _sh("commit", "-q", "-m", message, cwd=pub)
    _sh("push", "-q", "origin", "main", cwd=pub)


def test_guard_refuses_ratings_missing_from_the_public_repo(tmp_path):
    pub, priv = guard_repos(tmp_path, public_ratings=False)       # committed privately, never published
    with pytest.raises(mk.GuardError) as e:
        mk.registration_guard(pub, priv)
    msg = str(e.value)
    for path in mk.AARON_RATINGS:
        assert path in msg
    assert "origin/main" in msg and "public" in msg


@pytest.mark.parametrize("which", [0, 1])
def test_guard_names_only_the_one_public_rating_file_that_is_missing(tmp_path, which):
    pub, priv = guard_repos(tmp_path)
    _sh("rm", "-q", mk.AARON_RATINGS[which], cwd=pub)
    _pub_push(pub, "remove one")
    with pytest.raises(mk.GuardError) as e:
        mk.registration_guard(pub, priv)
    assert mk.AARON_RATINGS[which] in str(e.value) and mk.AARON_RATINGS[1 - which] not in str(e.value)


@pytest.mark.parametrize("which", [0, 1])
def test_guard_refuses_public_ratings_that_differ_from_the_private_file(tmp_path, which):
    pub, priv = guard_repos(tmp_path)
    path = mk.AARON_RATINGS[which]
    study = ("burst", "push")[which]
    (pub / path).write_text(_slim(study).replace("[]", "[ ]"), encoding="utf-8")     # one byte more
    _pub_push(pub, "differs")
    with pytest.raises(mk.GuardError) as e:
        mk.registration_guard(pub, priv)
    assert path in str(e.value) and "differs" in str(e.value) and mk.AARON_RATINGS[1 - which] not in str(e.value)


@pytest.mark.parametrize("private_crlf", [True, False])
def test_guard_compares_ratings_as_raw_bytes_so_crlf_cannot_slip_through(tmp_path, private_crlf):
    """A private file and its public copy that differ only in line endings are different bytes: the
    guard must say so (read_text would have folded CRLF into LF and passed both)."""
    pub, priv = guard_repos(tmp_path)
    for repo in (pub, priv):
        _sh("config", "core.autocrlf", "false", cwd=repo)
    path = mk.AARON_RATINGS[0]
    lf = _slim("burst").encode("utf-8")
    crlf = lf.replace(b"\n", b"\r\n")
    assert crlf != lf
    (priv / path).write_bytes(crlf if private_crlf else lf)
    _sh("commit", "-q", "-a", "--allow-empty", "-m", "line endings", cwd=priv)
    (pub / path).write_bytes(lf if private_crlf else crlf)
    _sh("add", "-A", cwd=pub)
    _sh("commit", "-q", "--allow-empty", "-m", "line endings", cwd=pub)    # the public side may already hold these bytes
    _sh("push", "-q", "origin", "main", cwd=pub)
    with pytest.raises(mk.GuardError) as e:
        mk.registration_guard(pub, priv)
    assert path in str(e.value) and "differs" in str(e.value)
    (pub / path).write_bytes(crlf if private_crlf else lf)                  # now byte-identical: accepted
    _sh("add", "-A", cwd=pub)
    _sh("commit", "-q", "--allow-empty", "-m", "same bytes", cwd=pub)
    _sh("push", "-q", "origin", "main", cwd=pub)
    mk.registration_guard(pub, priv)


def test_guard_compares_ratings_in_release_form(tmp_path):
    """The release build renames the creator-IP panel's private id; a private file that still holds
    it matches the public file that holds the public id, and the other way round does not."""
    old = "xyz-act-tank-1"          # a stand-in prefix: the guard matches the id by its shape, not by spelling
    pub, priv = guard_repos(tmp_path)
    path = mk.AARON_RATINGS[0]
    private_text = _slim("burst").replace('"ratings": []', '"ratings": [{"clip": "' + old + '_idle_wan22"}]')
    public_text = private_text.replace(old, "cip-act-tank-1")
    (priv / path).write_text(private_text, encoding="utf-8")
    _sh("commit", "-q", "-am", "private id", cwd=priv)
    (pub / path).write_text(public_text, encoding="utf-8")
    _pub_push(pub, "public id")
    mk.registration_guard(pub, priv)                                   # equal in release form
    (pub / path).write_text(private_text, encoding="utf-8")            # the private id leaked as-is
    _pub_push(pub, "unrenamed")
    with pytest.raises(mk.GuardError, match="differs"):
        mk.registration_guard(pub, priv)


@pytest.mark.parametrize("day", ["2026-11-01", "2026-10-31"])
def test_guard_refuses_public_ratings_not_after_registration(tmp_path, day):
    """The public check on its own: the public copy must be byte-identical to the private file's release
    form, so a public copy dated too early can only be matched by a private file with the same early day,
    which the private check refuses too. There is no state where only the public date is wrong, so
    this calls the public check directly (it must name the public copy), then the whole guard (both
    checks fire and both say so)."""
    pub, priv = guard_repos(tmp_path)
    for root in (pub, priv):                                           # identical, but too early
        (root / mk.AARON_RATINGS[1]).write_text(_slim("push", received_day=day), encoding="utf-8")
    _pub_push(pub, "early")
    _sh("commit", "-q", "-am", "early", cwd=priv)
    _sh("fetch", "-q", "origin", cwd=pub)
    registered = mk._day(REGISTERED_ON)
    msg = mk._check_public_ratings(pub, priv, mk.AARON_RATINGS[1], registered)
    assert msg and "the public copy's received_day" in msg and day in msg   # the public check, alone
    assert mk._check_public_ratings(pub, priv, mk.AARON_RATINGS[0], registered) is None   # the other file is fine
    with pytest.raises(mk.GuardError) as e:
        mk.registration_guard(pub, priv)
    assert "the public copy's received_day" in str(e.value)             # and the private check: its own message
    assert f"{mk.AARON_RATINGS[1]}: received_day" in str(e.value)


def test_public_ratings_check_is_not_reached_when_the_bytes_differ(tmp_path):
    """Byte identity comes first: a differing public copy is reported as differing, whatever its day."""
    pub, priv = guard_repos(tmp_path)
    (pub / mk.AARON_RATINGS[1]).write_text(_slim("push", received_day="2026-10-31"), encoding="utf-8")
    _pub_push(pub, "early and different")
    _sh("fetch", "-q", "origin", cwd=pub)
    msg = mk._check_public_ratings(pub, priv, mk.AARON_RATINGS[1], mk._day(REGISTERED_ON))
    assert "differs" in msg and "received_day" not in msg


def test_guard_keeps_the_private_head_checks_beside_the_public_ones(tmp_path):
    pub, priv = guard_repos(tmp_path)
    (priv / mk.AARON_RATINGS[0]).write_text(_slim("burst"), encoding="utf-8")     # same bytes: still clean
    mk.registration_guard(pub, priv)
    (priv / mk.AARON_RATINGS[0]).write_text(_slim("burst").replace("[]", "[ ]"), encoding="utf-8")
    with pytest.raises(mk.GuardError) as e:
        mk.registration_guard(pub, priv)
    assert "uncommitted" in str(e.value)                              # private check
    _sh("commit", "-q", "-am", "edit", cwd=priv)
    with pytest.raises(mk.GuardError) as e:
        mk.registration_guard(pub, priv)
    assert "differs" in str(e.value)                                  # public check


def test_score_refuses_an_a9_clip_before_registration(tmp_path, monkeypatch):
    root = fake_tree(tmp_path / "repo")
    monkeypatch.setattr(mk, "ROOT", root)
    cells = mk.a9_cells(root)
    masks = _mask_file(tmp_path / "m.json", {"act-line-1_idle": _row(panel_px=(84, 48))})
    clip = root / cells[0]["clip"]
    clip.parent.mkdir(parents=True, exist_ok=True)
    clip.write_bytes(b"pretend video bytes")
    copy = tmp_path / "renamed.mp4"
    copy.write_bytes(b"pretend video bytes")
    named = tmp_path / "act-line-1_idle_wan22.mp4"
    named.write_bytes(b"other bytes")
    for c in (str(clip), cells[0]["clip"], str(copy), str(named)):
        with pytest.raises(SystemExit, match="is an A9 clip"):
            mk.main(["score", c, "--masks", str(masks), "--row", "act-line-1_idle", "--out", str(tmp_path / "o.json")])
    assert not (tmp_path / "o.json").exists()


def test_is_a9_clip_leaves_other_clips_alone(tmp_path):
    root = fake_tree(tmp_path / "repo")
    cells = mk.a9_cells(root)
    clip = root / cells[0]["clip"]
    clip.parent.mkdir(parents=True, exist_ok=True)
    clip.write_bytes(b"pretend video bytes")
    other = tmp_path / "p47-something_idle_wan22.mp4"
    other.write_bytes(b"different bytes!!!!")              # same size, other bytes
    assert not mk.is_a9_clip(other, cells, root)
    assert mk.is_a9_clip(clip, cells, root)


def test_a9_run_requires_an_explicit_public_repo():
    with pytest.raises(SystemExit):
        mk.build_parser().parse_args(["a9-run"])
    with pytest.raises(SystemExit):
        mk.build_parser().parse_args(["a9-run", "--public-repo", "x", "--no-fetch"])


def test_a9_run_refuses_before_registration(tmp_path, monkeypatch):
    monkeypatch.setattr(mk, "ROOT", fake_tree(tmp_path / "repo"))
    monkeypatch.setattr(mk, "a9_cells", lambda *a, **k: pytest.fail("a9_cells must not be reached"))
    pub, _priv = guard_repos(tmp_path / "g", heading="### A8 \u2014 old\n")
    with pytest.raises(SystemExit, match="not registered"):
        mk.main(["a9-run", "--public-repo", str(pub)])


# ------------------------------------------------------------------ a9 run
def _a9_sets(rows_by_set=None):
    row = _row(panel_px=(84, 48), allowed=[LEFT])
    tank = _row("cip-act-tank-1", "burst", (84, 48), [], "nothing-allowed")
    sets = {}
    for name in mk.SET_NAMES:
        rows = {"act-line-1_idle": dict(row, allowed=[FULL] if name == "agent" else [LEFT]),
                "cip-act-tank-1_burst": dict(tank)}
        sets[name] = _doc(rows, name)
    return sets


def _a9_setup(tmp_path):
    root = fake_tree(tmp_path)
    cell = mk.a9_cells(root)[0]
    maps = random_maps(5)
    load, extract = _fake_io(maps)
    gate_px = inkstab._stats(mk.whole_frame_series(maps))["mean"]
    return root, cell, _a9_sets(), load, extract, gate_px


SHAS = {"aaron": "a" * 64, "agent": "b" * 64}


def test_a9_clip_writes_the_registered_record(tmp_path):
    root, cell, sets, load, extract, gate_px = _a9_setup(tmp_path)
    rec = mk.a9_clip(cell, root, "mps", ENV, sets, SHAS, "stretch", gate_px, load=load, extract=extract)
    assert rec["cell_id"] == "act-line-1_idle_wan22" and rec["panel"] == "act-line-1" and rec["engine"] == "wan22"
    assert rec["motion"] == "idle" and rec["n_frames"] == 5 and rec["resolution"] == [36, 64]
    assert rec["whole_frame"]["chamfer_px"] == gate_px and rec["whole_frame"]["gate_chamfer_px"] == gate_px
    assert set(rec["masked"]) == {"aaron", "agent"} and set(rec["masked"]["aaron"]) == {"m16", "m32", "m64"}
    assert rec["masked"]["agent"]["m32"]["region_frac"] == 0.0   # everything may move: nothing measured
    assert rec["masked"]["agent"]["m32"]["chamfer_px"] is None and rec["masked"]["agent"]["m32"]["no_scorable_frame"]
    assert rec["extraction"] == {"netG_sha256": "0" * 64, "torch": "x", "device": "mps"}
    assert rec["defs"] == {"inkstab": inkstab.DEFS, "masked": mk.MASKED_DEFS} and rec["mapping"] == "stretch"
    assert rec["masks_sha256"] == SHAS
    json.dumps(rec, allow_nan=False)                             # no NaN or infinity in the file


def test_a9_clip_uses_public_ids_for_the_creator_ip_panel(tmp_path):
    root, _cell, sets, load, extract, _ = _a9_setup(tmp_path)
    tank = mk.a9_cells(root)[1]
    maps = random_maps(5)
    load, extract = _fake_io(maps)
    gate_px = inkstab._stats(mk.whole_frame_series(maps))["mean"]
    rec = mk.a9_clip(tank, root, "mps", ENV, sets, SHAS, "centre-crop", gate_px, load=load, extract=extract)
    assert rec["cell_id"] == "cip-act-tank-1_burst_gen45" and rec["panel"] == "cip-act-tank-1"
    assert rec["engine"] == "gen4.5" and "xyz" not in json.dumps(rec)


def _drift_module():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
    import a9_masked_drift
    return a9_masked_drift


def test_a9_records_are_accepted_by_the_registered_analysis(tmp_path):
    drift = _drift_module()
    root = fake_tree(tmp_path / "repo")
    sets = _a9_sets()
    for i, cell in enumerate(mk.a9_cells(root)):
        maps = random_maps(5)
        if i == 1:
            maps[0] = np.zeros_like(maps[0])                     # empty frame 0: whole frame null too
        load, extract = _fake_io(maps)
        gate_px = inkstab._stats(mk.whole_frame_series(maps))["mean"]
        if gate_px is None:
            with pytest.raises(SystemExit, match="Stop and investigate"):
                mk.a9_clip(cell, root, "mps", ENV, sets, SHAS, "stretch", gate_px, load=load, extract=extract)
            continue
        rec = mk.a9_clip(cell, root, "mps", ENV, sets, SHAS, "stretch", gate_px, load=load, extract=extract)
        out = tmp_path / "out" / f"{cell['cell_id']}.json"
        mk.write_atomic(out, mk.record_text(rec))
        got = drift._read_clip(out)
        assert got["cell_id"] == f"{got['row']}_{drift.SUFFIX[got['engine']]}"
        assert got["engine"] in drift.LEAGUE_ORDER and got["motion"] in drift.MOTIONS
        assert got["whole"] == gate_px
        assert got["masked"][("agent", 32)][0] == float("inf")   # no scorable frame reads as +inf
        for s in ("aaron", "agent"):
            for m in (16, 32, 64):
                cond = rec["masked"][s][f"m{m}"]
                v = float("inf") if cond["chamfer_px"] is None else cond["chamfer_px"]
                assert got["masked"][(s, m)] == (v, cond["f0_line_px_in_R"])
        assert any(rec["masked"]["aaron"][f"m{m}"]["chamfer_px"] is not None for m in (16, 32, 64))


def test_record_text_is_utf8_lf_and_refuses_nan(tmp_path):
    assert mk.record_text({"a": 1}) == '{\n "a": 1\n}\n'
    with pytest.raises(ValueError):
        mk.record_text({"a": float("nan")})
    mk.write_atomic(tmp_path / "x.json", mk.record_text({"a": "\u2014"}))
    assert b"\r" not in (tmp_path / "x.json").read_bytes()


def test_a9_clip_stops_when_whole_frame_drifts_from_the_gate(tmp_path):
    root, cell, sets, load, extract, gate_px = _a9_setup(tmp_path)
    with pytest.raises(SystemExit, match="Stop and investigate"):
        mk.a9_clip(cell, root, "mps", ENV, sets, SHAS, "stretch", gate_px + 1e-5, load=load, extract=extract)
    rec = mk.a9_clip(cell, root, "mps", ENV, sets, SHAS, "stretch", gate_px + 1e-7, load=load, extract=extract)
    assert rec["whole_frame"]["gate_chamfer_px"] == gate_px + 1e-7


def test_a9_clip_stops_on_another_frame_count_or_grid(tmp_path):
    root, cell, sets, load, extract, gate_px = _a9_setup(tmp_path)
    for key, value in (("released_n_frames", 6), ("released_grid", [64, 36])):
        odd = dict(cell, **{key: value})
        with pytest.raises(SystemExit, match="Stop and investigate"):
            mk.a9_clip(odd, root, "mps", ENV, sets, SHAS, "stretch", gate_px, load=load, extract=extract)


def test_check_mask_sets_refuses_before_any_extraction(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    mk.check_mask_sets(cells, _a9_sets(), root)
    sets = _a9_sets()
    sets["aaron"]["rows"]["act-line-1_idle"]["panel_px"] = [1344, 768]
    with pytest.raises(SystemExit, match="is not the panel's size"):
        mk.check_mask_sets(cells, sets, root)
    sets = _a9_sets()
    del sets["agent"]["rows"]["cip-act-tank-1_burst"]
    with pytest.raises(SystemExit, match="has no row cip-act-tank-1_burst"):
        mk.check_mask_sets(cells, sets, root)
    sets = _a9_sets()
    sets["agent"]["set"] = "aaron"
    with pytest.raises(SystemExit, match="says set"):
        mk.check_mask_sets(cells, sets, root)
    with pytest.raises(SystemExit, match="mask sets"):
        mk.check_mask_sets(cells, {"aaron": _a9_sets()["aaron"]}, root)


def _fake_a9_record(cell, env, shas, mapping, gate_px, n=5):
    block = {"region_frac": 0.5, "f0_line_px_in_R": 600, "chamfer_px": 1.0, "no_scorable_frame": False,
             "chamfer_series": [1.0] * (n - 1)}
    return {"cell_id": cell["public_id"], "n_frames": n, "masks_sha256": shas, "mapping": mapping,
            "extraction": {k: env[k] for k in ("netG_sha256", "torch", "device")},
            "whole_frame": {"chamfer_px": gate_px, "chamfer_series": [gate_px] * (n - 1), "gate_chamfer_px": gate_px},
            "masked": {s: {f"m{m}": dict(block) for m in mk.MARGINS} for s in mk.SET_NAMES},
            "m_empty": {s: False for s in mk.SET_NAMES}}


def test_run_a9_is_resumable_and_names_files_by_the_repo_cell_id(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    calls = []

    def fake(cell, root_, device, env, sets, shas, mapping, gate_px):
        calls.append((cell["cell_id"], mapping, gate_px))
        return _fake_a9_record(cell, env, shas, mapping, gate_px)

    gate = {c["public_id"]: 1.0 + i for i, c in enumerate(cells)}
    maps = {"wan22": "stretch", "gen4.5": "centre-crop"}
    mk.run_a9(root, cells, "mps", ENV, gate, maps, {}, {}, clip_fn=fake, log=lambda s: None)
    mk.run_a9(root, cells, "mps", ENV, gate, maps, {}, {}, clip_fn=fake, log=lambda s: None)
    assert calls == [("act-line-1_idle_wan22", "stretch", 1.0), ("xyz-act-tank-1_burst_gen45", "centre-crop", 2.0)]
    assert (root / mk.MASKS_OUT / "xyz-act-tank-1_burst_gen45.json").exists()


def test_run_a9_reruns_a_damaged_record(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    calls = []

    def fake(cell, root_, device, env, sets, shas, mapping, gate_px):
        calls.append(cell["cell_id"])
        return _fake_a9_record(cell, env, shas, mapping, gate_px)

    gate = {c["public_id"]: 1.0 for c in cells}
    maps = {"wan22": "stretch", "gen4.5": "stretch"}
    mk.run_a9(root, cells, "mps", ENV, gate, maps, {}, {}, clip_fn=fake, log=lambda s: None)
    (root / mk.MASKS_OUT / f"{cells[0]['cell_id']}.json").write_text('{"cell_id": "act-', encoding="utf-8")
    mk.run_a9(root, cells, "mps", ENV, gate, maps, {}, {}, clip_fn=fake, log=lambda s: None)
    assert calls == [cells[0]["cell_id"], cells[1]["cell_id"], cells[0]["cell_id"]]


def _gate_csv(root, rows):
    p = root / mk.GATE_CSV
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("cell_id,device,chamfer_px,pass\n" + "".join(f"{c},{d},{v},{ok}\n" for c, d, v, ok in rows),
                 encoding="utf-8")


def test_read_gate_requires_109_passing_rows_on_one_device(tmp_path):
    _gate_csv(tmp_path, [(f"c{i}", "mps", 1.0, "true") for i in range(108)] + [("c108", "mps", 1.0, "false")])
    with pytest.raises(SystemExit, match="109 passing"):
        mk.read_gate(tmp_path)
    _gate_csv(tmp_path, [(f"c{i}", "mps", 1.0, "true") for i in range(108)])
    with pytest.raises(SystemExit, match="109 passing"):
        mk.read_gate(tmp_path)
    _gate_csv(tmp_path, [(f"c{i}", "mps" if i else "cpu", 1.5, "true") for i in range(109)])
    with pytest.raises(SystemExit, match="one device"):
        mk.read_gate(tmp_path)
    _gate_csv(tmp_path, [(f"c{i}", "mps", 1.5, "true") for i in range(109)])
    values, device = mk.read_gate(tmp_path)
    assert values["c0"] == 1.5 and device == "mps" and len(values) == 109


def test_cmd_a9_run_refuses_mismatched_gate_ids_and_wrong_device(tmp_path, monkeypatch):
    root = fake_tree(tmp_path)
    monkeypatch.setattr(mk, "ROOT", root)
    monkeypatch.setattr(mk, "A9_N_CLIPS", 2)
    monkeypatch.setattr(mk, "registration_guard", lambda *a, **k: {})
    cells = mk.a9_cells(root)
    _gate_csv(root, [(c["public_id"], "mps", 1.0, "true") for c in cells])
    geo = root / mk.GEOM_CSV
    geo.write_text("cell_id,engine,chamfer_stretch_px,chamfer_centre_crop_px\n"
                   + "".join(f"{c['public_id']},{c['engine']},1.0,2.0\n" for c in cells), encoding="utf-8")
    for name, doc in _a9_sets().items():
        (root / mk.MASK_FILES[name]).parent.mkdir(parents=True, exist_ok=True)
        (root / mk.MASK_FILES[name]).write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(mk.inkstab, "_device", lambda: "cpu")
    monkeypatch.setattr(mk, "environment", lambda *a, **k: pytest.fail("environment() must not be reached"))
    with pytest.raises(SystemExit, match="device"):
        mk.main(["a9-run", "--public-repo", "x"])
    monkeypatch.setattr(mk.inkstab, "_device", lambda: "mps")
    _gate_csv(root, [("someone-else", "mps", 1.0, "true"), (cells[1]["public_id"], "mps", 1.0, "true")])
    with pytest.raises(SystemExit, match="gate"):
        mk.main(["a9-run", "--public-repo", "x"])
    assert not (root / mk.MASKS_OUT).exists()


def test_cmd_a9_run_end_to_end_on_synthetic_clips(tmp_path, monkeypatch):
    root = fake_tree(tmp_path)
    monkeypatch.setattr(mk, "ROOT", root)
    monkeypatch.setattr(mk, "A9_N_CLIPS", 2)
    monkeypatch.setattr(mk, "registration_guard", lambda *a, **k: {})
    monkeypatch.setattr(mk.inkstab, "_device", lambda: "mps")
    monkeypatch.setattr(mk, "environment", lambda *a, **k: dict(ENV))
    maps = random_maps(5)
    load, extract = _fake_io(maps)
    monkeypatch.setattr(mk.inkstab, "_load_frames", load)
    monkeypatch.setattr(mk.inkstab, "_line_maps", extract)
    cells = mk.a9_cells(root)
    v = inkstab._stats(mk.whole_frame_series(maps))["mean"]
    _gate_csv(root, [(c["public_id"], "mps", repr(v), "true") for c in cells])
    (root / mk.GEOM_CSV).write_text("cell_id,engine,chamfer_stretch_px,chamfer_centre_crop_px\n"
                                    + "".join(f"{c['public_id']},{c['engine']},1.0,2.0\n" for c in cells),
                                    encoding="utf-8")
    for name, doc in _a9_sets().items():
        (root / mk.MASK_FILES[name]).parent.mkdir(parents=True, exist_ok=True)
        (root / mk.MASK_FILES[name]).write_text(json.dumps(doc), encoding="utf-8")
    assert mk.main(["a9-run", "--public-repo", "x"]) == 0
    drift = _drift_module()
    for c in cells:
        got = drift._read_clip(root / mk.MASKS_OUT / f"{c['cell_id']}.json")
        assert got["cell_id"] == c["public_id"] and got["whole"] == v


# ------------------------------------------------- review round: guard identity
def test_guard_refuses_the_private_repo_as_the_public_one(tmp_path):
    pub, priv = guard_repos(tmp_path)
    for fake_public in (priv, priv / "metrics"):
        with pytest.raises(mk.GuardError, match="is the private repo"):
            mk.registration_guard(fake_public, priv)


@pytest.mark.parametrize("url", [
    "https://github.com/aaronlsmiles/stilldrawn.git", "https://github.com/aaronlsmiles/stilldrawn",
    "git@github.com:aaronlsmiles/stilldrawn.git", "git@github.com:aaronlsmiles/stilldrawn",
    "ssh://git@github.com/aaronlsmiles/stilldrawn.git", "ssh://git@github.com/aaronlsmiles/stilldrawn",
])
def test_public_origin_pattern_accepts_https_and_ssh_forms(url):
    assert mk.PUBLIC_ORIGIN.fullmatch(url)


@pytest.mark.parametrize("url", [
    "https://github.com/someone/stilldrawn.git", "https://github.com/aaronlsmiles/stilldrawn-fork.git",
    "https://github.com/aaronlsmiles/other-repo.git", "https://gitlab.com/aaronlsmiles/stilldrawn.git",
    "https://evil.example/github.com/aaronlsmiles/stilldrawn.git", "/tmp/origin.git",
    "https://user:secret@github.com/aaronlsmiles/stilldrawn.git",
])
def test_public_origin_pattern_refuses_other_repos(url):
    assert not mk.PUBLIC_ORIGIN.fullmatch(url)


def test_guard_refuses_an_origin_that_is_not_the_public_repo(tmp_path):
    pub, priv = guard_repos(tmp_path)
    _sh("remote", "set-url", "origin", "https://github.com/someone/stilldrawn.git", cwd=pub)
    with pytest.raises(mk.GuardError, match="not the public StillDrawn repo"):
        mk.registration_guard(pub, priv)


def test_guard_refuses_credentials_in_the_origin_url(tmp_path):
    pub, priv = guard_repos(tmp_path)
    _sh("config", "remote.origin.url", "https://user:not-a-real-token@github.com/aaronlsmiles/stilldrawn.git",
        cwd=pub)
    with pytest.raises(mk.GuardError, match="origin URL carries credentials") as e:
        mk.registration_guard(pub, priv)
    assert "not-a-real-token" not in str(e.value)


def test_guard_refuses_without_the_tag_on_origin(tmp_path):
    pub, priv = guard_repos(tmp_path, tag=False)
    with pytest.raises(mk.GuardError, match="a9-registered"):
        mk.registration_guard(pub, priv)
    _sh("tag", "-a", "-m", "local only", mk.A9_TAG, cwd=pub)      # tagged locally, never pushed
    with pytest.raises(mk.GuardError, match="a9-registered"):
        mk.registration_guard(pub, priv)


def test_guard_accepts_a_lightweight_tag(tmp_path):
    pub, priv = guard_repos(tmp_path, tag=False)
    _sh("tag", mk.A9_TAG, cwd=pub)
    _sh("push", "-q", "origin", mk.A9_TAG, cwd=pub)
    assert set(mk.registration_guard(pub, priv)) == set(GUARD_FILES)


def test_guard_refuses_a_tag_that_is_not_on_main(tmp_path):
    pub, priv = guard_repos(tmp_path)
    _sh("checkout", "-q", "-b", "side", cwd=pub)
    (pub / "side.txt").write_text("x\n", encoding="utf-8")
    _sh("add", "side.txt", cwd=pub)
    _sh("commit", "-q", "-m", "side", cwd=pub)
    _sh("tag", "-f", "-a", "-m", "moved", mk.A9_TAG, cwd=pub)
    _sh("push", "-q", "-f", "origin", mk.A9_TAG, cwd=pub)
    with pytest.raises(mk.GuardError, match="ancestor"):
        mk.registration_guard(pub, priv)


def test_guard_refuses_a_tag_made_before_a9_was_written(tmp_path):
    pub, priv = guard_repos(tmp_path, heading="### A8 \u2014 old\n")      # tag on the commit without A9
    (pub / "docs" / "PREREGISTRATION.md").write_text("### A9 \u2014 2026-11-01: later\n", encoding="utf-8")
    _sh("commit", "-q", "-am", "A9 after the tag", cwd=pub)
    _sh("push", "-q", "origin", "main", cwd=pub)
    with pytest.raises(mk.GuardError, match="a9-registered.*not registered"):
        mk.registration_guard(pub, priv)


def test_guard_refuses_a_manifest_changed_after_the_tag(tmp_path):
    pub, priv = guard_repos(tmp_path)
    extra = {"analysis/extra.txt": "x\n"}
    manifest = (pub / mk.MANIFEST).read_text(encoding="utf-8") + _manifest(extra)
    _write(pub, {**extra, mk.MANIFEST: manifest})
    _write(priv, {mk.MANIFEST: manifest})
    _sh("add", "-A", cwd=pub)
    _sh("commit", "-q", "-m", "manifest moved after registration", cwd=pub)
    _sh("push", "-q", "origin", "main", cwd=pub)
    with pytest.raises(mk.GuardError, match="a9-registered"):
        mk.registration_guard(pub, priv)


def test_guard_refuses_a_file_changed_at_the_tag_but_restored_on_main(tmp_path):
    """Hashes are checked at the tag too: a manifest file that matched only later fails."""
    pub, priv = guard_repos(tmp_path, tag=False)
    good = (pub / "analysis" / "out" / "a9_geometry.csv").read_text(encoding="utf-8")
    (pub / "analysis" / "out" / "a9_geometry.csv").write_text("wrong\n", encoding="utf-8")
    _sh("commit", "-q", "-am", "wrong bytes", cwd=pub)
    _sh("tag", "-a", "-m", "A9", mk.A9_TAG, cwd=pub)
    (pub / "analysis" / "out" / "a9_geometry.csv").write_text(good, encoding="utf-8")
    _sh("commit", "-q", "-am", "fixed after the tag", cwd=pub)
    _sh("push", "-q", "origin", "main", mk.A9_TAG, cwd=pub)
    with pytest.raises(mk.GuardError, match="a9_geometry.csv: a9-registered's bytes"):
        mk.registration_guard(pub, priv)


# ---------------------------------------------- review round: inkstab and ratings
def test_guard_hashes_inkstab_in_its_release_form(tmp_path):
    pub, priv = guard_repos(tmp_path)
    home_line = "CAUX_SRC = pathlib.Path.home() / " + '"tools/ComfyUI/custom_nodes/comfyui_controlnet_aux/src"\n'
    private = "import pathlib\n" + home_line
    release = mk.release_form("metrics/inkstab.py", private)
    assert release != private and "STILLDRAWN_CONTROLNET_AUX_SRC" in release
    files = {**GUARD_FILES, "metrics/inkstab.py": release}
    manifest = _manifest(files)
    _write(pub, {"metrics/inkstab.py": release, mk.MANIFEST: manifest})
    _sh("commit", "-q", "-am", "real inkstab", cwd=pub)
    _sh("tag", "-f", "-a", "-m", "A9", mk.A9_TAG, cwd=pub)
    _sh("push", "-q", "origin", "main", cwd=pub)
    _sh("push", "-q", "-f", "origin", mk.A9_TAG, cwd=pub)
    _write(priv, {"metrics/inkstab.py": private, mk.MANIFEST: manifest})
    assert "metrics/inkstab.py" in mk.registration_guard(pub, priv)
    _write(priv, {"metrics/inkstab.py": private + "# edited\n"})
    with pytest.raises(mk.GuardError, match="metrics/inkstab.py: the local file is not the registered one"):
        mk.registration_guard(pub, priv)


def test_release_form_renames_any_three_letter_prefix_but_leaves_the_public_id_alone():
    for prefix in ("xyz", "abc", "zzz"):
        assert mk.release_form("a.json", f'"{prefix}-act-tank-1_idle_wan22"') == '"cip-act-tank-1_idle_wan22"'
        assert mk.release_form("a.txt", f"x/{prefix}-act-tank-1/y") == "x/cip-act-tank-1/y"
    for same in ("cip-act-tank-1_burst_gen45", "act-tank-1", "ab-act-tank-1", "ABC-act-tank-1", "abc-act-tank-2",
                 "abc-act-line-1"):
        assert mk.release_form("a.json", same) == same


def test_release_form_renames_the_real_private_id_like_the_release_build():
    repo = Path(__file__).resolve().parents[1]
    build = repo / "tools" / "build_release.py"
    if not build.exists():
        pytest.skip("the release build is private; the real private id is known only there")
    sys.path.insert(0, str(build.parent))
    import build_release as br
    for text in (br.OLD_ID, f"{br.OLD_ID}_burst_gen45", f'"{br.OLD_ID}_idle_wan22"', f"a/{br.OLD_ID}/b",
                 f"{br.NEW_ID}_idle_ltx23"):
        assert mk.release_form("a.json", text) == text.replace(br.OLD_ID, br.NEW_ID)


def test_release_form_matches_the_release_build_on_the_real_inkstab():
    repo = Path(__file__).resolve().parents[1]
    build = repo / "tools" / "build_release.py"
    if not build.exists():
        pytest.skip("the release build is private; in the release tree inkstab.py is already in release form")
    sys.path.insert(0, str(build.parent))
    import build_release as br
    for rel in ("metrics/inkstab.py", "metrics/masked.py"):
        text = (repo / rel).read_text(encoding="utf-8")
        assert mk.release_form(rel, text) == br.rewrite_text(rel, text, [])
    text = (repo / "metrics" / "inkstab.py").read_text(encoding="utf-8")
    assert mk.release_form("metrics/inkstab.py", mk.release_form("metrics/inkstab.py", text)) \
        == mk.release_form("metrics/inkstab.py", text)                      # idempotent: release tree


def test_guarded_inputs_include_the_frozen_extractor():
    assert "metrics/inkstab.py" in mk.GUARDED_INPUTS


@pytest.mark.parametrize("day", ["2026-11-01", "2026-10-31", "", "11/02/2026", None])
def test_guard_refuses_ratings_not_received_after_registration(tmp_path, day):
    pub, priv = guard_repos(tmp_path)
    (priv / mk.AARON_RATINGS[1]).write_text(_slim("push", received_day=day), encoding="utf-8")
    _sh("commit", "-q", "-am", "early", cwd=priv)
    with pytest.raises(mk.GuardError, match="received_day"):
        mk.registration_guard(pub, priv)


@pytest.mark.parametrize("registered_on", [None, "soon"])
def test_guard_refuses_without_a_registration_date(tmp_path, registered_on):
    pub, priv = guard_repos(tmp_path)
    (priv / mk.A9_CONFIG).write_text(_config(registered_on), encoding="utf-8")
    with pytest.raises(mk.GuardError, match="registered_on"):
        mk.registration_guard(pub, priv)


# ----------------------------------------------- review round: records and m_empty
def _run_twice(tmp_path, tamper, **kw):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    calls = []

    def fake(cell, root_, device, env, sets, shas, mapping, gate_px):
        calls.append(cell["cell_id"])
        return _fake_a9_record(cell, env, shas, mapping, gate_px)

    gate = {c["public_id"]: 1.0 for c in cells}
    maps = {"wan22": "stretch", "gen4.5": "stretch"}
    mk.run_a9(root, cells, "mps", ENV, gate, maps, {}, SHAS, clip_fn=fake, log=lambda s: None)
    p = root / mk.MASKS_OUT / f"{cells[0]['cell_id']}.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    tamper(rec)
    p.write_text(json.dumps(rec), encoding="utf-8")
    args = dict(gate=gate, mappings=maps, shas=SHAS, env=ENV)
    args.update(kw)
    mk.run_a9(root, cells, "mps", args["env"], args["gate"], args["mappings"], {}, args["shas"], clip_fn=fake,
              log=lambda s: None)
    return calls, cells


@pytest.mark.parametrize("tamper", [
    lambda r: r.update(masks_sha256={"aaron": "c" * 64, "agent": "b" * 64}),
    lambda r: r.update(mapping="centre-crop"),
    lambda r: r["extraction"].update(torch="other"),
    lambda r: r["extraction"].update(device="cpu"),
    lambda r: r["whole_frame"].update(gate_chamfer_px=1.5),
    lambda r: r.pop("whole_frame"),
    lambda r: r.pop("masks_sha256"),
])
def test_run_a9_reruns_a_stale_record(tmp_path, tamper):
    calls, cells = _run_twice(tmp_path, tamper)
    assert calls == [cells[0]["cell_id"], cells[1]["cell_id"], cells[0]["cell_id"]]


def test_run_a9_keeps_a_current_record(tmp_path):
    calls, cells = _run_twice(tmp_path, lambda r: None)
    assert calls == [cells[0]["cell_id"], cells[1]["cell_id"]]


def test_run_a9_refuses_a_foreign_record(tmp_path):
    with pytest.raises(SystemExit, match="holds cell"):
        _run_twice(tmp_path, lambda r: r.update(cell_id="cu-line-1_idle_wan22"))


def test_run_a9_reruns_every_record_when_the_masks_change(tmp_path):
    calls, cells = _run_twice(tmp_path, lambda r: None, shas={"aaron": "d" * 64, "agent": "b" * 64})
    assert calls == [cells[0]["cell_id"], cells[1]["cell_id"], cells[0]["cell_id"], cells[1]["cell_id"]]


def test_a_drawn_row_that_rasterises_empty_is_flagged():
    maps = random_maps(5)
    sliver = [[[0.1, 0.1], [0.1004, 0.1], [0.1, 0.1004]]]           # far below one pixel at 36 x 64
    assert not mk.rasterise(sliver, (64, 36), (36, 64), "stretch").any()
    rows = {"aaron": {"allowed": sliver, "panel_px": [64, 36], "status": "drawn"},
            "agent": {"allowed": [LEFT], "panel_px": [64, 36], "status": "drawn"}}
    res = mk.score_line_maps(maps, rows, "stretch")
    assert res["m_empty"] == {"aaron": True, "agent": False}
    assert res["masked"]["aaron"]["m32"]["chamfer_px"] == res["whole_frame"]["chamfer_px"]   # R is everything
    nothing = {"aaron": {"allowed": [], "panel_px": [64, 36], "status": "nothing-allowed"}}
    assert mk.score_line_maps(maps, nothing, "stretch")["m_empty"] == {"aaron": False}


def test_a9_record_carries_m_empty_per_set(tmp_path):
    root, cell, sets, load, extract, gate_px = _a9_setup(tmp_path)
    rec = mk.a9_clip(cell, root, "mps", ENV, sets, SHAS, "stretch", gate_px, load=load, extract=extract)
    assert rec["m_empty"] == {"aaron": False, "agent": False}
    assert type(rec["m_empty"]["aaron"]) is bool


def test_score_writes_the_clip_file_name_only(tmp_path, monkeypatch):
    root = fake_tree(tmp_path / "repo")
    monkeypatch.setattr(mk, "ROOT", root)
    maps = random_maps(5)
    load, extract = _fake_io(maps)
    monkeypatch.setattr(mk.inkstab, "_load_frames", load)
    monkeypatch.setattr(mk.inkstab, "_line_maps", extract)
    monkeypatch.setattr(mk.inkstab, "_device", lambda: "mps")
    monkeypatch.setattr(mk, "environment", lambda *a, **k: dict(ENV))
    clip = tmp_path / "private" / "folder" / "p47-test_idle_wan22.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"not an A9 clip")
    masks = _mask_file(tmp_path / "m.json", {"p47-test_idle": _row("p47-test", "idle", (64, 36), [LEFT])})
    out = tmp_path / "o.json"
    assert mk.main(["score", str(clip), "--masks", str(masks), "--row", "p47-test_idle", "--out", str(out)]) == 0
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["clip"] == "p47-test_idle_wan22.mp4" and str(tmp_path) not in out.read_text(encoding="utf-8")
    assert rec["m_empty"] == {"aaron": False} and set(rec["masked"]["aaron"]) == {"m16", "m32", "m64"}


def test_score_docstring_names_the_limits_of_its_a9_check():
    doc = mk.cmd_score.__doc__ + mk.is_a9_clip.__doc__
    assert "re-encoded" in doc and "identical bytes" in doc


def test_guarded_inputs_include_the_registration_config():
    assert mk.A9_CONFIG == "analysis/adherence/a9-config.json" and mk.A9_CONFIG in mk.GUARDED_INPUTS


def test_guard_refuses_a_config_edited_after_registration(tmp_path):
    """registered_on is read only from the manifest-verified config: a later local edit (say,
    an earlier registration day to let early ratings through) is refused."""
    pub, priv = guard_repos(tmp_path)
    (priv / mk.A9_CONFIG).write_text(_config("2026-10-01"), encoding="utf-8")
    with pytest.raises(mk.GuardError, match="a9-config.json: the local file is not the registered one"):
        mk.registration_guard(pub, priv)


def test_guard_hashes_the_config_as_raw_bytes(tmp_path):
    pub, priv = guard_repos(tmp_path)
    (priv / mk.A9_CONFIG).write_bytes(_config().replace("\n", "\r\n").encode("utf-8"))   # same text, CRLF
    with pytest.raises(mk.GuardError, match="a9-config.json: the local file is not the registered one"):
        mk.registration_guard(pub, priv)


# ------------------------------------------- review round 3: effective origin URL, record checks
def _bare_checkout(tmp_path):
    origin, pub = tmp_path / "origin.git", tmp_path / "pub"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(pub)], check=True, capture_output=True)
    return origin, pub


def test_origin_url_is_the_effective_url(tmp_path, monkeypatch):
    monkeypatch.setattr(mk, "_origin_url", REAL_ORIGIN_URL)
    origin, pub = _bare_checkout(tmp_path)
    _sh("remote", "set-url", "origin", PINNED, cwd=pub)
    assert mk._origin_url(pub) == PINNED
    mk._check_public_repo(pub, tmp_path / "priv")                  # the literal pinned URL passes
    _sh("config", f"url.{origin}.insteadOf", PINNED, cwd=pub)     # a rewrite sends it elsewhere
    assert mk._origin_url(pub) == str(origin)
    with pytest.raises(mk.GuardError, match="not the public StillDrawn repo"):
        mk._check_public_repo(pub, tmp_path / "priv")


def test_origin_url_rewrite_via_environment_is_refused_too(tmp_path, monkeypatch):
    monkeypatch.setattr(mk, "_origin_url", REAL_ORIGIN_URL)
    origin, pub = _bare_checkout(tmp_path)
    _sh("remote", "set-url", "origin", PINNED, cwd=pub)
    for k, v in {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": f"url.{origin}.insteadOf",
                 "GIT_CONFIG_VALUE_0": PINNED}.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(mk.GuardError, match="not the public StillDrawn repo"):
        mk._check_public_repo(pub, tmp_path / "priv")


def test_origin_url_with_credentials_is_refused_by_the_real_reader(tmp_path, monkeypatch):
    monkeypatch.setattr(mk, "_origin_url", REAL_ORIGIN_URL)
    _origin, pub = _bare_checkout(tmp_path)
    _sh("config", "remote.origin.url", "https://user:not-a-real-token@github.com/aaronlsmiles/stilldrawn.git",
        cwd=pub)
    with pytest.raises(mk.GuardError, match="origin URL carries credentials") as e:
        mk._check_public_repo(pub, tmp_path / "priv")
    assert "not-a-real-token" not in str(e.value)


def _expect(cell, shas=SHAS, mapping="stretch", gate_px=1.0):
    return mk.record_expectations(cell, ENV, shas, mapping, gate_px)


def test_record_state_accepts_a_complete_record(tmp_path):
    root = fake_tree(tmp_path)
    cell = mk.a9_cells(root)[0]
    p = tmp_path / "r.json"
    p.write_text(json.dumps(_fake_a9_record(cell, ENV, SHAS, "stretch", 1.0)), encoding="utf-8")
    assert mk.record_state(p, _expect(cell)) == "done"


def test_record_state_accepts_a_real_a9_record(tmp_path):
    root, cell, sets, load, extract, gate_px = _a9_setup(tmp_path)
    rec = mk.a9_clip(cell, root, "mps", ENV, sets, SHAS, "stretch", gate_px, load=load, extract=extract)
    p = tmp_path / "r.json"
    mk.write_atomic(p, mk.record_text(rec))
    assert mk.record_state(p, _expect(cell, gate_px=gate_px)) == "done"


@pytest.mark.parametrize("damage", [
    lambda r: r["masked"].pop("agent"),
    lambda r: r["masked"]["aaron"].pop("m64"),
    lambda r: r["masked"]["aaron"]["m32"].pop("f0_line_px_in_R"),
    lambda r: r["masked"]["agent"]["m16"].pop("no_scorable_frame"),
    lambda r: r["masked"]["agent"]["m16"].pop("region_frac"),
    lambda r: r["masked"]["agent"]["m16"].pop("chamfer_px"),
    lambda r: r["masked"]["agent"]["m16"].update(chamfer_series=[1.0, 1.0]),       # 2 != n_frames - 1
    lambda r: r["masked"]["aaron"]["m32"].update(chamfer_series=None),
    lambda r: r["whole_frame"].update(chamfer_series=[1.0] * 5),
    lambda r: r["whole_frame"].pop("chamfer_px"),
    lambda r: r.pop("n_frames"),
    lambda r: r.update(n_frames="5"),
    lambda r: r.pop("masked"),
    lambda r: r.pop("m_empty"),
    lambda r: r["m_empty"].pop("agent"),
])
def test_record_state_calls_an_incomplete_record_damaged(tmp_path, damage):
    root = fake_tree(tmp_path)
    cell = mk.a9_cells(root)[0]
    rec = _fake_a9_record(cell, ENV, SHAS, "stretch", 1.0)
    damage(rec)
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rec), encoding="utf-8")
    assert mk.record_state(p, _expect(cell)) == "damaged"


def test_run_a9_reruns_an_incomplete_record_and_logs_it(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    calls, lines = [], []

    def fake(cell, root_, device, env, sets, shas, mapping, gate_px):
        calls.append(cell["cell_id"])
        return _fake_a9_record(cell, env, shas, mapping, gate_px)

    gate = {c["public_id"]: 1.0 for c in cells}
    maps = {"wan22": "stretch", "gen4.5": "stretch"}
    mk.run_a9(root, cells, "mps", ENV, gate, maps, {}, SHAS, clip_fn=fake, log=lambda s: None)
    p = root / mk.MASKS_OUT / f"{cells[1]['cell_id']}.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    del rec["masked"]["agent"]["m32"]
    p.write_text(json.dumps(rec), encoding="utf-8")
    mk.run_a9(root, cells, "mps", ENV, gate, maps, {}, SHAS, clip_fn=fake, log=lines.append)
    assert calls == [cells[0]["cell_id"], cells[1]["cell_id"], cells[1]["cell_id"]]
    assert any("damaged record, re-running" in s for s in lines)


# ------------------------------------------------ review round 4: the guard's git layer
def _completed(args, code=0, out=b"", err=b""):
    return subprocess.CompletedProcess(args, code, out, err)


def test_git_helper_sets_timeouts_and_no_terminal_prompt(tmp_path, monkeypatch):
    seen = []

    def fake(cmd, **kw):
        seen.append((cmd, kw))
        return _completed(cmd)

    monkeypatch.setattr(mk, "_run", fake)
    mk._git(tmp_path, "fetch", "--quiet", "origin")
    mk._git(tmp_path, "ls-remote", "origin", "refs/heads/main")
    mk._git(tmp_path, "rev-parse", "HEAD")
    assert [kw["timeout"] for _cmd, kw in seen] == [120, 120, 60]
    for cmd, kw in seen:
        assert cmd[:3] == ["git", "-C", str(tmp_path)] and kw["env"]["GIT_TERMINAL_PROMPT"] == "0"
        assert kw["capture_output"] is True


def test_git_timeout_and_missing_git_become_guard_errors(tmp_path, monkeypatch):
    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw["timeout"])

    monkeypatch.setattr(mk, "_run", slow)
    with pytest.raises(mk.GuardError, match=r"git fetch --quiet origin timed out after 120 s"):
        mk._git(tmp_path, "fetch", "--quiet", "origin")

    def missing(cmd, **kw):
        raise FileNotFoundError("git")

    monkeypatch.setattr(mk, "_run", missing)
    with pytest.raises(mk.GuardError, match=r"git rev-parse HEAD could not run"):
        mk._git(tmp_path, "rev-parse", "HEAD")


def _runner_failing(match_args, code=128, err=b"fatal: unable to access the remote"):
    real = mk._run

    def run(cmd, **kw):
        if cmd[3:3 + len(match_args)] == list(match_args):
            return _completed(cmd, code, b"", err)
        return real(cmd, **kw)
    return run


def test_guard_turns_a_fetch_failure_into_a_guard_error(tmp_path, monkeypatch):
    pub, priv = guard_repos(tmp_path)
    monkeypatch.setattr(mk, "_run", _runner_failing(("fetch",)))
    with pytest.raises(mk.GuardError, match=r"git fetch --quiet origin failed .*unable to access"):
        mk.registration_guard(pub, priv)


def test_guard_runs_every_git_call_through_the_helper(tmp_path, monkeypatch):
    pub, priv = guard_repos(tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail(f"bare subprocess.run: {a}"))
    assert set(mk.registration_guard(pub, priv)) == set(GUARD_FILES)


def test_guard_reports_a_merge_base_error_apart_from_not_an_ancestor(tmp_path, monkeypatch):
    pub, priv = guard_repos(tmp_path)
    monkeypatch.setattr(mk, "_run", _runner_failing(("merge-base",), err=b"fatal: bad object"))
    with pytest.raises(mk.GuardError, match=r"git merge-base .*failed .*bad object") as e:
        mk.registration_guard(pub, priv)
    assert "not an ancestor" not in str(e.value)


def test_guard_refuses_a_stale_tracking_ref(tmp_path):
    pub, priv = guard_repos(tmp_path)
    _sh("config", "remote.origin.fetch", "+refs/tags/*:refs/tags/*", cwd=pub)   # fetch works but skips main
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(tmp_path / "origin.git"), str(other)], check=True, capture_output=True)
    (other / "later.txt").write_text("x\n", encoding="utf-8")
    _sh("add", "later.txt", cwd=other)
    _sh("commit", "-q", "-m", "later", cwd=other)
    _sh("push", "-q", "origin", "main", cwd=other)
    with pytest.raises(mk.GuardError, match="refs/remotes/origin/main is stale"):
        mk.registration_guard(pub, priv)


def test_guard_ignores_a_local_branch_named_origin_main(tmp_path):
    pub, priv = guard_repos(tmp_path, heading="### A8 \u2014 old\n")
    _sh("checkout", "-q", "-b", "origin/main", cwd=pub)                 # refs/heads/origin/main shadows it
    (pub / "docs" / "PREREGISTRATION.md").write_text("### A9 \u2014 2026-11-01: local only\n", encoding="utf-8")
    _sh("commit", "-q", "-am", "local A9", cwd=pub)
    with pytest.raises(mk.GuardError, match="origin/main's docs/PREREGISTRATION.md has no"):
        mk.registration_guard(pub, priv)


def test_guard_refuses_a_preregistration_that_is_not_utf8(tmp_path):
    pub, priv = guard_repos(tmp_path)
    (pub / "docs" / "PREREGISTRATION.md").write_bytes(b"### A9 \xe2\x80\x94 x\n\xff\xfe\n")
    _sh("commit", "-q", "-am", "bad bytes", cwd=pub)
    _sh("tag", "-f", "-a", "-m", "A9", mk.A9_TAG, cwd=pub)
    _sh("push", "-q", "origin", "main", cwd=pub)
    _sh("push", "-q", "-f", "origin", mk.A9_TAG, cwd=pub)
    with pytest.raises(mk.GuardError, match="UTF-8"):
        mk.registration_guard(pub, priv)


# ------------------------------------------------ review round 4: score, masks, run
def _score_env(tmp_path, monkeypatch):
    root = fake_tree(tmp_path / "repo")
    monkeypatch.setattr(mk, "ROOT", root)
    maps = random_maps(5)
    load, extract = _fake_io(maps)
    monkeypatch.setattr(mk.inkstab, "_load_frames", load)
    monkeypatch.setattr(mk.inkstab, "_line_maps", extract)
    monkeypatch.setattr(mk.inkstab, "_device", lambda: "mps")
    monkeypatch.setattr(mk, "environment", lambda *a, **k: dict(ENV))
    clip = tmp_path / "p47-test_idle_wan22.mp4"
    clip.write_bytes(b"not an A9 clip")
    return root, clip


def test_score_refuses_the_registered_masks_before_registration(tmp_path, monkeypatch):
    root, clip = _score_env(tmp_path, monkeypatch)
    doc = _doc({"p47-test_idle": _row("p47-test", "idle", (64, 36), [LEFT])})
    text = json.dumps(doc)
    (root / mk.MASK_FILES["agent"]).parent.mkdir(parents=True, exist_ok=True)
    (root / mk.MASK_FILES["agent"]).write_text(text, encoding="utf-8")
    copy = tmp_path / "elsewhere.json"
    copy.write_text(text, encoding="utf-8")                              # byte-identical copy
    out = tmp_path / "o.json"
    with pytest.raises(SystemExit, match="A9 mask set"):
        mk.main(["score", str(clip), "--masks", str(copy), "--row", "p47-test_idle", "--out", str(out)])
    assert not out.exists()
    copy.write_text(text + " ", encoding="utf-8")                        # other bytes: not the registered set
    assert mk.main(["score", str(clip), "--masks", str(copy), "--row", "p47-test_idle", "--out", str(out)]) == 0


def test_score_needs_the_run_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(mk, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match="runs/manifest.jsonl"):
        mk.main(["score", str(tmp_path / "x.mp4"), "--masks", "m.json", "--row", "r", "--out", "o.json"])


@pytest.mark.parametrize("bad", ["0", "-16", "x", "1.5"])
def test_score_margins_must_be_positive_ints(bad):
    with pytest.raises(SystemExit):
        mk.build_parser().parse_args(["score", "c.mp4", "--masks", "m", "--row", "r", "--out", "o", "--margins", bad])
    assert mk.build_parser().parse_args(["score", "c.mp4", "--masks", "m", "--row", "r", "--out", "o",
                                         "--margins", "8", "24"]).margins == [8, 24]


def test_load_masks_rejects_duplicate_keys(tmp_path):
    good = json.dumps(_doc({"act-line-1_idle": _row()}))
    for dup in (good.replace('"notes": ""', '"notes": "", "notes": "x"'),
                good.replace('"status": "drawn"', '"status": "drawn", "status": "drawn"'),
                good.replace('"rows": {', '"rows": {"act-line-1_idle": {}, ')):
        assert dup != good
        p = tmp_path / "dup.json"
        p.write_text(dup, encoding="utf-8")
        with pytest.raises(ValueError, match="duplicate"):
            mk.load_masks(p)


def test_read_masks_hashes_the_bytes_it_parsed(tmp_path):
    p = _mask_file(tmp_path / "m.json", {"act-line-1_idle": _row()})
    doc, sha = mk.read_masks(p)
    assert sha == mk.sha256_file(p) and doc["set"] == "aaron" and mk.load_masks(p) == doc


def test_regions_share_one_distance_transform_and_match_region():
    for _ in range(3):
        M = RNG.random((120, 200)) > 0.999
        got = mk.regions(M, mk.MARGINS)
        assert set(got) == set(mk.MARGINS)
        for m in mk.MARGINS:
            assert got[m].dtype == bool and np.array_equal(got[m], mk.region(M, m))
    empty = mk.regions(np.zeros((5, 5), bool), mk.MARGINS)
    assert all(r.all() for r in empty.values())


def test_run_a9_keeps_a_stale_record_until_its_replacement_is_written(tmp_path):
    root = fake_tree(tmp_path)
    cells = mk.a9_cells(root)
    gate = {c["public_id"]: 1.0 for c in cells}
    maps = {"wan22": "stretch", "gen4.5": "stretch"}

    def ok(cell, root_, device, env, sets, shas, mapping, gate_px):
        return _fake_a9_record(cell, env, shas, mapping, gate_px)

    mk.run_a9(root, cells, "mps", ENV, gate, maps, {}, SHAS, clip_fn=ok, log=lambda s: None)

    def stop(*args):
        raise SystemExit("Stop and investigate")

    newer = {"aaron": "e" * 64, "agent": "b" * 64}
    with pytest.raises(SystemExit):
        mk.run_a9(root, cells, "mps", ENV, gate, maps, {}, newer, clip_fn=stop, log=lambda s: None)
    p = root / mk.MASKS_OUT / f"{cells[0]['cell_id']}.json"
    assert p.exists() and json.loads(p.read_text(encoding="utf-8"))["masks_sha256"] == SHAS


@pytest.mark.parametrize("field,value", [("chamfer_px", ""), ("device", ""), ("cell_id", ""), ("chamfer_px", "abc")])
def test_read_gate_names_a_blank_or_bad_cell(tmp_path, field, value):
    rows = [{"cell_id": f"c{i}", "device": "mps", "chamfer_px": "1.0", "pass": "true"} for i in range(109)]
    rows[7][field] = value
    _gate_csv(tmp_path, [(r["cell_id"], r["device"], r["chamfer_px"], r["pass"]) for r in rows])
    with pytest.raises(SystemExit, match="row 8"):
        mk.read_gate(tmp_path)


def test_module_docstring_has_a_section_index():
    assert "Sections" in mk.__doc__
    for name in ("gate", "masked drift", "registration guard", "a9 run", "CLI"):
        assert name in mk.__doc__
