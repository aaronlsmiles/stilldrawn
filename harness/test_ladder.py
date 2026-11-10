"""Tests for harness/ladder.py (A10). No engine and no metric is run: a fake runner records
the commands it would have run.

    python -m pytest harness/test_ladder.py
"""
import hashlib
import json
import pathlib
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ladder  # noqa: E402
from pack_parser import _prompt_from_file  # noqa: E402

PANELS = ["act-black-2", "act-line-1", "act-tone-3", "act-tone-1", "cu-black-1", "cu-line-2",
          "cu-tone-1", "cu-line-3", "est-black-3", "est-line-1", "est-tone-2", "est-black-1"]
A10 = "### A10 — 2026-11-20: motion by construction\n"
# runway_gen.py's task-level outcome line (a refusal), and an error that is not one.
REFUSAL = ("task 0a1b2c3d FAILED: {'id': '0a1b2c3d', 'status': 'FAILED', "
           "'failure': 'Output failed', 'failureCode': 'INTERNAL.BAD_OUTPUT.CODE01'}")
REFUSED = "→ submit gen4.5 (/image_to_video)\n   … FAILED (5s)\n" + REFUSAL + "\nTraceback (gen_video)\n"
CANCELLED = "task 0a1b2c3d CANCELLED: {'id': '0a1b2c3d', 'status': 'CANCELLED'}\n"
NET = "API 503 on POST /image_to_video: upstream unavailable\n"


def tree(tmp_path, panels=PANELS):
    (tmp_path / "analysis" / "out").mkdir(parents=True)
    (tmp_path / "analysis" / "out" / "a10_panels.json").write_text(json.dumps({"panels": panels}))
    (tmp_path / "runs").mkdir()
    return tmp_path


def public(tmp_path, monkeypatch, text):
    p = tmp_path / "PUBLIC-PREREGISTRATION.md"
    p.write_text(text, encoding="utf-8")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(p))


class Runner:
    """Records commands. `fail` maps a cell to the stderr of each failing attempt, in order
    (then it succeeds); `partial` maps a cell to a clip path a failing attempt leaves behind."""
    def __init__(self, fail=None, partial=None):
        self.calls = []
        self.fail = {k: list(v) for k, v in (fail or {}).items()}
        self.partial = dict(partial or {})

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        cell = cmd[cmd.index("--cell-id") + 1] if "--cell-id" in cmd else None
        if self.fail.get(cell):
            if cell in self.partial:
                self.partial[cell].write_bytes(b"half")
            raise subprocess.CalledProcessError(1, cmd, stderr=self.fail[cell].pop(0))
        return subprocess.CompletedProcess(cmd, 0, stderr="")


def made(root, *cell_ids):
    """Clip lines in the manifest, as gen_video.py writes them (the keys run reads)."""
    with (root / "runs" / "manifest.jsonl").open("a") as f:
        for cid in cell_ids:
            f.write(json.dumps({"cell_id": cid, "out": f"runs/x/{cid}.mp4"}) + "\n")


def cells_called(runner):
    return [c[c.index("--cell-id") + 1] for c in runner.calls]


def test_cells_are_12_panels_by_4_levels_with_the_registered_ids():
    cs = ladder.cells("gen4.5", PANELS)
    assert len(cs) == 48 and len({c["cell_id"] for c in cs}) == 48
    assert cs[0]["cell_id"] == "ladder-act-black-2_still_gen45"
    assert cs[3]["cell_id"] == "ladder-act-black-2_high_gen45"
    assert {c["level"] for c in cs} == set(ladder.LEVELS)


def test_dry_run_prints_every_cell_and_its_prompt_and_calls_nothing(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, "no amendment here\n")            # a dry run needs no registration
    root, lines, runner = tree(tmp_path), [], Runner()
    ladder.run("wan22", root=root, dry_run=True, runner=runner, out=lines.append)
    rows = [line.split("\t") for line in lines if "\t" in line]
    assert len(rows) == 48 and not runner.calls
    for cell_id, level, prompt in rows:
        assert cell_id.startswith("ladder-") and cell_id.endswith("_wan22")
        assert prompt == _prompt_from_file(str(ladder.PACK), level)


def test_run_refuses_until_a10_is_public(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, "### A9 — 2026-11-03: exploratory\n")
    runner = Runner()
    with pytest.raises(SystemExit) as e:
        ladder.run("ltx23", root=tree(tmp_path), runner=runner, out=lambda s: None)
    assert "A10" in str(e.value) and not runner.calls


def test_run_refuses_a_local_engine_until_stilldrawn_hw_names_the_machine(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10)
    monkeypatch.delenv("STILLDRAWN_HW", raising=False)
    runner = Runner()
    with pytest.raises(SystemExit) as e:
        ladder.run("wan22", root=tree(tmp_path), runner=runner, out=lambda s: None)
    assert "STILLDRAWN_HW" in str(e.value) and not runner.calls


def test_run_generates_each_missing_cell_with_the_ladder_pack(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10)
    monkeypatch.setenv("STILLDRAWN_HW", "test-machine")
    root, runner = tree(tmp_path), Runner()
    (root / "runs" / "wan22").mkdir(parents=True)
    (root / "runs" / "wan22" / "ladder-act-black-2_still_wan22.mp4").write_bytes(b"x")    # resumes
    made(root, "ladder-act-black-2_still_wan22")
    res = ladder.run("wan22", root=root, runner=runner, out=lambda s: None)
    assert res == {"new": 47, "skipped": 1, "refused": 0} and len(runner.calls) == 47
    cmd = runner.calls[0]
    assert cmd[cmd.index("--pack") + 1] == str(ladder.PACK)
    assert cmd[cmd.index("--motion") + 1] == "LOW"
    assert "--seed" not in cmd                                     # gen_video's default, §5's 20260812


def test_a_hosted_cell_failing_twice_is_recorded_refused_and_skipped_on_resume(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10)
    root = tree(tmp_path)
    bad, flaky = "ladder-cu-line-2_high_gen45", "ladder-cu-line-2_mid_gen45"
    runner = Runner(fail={bad: [REFUSED, REFUSED], flaky: [NET]})
    echoed = []
    res = ladder.run("gen4.5", root=root, runner=runner, out=lambda s: None, err=echoed.append)
    assert res == {"new": 47, "skipped": 0, "refused": 1} and len(runner.calls) == 50
    assert echoed.count(REFUSED) == 2 and NET in echoed              # stderr is echoed
    rec = json.loads((root / "runs" / "manifest.jsonl").read_text().splitlines()[0])
    assert rec["cell_id"] == bad and rec["refused"] is True and rec["out"] is None
    assert rec["refusal"] == REFUSAL                                 # Runway's own reason, verbatim
    assert rec["prompt_pack"] == "harness/motion-ladder.md" and rec["motion_class"] == "HIGH"
    again = Runner()
    res2 = ladder.run("gen4.5", root=root, runner=again, out=lambda s: None)
    assert res2["refused"] == 0 and bad not in cells_called(again)


@pytest.mark.parametrize("stderrs", [[NET, NET], [REFUSED, NET], [NET, REFUSED],
                                     [CANCELLED, CANCELLED], [REFUSED, CANCELLED],
                                     ["/x/ladder.lock held — another driver is generating this cell\n"] * 2])
def test_a_hosted_double_failure_without_a_task_outcome_stops_with_no_manifest_line(
        tmp_path, monkeypatch, stderrs):
    public(tmp_path, monkeypatch, A10)
    root = tree(tmp_path)
    runner = Runner(fail={"ladder-act-tone-3_low_gen45": stderrs})
    with pytest.raises(SystemExit) as e:
        ladder.run("gen4.5", root=root, runner=runner, out=lambda s: None, err=lambda s: None)
    assert "ladder-act-tone-3_low_gen45" in str(e.value) and "Not recorded as refused" in str(e.value)
    assert not (root / "runs" / "manifest.jsonl").exists()


def test_a_clip_without_a_manifest_line_stops_the_run_and_is_named(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10)
    root, runner = tree(tmp_path), Runner()
    orphan = root / "runs" / "gen4.5" / "ladder-act-black-2_still_gen45.mp4"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"half")
    made(root, "ladder-act-black-2_still_wan22")                     # another engine's line does not count
    with pytest.raises(SystemExit) as e:
        ladder.run("gen4.5", root=root, runner=runner, out=lambda s: None)
    assert "ladder-act-black-2_still_gen45" in str(e.value) and "no line" in str(e.value)
    assert not runner.calls


def test_a_manifest_clip_line_without_its_file_stops_the_run_and_is_not_regenerated(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10)
    root, runner = tree(tmp_path), Runner()
    made(root, "ladder-act-black-2_still_gen45")                     # line written, file missing
    with pytest.raises(SystemExit) as e:
        ladder.run("gen4.5", root=root, runner=runner, out=lambda s: None)
    assert "ladder-act-black-2_still_gen45" in str(e.value) and "file is missing" in str(e.value)
    assert "not regenerating" in str(e.value) and not runner.calls


def test_a_failed_attempt_that_leaves_a_clip_stops_without_resubmitting_or_refusing(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10)
    root = tree(tmp_path)
    cell = "ladder-act-black-2_still_gen45"
    clip = root / "runs" / "gen4.5" / f"{cell}.mp4"
    clip.parent.mkdir(parents=True)
    runner = Runner(fail={cell: [NET, REFUSED]}, partial={cell: clip})
    with pytest.raises(SystemExit) as e:
        ladder.run("gen4.5", root=root, runner=runner, out=lambda s: None, err=lambda s: None)
    assert "left a clip behind" in str(e.value) and len(runner.calls) == 1
    assert not (root / "runs" / "manifest.jsonl").exists()


def test_negative_limit_is_rejected(tmp_path):
    with pytest.raises(SystemExit):
        ladder.run("gen4.5", root=tree(tmp_path), limit=-1, runner=Runner(), out=lambda s: None)
    with pytest.raises(SystemExit):
        ladder.main(["run", "--engine", "gen4.5", "--dry-run", "--limit", "-1"])


def test_the_summary_counts_the_remaining_cells(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10)
    lines = []
    ladder.run("gen4.5", root=tree(tmp_path), limit=21, runner=Runner(), out=lines.append)
    assert lines[-1] == "gen4.5: 21 new, 0 skipped, 0 refused, 27 remaining"


def test_a_local_cell_failing_twice_stops_the_run(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10)
    monkeypatch.setenv("STILLDRAWN_HW", "test-machine")
    runner = Runner(fail={"ladder-act-line-1_mid_ltx23": [NET, NET]})
    with pytest.raises(SystemExit) as e:
        ladder.run("ltx23", root=tree(tmp_path), runner=runner, out=lambda s: None, err=lambda s: None)
    assert "harness fault" in str(e.value)


def test_limit_stops_after_n_new_clips(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10)
    runner = Runner()
    res = ladder.run("gen4.5", root=tree(tmp_path), limit=21, runner=runner, out=lambda s: None)
    assert res["new"] == 21 and len(runner.calls) == 21


def test_build_writes_all_144_cells_the_prompts_and_the_pack_hash(tmp_path):
    rec = ladder.build(tree(tmp_path))
    saved = json.loads((tmp_path / "analysis" / "out" / "a10_cells.json").read_text())
    assert saved == rec and sum(len(v) for v in rec["cells"].values()) == 144
    assert set(rec["prompts"]) == set(ladder.LEVELS) and len(rec["pack_sha256"]) == 64
    panels_bytes = (tmp_path / "analysis" / "out" / "a10_panels.json").read_bytes()
    assert rec["panels_sha256"] == hashlib.sha256(panels_bytes).hexdigest()


def test_metrics_write_to_the_ladder_folders_only(tmp_path):
    root, runner = tree(tmp_path), Runner()
    clip = root / "runs" / "wan22" / "ladder-act-line-1_high_wan22.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"x")
    n = ladder.metrics("wan22", root=root, runner=runner, out=lambda s: None)
    assert n == 1 and len(runner.calls) == 2
    assert runner.calls[0][-1].endswith("runs/metrics-ladder/ladder-act-line-1_high_wan22.json")
    assert runner.calls[1][-1].endswith("runs/metrics-motion-ladder/ladder-act-line-1_high_wan22.json")


# ------------------------------------------------ per-engine hosted model and seed (A10, A15, A16)
A15 = "### A15 — 2026-11-20: a Kling scout with a declared decision rule\n"
A16 = "### A16 — 2026-11-20: a Midjourney video scout, run by hand\n"
GEN45_MODEL = "gen4.5 (Runway dev API, X-Runway-Version 2024-11-06)"
KLING_MODEL = "kling_4 (Runway dev API, X-Runway-Version 2024-11-06)"


def arg(cmd, flag):
    return cmd[cmd.index(flag) + 1]


KLING_PASS = "scout passed: Kling joins A10's motion test as a further engine"           # A15.5, reading 4
MJ_PASS = "scout passed: Midjourney joins A10's motion test as a further engine"         # A16.7


def scout(root, engine, reading):
    """The scout's logged reading, as analysis/scout_rule.py is to write it."""
    p = pathlib.Path(root) / ladder.ARMS[engine]["scout"]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"reading": reading}))
    return p


def test_the_gen45_ladder_sends_the_protocol_seed_and_its_refusal_line_records_it():
    c = ladder.cells("gen4.5", PANELS)[0]
    cmd = ladder.gen_cmd(c)
    assert arg(cmd, "--seed") == "20260812" and arg(cmd, "--ratio") == "1280:720"
    line = ladder.refusal_line(c, "P", REFUSAL)
    assert line["model_version"] == GEN45_MODEL and line["seed"] == 20260812 and line["ratio"] == "1280:720"


def test_a_kling_refusal_line_names_kling_with_no_seed_at_auto_720p():
    c = ladder.cells("kling_4", PANELS)[0]
    assert c["cell_id"] == "ladder-act-black-2_still_kling4"
    line = ladder.refusal_line(c, "P", REFUSAL)
    assert line["model_version"] == KLING_MODEL and line["engine"] == "kling_4"
    assert line["seed"] is None and line["ratio"] == "auto_720p" and line["refusal"] == REFUSAL
    cmd = ladder.gen_cmd(c)
    assert "--seed" not in cmd and arg(cmd, "--ratio") == "auto_720p"


def test_midjourney_runs_by_hand_and_this_driver_refuses_it(tmp_path, monkeypatch):
    c = ladder.cells("midjourney", PANELS)[0]
    assert c["cell_id"] == "ladder-act-black-2_still_mjv"
    with pytest.raises(SystemExit) as e:
        ladder.refusal_line(c, "P", REFUSAL)
    assert "by hand" in str(e.value)
    public(tmp_path, monkeypatch, A10 + A16)
    runner, root = Runner(), tree(tmp_path)
    scout(root, "midjourney", MJ_PASS)                                    # even after a logged pass
    with pytest.raises(SystemExit) as e:
        ladder.run("midjourney", root=root, runner=runner, out=lambda s: None)
    assert "by hand" in str(e.value) and not runner.calls
    assert not (tmp_path / "runs" / "manifest.jsonl").exists()


def test_kling_needs_a15_public_as_well_as_a10(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10)
    root, runner = tree(tmp_path), Runner()
    with pytest.raises(SystemExit) as e:
        ladder.run("kling_4", root=root, runner=runner, out=lambda s: None)
    assert "A15" in str(e.value) and not runner.calls
    public(tmp_path, monkeypatch, A15)                                  # A15 without A10: still refused
    with pytest.raises(SystemExit) as e:
        ladder.run("kling_4", root=root, runner=runner, out=lambda s: None)
    assert "A10" in str(e.value) and not runner.calls
    public(tmp_path, monkeypatch, A10 + A15)
    scout(root, "kling_4", KLING_PASS)
    assert ladder.run("kling_4", root=root, limit=2, runner=runner, out=lambda s: None)["new"] == 2


def test_a_kling_cell_failed_twice_is_recorded_under_klings_model(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10 + A15)
    root = tree(tmp_path)
    scout(root, "kling_4", KLING_PASS)
    bad = "ladder-cu-line-2_high_kling4"
    res = ladder.run("kling_4", root=root, runner=Runner(fail={bad: [REFUSED, REFUSED]}),
                     out=lambda s: None, err=lambda s: None)
    assert res == {"new": 47, "skipped": 0, "refused": 1}
    rec = json.loads((root / "runs" / "manifest.jsonl").read_text().splitlines()[0])
    assert rec["cell_id"] == bad and rec["model_version"] == KLING_MODEL and rec["seed"] is None
    assert rec["ratio"] == "auto_720p" and rec["refusal"] == REFUSAL


def test_every_gen45_submission_carries_the_seed_and_a_refusal_records_it(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10)
    root = tree(tmp_path)
    bad = "ladder-act-tone-1_low_gen45"
    runner = Runner(fail={bad: [REFUSED, REFUSED]})
    ladder.run("gen4.5", root=root, runner=runner, out=lambda s: None, err=lambda s: None)
    assert all(arg(c, "--seed") == "20260812" for c in runner.calls) and len(runner.calls) == 49
    rec = json.loads((root / "runs" / "manifest.jsonl").read_text().splitlines()[0])
    assert rec["cell_id"] == bad and rec["seed"] == 20260812 and rec["model_version"] == GEN45_MODEL


def test_build_keeps_a10s_three_engines_and_records_the_hosted_seed(tmp_path):
    rec = ladder.build(tree(tmp_path))
    assert list(rec["cells"]) == ["wan22", "ltx23", "gen4.5"] and rec["seed_hosted"] == 20260812
    assert rec["seed_local_engines"] == 20260812 and rec["ratio"] == "1280:720"


@pytest.mark.parametrize("arm,amendment,tag,ratio,seed", [
    ("kling_4", "A15", "kling4", "auto_720p", None),                       # A15.3.2; A15.3.3: no seed
    ("midjourney", "A16", "mjv", "per A16.3.2", "per A16.4.1")])           # left open by A16, never guessed
def test_an_arm_is_built_to_its_own_file_and_a10s_list_is_untouched(tmp_path, arm, amendment, tag, ratio, seed):
    root = tree(tmp_path)
    ladder.build(root)
    a10 = (root / ladder.CELLS_JSON).read_bytes()
    rec = ladder.build(root, arm=arm)
    saved = json.loads((root / ladder.ARMS[arm]["cells"]).read_text())
    assert saved == rec and rec["amendment"] == amendment and list(rec["cells"]) == [arm]
    assert len(rec["cells"][arm]) == 48 and all(c.endswith(f"_{tag}") for c in rec["cells"][arm])
    assert rec["ratio"] == ratio and rec["seed"] == seed and rec["prompts"] == ladder.prompts()
    assert (root / ladder.CELLS_JSON).read_bytes() == a10
    assert ladder.ARMS[arm]["cells"] == f"analysis/out/{amendment.lower()}_cells.json"


def test_the_shipped_a10_cell_list_is_what_build_writes(tmp_path):
    shipped = ladder.ROOT / ladder.CELLS_JSON
    if not shipped.exists():                       # the pod's copy carries a10_panels.json only
        pytest.skip("no analysis/out/a10_cells.json in this tree")
    (tmp_path / "analysis" / "out").mkdir(parents=True)
    (tmp_path / ladder.PANELS_JSON).write_bytes((ladder.ROOT / ladder.PANELS_JSON).read_bytes())
    ladder.build(tmp_path)
    assert (tmp_path / ladder.CELLS_JSON).read_bytes() == shipped.read_bytes()



def test_the_frozen_a16_file_names_no_ratio_and_no_seed(tmp_path):
    # A16.3.2 sets HD from the start frame with no ratio request; A16.4.1 decides the seed after
    # registration (ruled 8 Nov 2026). Neither may be frozen into a16_cells.json before then.
    root = tree(tmp_path)
    ladder.build(root, arm="midjourney")
    text = (root / "analysis" / "out" / "a16_cells.json").read_text()
    rec = json.loads(text)
    assert rec["ratio"] == "per A16.3.2" and rec["seed"] == "per A16.4.1"
    assert "1280:720" not in text and "20260812" not in text and "null" not in text



# ------------------------- an arm runs only after its scout's logged pass (ruled 8 Nov 2026)
@pytest.mark.parametrize("engine,amendment", [("kling_4", "A15"), ("midjourney", "A16")])
def test_an_arm_is_refused_without_its_scout_file(tmp_path, monkeypatch, engine, amendment):
    public(tmp_path, monkeypatch, A10 + A15 + A16)
    runner = Runner()
    with pytest.raises(SystemExit) as e:
        ladder.run(engine, root=tree(tmp_path), runner=runner, out=lambda s: None)
    msg = str(e.value)
    assert f"{amendment.lower()}_scout.json" in msg and "missing" in msg and not runner.calls
    assert not (tmp_path / "runs" / "manifest.jsonl").exists()


@pytest.mark.parametrize("engine,reading", [
    ("kling_4", "scout failed: refused (2 of 6 cells)"),
    ("kling_4", "scout failed: does not move on request (1 of 3 BURST draws above the floor)"),
    ("kling_4", "scout passed: Kling joins A10's motion test"),                 # a prefix is not the reading
    ("kling_4", MJ_PASS),                                                        # the other arm's pass
    ("kling_4", KLING_PASS + " "),
    ("midjourney", "scout failed: not measurable (act-black-3_burst_mjv-h2)"),
    ("midjourney", KLING_PASS),
])
def test_an_arm_is_refused_on_any_reading_but_its_own_exact_pass(tmp_path, monkeypatch, engine, reading):
    public(tmp_path, monkeypatch, A10 + A15 + A16)
    root, runner = tree(tmp_path), Runner()
    scout(root, engine, reading)
    with pytest.raises(SystemExit) as e:
        ladder.run(engine, root=root, runner=runner, out=lambda s: None)
    assert repr(reading) in str(e.value) and "by hand" not in str(e.value) and not runner.calls


def test_kling_runs_after_its_exact_logged_pass(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10 + A15)
    root, runner = tree(tmp_path), Runner()
    scout(root, "kling_4", KLING_PASS)
    assert ladder.run("kling_4", root=root, limit=3, runner=runner, out=lambda s: None)["new"] == 3
    assert all(c[c.index("--engine") + 1] == "kling_4" for c in runner.calls)


def test_a10s_three_engines_need_no_scout_file(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10)
    monkeypatch.setenv("STILLDRAWN_HW", "test-machine")
    root = tree(tmp_path)
    scout(root, "kling_4", "scout failed: refused (3 of 6 cells)")           # an arm's failure changes nothing here
    for engine in ("wan22", "ltx23", "gen4.5"):
        runner = Runner()
        assert ladder.run(engine, root=root, limit=1, runner=runner, out=lambda s: None)["new"] == 1


def test_the_pass_and_fail_readings_are_the_drafts_own():
    assert ladder.ARMS["kling_4"]["scout_passed"] == KLING_PASS
    assert ladder.ARMS["midjourney"]["scout_passed"] == MJ_PASS == KLING_PASS.replace("Kling", "Midjourney")
    for reading, ok in (("scout failed: refused (2 of 6 cells)", True), ("scout failed: refused (2 of 3 cells)", True),
                        ("scout failed: not measurable (flint-cu-line-2--cu-line-1_kling4)", True),
                        ("scout failed: does not move on request (0 of 3 BURST draws above the floor)", True),
                        ("scout failed: does not move", False), ("scout failed: refused", False),
                        ("scout failed: does not move on request (4 of 3 BURST draws above the floor)", False)):
        assert ladder.scout_failed(reading) is ok, reading
    draft = ladder.ROOT / "docs" / "A14-A16-DRAFT.md"
    if not draft.is_file():
        pytest.skip("no docs/A14-A16-DRAFT.md in this tree (the release ships no drafts)")
    text = draft.read_text(encoding="utf-8")
    a15_5 = text.split("#### A15.5")[1].split("#### A15.6")[0]
    assert f'4. Otherwise "{KLING_PASS}".' in a15_5
    for form in ('"scout failed: refused (R of N cells)"', '"scout failed: not measurable (<cell ids>)"',
                 '"scout failed: does not move on request (B of 3 BURST draws above the floor)"'):
        assert form in a15_5
    assert 'verbatim, with "Midjourney" for "Kling" in its last reading' in text.split("#### A16.7")[1]


# ------------------------------- the shared run loop (ladder.drive): A10, and A14's and A15's drivers
def test_drive_runs_the_same_loop_for_any_folder_and_calls_the_hook_after_each_new_clip(tmp_path):
    root = tree(tmp_path)
    todo = [{"cell_id": f"x_idle_sd2r-h{k}"} for k in (1, 2, 3)]
    seen = []
    runner = Runner(fail={"x_idle_sd2r-h2": [REFUSED, REFUSED]})
    res = ladder.drive(todo, "seedance2", root, lambda c: ["gen", "--cell-id", c["cell_id"]],
                       lambda c, reason: {"cell_id": c["cell_id"], "refused": True, "refusal": reason},
                       label="A14", after=lambda c: seen.append(c["cell_id"]), runner=runner,
                       out=lambda s: None, err=lambda s: None)
    assert res == {"new": 2, "skipped": 0, "refused": 1} and seen == ["x_idle_sd2r-h1", "x_idle_sd2r-h3"]
    rec = json.loads((root / "runs" / "manifest.jsonl").read_text())
    assert rec == {"cell_id": "x_idle_sd2r-h2", "refused": True, "refusal": REFUSAL}
    with pytest.raises(SystemExit) as e:                         # a hook may stop the run
        ladder.drive([{"cell_id": "y_idle_sd2r-h1"}], "seedance2", root, lambda c: ["gen", "--cell-id", c["cell_id"]],
                     lambda c, r: {}, after=lambda c: (_ for _ in ()).throw(SystemExit("stop: route mismatch")),
                     runner=Runner(), out=lambda s: None)
    assert "route mismatch" in str(e.value)


def test_drive_counts_a_refused_cell_toward_limit(tmp_path):
    root = tree(tmp_path)
    todo = [{"cell_id": f"x_idle_sd2r-h{k}"} for k in (1, 2, 3)]
    refuse = lambda c, reason: {"cell_id": c["cell_id"], "refused": True, "refusal": reason}   # noqa: E731
    mk = lambda c: ["gen", "--cell-id", c["cell_id"]]                                          # noqa: E731
    runner = Runner(fail={"x_idle_sd2r-h1": [REFUSED, REFUSED]})
    lines = []
    res = ladder.drive(todo, "seedance2", root, mk, refuse, limit=1, runner=runner, out=lines.append,
                       err=lambda s: None)
    assert res == {"new": 0, "skipped": 0, "refused": 1} and "--limit 1 reached" in lines   # the refused first cell ends the run
    assert cells_called(runner) == ["x_idle_sd2r-h1"] * 2                                      # one cell, its two attempts; no cell 2
    res = ladder.drive(todo, "seedance2", root, mk, refuse, limit=2, runner=Runner(), out=lambda s: None)
    assert res == {"new": 2, "skipped": 1, "refused": 0}                                       # two attempts, whatever the outcome
    runner = Runner(fail={"x_idle_sd2r-h2": [REFUSED, REFUSED]})
    root2 = tree(tmp_path / "b")
    res = ladder.drive(todo, "seedance2", root2, mk, refuse, limit=2, runner=runner, out=lambda s: None,
                       err=lambda s: None)
    assert res == {"new": 1, "skipped": 0, "refused": 1} and "x_idle_sd2r-h3" not in cells_called(runner)


def test_adopt_records_a_kling_ladder_cell_and_refuses_gen45_and_a_local_engine(tmp_path, monkeypatch):
    import shutil as _sh
    import gen_video as gv
    if not (_sh.which("ffmpeg") and _sh.which("ffprobe")):
        pytest.skip("ffmpeg and ffprobe needed")
    public(tmp_path, monkeypatch, A10 + A15)
    root = tree(tmp_path)
    scout(root, "kling_4", KLING_PASS)
    monkeypatch.setattr(gv, "ROOT", root)
    (root / "harness").mkdir()
    _sh.copyfile(ladder.PACK, root / "harness" / "motion-ladder.md")
    monkeypatch.setattr(ladder, "PACK", root / "harness" / "motion-ladder.md")
    f = root / "incoming" / "k.mp4"
    f.parent.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=1260x720:d=0.2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(f)], check=True)
    line = ladder.adopt("kling_4", "ladder-act-black-2_mid_kling4", f, "task-k", root)
    assert line["seed"] is None and line["prompt_pack"] == "harness/motion-ladder.md" and line["task_id"] == "task-k"
    for engine, cell in (("gen4.5", "ladder-act-black-2_mid_gen45"), ("wan22", "ladder-act-black-2_mid_wan22")):
        with pytest.raises(SystemExit) as e:                      # A10's own engines and the local ones: not adopted here
            ladder.adopt(engine, cell, f, "t", root)
        assert "not an adoptable ladder arm" in str(e.value)


def test_adopt_needs_a10_and_the_arms_amendment_and_scout_pass_as_run_does(tmp_path, monkeypatch):
    root = tree(tmp_path)
    f = root / "k.mp4"
    f.write_bytes(b"x")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(tmp_path / "no-public-prereg.md"))   # no public pre-registration
    with pytest.raises(SystemExit) as e:                          # tripwire: nothing registered
        ladder.adopt("kling_4", "ladder-act-black-2_mid_kling4", f, "t", root)
    assert "REFUSING" in str(e.value) and "A10" in str(e.value)
    public(tmp_path, monkeypatch, A10)                            # A10 without A15: still refused
    with pytest.raises(SystemExit) as e:
        ladder.adopt("kling_4", "ladder-act-black-2_mid_kling4", f, "t", root)
    assert "REFUSING" in str(e.value) and "A15" in str(e.value)
    public(tmp_path, monkeypatch, A10 + A15)                      # both public, no scout pass logged: refused
    with pytest.raises(SystemExit) as e:
        ladder.adopt("kling_4", "ladder-act-black-2_mid_kling4", f, "t", root)
    assert "REFUSING" in str(e.value) and "scout" in str(e.value)
    assert not (root / "runs" / "manifest.jsonl").exists()


# ---- Stage 2 fix round: stops name adopt, one --limit help, record docs checked, adopt args from gen_cmd
def test_an_orphan_hosted_clip_names_adopt_and_never_a_move_aside_and_re_run(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10 + A15)
    root, runner = tree(tmp_path), Runner()
    scout(root, "kling_4", KLING_PASS)
    cell = "ladder-act-black-2_still_kling4"
    orphan = root / "runs" / "kling_4" / f"{cell}.mp4"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"delivered")
    with pytest.raises(SystemExit) as e:
        ladder.run("kling_4", root=root, runner=runner, out=lambda s: None)
    msg = str(e.value)
    assert f"adopt --cell {cell} --file <delivered path> --task <task id> [--record" in msg
    assert "ladder.py adopt --cell" in msg and msg.rstrip().count("--engine kling_4") == 1 and "paid for" in msg and "submits the cell again" in msg
    assert "move it aside by hand" not in msg and not runner.calls


def test_a_failed_attempt_that_leaves_a_hosted_clip_names_adopt_too(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10 + A15)
    root = tree(tmp_path)
    scout(root, "kling_4", KLING_PASS)
    cell = "ladder-act-black-2_still_kling4"
    clip = root / "runs" / "kling_4" / f"{cell}.mp4"
    clip.parent.mkdir(parents=True)
    runner = Runner(fail={cell: [NET]}, partial={cell: clip})
    with pytest.raises(SystemExit) as e:
        ladder.run("kling_4", root=root, runner=runner, out=lambda s: None, err=lambda s: None)
    assert f"adopt --cell {cell} --file <delivered path> --task <task id>" in str(e.value)
    assert "move it aside, re-run" not in str(e.value) and len(runner.calls) == 1


def test_a_local_orphan_is_still_moved_aside_and_gen45_names_aaron_not_adopt(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10)
    monkeypatch.setenv("STILLDRAWN_HW", "test-machine")
    root = tree(tmp_path)
    for engine, tag in (("wan22", "wan22"), ("gen4.5", "gen45")):
        orphan = root / "runs" / engine / f"ladder-act-black-2_still_{tag}.mp4"
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_bytes(b"half")
        with pytest.raises(SystemExit) as e:
            ladder.run(engine, root=root, runner=Runner(), out=lambda s: None)
        msg = str(e.value)
        if engine == "wan22":
            assert "move it aside by hand" in msg and "adopt" not in msg and "submitted" not in msg
        else:
            assert "tell Aaron" in msg and "adopt --cell" not in msg


def test_the_adopt_refusal_does_not_list_midjourney_as_adoptable(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A10 + A15)
    with pytest.raises(SystemExit) as e:
        ladder.adopt("gen4.5", "ladder-act-black-2_mid_gen45", tmp_path / "f.mp4", "t", tree(tmp_path))
    assert "only kling_4;" in str(e.value) and "midjourney" not in str(e.value)


def test_every_driver_takes_its_limit_help_from_ladder():
    assert ladder.LIMIT_HELP == "stop after this many cells, delivered or refused (a refused cell counts)"
    import a14_draws
    import scout as scout_mod
    for mod, argv in ((ladder, ["run"]), (scout_mod, ["run"]), (a14_draws, ["run"])):
        text = pathlib.Path(mod.__file__).read_text()
        assert "LIMIT_HELP" in text and "submissions" not in text.split("def main")[1]


def test_a_changed_record_doc_is_refused(tmp_path):
    root = tree(tmp_path)
    (root / "docs").mkdir()
    doc = root / "docs" / "X-ROUTE.md"
    doc.write_text("captured\n")
    verdict = root / "analysis" / "out" / "x_route.json"
    verdict.write_text(json.dumps({"verdict": "offered", "record_sha256": hashlib.sha256(doc.read_bytes()).hexdigest()}))
    ladder.require_record_doc_unchanged(root, "docs/X-ROUTE.md", "analysis/out/x_route.json")      # unchanged: passes
    doc.write_text("captured, then edited\n")
    with pytest.raises(SystemExit) as e:
        ladder.require_record_doc_unchanged(root, "docs/X-ROUTE.md", "analysis/out/x_route.json")
    assert str(e.value).startswith("REFUSING: docs/X-ROUTE.md has changed since its verdict was recorded")
    doc.unlink()
    with pytest.raises(SystemExit) as e:
        ladder.require_record_doc_unchanged(root, "docs/X-ROUTE.md", "analysis/out/x_route.json")
    assert "has changed since its verdict was recorded" in str(e.value) and "missing" in str(e.value)
    doc.write_text("captured\n")
    verdict.write_text(json.dumps({"verdict": "offered"}))                                            # no hash to compare
    with pytest.raises(SystemExit):
        ladder.require_record_doc_unchanged(root, "docs/X-ROUTE.md", "analysis/out/x_route.json")


def test_adopt_takes_its_arguments_from_the_command_the_run_was_given(tmp_path, monkeypatch):
    import shutil as _sh
    import gen_video as gv
    if not (_sh.which("ffmpeg") and _sh.which("ffprobe")):
        pytest.skip("ffmpeg and ffprobe needed")
    public(tmp_path, monkeypatch, A10 + A15)
    root, runner = tree(tmp_path), Runner()
    scout(root, "kling_4", KLING_PASS)
    monkeypatch.setattr(gv, "ROOT", root)
    (root / "harness").mkdir()
    _sh.copyfile(ladder.PACK, root / "harness" / "motion-ladder.md")
    monkeypatch.setattr(ladder, "PACK", root / "harness" / "motion-ladder.md")
    ladder.run("kling_4", root=root, limit=1, runner=runner, out=lambda s: None)         # the command the run was given
    (cmd,) = runner.calls
    ran = gv.build_parser().parse_args(cmd[2:])
    cell = ran.cell_id
    record = {"model": "kling_4", "request": gv.runway_body(ran, gv.resolve_prompt(ran.motion, ran.pack)),
              "task_id": "t-1", "seed": None, "task": {"id": "t-1", "model": "kling-4"}}
    f = root / "incoming" / "k.mp4"
    f.parent.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=1260x720:d=0.2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(f)], check=True)
    line = ladder.adopt("kling_4", cell, f, "t-1", root, record=record)
    assert line["adopted"]["task_record"] == "the route record the run printed" and line["request"] == record["request"]
