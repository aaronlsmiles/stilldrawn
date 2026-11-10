"""Tests for gen_video.py's --pack (A10). No engine is called: the parser, the prompt
resolution and the manifest record only.

    python -m pytest harness/test_gen_video.py
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_video as gv  # noqa: E402
from pack_parser import _prompt_from_file  # noqa: E402

FROZEN_KEYS = ["cell_id", "panel", "motion_class", "prompt", "engine", "model_version", "seed",
               "duration_s", "ratio", "requested_ratio", "wall_s", "cost_usd", "date", "out"]
BASE = ["--engine", "wan22", "--panel", "dataset/panels/cu-line-1.png", "--motion", "IDLE",
        "--cell-id", "x_idle_wan22"]


def line_for(argv):
    a = gv.build_parser().parse_args(argv)
    prompt = gv.resolve_prompt(a.motion, a.pack)
    out = gv.ROOT / "runs" / a.engine / f"{a.cell_id}.mp4"
    return a, gv.manifest_line(a, prompt, "v", 20260812, 12.34, 0.0, "1280x704",
                               dt.datetime(2026, 11, 20, 9, 0), out, prompt_pack=gv.pack_field(a.pack))


def test_pack_defaults_to_the_frozen_file():
    a = gv.build_parser().parse_args(BASE)
    assert Path(a.pack) == gv.MOTION_PACK and gv.MOTION_PACK.name == "motion-prompts.md"


def test_the_frozen_pack_resolves_and_records_exactly_as_before():
    _, line = line_for(BASE)
    assert line["prompt"] == _prompt_from_file(str(gv.MOTION_PACK), "IDLE")
    assert list(line) == FROZEN_KEYS                                # no prompt_pack key, frozen key order
    assert line["wall_s"] == 12.3 and line["date"] == "2026-11-20"
    assert line["out"] == "runs/wan22/x_idle_wan22.mp4"


def test_the_ladder_pack_resolves_high_and_is_recorded():
    ladder = gv.HERE / "motion-ladder.md"
    _, line = line_for(BASE[:5] + ["HIGH", "--cell-id", "ladder-cu-line-1_high_wan22", "--pack", str(ladder)])
    assert line["prompt"] == _prompt_from_file(str(ladder), "HIGH")
    assert line["motion_class"] == "HIGH"
    assert list(line) == FROZEN_KEYS + ["prompt_pack"] and line["prompt_pack"] == "harness/motion-ladder.md"


def test_naming_the_frozen_pack_explicitly_changes_nothing():
    _, line = line_for(BASE + ["--pack", str(gv.MOTION_PACK)])
    assert "prompt_pack" not in line


def test_a_pack_outside_the_repository_is_refused(tmp_path):
    p = tmp_path / "pack.md"
    p.write_text((gv.HERE / "motion-ladder.md").read_text())
    with pytest.raises(SystemExit):
        gv.pack_field(p)


def test_a_missing_pack_is_refused_with_a_message(tmp_path):
    with pytest.raises(SystemExit) as e:
        gv.pack_field(gv.HERE / "no-such-pack.md")
    assert "no such prompt pack" in str(e.value)


def _rebuild(raw):
    """Feed a recorded manifest line back through manifest_line."""
    rec = json.loads(raw)
    a = argparse.Namespace(cell_id=rec["cell_id"], panel=rec["panel"], motion=rec["motion_class"],
                           engine=rec["engine"], duration=rec["duration_s"],
                           ratio=rec["requested_ratio"], last_panel=rec.get("last_panel"),
                           pack=str(gv.MOTION_PACK))
    return gv.manifest_line(a, rec["prompt"], rec["model_version"], rec["seed"], rec["wall_s"],
                            rec["cost_usd"], rec["ratio"],
                            dt.datetime.strptime(rec["date"], "%Y-%m-%d"), gv.ROOT / rec["out"],
                            prompt_pack=gv.pack_field(a.pack))


def test_recorded_lines_rebuild_byte_for_byte():
    manifest = gv.ROOT / "runs" / "manifest.jsonl"
    if not manifest.exists():
        pytest.skip("no runs/manifest.jsonl in this tree")
    plain = with_last = None
    for raw in manifest.read_text().splitlines():
        keys = list(json.loads(raw))
        if plain is None and keys == FROZEN_KEYS:
            plain = raw
        if with_last is None and keys == FROZEN_KEYS + ["last_panel"]:
            with_last = raw
    assert plain and with_last
    for raw in (plain, with_last):
        assert json.dumps(_rebuild(raw)) == raw


def test_last_panel_then_prompt_pack():
    ladder = gv.HERE / "motion-ladder.md"
    _, line = line_for(BASE[:5] + ["HIGH", "--cell-id", "x_high_wan22", "--pack", str(ladder),
                                   "--last-panel", "dataset/panels/cu-line-2.png"])
    assert list(line) == FROZEN_KEYS + ["last_panel", "prompt_pack"]


# ------------------------------------------- seeds and the routes through harness/runway_task.py
# (A10 and A12: a seed on gen4.5 and gen4_turbo; A14: seedance2; A15: kling_4). Nothing is sent:
# subprocess.run is replaced by a fake child that writes the clip and prints the task record.
import hashlib  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402

FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")
PANEL = "dataset/panels/cu-line-1.png"
LAST = "dataset/panels/cu-line-2.png"


def args(engine, *extra):
    return gv.build_parser().parse_args(["--engine", engine, "--panel", PANEL, "--motion", "IDLE",
                                         "--cell-id", f"x_idle_{engine}", *extra])


def test_seed_defaults_to_none_and_local_engines_still_run_at_20260812():
    assert gv.build_parser().parse_args(BASE).seed is None
    assert gv.effective_seed(args("wan22")) == 20260812 == gv.SEED_DEFAULT
    assert gv.effective_seed(args("ltx23", "--seed", "20260813")) == 20260813
    assert gv.effective_seed(args("gen4.5")) is None                       # nothing sent, as before
    assert gv.effective_seed(args("gen4.5", "--seed", "20260812")) == 20260812
    assert gv.effective_seed(args("gen4_turbo", "--seed", "20260813")) == 20260813
    assert gv.effective_seed(args("seedance2", "--seed", "20260813")) == 20260813
    assert gv.effective_seed(args("seedance2")) is None
    assert gv.effective_seed(args("h3-fal", "--seed", "5")) is None         # fal: ignored, as before


def test_only_a_seeded_gen4_or_a_routed_model_goes_through_runway_task():
    assert not gv.uses_runway_task(args("gen4.5")) and not gv.uses_runway_task(args("gen4_turbo"))
    assert gv.uses_runway_task(args("gen4.5", "--seed", "20260812"))
    assert gv.uses_runway_task(args("gen4_turbo", "--seed", "20260813"))
    assert gv.uses_runway_task(args("seedance2")) and gv.uses_runway_task(args("kling_4", "--ratio", "auto_720p"))
    assert not gv.uses_runway_task(args("wan22", "--seed", "1"))


def test_the_seeded_gen45_request_carries_the_seed():
    a = args("gen4.5", "--seed", "20260812")
    assert gv.runway_body(a, "P") == {"model": "gen4.5", "promptText": "P", "ratio": "1280:720",
                                      "duration": 5, "promptImage": PANEL, "seed": 20260812}


def test_seedance2_first_frame_and_first_last_with_audio_off_and_the_draw_seed():
    a = args("seedance2", "--seed", "20260813")
    assert gv.runway_body(a, "P") == {"model": "seedance2", "promptText": "P", "ratio": "1280:720",
                                      "duration": 5, "promptImage": [{"uri": PANEL, "position": "first"}],
                                      "audio": False, "seed": 20260813}
    b = gv.runway_body(args("seedance2", "--last-panel", LAST), "P")
    assert b["promptImage"] == [{"uri": PANEL, "position": "first"}, {"uri": LAST, "position": "last"}]
    assert b["audio"] is False and "seed" not in b


def test_kling4_sends_auto_720p_no_seed_and_no_audio_field():
    b = gv.runway_body(args("kling_4", "--ratio", "auto_720p", "--last-panel", LAST), "P")
    assert b == {"model": "kling_4", "promptText": "P", "ratio": "auto_720p", "duration": 5,
                 "promptImage": [{"uri": PANEL, "position": "first"}, {"uri": LAST, "position": "last"}]}
    assert gv.runway_body(args("kling_4", "--ratio", "auto_720p"), "P")["promptImage"] == [
        {"uri": PANEL, "position": "first"}]


@pytest.mark.parametrize("engine,extra,words", [
    ("kling_4", ["--ratio", "auto_720p", "--seed", "20260812"], "takes no seed"),
    ("kling_4", [], "--ratio auto_720p"),
    ("kling_4", ["--ratio", "auto_720p", "--duration", "10"], "5 s"),
    ("seedance2", ["--ratio", "1920:1080"], "--ratio 1280:720"),
    ("seedance2", ["--duration", "4"], "5 s"),
    ("gen4.5", ["--seed", "20260812", "--last-panel", LAST], "first frame only"),
    ("gen4_turbo", ["--seed", "-1"], "0-4294967295"),
])
def test_a_request_outside_the_registered_settings_is_refused_before_anything_runs(engine, extra, words):
    with pytest.raises(SystemExit) as e:
        gv.check_runway_task(args(engine, *extra))
    assert words in str(e.value)


def test_registered_settings_pass_the_check():
    for a in (args("gen4.5", "--seed", "20260812"), args("seedance2", "--seed", "20260813"),
              args("seedance2", "--last-panel", LAST), args("kling_4", "--ratio", "auto_720p"),
              args("kling_4", "--ratio", "auto_720p", "--last-panel", LAST)):
        gv.check_runway_task(a)


def test_kling_costs_the_promotion_to_30_november_then_list():
    assert gv.runway_cost("kling_4", 5, dt.date(2026, 11, 30)) == 0.63
    assert gv.runway_cost("kling_4", 5, dt.date(2026, 12, 1)) == 0.79
    assert gv.runway_cost("seedance2", 5, dt.date(2026, 11, 20)) == 1.5
    assert gv.runway_cost("gen4.5", 5, dt.date(2026, 11, 20)) == 0.6
    assert gv.runway_model_version("kling_4") == "kling_4 (Runway dev API, X-Runway-Version 2024-11-06)"


REAL_RUN = subprocess.run


def make_clip(path, audio):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=64x48:d=0.2"]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=0.2", "-map", "0:v", "-map", "1:a",
                "-c:a", "aac"]
    REAL_RUN(cmd + ["-c:v", "libx264", str(path)], check=True)


class Child:
    """Stands in for the `op run` child only (ffmpeg and ffprobe run for real): records the
    command, writes a clip to --out (a real one when `audio` is not None, else a few bytes) and
    prints the task record on stdout."""
    def __init__(self, audio=None, task=None):
        self.audio, self.cmds = audio, []
        self.task = task or {"id": "0a1b2c3d", "status": "SUCCEEDED", "createdAt": "2026-11-20T09:00:00Z"}

    def __call__(self, cmd, **kw):
        if cmd[0] != "op":
            return REAL_RUN(cmd, **kw)
        self.cmds.append(cmd)
        out = Path(cmd[cmd.index("--out") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        if self.audio is None:
            out.write_bytes(b"clip")
        else:
            make_clip(out, self.audio)
        return subprocess.CompletedProcess(cmd, 0, stdout="progress is on stderr\n" + json.dumps(
            {"task_id": self.task["id"], "task": self.task}) + "\n")


def public(tmp_path, monkeypatch, amendments):
    """A public pre-registration (outside any private tree) carrying these amendments' headings."""
    p = tmp_path / "public" / "PREREGISTRATION.md"
    p.parent.mkdir(exist_ok=True)
    p.write_text("".join(f"### {x} — 2026-11-20: registered\n" for x in amendments), encoding="utf-8")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(p))


def run_main(tmp_path, monkeypatch, argv, child, registered=("A10", "A14", "A15")):
    public(tmp_path, monkeypatch, registered)
    monkeypatch.setattr(gv, "ROOT", tmp_path)
    monkeypatch.setattr(gv.subprocess, "run", child)
    monkeypatch.setattr(sys, "argv", ["gen_video.py", *argv])
    gv.main()
    lines = (tmp_path / "runs" / "manifest.jsonl").read_text().splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


def test_unseeded_gen4_keeps_the_original_command_and_line(tmp_path, monkeypatch):
    child = Child()
    line = run_main(tmp_path, monkeypatch, ["--engine", "gen4.5", "--panel", PANEL, "--motion", "IDLE",
                                            "--cell-id", "x_idle_gen45"], child)
    cmd = child.cmds[0]
    assert cmd[:4] == ["op", "run", "--env-file", str(gv.BACKEND_SCRIPTS / "runway.env")]
    assert cmd[5:] == ["python3", str(gv.BACKEND_SCRIPTS / "runway_gen.py"), "video", "--model", "gen4.5",
                       "--image", PANEL, "--prompt", gv.resolve_prompt("IDLE"), "--ratio", "1280:720",
                       "--duration", "5", "--out", str(tmp_path / "runs" / "gen4.5" / "x_idle_gen45.mp4")]
    assert list(line) == FROZEN_KEYS and line["seed"] is None and line["cost_usd"] == 0.6
    assert line["model_version"] == "gen4.5 (Runway dev API, X-Runway-Version 2024-11-06)"


def test_a_seeded_gen45_cell_sends_and_records_its_seed_task_and_request(tmp_path, monkeypatch):
    child = Child(task={"id": "t9", "status": "SUCCEEDED", "createdAt": "c", "seed": 20260812})
    ladder = tmp_path / "harness" / "motion-ladder.md"          # the pack inside the (patched) repository
    ladder.parent.mkdir()
    shutil.copyfile(gv.HERE / "motion-ladder.md", ladder)
    ladder = str(ladder)
    line = run_main(tmp_path, monkeypatch, ["--engine", "gen4.5", "--panel", PANEL, "--motion", "HIGH",
                                            "--cell-id", "ladder-cu-line-1_high_gen45", "--ratio", "1280:720",
                                            "--pack", ladder, "--seed", "20260812"], child)
    cmd = child.cmds[0]
    assert cmd[5:7] == ["python3", str(gv.HERE / "runway_task.py")]
    sent = json.loads(cmd[cmd.index("--request") + 1])
    assert sent["seed"] == 20260812 and sent["model"] == "gen4.5" and sent["promptImage"] == PANEL
    assert list(line)[:len(FROZEN_KEYS) + 1] == FROZEN_KEYS + ["prompt_pack"]
    assert line["seed"] == 20260812 and line["ratio"] == "1280:720" and line["cost_usd"] == 0.6
    assert line["route"] == "Runway" and line["model_id"] == "gen4.5" and line["runway_api_version"] == "2024-11-06"
    assert line["request"] == sent and line["task_id"] == "t9" and line["task"]["seed"] == 20260812
    assert "audio" not in line


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_kling4_audio_is_stripped_by_stream_copy_and_recorded(tmp_path, monkeypatch):
    line = run_main(tmp_path, monkeypatch, ["--engine", "kling_4", "--panel", PANEL, "--motion", "BURST",
                                            "--cell-id", "act-black-3_burst_kling4-h1", "--ratio", "auto_720p"],
                    Child(audio=True))
    clip = tmp_path / "runs" / "kling_4" / "act-black-3_burst_kling4-h1.mp4"
    kept = tmp_path / "runs" / "delivered" / "kling_4" / "act-black-3_burst_kling4-h1.mp4"
    assert gv.audio_streams(clip) == 0 and gv.audio_streams(kept) == 1
    assert gv.video_md5(clip) == gv.video_md5(kept)                       # the video packets, unchanged
    au = line["audio"]
    assert au == {"sent": None, "delivered_audio_streams": 1,
                  "delivered_sha256": hashlib.sha256(kept.read_bytes()).hexdigest(), "stripped": True,
                  "video_packet_md5": gv.video_md5(clip),
                  "delivered_kept": "runs/delivered/kling_4/act-black-3_burst_kling4-h1.mp4"}
    assert line["seed"] is None and line["requested_ratio"] == "auto_720p" and line["ratio"] == "64x48"
    assert "seed" not in line["request"] and "audio" not in line["request"]
    assert line["model_version"] == "kling_4 (Runway dev API, X-Runway-Version 2024-11-06)"


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_seedance2_with_audio_off_records_a_silent_delivery_and_its_draw_seed(tmp_path, monkeypatch):
    line = run_main(tmp_path, monkeypatch, ["--engine", "seedance2", "--panel", PANEL, "--motion", "IDLE",
                                            "--cell-id", "cu-line-1_idle_sd2r-h1", "--seed", "20260813"],
                    Child(audio=False))
    clip = tmp_path / "runs" / "seedance2" / "cu-line-1_idle_sd2r-h1.mp4"
    assert line["audio"] == {"sent": False, "delivered_audio_streams": 0,
                             "delivered_sha256": hashlib.sha256(clip.read_bytes()).hexdigest(), "stripped": False}
    assert line["request"]["audio"] is False and line["request"]["seed"] == 20260813 == line["seed"]
    assert not (tmp_path / "runs" / "delivered").exists() and line["cost_usd"] == 1.5


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_seedance2_audio_delivered_despite_the_switch_is_stripped_too(tmp_path, monkeypatch):
    line = run_main(tmp_path, monkeypatch, ["--engine", "seedance2", "--panel", PANEL, "--motion", "IDLE",
                                            "--cell-id", "cu-line-1_idle_sd2r-h2", "--seed", "20260814"],
                    Child(audio=True))
    assert line["audio"]["sent"] is False and line["audio"]["stripped"] is True
    assert gv.audio_streams(tmp_path / "runs" / "seedance2" / "cu-line-1_idle_sd2r-h2.mp4") == 0


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_a_failed_strip_leaves_the_delivered_clip_in_place_and_writes_no_line(tmp_path, monkeypatch):
    md5s = iter(["MD5=aa", "MD5=bb"])
    monkeypatch.setattr(gv, "video_md5", lambda p: next(md5s))
    with pytest.raises(SystemExit) as e:
        run_main(tmp_path, monkeypatch, ["--engine", "kling_4", "--panel", PANEL, "--motion", "IDLE",
                                         "--cell-id", "x_idle_kling4", "--ratio", "auto_720p"], Child(audio=True))
    clip = tmp_path / "runs" / "kling_4" / "x_idle_kling4.mp4"
    assert "video packets differ" in str(e.value) and str(clip) in str(e.value)
    assert clip.exists() and gv.audio_streams(clip) == 1     # harness/ladder.py stops on a clip left behind
    assert not (tmp_path / "runs" / "manifest.jsonl").exists()
    assert not list((tmp_path / "runs" / "kling_4").glob("x_idle_kling4.tmp.mp4"))



# ------------------------------------- a paid clip never loses its record (ruled 8 Nov 2026)
import ladder  # noqa: E402

# The child as a real process, with only its HTTP transport faked: Runway answers RUNNING, FAILED.
FAILING_CHILD = """
import sys
sys.path.insert(0, {harness!r})
import runway_task as rt
seq = iter(["RUNNING", "FAILED"])
def fake(method, path, body=None):
    if method == "POST":
        return {{"id": "0a1b2c3d"}}
    status = next(seq)
    rec = {{"id": "0a1b2c3d", "status": status}}
    if status == "FAILED":
        rec.update(failure="Output failed", failureCode="INTERNAL.BAD_OUTPUT.CODE01")
    return rec
rt._req = fake
rt.POLL_SECONDS = 0
rt.time.sleep = lambda s: None
sys.exit(rt.main(sys.argv[1:]))
"""


def test_a_failed_task_reaches_the_callers_stderr_through_main_and_only_it_reads_as_a_refusal(
        tmp_path, monkeypatch, capfd):
    def op(cmd, **kw):                    # stands in for `op run --env-file ... --`, then runs the real child
        if cmd[0] != "op":
            return REAL_RUN(cmd, **kw)
        rest = cmd[cmd.index("--") + 1:]
        assert rest[:2] == ["python3", str(gv.HERE / "runway_task.py")]
        child = [sys.executable, "-c", FAILING_CHILD.format(harness=str(gv.HERE)), *rest[2:]]
        return REAL_RUN(child, **kw)
    monkeypatch.setattr(gv, "ROOT", tmp_path)
    monkeypatch.setattr(gv.subprocess, "run", op)
    panel = str(gv.HERE.parent / PANEL)
    monkeypatch.setattr(sys, "argv", ["gen_video.py", "--engine", "gen4.5", "--panel", panel, "--motion", "IDLE",
                                      "--cell-id", "x_idle_gen45", "--seed", "20260812"])
    with pytest.raises(subprocess.CalledProcessError):
        gv.main()
    err = capfd.readouterr().err
    assert "submitted gen4.5 as task 0a1b2c3d" in err.splitlines()
    assert ladder.task_outcome(err).startswith("task 0a1b2c3d FAILED: {")
    others = [ln for ln in err.splitlines() if not ln.startswith("task 0a1b2c3d FAILED: ")]
    assert not any(ladder.TASK_OUTCOME.search(ln) for ln in others)
    assert not (tmp_path / "runs" / "manifest.jsonl").exists()
    assert not (tmp_path / "runs" / "gen4.5" / "x_idle_gen45.mp4").exists()


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_the_route_record_reaches_stderr_before_the_strip_so_a_failed_strip_keeps_it(
        tmp_path, monkeypatch, capsys):
    md5s = iter(["MD5=aa", "MD5=bb"])
    monkeypatch.setattr(gv, "video_md5", lambda p: next(md5s))
    with pytest.raises(SystemExit):
        run_main(tmp_path, monkeypatch, ["--engine", "kling_4", "--panel", PANEL, "--motion", "IDLE",
                                         "--cell-id", "x_idle_kling4", "--ratio", "auto_720p"],
                 Child(audio=True, task={"id": "t7", "status": "SUCCEEDED", "createdAt": "c"}))
    err = capsys.readouterr().err
    rec_lines = [ln for ln in err.splitlines() if ln.startswith("runway route record: ")]
    assert len(rec_lines) == 1 and not ladder.TASK_OUTCOME.search(rec_lines[0])
    rec = json.loads(rec_lines[0][len("runway route record: "):])
    assert rec["model"] == "kling_4" and rec["task_id"] == "t7" and rec["seed"] is None
    assert rec["request"]["ratio"] == "auto_720p" and rec["out"].endswith("runs/kling_4/x_idle_kling4.mp4")
    assert not (tmp_path / "runs" / "manifest.jsonl").exists()      # still no line: the run stops


def test_a_seeded_gen45_route_record_carries_its_seed(tmp_path, monkeypatch, capsys):
    run_main(tmp_path, monkeypatch, ["--engine", "gen4.5", "--panel", PANEL, "--motion", "IDLE",
                                     "--cell-id", "x_idle_gen45", "--seed", "20260812"], Child())
    (ln,) = [x for x in capsys.readouterr().err.splitlines() if x.startswith("runway route record: ")]
    rec = json.loads(ln[len("runway route record: "):])
    assert rec["seed"] == 20260812 == rec["request"]["seed"] and rec["task_id"] == "0a1b2c3d"



# ------------------- a second guard until A14's and A15's drivers exist (ruled 8 Nov 2026)
@pytest.mark.parametrize("engine,extra,needs,registered", [
    ("seedance2", ["--seed", "20260813"], "A14", ("A10", "A15")),
    ("kling_4", ["--ratio", "auto_720p"], "A15", ("A10", "A14")),
    ("seedance2", [], "A14", ()),
    ("kling_4", ["--ratio", "auto_720p"], "A15", ("A1", "A5", "A150")),
])
def test_a_routed_model_is_refused_until_its_amendment_is_public(tmp_path, monkeypatch, engine, extra,
                                                                  needs, registered):
    child = Child()
    with pytest.raises(SystemExit) as e:
        run_main(tmp_path, monkeypatch, ["--engine", engine, "--panel", PANEL, "--motion", "IDLE",
                                         "--cell-id", f"x_idle_{engine}", *extra], child, registered=registered)
    assert f"amendment {needs} is not in the public pre-registration" in str(e.value)
    assert not child.cmds and not (tmp_path / "runs").exists()          # nothing sent, no folder, no lock


def test_a_seeded_gen4_needs_no_amendment_here(tmp_path, monkeypatch):
    line = run_main(tmp_path, monkeypatch, ["--engine", "gen4.5", "--panel", PANEL, "--motion", "IDLE",
                                            "--cell-id", "x_idle_gen45", "--seed", "20260812"], Child(),
                    registered=())
    assert line["seed"] == 20260812                    # A10's and A12's own drivers carry their tripwires


# ------------- adopt: a paid clip left behind is recorded from the delivered file and its task id
def hd_clip(path, size="1280x720", audio=False, colour="white"):
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s={size}:d=0.2"]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=0.2", "-map", "0:v", "-map", "1:a", "-c:a", "aac"]
    REAL_RUN(cmd + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def ns(engine, cell, **kw):
    a = args(engine, *kw.pop("extra", ()))
    a.cell_id = cell
    for k, v in kw.items():
        setattr(a, k, v)
    return a


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_adopt_records_a_clip_left_behind_from_the_delivered_file_and_task_id(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, ("A14",))
    monkeypatch.setattr(gv, "ROOT", tmp_path)
    cell = "cu-line-1_idle_sd2r-h2"
    delivered = hd_clip(tmp_path / "incoming" / "from-dashboard.mp4")                # the video, from Runway
    left = tmp_path / "runs" / "seedance2" / f"{cell}.mp4"                           # the run stopped here: the
    left.parent.mkdir(parents=True, exist_ok=True)                                   # same packets, other bytes
    REAL_RUN(["ffmpeg", "-v", "error", "-y", "-i", str(delivered), "-c", "copy", "-metadata", "title=left",
              str(left)], check=True)
    assert left.read_bytes() != delivered.read_bytes()
    line = gv.adopt(ns("seedance2", cell, seed=20260814), delivered, "task-77")
    assert line["cell_id"] == cell and line["task_id"] == "task-77" and line["task"] == {"id": "task-77"}
    assert line["seed"] == 20260814 and line["request"]["seed"] == 20260814 and line["request"]["audio"] is False
    assert line["ratio"] == "1280x720" and line["audio"]["delivered_audio_streams"] == 0
    assert line["adopted"]["left_behind"]["kept"] == f"runs/delivered/seedance2/{cell}.left-behind.mp4"
    assert (tmp_path / line["adopted"]["left_behind"]["kept"]).exists() and left.exists()
    saved = json.loads((tmp_path / "runs" / "manifest.jsonl").read_text().splitlines()[-1])
    assert saved == line and list(line)[:len(FROZEN_KEYS)] == FROZEN_KEYS


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_adopt_refuses_another_video_a_wrong_frame_size_or_a_cell_with_a_line(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, ("A14",))
    monkeypatch.setattr(gv, "ROOT", tmp_path)
    cell = "cu-line-1_idle_sd2r-h3"
    hd_clip(tmp_path / "runs" / "seedance2" / f"{cell}.mp4", colour="white")
    other = hd_clip(tmp_path / "incoming" / "other.mp4", colour="black")
    with pytest.raises(SystemExit) as e:
        gv.adopt(ns("seedance2", cell, seed=20260815), other, "t1")
    assert "video packets" in str(e.value)
    small = hd_clip(tmp_path / "incoming" / "small.mp4", size="640x360")
    with pytest.raises(SystemExit) as e:
        gv.adopt(ns("seedance2", "cu-line-1_idle_sd2r-h4", seed=20260816), small, "t2")
    assert "frame size 640x360" in str(e.value)
    (tmp_path / "runs" / "manifest.jsonl").write_text(json.dumps({"cell_id": "cu-line-1_idle_sd2r-h5"}) + "\n")
    with pytest.raises(SystemExit) as e:
        gv.adopt(ns("seedance2", "cu-line-1_idle_sd2r-h5", seed=20260817), hd_clip(tmp_path / "incoming" / "x.mp4"), "t3")
    assert "already has a manifest line" in str(e.value)
    assert not (tmp_path / "runs" / "seedance2" / "cu-line-1_idle_sd2r-h4.mp4").exists()


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_adopt_strips_klings_audio_and_checks_the_720p_side(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, ("A15",))
    monkeypatch.setattr(gv, "ROOT", tmp_path)
    cell = "act-black-3_burst_kling4-h1"
    line = gv.adopt(ns("kling_4", cell, ratio="auto_720p", motion="BURST"),
                    hd_clip(tmp_path / "incoming" / "k.mp4", size="1260x720", audio=True), "t9")
    assert line["audio"]["stripped"] is True and line["ratio"] == "1260x720" and line["seed"] is None
    assert gv.audio_streams(tmp_path / "runs" / "kling_4" / f"{cell}.mp4") == 0
    with pytest.raises(SystemExit) as e:
        gv.adopt(ns("kling_4", "act-black-3_burst_kling4-h2", ratio="auto_720p", motion="BURST"),
                 hd_clip(tmp_path / "incoming" / "k2.mp4", size="1280x768"), "t10")
    assert "frame size 1280x768" in str(e.value)


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_adopt_takes_the_clip_left_in_place_when_the_audio_check_stopped_the_run(tmp_path, monkeypatch):
    # A15.3.4's strip failed: the delivered clip stays at the cell's path with its audio; once the strip is
    # fixed, adopt records it from there, and nothing is fetched from Runway again.
    public(tmp_path, monkeypatch, ("A15",))
    monkeypatch.setattr(gv, "ROOT", tmp_path)
    cell = "act-black-3_burst_kling4-h3"
    left = hd_clip(tmp_path / "runs" / "kling_4" / f"{cell}.mp4", size="1260x720", audio=True)
    sha = hashlib.sha256(left.read_bytes()).hexdigest()
    line = gv.adopt(ns("kling_4", cell, ratio="auto_720p", motion="BURST"), left, "t11")
    assert line["adopted"]["file_sha256"] == sha and line["adopted"]["left_behind"]["in_place"] is True
    assert line["audio"]["stripped"] is True and gv.audio_streams(left) == 0
    assert line["audio"]["delivered_sha256"] == sha


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_adopt_takes_the_task_record_from_the_route_record_the_run_printed_and_checks_it(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, ("A14",))
    monkeypatch.setattr(gv, "ROOT", tmp_path)
    cell = "cu-line-1_idle_sd2r-h1"
    a = ns("seedance2", cell, seed=20260813)
    body = gv.runway_body(a, gv.resolve_prompt(a.motion, a.pack))
    record = {"model": "seedance2", "request": body, "task_id": "t1", "seed": 20260813,
              "task": {"id": "t1", "status": "SUCCEEDED", "model": "seedance-2.0"}}
    clip = hd_clip(tmp_path / "incoming" / "d.mp4")
    for bad in ({**record, "task_id": "t2"}, {**record, "request": {**body, "seed": 1}}, {**record, "model": "kling_4"}):
        with pytest.raises(SystemExit) as e:
            gv.adopt(a, clip, "t1", record=bad)
        assert "route record" in str(e.value)
    assert not (tmp_path / "runs" / "seedance2" / f"{cell}.mp4").exists()
    line = gv.adopt(a, clip, "t1", record="runway route record: " + json.dumps(record))
    assert line["task"] == record["task"] and line["adopted"]["task_record"] == "the route record the run printed"


# ---- adopt hardening (Stage 2 fix round): a malformed record, a retry, one file for two cells, the lock
def _record_for(a, task_id="t1", task=None):
    body = gv.runway_body(a, gv.resolve_prompt(a.motion, a.pack))
    return {"model": a.engine, "request": body, "task_id": task_id, "seed": a.seed,
            "task": task or {"id": task_id, "status": "SUCCEEDED"}}


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
@pytest.mark.parametrize("bad,why", [("runway route record: {not json", "Expecting"), ("{oops", "Expecting"),
                                     ("runway route record: [1, 2]", "list"), ("5", "int"), ("null", "NoneType")])
def test_adopt_refuses_a_record_that_is_not_a_route_record_line(tmp_path, monkeypatch, bad, why):
    public(tmp_path, monkeypatch, ("A14",))
    monkeypatch.setattr(gv, "ROOT", tmp_path)
    cell = "cu-line-1_idle_sd2r-h1"
    clip = hd_clip(tmp_path / "incoming" / "d.mp4")
    with pytest.raises(SystemExit) as e:
        gv.adopt(ns("seedance2", cell, seed=20260813), clip, "t1", record=bad)
    msg = str(e.value)
    assert msg.startswith("REFUSING: --record is not a 'runway route record:' line (") and why in msg
    assert msg.endswith("not adopted")
    assert not (tmp_path / "runs" / "seedance2" / f"{cell}.mp4").exists()
    assert not (tmp_path / "runs" / "seedance2" / f"{cell}.lock").exists()          # the lock is released
    assert not (tmp_path / "runs" / "manifest.jsonl").exists()


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_adopt_refuses_a_retry_over_an_earlier_adopts_kept_copy(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, ("A14",))
    monkeypatch.setattr(gv, "ROOT", tmp_path)
    cell = "cu-line-1_idle_sd2r-h2"
    left = hd_clip(tmp_path / "runs" / "seedance2" / f"{cell}.mp4")
    kept = tmp_path / "runs" / "delivered" / "seedance2" / f"{cell}.left-behind.mp4"
    kept.parent.mkdir(parents=True)
    kept.write_bytes(b"an earlier adopt stopped after this copy")
    with pytest.raises(SystemExit) as e:
        gv.adopt(ns("seedance2", cell, seed=20260814), hd_clip(tmp_path / "incoming" / "d.mp4"), "t1")
    assert str(e.value) == f"REFUSING: an earlier adopt stopped part-way for {cell}; inspect {kept} before adopting"
    assert kept.read_bytes() == b"an earlier adopt stopped after this copy" and left.exists()
    assert not (tmp_path / "runs" / "manifest.jsonl").exists()


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_adopt_refuses_one_delivered_file_for_two_cells(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, ("A14", "A15"))
    monkeypatch.setattr(gv, "ROOT", tmp_path)
    one = hd_clip(tmp_path / "incoming" / "one.mp4")
    first = gv.adopt(ns("seedance2", "cu-line-1_idle_sd2r-h1", seed=20260813), one, "t1")
    with pytest.raises(SystemExit) as e:
        gv.adopt(ns("seedance2", "cu-line-1_idle_sd2r-h2", seed=20260814), one, "t2")
    assert "REFUSING" in str(e.value) and "cu-line-1_idle_sd2r-h1" in str(e.value) and "not adopted" in str(e.value)
    assert not (tmp_path / "runs" / "seedance2" / "cu-line-1_idle_sd2r-h2.mp4").exists()
    # the same refusal on audio.delivered_sha256 (a line the normal path wrote, with no `adopted` block)
    lines = (tmp_path / "runs" / "manifest.jsonl").read_text().splitlines()
    normal = {k: v for k, v in json.loads(lines[0]).items() if k != "adopted"}
    normal["cell_id"] = "normal-cell"
    (tmp_path / "runs" / "manifest.jsonl").write_text(json.dumps(normal) + "\n")
    assert normal["audio"]["delivered_sha256"] == first["adopted"]["file_sha256"]
    with pytest.raises(SystemExit) as e:
        gv.adopt(ns("seedance2", "cu-line-1_idle_sd2r-h2", seed=20260814), one, "t2")
    assert "normal-cell" in str(e.value)
    two = hd_clip(tmp_path / "incoming" / "two.mp4", colour="black")                # a different clip is fine
    assert gv.adopt(ns("seedance2", "cu-line-1_idle_sd2r-h2", seed=20260814), two, "t2")["task_id"] == "t2"


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_adopt_takes_the_per_cell_lock_the_normal_path_takes(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, ("A14",))
    monkeypatch.setattr(gv, "ROOT", tmp_path)
    cell = "cu-line-1_idle_sd2r-h3"
    lock = tmp_path / "runs" / "seedance2" / f"{cell}.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("")
    clip = hd_clip(tmp_path / "incoming" / "d.mp4")
    with pytest.raises(SystemExit) as e:
        gv.adopt(ns("seedance2", cell, seed=20260815), clip, "t1")
    assert "held" in str(e.value) and lock.exists() and not (tmp_path / "runs" / "manifest.jsonl").exists()
    lock.unlink()
    gv.adopt(ns("seedance2", cell, seed=20260815), clip, "t1")
    assert not lock.exists()                                                       # released after the line


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_adopt_dates_the_line_and_prices_kling_from_the_records_creation_time(tmp_path, monkeypatch):
    public(tmp_path, monkeypatch, ("A15",))
    monkeypatch.setattr(gv, "ROOT", tmp_path)
    after_promo = dt.date(2026, 12, 5)                                            # the adopt day: list price
    a = ns("kling_4", "act-black-3_burst_kling4-h1", ratio="auto_720p", motion="BURST")
    rec = _record_for(a, task={"id": "t1", "status": "SUCCEEDED", "createdAt": "2026-11-29T12:00:00.000Z"})
    line = gv.adopt(a, hd_clip(tmp_path / "incoming" / "k1.mp4"), "t1", today=after_promo, record=rec)
    assert line["date"] == "2026-11-29" and line["cost_usd"] == round(gv.KLING4_USD_PER_S[0] * 5, 2)
    assert line["adopted"]["date"] == "2026-12-05"
    b = ns("kling_4", "act-black-3_burst_kling4-h2", ratio="auto_720p", motion="BURST")
    plain = gv.adopt(b, hd_clip(tmp_path / "incoming" / "k2.mp4", colour="black"), "t2", today=after_promo)
    assert plain["date"] == dt.date.today().isoformat() and plain["cost_usd"] == round(gv.KLING4_USD_PER_S[1] * 5, 2)
    c = ns("kling_4", "act-black-3_burst_kling4-h3", ratio="auto_720p", motion="BURST")
    odd = _record_for(c, "t3", task={"id": "t3", "createdAt": "c"})                # not a time: the adopt day
    got = gv.adopt(c, hd_clip(tmp_path / "incoming" / "k3.mp4", colour="red"), "t3", today=after_promo, record=odd)
    assert got["cost_usd"] == round(gv.KLING4_USD_PER_S[1] * 5, 2)


def test_record_file_prefers_the_line_whose_task_id_is_the_one_adopted(tmp_path):
    # an appended batch stderr log: the previous cell's record is the last line, this cell's is earlier
    f = tmp_path / "batch.log"
    f.write_text('runway route record: {"task_id": "t-this"}\nnoise\nrunway route record: {"task_id": "t-next"}\n')
    rec = gv.record_from_args(None, str(f))
    assert gv.parse_record(rec, "t-this")["task_id"] == "t-this"
    assert gv.parse_record(rec, "t-next")["task_id"] == "t-next"
    assert gv.parse_record(rec, "t-none")["task_id"] == "t-next"      # no line carries it: the last; adopt's match refuses
    assert gv.parse_record(rec)["task_id"] == "t-next"


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_adopt_refuses_its_own_earlier_copy_as_a_left_behind_clip(tmp_path, monkeypatch):
    # no clip was left; the audio step exited after adopt copied the file to the cell's path. A retry must not
    # record that copy as a clip the run left behind.
    public(tmp_path, monkeypatch, ("A14",))
    monkeypatch.setattr(gv, "ROOT", tmp_path)
    cell = "cu-line-1_idle_sd2r-h2"
    delivered = hd_clip(tmp_path / "incoming" / "d.mp4")
    own = tmp_path / "runs" / "seedance2" / f"{cell}.mp4"
    own.parent.mkdir(parents=True)
    own.write_bytes(delivered.read_bytes())
    with pytest.raises(SystemExit) as e:
        gv.adopt(ns("seedance2", cell, seed=20260814), delivered, "t1")
    assert str(e.value) == (f"REFUSING: {own} already holds this clip for {cell}; adopt it in place with "
                            f"--file {own}; not adopted")
    assert not (tmp_path / "runs" / "delivered").exists() and not (tmp_path / "runs" / "manifest.jsonl").exists()
    assert not own.with_suffix(".lock").exists()


def test_record_file_reads_the_line_or_the_json_and_excludes_record(tmp_path):
    f = tmp_path / "rec.txt"
    f.write_text('noise\nrunway route record: {"task_id": "old"}\nmore\nrunway route record: {"task_id": "t9"}\n')
    assert gv.parse_record(gv.record_from_args(None, str(f)))["task_id"] == "t9"      # the last record line
    f.write_text('{"task_id": "t8"}\n')
    assert gv.parse_record(gv.record_from_args(None, str(f)))["task_id"] == "t8"      # bare JSON
    assert gv.record_from_args("x", None) == "x" and gv.record_from_args(None, None) is None
    with pytest.raises(SystemExit) as e:
        gv.record_from_args("x", str(f))
    assert "not both" in str(e.value)
    with pytest.raises(SystemExit) as e:
        gv.record_from_args(None, str(tmp_path / "missing.txt"))
    assert "no such file" in str(e.value)
