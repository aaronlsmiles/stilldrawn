"""Tests for harness/a14_draws.py (A14). No engine is called: a fake gen_video records the
commands it would have run, and writes the clip and manifest line a real one would.

    python -m pytest harness/test_a14_draws.py
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a14_draws as ad  # noqa: E402
from pack_parser import _prompt_from_file  # noqa: E402

A14 = "### A14 — 2026-11-20: confirmatory: A5's Seedance hazard replication completed at five fresh draws per cell\n"
REFUSAL = ("task 0a1b2c3d FAILED: {'id': '0a1b2c3d', 'status': 'FAILED', "
           "'failure': 'Output failed', 'failureCode': 'INTERNAL.BAD_OUTPUT.CODE01'}")
CANCELLED = "task 0a1b2c3d CANCELLED: {'id': '0a1b2c3d', 'status': 'CANCELLED'}\n"
BASE20 = ([f"cu-line-1_idle_sd2r-h{k}" for k in range(1, 6)] + [f"cu-line-1_burst_sd2r-h{k}" for k in range(1, 6)]
          + [f"act-black-3_idle_sd2r-h{k}" for k in range(1, 6)] + [f"act-black-3_burst_sd2r-h{k}" for k in range(4, 9)])


def arg(cmd, flag):
    return cmd[cmd.index(flag) + 1]


@pytest.fixture(autouse=True)
def registered(tmp_path, monkeypatch):
    """A14 public by default (the route check comes after registration, A14.7); tests override it."""
    public(tmp_path, monkeypatch, A14)


def tree(tmp_path, verdict=None):
    (tmp_path / "runs").mkdir()
    (tmp_path / "docs").mkdir()
    ad.build(tmp_path)
    if verdict:
        (tmp_path / "docs" / "A14-ROUTE.md").write_text(f"# Route check\n\nRoute: {verdict}\n")
        ad.route(verdict, tmp_path)
    return tmp_path


def public(tmp_path, monkeypatch, text):
    p = tmp_path / "public" / "PREREGISTRATION.md"
    p.parent.mkdir(exist_ok=True)
    p.write_text(text, encoding="utf-8")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(p))


class FakeGen:
    """Stands in for gen_video.py: writes the clip and its manifest line (with a task record), or
    fails with the given stderr per attempt."""
    def __init__(self, root, fail=None, tasks=({"model": "seedance2"},),
                 versions=("seedance2 (Runway dev API, X-Runway-Version 2024-11-06)",)):
        """`tasks`: the Runway-reported fields each successive clip's task record carries beside id and
        status; `versions`: its line's model_version, the harness's own string (the last value repeats)."""
        self.root, self.calls, self.made = Path(root), [], 0
        self.tasks, self.versions = list(tasks), list(versions)
        self.fail = {k: list(v) for k, v in (fail or {}).items()}

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        cell = arg(cmd, "--cell-id")
        if self.fail.get(cell):
            raise subprocess.CalledProcessError(1, cmd, stderr=self.fail[cell].pop(0))
        clip = self.root / "runs" / arg(cmd, "--engine") / f"{cell}.mp4"
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"clip")
        extra = self.tasks[min(self.made, len(self.tasks) - 1)]
        version = self.versions[min(self.made, len(self.versions) - 1)]
        self.made += 1
        task = {"id": "t", "status": "SUCCEEDED", "createdAt": "2026-11-21T09:00:00Z"} | extra
        with (self.root / "runs" / "manifest.jsonl").open("a") as f:
            f.write(json.dumps({"cell_id": cell, "seed": int(arg(cmd, "--seed")), "task": task,
                                "model_version": version, "out": f"runs/seedance2/{cell}.mp4"}) + "\n")
        return subprocess.CompletedProcess(cmd, 0, stderr="")


def test_the_cells_are_the_twenty_a14_names_with_one_seed_per_draw():
    assert [c["cell_id"] for c in ad.cells()] == BASE20
    for c in ad.cells():
        assert c["seed"] == 20260812 + c["draw"] and c["cell_id"].endswith(f"_sd2r-h{c['draw']}")
    seeds = {c["cell_id"]: c["seed"] for c in ad.cells()}
    assert seeds["cu-line-1_idle_sd2r-h1"] == 20260813 and seeds["act-black-3_burst_sd2r-h5"] == 20260817
    assert seeds["act-black-3_burst_sd2r-h8"] == 20260820


def test_build_writes_the_cell_list_with_the_frozen_prompts(tmp_path):
    rec = ad.build(tmp_path)
    saved = json.loads((tmp_path / "analysis" / "out" / "a14_cells.json").read_text())
    assert saved == rec and [c["cell_id"] for c in rec["cells"]] == BASE20
    assert "mismatch_extra" not in rec                                    # a mismatch adds no draw (A14.3.4)
    assert "adds no draw" in rec["mismatch_rule"] and "P" + "69" not in json.dumps(rec) and "call " not in json.dumps(rec)
    assert [c["cell_id"] for c in rec["scout"]] == [f"act-black-3_burst_sd2-h{k}" for k in (1, 2, 3)]
    pack = ad.HERE / "motion-prompts.md"
    assert rec["prompts"] == {m: _prompt_from_file(str(pack), m) for m in ("IDLE", "BURST")}
    assert rec["pack_sha256"] == ad.pack_sha256()                         # the released form (below)
    assert rec["engine"] == "seedance2" and rec["ratio"] == "1280:720" and rec["duration_s"] == 5


def test_the_cell_list_records_the_packs_released_form():
    # The pack has two byte forms (its title line carries the working name in the private tree); the
    # cell list records the released one, so the test reads the same in both trees.
    released = "43a022980cdd4884c1eaaf4702baf5bc9b6b925ac9c8a611a23b1ed354e0ef31"
    assert ad.pack_sha256() == released
    raw = hashlib.sha256(ad.PACK.read_bytes()).hexdigest()
    assert raw in (released,                                                               # public release
                   "4978eb9c6044b3eb59635e725a5225ff7b07465b314bae638e0a05bee2f4a499")   # private tree


def test_the_shipped_cell_list_is_what_build_writes(tmp_path):
    shipped = ad.ROOT / ad.CELLS_JSON
    if not shipped.exists():
        pytest.skip("no analysis/out/a14_cells.json in this tree")
    ad.build(tmp_path)
    assert (tmp_path / ad.CELLS_JSON).read_bytes() == shipped.read_bytes()


def test_a_dry_run_lists_the_draws_and_calls_nothing(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, "nothing registered\n")
    lines, gen = [], FakeGen(tmp_path)
    ad.run(root=tree(tmp_path), dry_run=True, runner=gen, out=lines.append)
    assert not gen.calls and sum(1 for ln in lines if "\t" in ln) == 20
    assert any(ln.startswith("act-black-3_burst_sd2r-h8\t") for ln in lines) and "mismatch" not in lines[-1]


def test_run_refuses_until_a14_is_public_and_then_until_the_route_is_recorded(tmp_path, monkeypatch):
    root, gen = tree(tmp_path), FakeGen(tmp_path)
    public(tmp_path, monkeypatch, "### A10 — 2026-11-20: ladder\n")
    with pytest.raises(SystemExit) as e:
        ad.run(root=root, runner=gen, out=lambda s: None)
    assert "A14" in str(e.value) and not gen.calls
    public(tmp_path, monkeypatch, A14)
    with pytest.raises(SystemExit) as e:
        ad.run(root=root, runner=gen, out=lambda s: None)
    assert "a14_route.json" in str(e.value) and "A14.3.3" in str(e.value) and not gen.calls


def test_the_route_verdict_needs_the_capture_and_is_fixed_once_recorded(tmp_path):
    root = tree(tmp_path)
    with pytest.raises(SystemExit) as e:
        ad.route("match", root)
    assert "docs/A14-ROUTE.md" in str(e.value)
    doc = root / "docs" / "A14-ROUTE.md"
    doc.write_text("captured\n")
    rec = ad.route("match", root)
    assert rec["verdict"] == "match" and rec["record_sha256"] == hashlib.sha256(doc.read_bytes()).hexdigest()
    assert ad.route("match", root)["verdict"] == "match"                     # the same verdict again: no change
    with pytest.raises(SystemExit) as e:
        ad.route("mismatch", root)
    assert "already" in str(e.value)
    with pytest.raises(SystemExit):
        ad.route("maybe", root)


def run_all(root, gen, **kw):
    """The watched first draw alone (`run --limit 1`, A14.3.4), then the rest."""
    first = ad.run(root=root, runner=gen, limit=1, out=lambda s: None, **kw)
    rest = ad.run(root=root, runner=gen, out=lambda s: None, **kw)
    return {k: first[k] + rest[k] for k in ("new", "refused")}


def test_a_match_runs_the_twenty_on_seedance2_with_their_seeds(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A14)
    root = tree(tmp_path, "match")
    gen = FakeGen(root)
    assert run_all(root, gen) == {"new": 20, "refused": 0}
    assert [arg(c, "--cell-id") for c in gen.calls] == BASE20
    for c in gen.calls:
        cell = arg(c, "--cell-id")
        assert arg(c, "--engine") == "seedance2" and arg(c, "--seed") == str(20260812 + int(cell.rsplit("-h", 1)[1]))
        assert arg(c, "--motion") == cell.split("_")[1].upper()
        assert arg(c, "--panel").endswith(f"dataset/panels/{cell.split('_')[0]}.png")
        assert "--ratio" not in c and "--last-panel" not in c                  # gen_video's 1280:720, first frame only


def test_a_mismatch_at_the_route_check_changes_nothing_in_the_batch(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A14)
    root = tree(tmp_path, "mismatch")
    gen = FakeGen(root)
    assert run_all(root, gen) == {"new": 20, "refused": 0}
    assert [arg(c, "--cell-id") for c in gen.calls] == BASE20
    assert [arg(c, "--seed") for c in gen.calls[-5:]] == [str(s) for s in range(20260816, 20260821)]


def test_a_draw_failed_twice_at_runway_is_refused_with_its_seed_and_resume_skips_it(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A14)
    root = tree(tmp_path, "match")
    bad = "cu-line-1_burst_sd2r-h3"
    gen = FakeGen(root, fail={bad: [REFUSAL + "\n", REFUSAL + "\n"]})
    assert run_all(root, gen, err=lambda s: None) == {"new": 19, "refused": 1}
    lines = [json.loads(x) for x in (root / "runs" / "manifest.jsonl").read_text().splitlines()]
    (ref,) = [x for x in lines if x.get("refused")]
    assert ref["cell_id"] == bad and ref["seed"] == 20260815 and ref["refusal"] == REFUSAL
    assert ref["engine"] == "seedance2" and ref["motion_class"] == "BURST" and ref["out"] is None
    assert ref["model_version"] == "seedance2 (Runway dev API, X-Runway-Version 2024-11-06)"
    again = FakeGen(root)
    assert ad.run(root=root, runner=again, out=lambda s: None)["skipped"] == 20 and not again.calls


def test_a_cancelled_task_stops_the_run_without_a_line(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, A14)
    root = tree(tmp_path, "match")
    gen = FakeGen(root, fail={"cu-line-1_idle_sd2r-h1": [CANCELLED, CANCELLED]})
    with pytest.raises(SystemExit) as e:
        ad.run(root=root, runner=gen, limit=1, out=lambda s: None, err=lambda s: None)
    assert "Not recorded as refused" in str(e.value)
    assert not (root / "runs" / "manifest.jsonl").exists()


# The reference (A14.3.4, as ruled after the drivers were confirmed): from the watched first
# draw's Runway task record: its `model` field; else every Runway-reported field whose name holds
# "model" or "version", by name; else none, and the in-run check cannot fire. Never the harness's
# own version string.
def reference(root):
    return json.loads((root / ad.ROUTE_JSON).read_text())["task_reference"]


def test_the_first_draw_runs_alone(tmp_path):
    root = tree(tmp_path, "match")
    gen = FakeGen(root)
    with pytest.raises(SystemExit) as e:
        ad.run(root=root, runner=gen, out=lambda s: None)
    assert "--limit 1" in str(e.value) and not gen.calls
    with pytest.raises(SystemExit):
        ad.run(root=root, runner=gen, limit=2, out=lambda s: None)
    assert ad.run(root=root, runner=gen, limit=1, out=lambda s: None)["new"] == 1
    assert reference(root)["captured_from"] == "cu-line-1_idle_sd2r-h1"


def test_the_model_field_is_the_reference_and_a_change_stops_generation_for_good(tmp_path):
    root = tree(tmp_path, "match")
    gen = FakeGen(root, tasks=({"model": "seedance2-2.0-standard"}, {"model": "seedance2-2.0-standard"},
                               {"model": "seedance2-fast"}))
    ad.run(root=root, runner=gen, limit=1, out=lambda s: None)
    ref = reference(root)
    assert ref["fields"] == {"model": "seedance2-2.0-standard"} and ref["check"] == "the model field"
    with pytest.raises(SystemExit) as e:
        ad.run(root=root, runner=gen, out=lambda s: None)
    assert "route mismatch found during the run" in str(e.value) and "seedance2-fast" in str(e.value)
    assert len(gen.calls) == 3                                               # stopped at the clip that changed
    again = FakeGen(root)
    with pytest.raises(SystemExit) as e:                                     # and never resumes
        ad.run(root=root, runner=again, out=lambda s: None)
    assert "found during the run" in str(e.value) and not again.calls
    with pytest.raises(SystemExit):                                          # the verdict itself never changes
        ad.route("mismatch", root)


def test_without_a_model_field_the_fields_named_model_or_version_are_the_reference(tmp_path):
    root = tree(tmp_path, "match")
    gen = FakeGen(root, tasks=({"modelVersion": "2.0.1", "apiVersion": "2024-11-06", "progress": 1},
                               {"modelVersion": "2.0.2", "apiVersion": "2024-11-06", "progress": 1}))
    ad.run(root=root, runner=gen, limit=1, out=lambda s: None)
    ref = reference(root)
    assert ref["fields"] == {"modelVersion": "2.0.1", "apiVersion": "2024-11-06"}
    assert ref["check"] == "Runway-reported fields named model or version"
    with pytest.raises(SystemExit) as e:
        ad.run(root=root, runner=gen, out=lambda s: None)
    assert "modelVersion" in str(e.value) and "2.0.2" in str(e.value) and len(gen.calls) == 2


def test_with_neither_the_check_cannot_fire_and_the_harness_string_is_never_compared(tmp_path):
    root = tree(tmp_path, "match")
    gen = FakeGen(root, tasks=({},), versions=("seedance2 (Runway dev API, X-Runway-Version 2024-11-06)",
                                               "seedance2 (Runway dev API, X-Runway-Version 2026-01-01)"))
    assert run_all(root, gen) == {"new": 20, "refused": 0}                 # nothing stops it
    ref = reference(root)
    assert ref["fields"] == {} and "cannot fire" in ref["check"] and "route verdict" in ref["check"]


def test_a_run_that_died_before_the_capture_takes_the_first_draw_not_a_later_one(tmp_path):
    root = tree(tmp_path, "match")
    FakeGen(root, tasks=({"model": "seedance2-2.0-standard"},))(          # gen_video wrote the first line,
        ad.gen_cmd(ad.cells()[0], root))                                    # then the run died: no reference
    assert "task_reference" not in json.loads((root / ad.ROUTE_JSON).read_text())
    gen = FakeGen(root, tasks=({"model": "seedance2-other"},))
    with pytest.raises(SystemExit) as e:                                    # the reference is taken first, from the
        ad.run(root=root, runner=gen, out=lambda s: None)                   # first draw, before any submission
    assert reference(root)["captured_from"] == "cu-line-1_idle_sd2r-h1"
    assert reference(root)["fields"] == {"model": "seedance2-2.0-standard"}
    assert "seedance2-other" in str(e.value) and len(gen.calls) == 1


def test_metrics_go_to_the_seedance_folders(tmp_path):
    root = tree(tmp_path)
    clip = root / "runs" / "seedance2" / "cu-line-1_idle_sd2r-h1.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"x")
    calls = []
    n = ad.metrics(root=root, runner=lambda cmd, **kw: calls.append(cmd), out=lambda s: None)
    assert n == 1 and len(calls) == 2
    assert calls[0][-1].endswith("runs/metrics-seedance/cu-line-1_idle_sd2r-h1.json")
    assert calls[0][calls[0].index("--panel") + 1].endswith("dataset/panels/cu-line-1.png")
    assert calls[1][-1].endswith("runs/metrics-motion-seedance/cu-line-1_idle_sd2r-h1.json")



def test_the_route_check_refuses_until_a14_is_public(tmp_path, monkeypatch):
    root = tree(tmp_path)
    (root / "docs" / "A14-ROUTE.md").write_text("captured\n")
    public(tmp_path, monkeypatch, "### A10 — 2026-11-20: ladder\n")
    with pytest.raises(SystemExit) as e:
        ad.route("match", root)
    assert "A14" in str(e.value) and not (root / ad.ROUTE_JSON).exists()


# A later record that LACKS a captured field is a harness fault, resumable once the operator records
# why; "route mismatch found during the run" is reserved for a captured field present and different.
def test_a_record_lacking_the_captured_field_is_a_resumable_harness_fault(tmp_path):
    root = tree(tmp_path, "match")
    gen = FakeGen(root, tasks=({"model": "seedance2-2.0-standard"}, {}, {"model": "seedance2-2.0-standard"}))
    ad.run(root=root, runner=gen, limit=1, out=lambda s: None)
    with pytest.raises(SystemExit) as e:
        ad.run(root=root, runner=gen, out=lambda s: None)
    msg = str(e.value)
    assert "harness fault" in msg and "lacks" in msg and "model" in msg and "cu-line-1_idle_sd2r-h2" in msg
    assert "if the absence cannot be explained, the run stays stopped and Aaron is told (A14.3.4)" in msg
    assert "rules if the reason" not in msg                                # the old wording, gone
    assert "found during the run" not in msg and len(gen.calls) == 2      # never the registered reading
    assert ad.found_during_run(root, {c["cell_id"] for c in ad.cells()}) is None
    with pytest.raises(SystemExit) as e:                                     # unexplained: still refused at start
        ad.run(root=root, runner=gen, out=lambda s: None)
    assert "harness fault" in str(e.value) and len(gen.calls) == 2
    ad.note_absent("cu-line-1_idle_sd2r-h2", "the task record was fetched before Runway filled the field", root)
    notes = json.loads((root / ad.ROUTE_JSON).read_text())["absent_field_notes"]
    assert notes == {"cu-line-1_idle_sd2r-h2": "the task record was fetched before Runway filled the field"}
    assert ad.run(root=root, runner=gen, out=lambda s: None)["new"] == 18          # the run resumes and completes


def test_a_note_names_only_a_cell_whose_record_lacks_a_field(tmp_path):
    root = tree(tmp_path, "match")
    gen = FakeGen(root, tasks=({"model": "seedance2"},))
    ad.run(root=root, runner=gen, limit=1, out=lambda s: None)
    with pytest.raises(SystemExit) as e:
        ad.note_absent("cu-line-1_idle_sd2r-h1", "x", root)
    assert "lacks no captured field" in str(e.value)


def test_adopt_records_a_draw_from_its_cell_list(tmp_path, monkeypatch):
    import shutil as _sh
    import gen_video as gv
    if not (_sh.which("ffmpeg") and _sh.which("ffprobe")):
        pytest.skip("ffmpeg and ffprobe needed")
    root = tree(tmp_path, "match")
    monkeypatch.setattr(gv, "ROOT", root)
    f = root / "incoming" / "d.mp4"
    f.parent.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=1280x720:d=0.2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(f)], check=True)
    with pytest.raises(SystemExit) as e:                    # the first draw's task record is the reference
        ad.adopt("act-black-3_burst_sd2r-h4", f, "task-5", root)
    assert "--record" in str(e.value) and not (root / "runs" / "manifest.jsonl").exists()
    a = gv.build_parser().parse_args(ad.gen_cmd(ad.cell("act-black-3", "BURST", 4), root)[2:])
    body = gv.runway_body(a, gv.resolve_prompt("BURST", a.pack))
    record = {"model": "seedance2", "request": body, "task_id": "task-5", "seed": 20260816,
              "task": {"id": "task-5", "model": "seedance-2.0"}}
    line = ad.adopt("act-black-3_burst_sd2r-h4", f, "task-5", root,
                    record="runway route record: " + json.dumps(record))
    assert line["seed"] == 20260816 and line["motion_class"] == "BURST" and line["engine"] == "seedance2"
    assert line["panel"].endswith("dataset/panels/act-black-3.png") and line["task_id"] == "task-5"
    assert line["task"] == {"id": "task-5", "model": "seedance-2.0"}
    ids = {c["cell_id"] for c in ad.load_cells(root)["cells"]}
    assert ad.ensure_reference(root, ids)["fields"] == {"model": "seedance-2.0"}
    g = root / "incoming" / "e.mp4"                                                  # one delivered file per cell
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=0.2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(g)], check=True)
    later = ad.adopt("act-black-3_burst_sd2r-h5", g, "task-7", root)               # a later draw: allowed
    assert later["task"] == {"id": "task-7"} and later["adopted"]["task_record"] is None
    with pytest.raises(SystemExit) as e:
        ad.adopt("act-black-3_burst_sd2r-h9", g, "task-6", root)                    # beyond the registered 20
    assert "not one of A14's draws" in str(e.value)


def test_adopt_refuses_unless_a14_is_in_the_public_preregistration(tmp_path, monkeypatch):
    root = tree(tmp_path, "match")
    f = root / "d.mp4"
    f.write_bytes(b"x")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(tmp_path / "no-public-prereg.md"))
    with pytest.raises(SystemExit) as e:
        ad.adopt("act-black-3_burst_sd2r-h4", f, "task-5", root, record="runway route record: {}")
    assert "REFUSING" in str(e.value) and "A14" in str(e.value)
    assert not (root / "runs" / "manifest.jsonl").exists()


def test_adopt_takes_its_arguments_from_the_command_the_run_was_given(tmp_path, monkeypatch):
    import shutil as _sh
    import gen_video as gv
    if not (_sh.which("ffmpeg") and _sh.which("ffprobe")):
        pytest.skip("ffmpeg and ffprobe needed")
    root = tree(tmp_path, "match")
    monkeypatch.setattr(gv, "ROOT", root)
    calls = []
    ad.run(root=root, limit=1, runner=lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, stderr=""),
           out=lambda s: None)
    (cmd,) = calls
    ran = gv.build_parser().parse_args(cmd[2:])                       # what the run was given
    record = {"model": "seedance2", "request": gv.runway_body(ran, gv.resolve_prompt(ran.motion, ran.pack)),
              "task_id": "t-1", "seed": ran.seed, "task": {"id": "t-1", "model": "seedance-2.0"}}
    f = root / "incoming" / "d.mp4"
    f.parent.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=1280x720:d=0.2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(f)], check=True)
    line = ad.adopt(ran.cell_id, f, "t-1", root, record=record)
    assert line["adopted"]["task_record"] == "the route record the run printed" and line["request"] == record["request"]


def test_a_changed_route_doc_stops_the_run_before_any_submission(tmp_path):
    root = tree(tmp_path, "match")
    gen = FakeGen(root)
    (root / "docs" / "A14-ROUTE.md").write_text("# Route check\n\nRoute: match\n\nedited after the verdict\n")
    with pytest.raises(SystemExit) as e:
        ad.run(root=root, runner=gen, limit=1, out=lambda s: None)
    assert str(e.value).startswith("REFUSING: docs/A14-ROUTE.md has changed since its verdict was recorded")
    assert not gen.calls and not (root / "runs" / "manifest.jsonl").exists()


def test_the_driver_and_its_test_carry_no_card_or_call_identifier():
    """They ship with the release and are frozen in A14's manifest: dates, never a private card or log number."""
    import re
    for f in (Path(ad.__file__), Path(__file__)):
        text = f.read_text(encoding="utf-8")
        assert "P" + "69" not in text and not re.search(r"\bcall" + r"s? \d", text), f.name
