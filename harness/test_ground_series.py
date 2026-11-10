"""Tests for ground_series.py's --draw (A12). No engine and no metric is run.

    python -m pytest harness/test_ground_series.py
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ground_series as gs  # noqa: E402

A12 = "### A12 — 2026-11-20: grey ground with a noise floor\n"
LEVELS = ("100", "090", "080", "065", "052")


class Runner:
    """Records commands and keyword arguments. `fail` maps a cell to the stderr of each failing
    attempt, in order (then it succeeds); `partial` maps a cell to a clip path a failing attempt
    leaves behind (as harness/test_ladder.py's runner)."""
    def __init__(self, fail=None, partial=None):
        self.calls, self.kwargs = [], []
        self.fail = {k: list(v) for k, v in (fail or {}).items()}
        self.partial = dict(partial or {})

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        self.kwargs.append(kw)
        cell = cmd[cmd.index("--cell-id") + 1] if "--cell-id" in cmd else None
        if self.fail.get(cell):
            if cell in self.partial:
                self.partial[cell].parent.mkdir(parents=True, exist_ok=True)
                self.partial[cell].write_bytes(b"half")
            raise subprocess.CalledProcessError(1, cmd, stderr=self.fail[cell].pop(0))
        return subprocess.CompletedProcess(cmd, 0, stderr="")


REFUSAL = ("task 0a1b2c3d FAILED: {'id': '0a1b2c3d', 'status': 'FAILED', "
           "'failure': 'Content moderation', 'failureCode': 'SAFETY.INPUT'}")
REFUSED = "-> submit gen4_turbo (/image_to_video)\n   ... FAILED (5s)\n" + REFUSAL + "\nTraceback (gen_video)\n"
CANCELLED = "task 0a1b2c3d CANCELLED: {'id': '0a1b2c3d', 'status': 'CANCELLED'}\n"
OTHER = "op: not signed in\n"


def public(tmp_path, monkeypatch, text):
    p = tmp_path / "PUBLIC-PREREGISTRATION.md"
    p.write_text(text, encoding="utf-8")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(p))


def arg(cmd, flag):
    return cmd[cmd.index(flag) + 1]


def test_without_draw_the_command_is_exactly_a3s():
    assert gs.gen_cmd(1.00, "wan22") == [
        str(gs.VENV_PY), str(gs.HERE / "gen_video.py"), "--engine", "wan22",
        "--panel", str(gs.ROOT / "dataset/panels" / "ground-cu-line-1-v100.png"),
        "--motion", "IDLE", "--cell-id", "ground-cu-line-1-v100_idle_wan22", "--ratio", "1280:720"]


def test_cell_ids_by_draw():
    assert gs.cell_id(0.80, "wan22") == "ground-cu-line-1-v080_idle_wan22"     # A3's cell
    assert gs.cell_id(1.00, "wan22", 1) == "ground-cu-line-1-v100_idle_wan22-d1"
    assert gs.cell_id(0.52, "ltx23", 2) == "ground-cu-line-1-v052_idle_ltx23-d2"
    assert gs.cell_id(0.65, "gen4_turbo", 3) == "ground-cu-line-1-v065_idle_gen4t-d3"


def test_local_draws_one_to_three_run_at_the_three_seeds():
    for eng in ("wan22", "ltx23"):
        for draw, seed in ((1, 20260812), (2, 20260813), (3, 20260814)):
            assert gs.draw_seed(eng, draw) == seed
            c = gs.gen_cmd(0.8, eng, draw)
            assert arg(c, "--seed") == str(seed)
            assert arg(c, "--cell-id").endswith(f"-d{draw}")


def test_turbo_draws_two_and_three_send_their_draw_seeds():
    # Ruled 7 Nov 2026: Runway takes a seed; A12's Turbo draws send the series' seeds (gen_video.py
    # then routes them through harness/runway_task.py). A3's draw 1 was sent none.
    for draw, seed in ((2, 20260813), (3, 20260814)):
        assert gs.draw_seed("gen4_turbo", draw) == seed
        c = gs.gen_cmd(0.8, "gen4_turbo", draw)
        assert arg(c, "--seed") == str(seed) and arg(c, "--cell-id").endswith(f"-d{draw}")
    assert "--seed" not in gs.gen_cmd(0.8, "gen4_turbo")      # A3's cells: unchanged


def test_refusals():
    with pytest.raises(SystemExit) as e:          # Turbo's draw 1 is A3's existing cell
        gs.check_draw("gen4_turbo", 1)
    assert "gen4_turbo" in str(e.value) and "draw 1" in str(e.value)
    for eng in ("gen4.5", "h3-fal"):              # A12 does not extend these engines
        for draw in (1, 2, 3):
            with pytest.raises(SystemExit):
                gs.check_draw(eng, draw)
    for eng in gs.ENGINE_TAG:                     # no --draw: A3's behaviour, every engine
        gs.check_draw(eng, None)
    for draw in (0, 4):
        with pytest.raises(SystemExit):
            gs.check_draw("wan22", draw)


def test_draws_refuse_until_a12_is_public(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, "### A10 — 2026-11-20: ladder\n")
    monkeypatch.setenv("STILLDRAWN_HW", "test-gpu")
    monkeypatch.setattr(gs, "ROOT", tmp_path)
    for eng, draw in (("wan22", 1), ("ltx23", 3), ("gen4_turbo", 2)):
        runner = Runner()
        with pytest.raises(SystemExit) as e:
            gs.run(eng, draw, runner=runner)
        assert "A12" in str(e.value) and not runner.calls


def test_local_draw_one_runs_the_five_cells_once_registered(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A12)
    monkeypatch.setenv("STILLDRAWN_HW", "test-gpu")
    monkeypatch.setattr(gs, "ROOT", tmp_path)
    runner = Runner()
    gs.run("ltx23", 1, runner=runner)
    assert [arg(c, "--cell-id") for c in runner.calls] == [
        f"ground-cu-line-1-v{v}_idle_ltx23-d1" for v in LEVELS]
    assert all(arg(c, "--seed") == "20260812" for c in runner.calls)


def test_turbo_draw_two_runs_the_five_cells_once_registered(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A12)
    monkeypatch.setattr(gs, "ROOT", tmp_path)
    runner = Runner()
    gs.run("gen4_turbo", 2, runner=runner)
    assert [arg(c, "--cell-id") for c in runner.calls] == [
        f"ground-cu-line-1-v{v}_idle_gen4t-d2" for v in LEVELS]
    assert all(arg(c, "--seed") == "20260813" for c in runner.calls)


def test_a3s_existing_cell_is_not_a_draw(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A12)
    monkeypatch.setenv("STILLDRAWN_HW", "test-gpu")
    monkeypatch.setattr(gs, "ROOT", tmp_path)
    a3 = tmp_path / "runs" / "wan22" / "ground-cu-line-1-v100_idle_wan22.mp4"
    a3.parent.mkdir(parents=True)
    a3.write_bytes(b"x")
    runner = Runner()
    gs.run("wan22", 1, runner=runner)              # A3's file does not stand in for -d1
    assert len(runner.calls) == 5
    assert arg(runner.calls[0], "--cell-id") == "ground-cu-line-1-v100_idle_wan22-d1"


def test_without_draw_needs_no_registration(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, "nothing registered\n")
    monkeypatch.delenv("STILLDRAWN_HW", raising=False)       # nor a named machine
    monkeypatch.setattr(gs, "ROOT", tmp_path)
    runner = Runner()
    gs.run("wan22", runner=runner)                  # A3's own cells: behaviour unchanged
    assert len(runner.calls) == 5 and all("--seed" not in c for c in runner.calls)
    assert all(not arg(c, "--cell-id").endswith(("-d1", "-d2", "-d3")) for c in runner.calls)


def test_metric_file_names_carry_the_draw_suffix(tmp_path, monkeypatch):
    monkeypatch.setattr(gs, "ROOT", tmp_path)
    for eng, tag, draw in (("gen4_turbo", "gen4t", 2), ("wan22", "wan22", 1)):
        clip = tmp_path / "runs" / eng / f"ground-cu-line-1-v090_idle_{tag}-d{draw}.mp4"
        clip.parent.mkdir(parents=True)
        clip.write_bytes(b"x")
        runner = Runner()
        gs.metrics(eng, draw, runner=runner)
        assert len(runner.calls) == 1
        cmd = runner.calls[0]
        assert arg(cmd, "--out").endswith(
            f"runs/metrics-ground/ground-cu-line-1-v090_idle_{tag}-d{draw}.json")
        assert arg(cmd, "--panel").endswith("dataset/panels/ground-cu-line-1-v090.png")


def test_the_cli_refuses_draws_outside_the_rule(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, "nothing registered\n")   # even a slip could not submit
    monkeypatch.setattr(gs, "ROOT", tmp_path)
    with pytest.raises(SystemExit):
        gs.main(["run", "--engine", "wan22", "--draw", "4"])
    with pytest.raises(SystemExit) as e:
        gs.main(["run", "--engine", "gen4_turbo", "--draw", "1"])
    assert "draw 1" in str(e.value) and not str(e.value).startswith("REFUSING")  # the rule, not the tripwire
    with pytest.raises(SystemExit) as e:
        gs.main(["metrics", "--engine", "gen4.5", "--draw", "2"])
    assert "gen4.5" in str(e.value)


def test_draw_stem_is_the_one_source_of_a_draws_file_name():
    stem = "ground-cu-line-1-v065_idle_"
    for eng, tag in (("wan22", "wan22"), ("ltx23", "ltx23")):
        assert [gs.draw_stem(0.65, eng, d) for d in (1, 2, 3)] == [
            f"{stem}{tag}-d{d}" for d in (1, 2, 3)]
    assert [gs.draw_stem(0.65, "gen4_turbo", d) for d in (1, 2, 3)] == [
        f"{stem}gen4t", f"{stem}gen4t-d2", f"{stem}gen4t-d3"]   # Turbo's draw 1 is A3's cell
    assert gs.draw_stem(0.65, "wan22", None) == f"{stem}wan22"
    for eng in gs.DRAWS:                                       # the runner uses the same stem
        for d in gs.DRAWS[eng]:
            c = gs.gen_cmd(0.65, eng, d)
            assert arg(c, "--cell-id") == gs.draw_stem(0.65, eng, d)


def test_local_draws_refuse_without_the_machine_named(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A12)
    monkeypatch.setattr(gs, "ROOT", tmp_path)
    monkeypatch.delenv("STILLDRAWN_HW", raising=False)
    runner = Runner()
    with pytest.raises(SystemExit) as e:
        gs.run("wan22", 2, runner=runner)
    assert "STILLDRAWN_HW" in str(e.value) and not runner.calls


def made(root, *cell_ids):
    """Clip lines in the manifest, as gen_video.py writes them (the keys run reads)."""
    m = root / "runs" / "manifest.jsonl"
    m.parent.mkdir(parents=True, exist_ok=True)
    with m.open("a") as f:
        for cid in cell_ids:
            f.write(json.dumps({"cell_id": cid, "out": f"runs/x/{cid}.mp4"}) + "\n")


def clip(root, engine, cell):
    p = root / "runs" / engine / f"{cell}.mp4"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    return p


def lines(root):
    m = root / "runs" / "manifest.jsonl"
    return [json.loads(x) for x in m.read_text().splitlines()] if m.exists() else []


def registered(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A12)
    monkeypatch.setenv("STILLDRAWN_HW", "test-gpu")
    monkeypatch.setattr(gs, "ROOT", tmp_path)


def test_an_existing_draw_clip_with_its_line_is_skipped_on_rerun(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    clip(tmp_path, "gen4_turbo", "ground-cu-line-1-v080_idle_gen4t-d2")
    made(tmp_path, "ground-cu-line-1-v080_idle_gen4t-d2")
    runner = Runner()
    gs.run("gen4_turbo", 2, runner=runner)
    assert len(runner.calls) == 4
    assert "ground-cu-line-1-v080_idle_gen4t-d2" not in [arg(c, "--cell-id") for c in runner.calls]


def test_a_refused_draw_is_skipped_on_rerun(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    cell = "ground-cu-line-1-v065_idle_gen4t-d3"
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "manifest.jsonl").write_text(json.dumps({"cell_id": cell, "refused": True, "out": None}) + "\n")
    runner = Runner()
    gs.run("gen4_turbo", 3, runner=runner)
    assert len(runner.calls) == 4 and cell not in [arg(c, "--cell-id") for c in runner.calls]


def test_an_orphan_draw_clip_stops_the_run_and_is_named(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    orphan = clip(tmp_path, "wan22", "ground-cu-line-1-v100_idle_wan22-d2")
    runner = Runner()
    with pytest.raises(SystemExit) as e:
        gs.run("wan22", 2, runner=runner)
    assert str(orphan) in str(e.value) and "orphan" in str(e.value) and not runner.calls


def test_a_draw_clip_line_without_its_file_stops_the_run_and_is_named(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    made(tmp_path, "ground-cu-line-1-v090_idle_ltx23-d3")
    runner = Runner()
    with pytest.raises(SystemExit) as e:
        gs.run("ltx23", 3, runner=runner)
    assert "ground-cu-line-1-v090_idle_ltx23-d3" in str(e.value) and "missing" in str(e.value)
    assert [arg(c, "--cell-id") for c in runner.calls] == ["ground-cu-line-1-v100_idle_ltx23-d3"]


def test_a_draw_runs_with_stderr_captured_and_echoed(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    runner = Runner()
    gs.run("gen4_turbo", 2, runner=runner)
    assert all(kw == {"check": True, "stderr": subprocess.PIPE, "text": True} for kw in runner.kwargs)


def test_a_turbo_draw_failed_twice_by_runway_is_recorded_as_refused(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    cell = "ground-cu-line-1-v052_idle_gen4t-d2"
    runner = Runner(fail={cell: [REFUSED, REFUSED]})
    gs.run("gen4_turbo", 2, runner=runner)
    ids = [arg(c, "--cell-id") for c in runner.calls]
    assert ids.count(cell) == 2 and len(ids) == 6                     # one identical resubmission
    assert runner.calls[-1] == runner.calls[-2]
    (line,) = lines(tmp_path)
    assert line["cell_id"] == cell and line["refused"] is True and line["out"] is None
    assert line["refusal"] == REFUSAL                                 # the last FAILED line, verbatim
    assert line["engine"] == "gen4_turbo" and line["motion_class"] == "IDLE" and line["seed"] == 20260813
    assert line["panel"] == "dataset/panels/ground-cu-line-1-v052.png"
    assert line["model_version"].startswith("gen4_turbo (Runway dev API, X-Runway-Version ")
    import gen_video
    assert line["prompt"] == gen_video.resolve_prompt("IDLE")
    assert list(line)[-2:] == ["refused", "refusal"] and "prompt_pack" not in line
    runner2 = Runner()
    gs.run("gen4_turbo", 2, runner=runner2)                           # resumes: the refusal is not retried
    assert cell not in [arg(c, "--cell-id") for c in runner2.calls]


def test_a_turbo_draw_that_succeeds_on_resubmission_is_not_refused(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    cell = "ground-cu-line-1-v100_idle_gen4t-d3"
    runner = Runner(fail={cell: [REFUSED]})
    gs.run("gen4_turbo", 3, runner=runner)
    assert [arg(c, "--cell-id") for c in runner.calls].count(cell) == 2 and lines(tmp_path) == []


@pytest.mark.parametrize("errs", [[REFUSED, OTHER], [OTHER, REFUSED], [CANCELLED, CANCELLED],
                                  [REFUSED, CANCELLED], [OTHER, OTHER]])
def test_any_other_double_failure_of_a_turbo_draw_stops_without_a_line(tmp_path, monkeypatch, errs):
    registered(tmp_path, monkeypatch)
    cell = "ground-cu-line-1-v090_idle_gen4t-d2"
    runner = Runner(fail={cell: errs})
    with pytest.raises(SystemExit) as e:
        gs.run("gen4_turbo", 2, runner=runner)
    assert cell in str(e.value) and "Not recorded as refused" in str(e.value)
    assert lines(tmp_path) == []


def test_a_local_draw_that_fails_twice_stops_even_on_a_runway_like_line(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    cell = "ground-cu-line-1-v100_idle_wan22-d1"
    runner = Runner(fail={cell: [REFUSED, REFUSED]})
    with pytest.raises(SystemExit) as e:
        gs.run("wan22", 1, runner=runner)
    assert cell in str(e.value) and "harness fault" in str(e.value) and lines(tmp_path) == []
    assert len(runner.calls) == 2


def test_a_failed_draw_attempt_that_leaves_a_clip_stops_without_resubmitting(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    cell = "ground-cu-line-1-v100_idle_gen4t-d2"
    half = tmp_path / "runs" / "gen4_turbo" / f"{cell}.mp4"
    runner = Runner(fail={cell: [REFUSED, REFUSED]}, partial={cell: half})
    with pytest.raises(SystemExit) as e:
        gs.run("gen4_turbo", 2, runner=runner)
    assert str(half) in str(e.value) and len(runner.calls) == 1 and lines(tmp_path) == []


def test_without_draw_the_a3_path_is_unchanged(tmp_path, monkeypatch):
    """A3's cells: skipped when the clip exists (no manifest check), one attempt, no stderr capture."""
    public(tmp_path, monkeypatch, "nothing registered\n")
    monkeypatch.setattr(gs, "ROOT", tmp_path)
    clip(tmp_path, "gen4_turbo", "ground-cu-line-1-v080_idle_gen4t")      # no manifest line: still skipped
    runner = Runner()
    gs.run("gen4_turbo", runner=runner)
    assert len(runner.calls) == 4 and all(kw == {"check": True} for kw in runner.kwargs)
    runner = Runner(fail={"ground-cu-line-1-v100_idle_gen4t": [REFUSED, REFUSED]})
    with pytest.raises(subprocess.CalledProcessError):
        gs.run("gen4_turbo", runner=runner)
    assert len(runner.calls) == 1 and lines(tmp_path) == []


# ------------------------------------------------ A12.3.1: a machine lost mid-series (ruled 10 Nov 2026)
WAN = [f"ground-cu-line-1-v{v}_idle_wan22-d{d}" for d in (1, 2, 3) for v in LEVELS]


def pod_manifest(root, recs):
    p = root / "runs" / "pod-a10-manifest.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in recs))
    return p


def pod_line(cell, hw="pod-a"):
    return {"cell_id": cell, "engine": "wan22", "model_version": f"Wan 2.2 [{hw}]", "out": f"runs/wan22/{cell}.mp4"}


def test_series_cells_are_the_fifteen_local_draws():
    assert gs.series_cells("wan22") == WAN
    assert len(gs.series_cells("ltx23")) == 15 and all(c.endswith(("-d1", "-d2", "-d3")) for c in gs.series_cells("ltx23"))


def test_abandon_writes_the_whole_series_once_and_keeps_retrieved_draws_privately(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    got = WAN[:4]                                                    # four draws came back with their clips
    for c in got:
        clip(tmp_path, "wan22", c)
    ladder = {"cell_id": "ladder-act-black-1_still_ltx23", "out": "runs/ltx23/ladder-act-black-1_still_ltx23.mp4"}
    pm = pod_manifest(tmp_path, [pod_line(c) for c in got + [WAN[4]]] + [ladder])   # WAN[4]: a line, no clip
    original = pm.read_text()
    gs.abandon("wan22", pod_manifest=pm, out=lambda *_: None)
    recs = lines(tmp_path)
    assert [r["cell_id"] for r in recs] == WAN                      # one line per cell of the series
    assert all(r["abandoned"] == "machine lost" and r["out"] is None and r["engine"] == "wan22" for r in recs)
    assert [r["seed"] for r in recs] == [20260812] * 5 + [20260813] * 5 + [20260814] * 5
    assert [r["clip_kept_privately"] for r in recs] == [True] * 4 + [False] * 11
    assert [r["model_version"] for r in recs] == ["Wan 2.2 [pod-a]"] * 5 + [None] * 10
    for c in got:                                                    # kept privately, out of the engine folder
        assert not (tmp_path / "runs" / "wan22" / f"{c}.mp4").exists()
        assert (tmp_path / "runs" / "abandoned" / "wan22" / f"{c}.mp4").read_bytes() == b"x"
    assert [json.loads(x) for x in pm.read_text().splitlines()] == [ladder]   # the rest merges as usual
    (kept,) = (tmp_path / "runs").glob("pod-a10-manifest-lost-*.jsonl")
    assert kept.read_text() == original                              # the lost machine's own record, untouched


def test_abandon_without_anything_retrieved_still_records_the_series(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    gs.abandon("ltx23", out=lambda *_: None)
    recs = lines(tmp_path)
    assert [r["cell_id"] for r in recs] == gs.series_cells("ltx23")
    assert not any(r["clip_kept_privately"] for r in recs) and all(r["model_version"] is None for r in recs)


def test_after_abandon_the_rerun_makes_the_same_cells_at_the_same_seeds(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    for c in WAN[:3]:
        clip(tmp_path, "wan22", c)
    gs.abandon("wan22", out=lambda *_: None)
    assert gs.manifest_cells(tmp_path) == (set(), set())            # an abandoned draw is neither made nor refused
    seeds = {r["cell_id"]: r["seed"] for r in lines(tmp_path)}
    for d in (1, 2, 3):
        runner = Runner()
        gs.run("wan22", d, runner=runner)
        assert [arg(c, "--cell-id") for c in runner.calls] == [c for c in WAN if c.endswith(f"-d{d}")]
        assert all(int(arg(c, "--seed")) == seeds[arg(c, "--cell-id")] for c in runner.calls)


def test_a_second_loss_is_refused_and_changes_nothing(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    gs.abandon("wan22", out=lambda *_: None)
    before = (tmp_path / "runs" / "manifest.jsonl").read_text()
    clip(tmp_path, "wan22", WAN[0])                                  # the fresh machine's partial draw
    with pytest.raises(SystemExit) as e:
        gs.abandon("wan22", out=lambda *_: None)
    assert "second loss" in str(e.value) and "incomplete: N points missing" in str(e.value)
    assert (tmp_path / "runs" / "manifest.jsonl").read_text() == before
    assert (tmp_path / "runs" / "wan22" / f"{WAN[0]}.mp4").exists()     # not moved: it stands in the series
    gs.abandon("ltx23", out=lambda *_: None)                       # the other engine keeps its own one re-run


def test_abandon_refuses_a_series_already_in_the_manifest(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    made(tmp_path, WAN[7])
    clip(tmp_path, "wan22", WAN[0])
    before = (tmp_path / "runs" / "manifest.jsonl").read_text()
    with pytest.raises(SystemExit) as e:
        gs.abandon("wan22", out=lambda *_: None)
    assert WAN[7] in str(e.value) and (tmp_path / "runs" / "manifest.jsonl").read_text() == before
    assert (tmp_path / "runs" / "wan22" / f"{WAN[0]}.mp4").exists()


def test_abandon_refuses_a_measured_draw(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    m = tmp_path / "runs" / "metrics-ground" / f"{WAN[2]}.json"
    m.parent.mkdir(parents=True)
    m.write_text("{}")
    with pytest.raises(SystemExit) as e:
        gs.abandon("wan22", out=lambda *_: None)
    assert WAN[2] in str(e.value) and "measured" in str(e.value) and lines(tmp_path) == []


def test_abandon_is_for_the_local_engines_and_waits_for_registration(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    for eng in ("gen4_turbo", "gen4.5"):
        with pytest.raises(SystemExit) as e:
            gs.abandon(eng, out=lambda *_: None)
        assert "local" in str(e.value)
    public(tmp_path, monkeypatch, "### A10 — 2026-11-20: ladder\n")
    with pytest.raises(SystemExit) as e:
        gs.abandon("wan22", out=lambda *_: None)
    assert "A12" in str(e.value) and lines(tmp_path) == []


def test_the_metrics_step_never_measures_an_abandoned_draw(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    for c in WAN[:5]:
        clip(tmp_path, "wan22", c)
    gs.abandon("wan22", out=lambda *_: None)
    runner = Runner()
    gs.metrics("wan22", 1, runner=runner)
    assert runner.calls == []


def test_the_cli_abandons_a_whole_series_only(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    with pytest.raises(SystemExit) as e:
        gs.main(["abandon", "--engine", "wan22", "--draw", "1"])
    assert "whole series" in str(e.value) and lines(tmp_path) == []
    pm = pod_manifest(tmp_path, [pod_line(WAN[0])])
    gs.main(["abandon", "--engine", "wan22", "--pod-manifest", str(pm)])
    assert len(lines(tmp_path)) == 15 and lines(tmp_path)[0]["model_version"] == "Wan 2.2 [pod-a]"


def ltx_line(cell, hw="pod-a"):
    return {"cell_id": cell, "engine": "ltx23", "model_version": f"LTX-2.3 [{hw}]", "out": f"runs/ltx23/{cell}.mp4"}


def test_one_pod_losing_both_series_abandons_both_with_a_copy_per_engine(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    ltx = gs.series_cells("ltx23")
    clip(tmp_path, "wan22", WAN[0])
    clip(tmp_path, "ltx23", ltx[0])
    pm = pod_manifest(tmp_path, [pod_line(WAN[0]), ltx_line(ltx[0]), ltx_line(ltx[1])])
    original = pm.read_text()
    gs.abandon("wan22", pod_manifest=pm, out=lambda *_: None)
    gs.abandon("ltx23", pod_manifest=pm, out=lambda *_: None)
    assert [r["cell_id"] for r in lines(tmp_path)] == WAN + ltx
    copies = sorted(p.name for p in (tmp_path / "runs").glob("pod-a10-manifest-lost-*.jsonl"))
    assert len(copies) == 2 and "-lost-wan22-" in copies[1] and "-lost-ltx23-" in copies[0]
    assert (tmp_path / "runs" / copies[1]).read_text() == original      # wan22's: the lost machine's file
    assert pm.read_text() == ""                                         # nothing of either series left to merge


def test_abandon_refuses_a_series_that_came_back_whole(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    for c in WAN:
        clip(tmp_path, "wan22", c)
    pm = pod_manifest(tmp_path, [pod_line(c) for c in WAN])
    before = pm.read_text()
    with pytest.raises(SystemExit) as e:
        gs.abandon("wan22", pod_manifest=pm, out=lambda *_: None)
    assert "came back whole" in str(e.value) and "merge it" in str(e.value)
    assert lines(tmp_path) == [] and pm.read_text() == before
    assert all((tmp_path / "runs" / "wan22" / f"{c}.mp4").exists() for c in WAN)


def test_abandon_without_pod_manifest_refuses_while_a_retrieved_one_is_there(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    pod_manifest(tmp_path, [pod_line(WAN[0])])
    with pytest.raises(SystemExit) as e:
        gs.abandon("wan22", out=lambda *_: None)
    assert "--pod-manifest" in str(e.value) and lines(tmp_path) == []


# ------------------------------------------------ abandon is safe to retry after a crash at any step
class Crash(Exception):
    pass


def lost_scene(root):
    """Four wan22 draws came back with their clips, a fifth line without a clip, one ladder line."""
    for c in WAN[:4]:
        clip(root, "wan22", c)
    ladder = {"cell_id": "ladder-act-black-1_still_ltx23", "out": "runs/ltx23/ladder-act-black-1_still_ltx23.mp4"}
    return pod_manifest(root, [pod_line(c) for c in WAN[:5]] + [ladder]), ladder


def finished(root, pm, ladder, original):
    recs = lines(root)
    assert [r["cell_id"] for r in recs] == WAN and all(r["abandoned"] == "machine lost" for r in recs)
    assert [r["clip_kept_privately"] for r in recs] == [True] * 4 + [False] * 11
    assert [r["model_version"] for r in recs] == ["Wan 2.2 [pod-a]"] * 5 + [None] * 10
    assert [json.loads(x) for x in pm.read_text().splitlines()] == [ladder]
    (kept,) = (root / "runs").glob("pod-a10-manifest-lost-wan22-*.jsonl")
    assert kept.read_text() == original
    assert sorted(p.name for p in (root / "runs" / "abandoned" / "wan22").iterdir()) == sorted(f"{c}.mp4" for c in WAN[:4])
    assert not list((root / "runs" / "wan22").glob("*-d[123].mp4"))
    assert not list((root / "runs").glob("*.tmp"))


def crash_on(monkeypatch, name, after=0):
    """Make gs.<name> raise on its (after + 1)th call."""
    real, calls = getattr(gs, name), []

    def boom(*a, **k):
        calls.append(1)
        if len(calls) > after:
            raise Crash(name)
        return real(*a, **k)
    monkeypatch.setattr(gs, name, boom)
    return real


@pytest.mark.parametrize("step,after", [("_write_rest", 0), ("_keep_clip", 0), ("_keep_clip", 2),
                                        ("_append_lines", 0)])
def test_a_crash_at_any_step_of_abandon_is_finished_by_a_retry(tmp_path, monkeypatch, step, after):
    registered(tmp_path, monkeypatch)
    pm, ladder = lost_scene(tmp_path)
    original = pm.read_text()
    real = crash_on(monkeypatch, step, after)
    with pytest.raises(Crash):
        gs.abandon("wan22", pod_manifest=pm, out=lambda *_: None)
    assert lines(tmp_path) == []                                   # the manifest is the commit point: nothing yet
    monkeypatch.setattr(gs, step, real)
    said = []
    gs.abandon("wan22", pod_manifest=pm, out=said.append)
    finished(tmp_path, pm, ladder, original)
    assert any("resum" in s for s in said)                         # the retry says what it found


def test_a_crash_before_anything_was_written_leaves_nothing_to_resume(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    pm, ladder = lost_scene(tmp_path)
    original = pm.read_text()
    crash_on(monkeypatch, "_write_lost_copy")
    with pytest.raises(Crash):
        gs.abandon("wan22", pod_manifest=pm, out=lambda *_: None)
    assert pm.read_text() == original and not list((tmp_path / "runs").glob("*-lost-*"))
    monkeypatch.undo()
    registered(tmp_path, monkeypatch)
    gs.abandon("wan22", pod_manifest=pm, out=lambda *_: None)
    finished(tmp_path, pm, ladder, original)


def test_a_crash_without_a_pod_manifest_is_finished_by_a_retry(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    for c in WAN[:3]:
        clip(tmp_path, "wan22", c)
    real = crash_on(monkeypatch, "_keep_clip", 1)
    with pytest.raises(Crash):
        gs.abandon("wan22", out=lambda *_: None)
    monkeypatch.setattr(gs, "_keep_clip", real)
    gs.abandon("wan22", out=lambda *_: None)
    assert [r["clip_kept_privately"] for r in lines(tmp_path)] == [True] * 3 + [False] * 12


def test_abandon_refuses_a_clip_in_both_the_engine_folder_and_the_abandoned_folder(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    clip(tmp_path, "wan22", WAN[0])
    other = tmp_path / "runs" / "abandoned" / "wan22" / f"{WAN[0]}.mp4"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"older")
    with pytest.raises(SystemExit) as e:
        gs.abandon("wan22", out=lambda *_: None)
    assert str(other) in str(e.value) and "both" in str(e.value) and lines(tmp_path) == []
    assert other.read_bytes() == b"older"


def test_abandon_refuses_a_lost_copy_that_does_not_match_the_pod_manifest(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    pm, _ = lost_scene(tmp_path)
    stray = tmp_path / "runs" / "pod-a10-manifest-lost-wan22-2026-11-19.jsonl"
    stray.write_text(json.dumps(pod_line(WAN[9], hw="pod-z")) + "\n")
    before = pm.read_text()
    with pytest.raises(SystemExit) as e:
        gs.abandon("wan22", pod_manifest=pm, out=lambda *_: None)
    assert str(stray) in str(e.value) and "matches neither" in str(e.value)
    assert pm.read_text() == before and lines(tmp_path) == []


def test_abandon_refuses_a_pod_manifest_path_that_does_not_exist(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    with pytest.raises(SystemExit) as e:
        gs.abandon("wan22", pod_manifest=tmp_path / "runs" / "nope.jsonl", out=lambda *_: None)
    assert "no such file" in str(e.value) and lines(tmp_path) == []


def test_a_retry_after_the_commit_point_says_the_abandon_already_finished(tmp_path, monkeypatch):
    registered(tmp_path, monkeypatch)
    gs.abandon("wan22", out=lambda *_: None)
    with pytest.raises(SystemExit) as e:
        gs.abandon("wan22", out=lambda *_: None)
    assert "an earlier abandon finished" in str(e.value) and "0 of its cells have lines" in str(e.value)


@pytest.mark.parametrize("crash_step", ["_write_rest", "_keep_clip", "_append_lines"])   # after steps 1, 2, 3
@pytest.mark.parametrize("first,second", [("wan22", "ltx23"), ("ltx23", "wan22")])
def test_two_engines_from_one_pod_resume_after_the_other_finished(tmp_path, monkeypatch, first, second,
                                                                 crash_step):
    """One engine's abandon stops part-way, the other engine's completes, the first is retried."""
    registered(tmp_path, monkeypatch)
    cells = {e: gs.series_cells(e) for e in ("wan22", "ltx23")}
    recs = []
    for e in ("wan22", "ltx23"):
        for c in cells[e][:3]:
            clip(tmp_path, e, c)
            recs.append({"cell_id": c, "engine": e, "model_version": f"{e} [pod-a]", "out": f"runs/{e}/{c}.mp4"})
    ladder = {"cell_id": "ladder-act-black-1_still_ltx23", "out": "runs/ltx23/ladder-act-black-1_still_ltx23.mp4"}
    pm = pod_manifest(tmp_path, recs + [ladder])
    original = pm.read_text()
    real = crash_on(monkeypatch, crash_step)
    with pytest.raises(Crash):
        gs.abandon(first, pod_manifest=pm, out=lambda *_: None)
    monkeypatch.setattr(gs, crash_step, real)
    gs.abandon(second, pod_manifest=pm, out=lambda *_: None)
    gs.abandon(first, pod_manifest=pm, out=lambda *_: None)        # the retry finishes
    got = [r["cell_id"] for r in lines(tmp_path)]
    assert sorted(got) == sorted(cells["wan22"] + cells["ltx23"])
    assert [json.loads(x) for x in pm.read_text().splitlines()] == [ladder]
    (lost_first,) = (tmp_path / "runs").glob(f"pod-a10-manifest-lost-{first}-*.jsonl")
    assert lost_first.read_text() == original
    by_cell = {r["cell_id"]: r for r in lines(tmp_path)}
    for e in ("wan22", "ltx23"):
        assert sorted(p.stem for p in (tmp_path / "runs" / "abandoned" / e).glob("*.mp4")) == sorted(cells[e][:3])
        assert [by_cell[c]["model_version"] for c in cells[e]] == [f"{e} [pod-a]"] * 3 + [None] * 12
        assert [by_cell[c]["clip_kept_privately"] for c in cells[e]] == [True] * 3 + [False] * 12
        assert not list((tmp_path / "runs" / e).glob("ground-*-d[123].mp4"))


def test_a_later_line_for_the_other_engines_cell_is_not_dropped(tmp_path, monkeypatch):
    """Only lines held in another engine's lost copy are taken as gone from the pod manifest: a line
    for one of its cells that the copy does not hold (a later session's) stays in what is merged."""
    registered(tmp_path, monkeypatch)
    ltx = gs.series_cells("ltx23")
    pm = pod_manifest(tmp_path, [ltx_line(ltx[0]), pod_line(WAN[0])])
    gs.abandon("ltx23", pod_manifest=pm, out=lambda *_: None)
    later = ltx_line(ltx[1], hw="pod-b")                               # not in ltx23's lost copy
    with pm.open("a") as f:
        f.write(json.dumps(later) + "\n")
    gs.abandon("wan22", pod_manifest=pm, out=lambda *_: None)
    assert [json.loads(x) for x in pm.read_text().splitlines()] == [later]
