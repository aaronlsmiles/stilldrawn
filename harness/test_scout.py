"""Tests for harness/scout.py (A15.4; A16.6's placeholder). No engine is called: a fake runner
records the commands it would have run.

    python -m pytest harness/test_scout.py
"""
import json
import pathlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "analysis"))
import scout  # noqa: E402
import scout_rule  # noqa: E402
from pack_parser import _prompt_from_file  # noqa: E402

A15 = "### A15 — 2026-11-20: a Kling scout with a declared decision rule\n"
A16 = "### A16 — 2026-11-20: a Midjourney video scout, run by hand\n"
REFUSAL = ("task 0a1b2c3d FAILED: {'id': '0a1b2c3d', 'status': 'FAILED', "
           "'failure': 'Output failed', 'failureCode': 'INTERNAL.BAD_OUTPUT.CODE01'}")
KLING = ["flint-cu-line-2--cu-line-1_kling4", "flint-act-line-2--act-tone-3_kling4",
         "flint-est-line-2--est-black-3_kling4"] + [f"act-black-3_burst_kling4-h{k}" for k in (1, 2, 3)]


def arg(cmd, flag):
    return cmd[cmd.index(flag) + 1]


def tree(tmp_path):
    (tmp_path / "runs").mkdir()
    scout_rule.build_cells(tmp_path)
    for name in ("a10_cells.json", "a15_cells.json"):              # A10's and A15's own cell files
        (tmp_path / "analysis" / "out" / name).write_text('{"cells": "untouched"}\n')
    return tmp_path


def route(root, verdict="offered"):
    """The A15 route record (scout.py route), as the operator writes it before the scout."""
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "A15-ROUTE.md").write_text("captured\n")
    return scout.route("kling_4", verdict, root)


def public(tmp_path, monkeypatch, text):
    p = tmp_path / "public" / "PREREGISTRATION.md"
    p.parent.mkdir(exist_ok=True)
    p.write_text(text, encoding="utf-8")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(p))


class Writer:
    """Stands in for gen_video.py on the first cell: writes its clip and manifest line, as a real run does."""
    def __init__(self, root, fail=None):
        self.root, self.calls = root, []
        self.fail = {k: list(v) for k, v in (fail or {}).items()}

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if self.fail.get(arg(cmd, "--cell-id")):
            raise subprocess.CalledProcessError(1, cmd, stderr=self.fail[arg(cmd, "--cell-id")].pop(0))
        cell = arg(cmd, "--cell-id")
        clip = self.root / "runs" / "kling_4" / f"{cell}.mp4"
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"clip")
        with (self.root / "runs" / "manifest.jsonl").open("a") as f:
            f.write(json.dumps({"cell_id": cell, "out": f"runs/kling_4/{cell}.mp4"}) + "\n")
        return subprocess.CompletedProcess(cmd, 0, stderr="")


class Runner:
    def __init__(self, fail=None):
        self.calls, self.fail = [], {k: list(v) for k, v in (fail or {}).items()}

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        cell = arg(cmd, "--cell-id")
        if self.fail.get(cell):
            raise subprocess.CalledProcessError(1, cmd, stderr=self.fail[cell].pop(0))
        return subprocess.CompletedProcess(cmd, 0, stderr="")


def test_a_dry_run_lists_the_six_cells_with_their_frozen_prompts(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, "nothing registered\n")
    lines, runner = [], Runner()
    scout.run("kling_4", root=tree(tmp_path), dry_run=True, runner=runner, out=lines.append)
    rows = [ln.split("\t") for ln in lines if "\t" in ln]
    assert [r[0] for r in rows] == KLING and not runner.calls
    pack = str(HERE / "motion-prompts.md")
    assert rows[0][2] == _prompt_from_file(pack, "FLINT") and rows[3][2] == _prompt_from_file(pack, "BURST")


def test_the_kling_scout_refuses_until_a15_is_public(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, "### A10 — 2026-11-20: ladder\n" + A16)
    runner = Runner()
    with pytest.raises(SystemExit) as e:
        scout.run("kling_4", root=tree(tmp_path), runner=runner, out=lambda s: None)
    assert "A15" in str(e.value) and not runner.calls


def test_the_kling_scout_runs_a5s_composition_on_kling_4(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A15)
    root, runner = tree(tmp_path), Writer(tmp_path)
    route(root)
    a10 = (root / "analysis" / "out" / "a10_cells.json").read_bytes()
    first = scout.run("kling_4", root=root, limit=1, runner=runner, out=lambda s: None)
    flints = scout.run("kling_4", root=root, limit=2, runner=runner, out=lambda s: None)
    burst1 = scout.run("kling_4", root=root, limit=1, runner=runner, out=lambda s: None)
    res = scout.run("kling_4", root=root, runner=runner, out=lambda s: None)
    assert (first["new"], flints["new"], burst1["new"]) == (1, 2, 1) and res == {"new": 2, "skipped": 4, "refused": 0}
    assert [arg(c, "--cell-id") for c in runner.calls] == KLING
    for c in runner.calls:
        assert arg(c, "--engine") == "kling_4" and arg(c, "--ratio") == "auto_720p" and "--seed" not in c
    flint, burst = runner.calls[0], runner.calls[3]
    assert arg(flint, "--motion") == "FLINT" and arg(flint, "--panel").endswith("dataset/panels/cu-line-2.png")
    assert arg(flint, "--last-panel").endswith("dataset/panels/cu-line-1.png")
    assert arg(burst, "--motion") == "BURST" and "--last-panel" not in burst
    assert arg(burst, "--panel").endswith("dataset/panels/act-black-3.png")
    assert (root / "analysis" / "out" / "a10_cells.json").read_bytes() == a10       # never A10's files
    assert (root / "analysis" / "out" / "a15_cells.json").read_text() == '{"cells": "untouched"}\n'


def test_a_refused_first_cell_ends_the_limit_1_run_and_the_watch_repeats(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A15)
    root = tree(tmp_path)
    route(root)
    runner = Runner(fail={KLING[0]: [REFUSAL, REFUSAL]})
    res = scout.run("kling_4", root=root, limit=1, runner=runner, out=lambda s: None, err=lambda s: None)
    assert res == {"new": 0, "skipped": 0, "refused": 1}
    assert {arg(c, "--cell-id") for c in runner.calls} == {KLING[0]}               # cell 2 was never submitted
    with pytest.raises(SystemExit) as e:                                           # no clip yet: the watch repeats
        scout.run("kling_4", root=root, runner=Runner(), out=lambda s: None)
    assert "--limit 1" in str(e.value)


def test_a_cell_failed_twice_at_runway_is_refused_with_klings_model_and_resume_skips_it(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A15)
    root = tree(tmp_path)
    route(root)
    bad = KLING[1]
    scout.run("kling_4", root=root, limit=1, runner=Writer(root), out=lambda s: None)
    res = scout.run("kling_4", root=root, limit=2, runner=Writer(root, fail={bad: [REFUSAL, REFUSAL]}),
                    out=lambda s: None, err=lambda s: None)
    assert res == {"new": 1, "skipped": 1, "refused": 1}
    scout.run("kling_4", root=root, limit=1, runner=Writer(root), out=lambda s: None)   # the first BURST cell, watched
    res = scout.run("kling_4", root=root, runner=Writer(root), out=lambda s: None)
    assert res == {"new": 2, "skipped": 4, "refused": 0}
    rec = [json.loads(x) for x in (root / "runs" / "manifest.jsonl").read_text().splitlines() if '"refused"' in x][0]
    assert rec["cell_id"] == bad and rec["refused"] is True and rec["refusal"] == REFUSAL and rec["seed"] is None
    assert rec["model_version"] == "kling_4 (Runway dev API, X-Runway-Version 2024-11-06)"
    assert rec["ratio"] == "auto_720p" and rec["last_panel"] == "dataset/panels/act-tone-3.png"
    assert rec["motion_class"] == "FLINT"
    again = Runner()
    assert scout.run("kling_4", root=root, runner=again, out=lambda s: None)["refused"] == 0
    assert bad not in [arg(c, "--cell-id") for c in again.calls]


def test_a_written_reading_ends_the_scout(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A15)
    root = tree(tmp_path)
    route(root)
    (root / "analysis" / "out" / "a15_scout.json").write_text('{"reading": "scout failed: refused (2 of 6 cells)"}')
    runner = Runner()
    with pytest.raises(SystemExit) as e:
        scout.run("kling_4", root=root, limit=1, runner=runner, out=lambda s: None)
    assert "final" in str(e.value) and not runner.calls


def test_the_midjourney_scout_runs_by_hand_and_is_refused_here(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A15 + A16)
    runner = Runner()
    with pytest.raises(SystemExit) as e:
        scout.run("midjourney", root=tree(tmp_path), runner=runner, out=lambda s: None)
    assert "by hand" in str(e.value) and "mj_log.py" in str(e.value) and not runner.calls


def test_metrics_measure_each_clip_against_its_first_panel_in_the_scout_folders(tmp_path):
    root = tree(tmp_path)
    for cid in (KLING[0], KLING[4]):
        clip = root / "runs" / "kling_4" / f"{cid}.mp4"
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"x")
    calls = []
    assert scout.metrics("kling_4", root=root, runner=lambda cmd, **kw: calls.append(cmd), out=lambda s: None) == 2
    ink = [c for c in calls if c[1].endswith("inkstab.py")]
    assert ink[0][-1].endswith(f"runs/metrics-scout/{KLING[0]}.json")
    assert arg(ink[0], "--panel").endswith("dataset/panels/cu-line-2.png")
    assert arg(ink[0], "--lineart").endswith("dataset/lineart/cu-line-2-lines.png")
    assert any(c[-1].endswith(f"runs/metrics-motion-scout/{KLING[4]}.json") for c in calls)



# The metrics step's record: every delivered clip it measured, with
# the sha256 of each metric file; a tool that fails on a clip leaves it named with no file.
def test_the_metrics_step_records_every_delivered_clip_with_its_files_sha256(tmp_path):
    import hashlib
    root = tree(tmp_path)
    for cid in (KLING[0], KLING[4]):
        clip = root / "runs" / "kling_4" / f"{cid}.mp4"
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"x")

    def tools(cmd, **kw):                                    # the frozen tools, faked: write their JSON
        pathlib.Path(cmd[-1]).write_text(json.dumps({"cell": cmd[-1]}))
    scout.metrics("kling_4", root=root, runner=tools, out=lambda s: None)
    rec = json.loads((root / "analysis" / "out" / "a15_scout_metrics.json").read_text())
    assert sorted(rec["cells"]) == sorted([KLING[0], KLING[4]]) and rec["engine"] == "kling_4"
    f = root / "runs" / "metrics-scout" / f"{KLING[0]}.json"
    released = f.read_bytes().replace(f"{root}/".encode(), b"")             # the release form: no absolute prefix
    assert rec["cells"][KLING[0]]["inkstab"] == {"path": f"runs/metrics-scout/{KLING[0]}.json",
                                                 "sha256": hashlib.sha256(released).hexdigest()}
    assert f"{root}/".encode() in f.read_bytes()                            # the private file does carry it
    assert rec["cells"][KLING[4]]["motion"]["path"] == f"runs/metrics-motion-scout/{KLING[4]}.json"


def test_a_tool_failure_is_recorded_with_its_reason_and_a_rerun_is_flagged(tmp_path):
    root = tree(tmp_path)
    for cid in (KLING[0], KLING[4]):
        clip = root / "runs" / "kling_4" / f"{cid}.mp4"
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"x")
    fail = {"on": True}

    def tools(cmd, **kw):
        if fail["on"] and KLING[0] in cmd[2] and cmd[1].endswith("inkstab.py"):
            raise subprocess.CalledProcessError(1, cmd, stderr="cannot decode")
        pathlib.Path(cmd[-1]).write_text("{}")
    lines = []
    scout.metrics("kling_4", root=root, runner=tools, out=lines.append)
    p = root / "analysis" / "out" / "a15_scout_metrics.json"
    rec = json.loads(p.read_text())
    c = rec["cells"][KLING[0]]
    assert c["inkstab"]["sha256"] is None and c["motion"]["sha256"] and c["retried"] is False
    assert c["failures"] == [{"tool": "inkstab.py", "reason": "CalledProcessError: exit 1", "run": 1}]
    assert rec["cells"][KLING[4]]["inkstab"]["sha256"] and any("confirming re-run" in ln for ln in lines)
    scout.metrics("kling_4", root=root, runner=tools, out=lambda s: None)          # the confirming re-run fails
    c = json.loads(p.read_text())["cells"][KLING[0]]
    assert c["retried"] is True and len(c["failures"]) == 2 and c["failures"][1]["run"] == 2
    fail["on"] = False
    scout.metrics("kling_4", root=root, runner=tools, out=lambda s: None)          # a later run recovers
    assert json.loads(p.read_text())["cells"][KLING[0]]["inkstab"]["sha256"]


def test_a_dry_run_writes_no_record(tmp_path):
    root = tree(tmp_path)
    clip = root / "runs" / "kling_4" / f"{KLING[0]}.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"x")
    scout.metrics("kling_4", root=root, dry_run=True, out=lambda s: None)
    assert not (root / "analysis" / "out" / "a15_scout_metrics.json").exists()


# A15's route record and the watched first cell.
def test_the_route_verdict_is_recorded_once_after_a15_is_public(tmp_path, monkeypatch):
    root = tree(tmp_path)
    public(tmp_path, monkeypatch, "### A10 — 2026-11-20: ladder\n")
    with pytest.raises(SystemExit) as e:
        scout.route("kling_4", "offered", root)
    assert "A15" in str(e.value)
    public(tmp_path, monkeypatch, A15)
    with pytest.raises(SystemExit) as e:
        scout.route("kling_4", "offered", root)
    assert "docs/A15-ROUTE.md" in str(e.value)
    (root / "docs").mkdir()
    (root / "docs" / "A15-ROUTE.md").write_text("captured\n")
    rec = scout.route("kling_4", "offered", root)
    assert rec["verdict"] == "offered" and len(rec["record_sha256"]) == 64
    with pytest.raises(SystemExit) as e:
        scout.route("kling_4", "not-offered", root)
    assert "never changed" in str(e.value)
    with pytest.raises(SystemExit):
        scout.route("midjourney", "offered", root)


def test_the_scout_needs_its_route_record_and_runs_its_first_cell_alone(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A15)
    root, runner = tree(tmp_path), Runner()
    with pytest.raises(SystemExit) as e:
        scout.run("kling_4", root=root, runner=runner, out=lambda s: None)
    assert "a15_route.json" in str(e.value) and not runner.calls
    route(root, "not-offered")
    with pytest.raises(SystemExit) as e:
        scout.run("kling_4", root=root, limit=1, runner=runner, out=lambda s: None)
    assert "not offered" in str(e.value) and not runner.calls


def test_the_first_cell_runs_alone_then_the_rest(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A15)
    root, runner = tree(tmp_path), Runner()
    route(root)
    with pytest.raises(SystemExit) as e:
        scout.run("kling_4", root=root, runner=runner, out=lambda s: None)
    assert "--limit 1" in str(e.value) and not runner.calls


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg needed")
def test_adopt_records_a_scout_cell_and_refuses_midjourney(tmp_path, monkeypatch):
    import gen_video as gv
    public(tmp_path, monkeypatch, A15)
    root = tree(tmp_path)
    monkeypatch.setattr(gv, "ROOT", root)
    f = root / "incoming" / "k.mp4"
    f.parent.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=1260x720:d=0.2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(f)], check=True)
    line = scout.adopt("kling_4", KLING[0], f, "task-k", root)
    assert line["last_panel"].endswith("dataset/panels/cu-line-1.png") and line["motion_class"] == "FLINT"
    assert line["request"]["promptImage"][1]["position"] == "last" and line["task_id"] == "task-k"
    with pytest.raises(SystemExit) as e:
        scout.adopt("midjourney", "act-black-3_burst_mjv-h1", f, "x", root)
    assert "by hand" in str(e.value)


def test_adopt_refuses_unless_a15_is_in_the_public_preregistration(tmp_path, monkeypatch):
    root = tree(tmp_path)
    f = root / "k.mp4"
    f.write_bytes(b"x")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(tmp_path / "no-public-prereg.md"))
    with pytest.raises(SystemExit) as e:
        scout.adopt("kling_4", KLING[0], f, "task-k", root)
    assert "REFUSING" in str(e.value) and "A15" in str(e.value)
    assert not (root / "runs" / "manifest.jsonl").exists()


def lines_for(root, *cells, refused=()):
    """Manifest lines as a run left them: delivered (with a clip) for `cells`, refused for `refused`."""
    with (root / "runs" / "manifest.jsonl").open("a") as f:
        for cid in cells:
            clip = root / "runs" / "kling_4" / f"{cid}.mp4"
            clip.parent.mkdir(parents=True, exist_ok=True)
            clip.write_bytes(b"clip")
            f.write(json.dumps({"cell_id": cid, "out": f"runs/kling_4/{cid}.mp4"}) + "\n")
        for cid in refused:
            f.write(json.dumps({"cell_id": cid, "refused": True, "refusal": REFUSAL, "out": None}) + "\n")


def watched(tmp_path, monkeypatch, delivered=(), refused=()):
    public(tmp_path, monkeypatch, A15)
    root = tree(tmp_path)
    route(root)
    lines_for(root, *delivered, refused=refused)
    return root


def test_after_the_first_flint_clip_a_plain_run_is_refused_and_limit_may_not_pass_the_pending_flint(tmp_path, monkeypatch):
    root = watched(tmp_path, monkeypatch, delivered=KLING[:1])
    runner = Runner()
    for kw in ({}, {"limit": 3}):                                  # plain, or past the two pending FLINT cells
        with pytest.raises(SystemExit) as e:
            scout.run("kling_4", root=root, runner=runner, out=lambda s: None, **kw)
        assert "REFUSING" in str(e.value) and "BURST" in str(e.value) and not runner.calls
    res = scout.run("kling_4", root=root, limit=2, runner=runner, out=lambda s: None)    # exactly the pending FLINT
    assert res["new"] == 2 and [arg(c, "--cell-id") for c in runner.calls] == KLING[1:3]


def test_a_refused_flint_cell_leaves_fewer_pending_so_the_limit_bound_follows(tmp_path, monkeypatch):
    root = watched(tmp_path, monkeypatch, delivered=KLING[:1], refused=KLING[1:2])
    with pytest.raises(SystemExit):                                # one FLINT pending now: 2 is too many
        scout.run("kling_4", root=root, limit=2, runner=Runner(), out=lambda s: None)
    assert scout.run("kling_4", root=root, limit=1, runner=Runner(), out=lambda s: None)["new"] == 1


def test_with_all_flint_lines_in_place_the_first_burst_cell_runs_alone(tmp_path, monkeypatch):
    root = watched(tmp_path, monkeypatch, delivered=KLING[:3])
    runner = Runner()
    for kw in ({}, {"limit": 2}):
        with pytest.raises(SystemExit) as e:
            scout.run("kling_4", root=root, runner=runner, out=lambda s: None, **kw)
        assert "REFUSING" in str(e.value) and "--limit 1" in str(e.value) and not runner.calls
    res = scout.run("kling_4", root=root, limit=1, runner=runner, out=lambda s: None)
    assert res["new"] == 1 and [arg(c, "--cell-id") for c in runner.calls] == KLING[3:4]


def test_a_refused_first_burst_cell_repeats_the_watch(tmp_path, monkeypatch):
    root = watched(tmp_path, monkeypatch, delivered=KLING[:3], refused=KLING[3:4])
    runner = Runner()
    with pytest.raises(SystemExit) as e:
        scout.run("kling_4", root=root, runner=runner, out=lambda s: None)
    assert "--limit 1" in str(e.value) and not runner.calls
    assert scout.run("kling_4", root=root, limit=1, runner=runner, out=lambda s: None)["new"] == 1


def test_once_a_burst_clip_is_delivered_a_plain_run_is_allowed(tmp_path, monkeypatch):
    root = watched(tmp_path, monkeypatch, delivered=KLING[:4])
    runner = Runner()
    assert scout.run("kling_4", root=root, runner=runner, out=lambda s: None)["new"] == 2
    assert [arg(c, "--cell-id") for c in runner.calls] == KLING[4:]


def test_a_changed_route_doc_stops_the_scout_before_any_submission(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A15)
    root, runner = tree(tmp_path), Runner()
    route(root)
    (root / "docs" / "A15-ROUTE.md").write_text("captured, then edited\n")
    with pytest.raises(SystemExit) as e:
        scout.run("kling_4", root=root, limit=1, runner=runner, out=lambda s: None)
    assert str(e.value).startswith("REFUSING: docs/A15-ROUTE.md has changed since its verdict was recorded")
    assert not runner.calls


def test_the_flint_cells_must_precede_the_burst_cells(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A15)
    root, runner = tree(tmp_path), Runner()
    route(root)
    cells = json.loads((root / scout.CELLS_JSON).read_text())
    cells["kling_4"] = cells["kling_4"][3:] + cells["kling_4"][:3]               # BURST cells first
    (root / scout.CELLS_JSON).write_text(json.dumps(cells))
    with pytest.raises(SystemExit) as e:
        scout.run("kling_4", root=root, limit=1, runner=runner, out=lambda s: None)
    assert "FLINT cells must precede the BURST cells" in str(e.value) and not runner.calls


def test_an_orphan_scout_clip_names_scouts_adopt(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A15)
    root, runner = tree(tmp_path), Runner()
    route(root)
    orphan = root / "runs" / "kling_4" / f"{KLING[0]}.mp4"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"x")
    with pytest.raises(SystemExit) as e:
        scout.run("kling_4", root=root, limit=1, runner=runner, out=lambda s: None)
    assert f"scout.py adopt --cell {KLING[0]} --file <delivered path> --task <task id>" in str(e.value)
    assert not runner.calls


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg needed")
def test_adopt_takes_its_arguments_from_the_command_the_run_was_given(tmp_path, monkeypatch):
    import gen_video as gv
    public(tmp_path, monkeypatch, A15)
    root, runner = tree(tmp_path), Runner()
    route(root)
    monkeypatch.setattr(gv, "ROOT", root)
    scout.run("kling_4", root=root, limit=1, runner=runner, out=lambda s: None)
    (cmd,) = runner.calls
    ran = gv.build_parser().parse_args(cmd[2:])                       # a FLINT cell: two images
    record = {"model": "kling_4", "request": gv.runway_body(ran, gv.resolve_prompt(ran.motion, ran.pack)),
              "task_id": "t-1", "seed": None, "task": {"id": "t-1", "model": "kling-4"}}
    f = root / "incoming" / "k.mp4"
    f.parent.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=1260x720:d=0.2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(f)], check=True)
    line = scout.adopt("kling_4", ran.cell_id, f, "t-1", root, record=record)
    assert line["adopted"]["task_record"] == "the route record the run printed" and line["request"] == record["request"]
    assert len(line["request"]["promptImage"]) == 2
