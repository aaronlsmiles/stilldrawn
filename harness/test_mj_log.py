"""Tests for harness/mj_log.py (A16.3 to A16.5, A16.8). Synthetic clips only: nothing is generated.

    python -m pytest harness/test_mj_log.py
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "analysis"))
import ladder  # noqa: E402
import mj_log as mj  # noqa: E402
import scout_rule  # noqa: E402
from pack_parser import _prompt_from_file  # noqa: E402

A16 = "### A16 — 2026-11-20: a Midjourney video scout, run by hand\n"
FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")
PANELS = ["act-black-2", "act-line-1", "act-tone-3", "act-tone-1", "cu-black-1", "cu-line-2",
          "cu-tone-1", "cu-line-3", "est-black-3", "est-line-1", "est-tone-2", "est-black-1"]
SCOUT = ["flint-cu-line-2--cu-line-1_mjv", "flint-act-line-2--act-tone-3_mjv",
         "flint-est-line-2--est-black-3_mjv"] + [f"act-black-3_burst_mjv-h{k}" for k in (1, 2, 3)]


@pytest.fixture(autouse=True)
def registered(tmp_path, monkeypatch):
    """A16 public by default (setup runs after registration, A16.1, A16.10); tests override it."""
    public(tmp_path, monkeypatch)


def tree(tmp_path, setup=True, end_frame=True):
    root = tmp_path / "repo"
    (root / "analysis" / "out").mkdir(parents=True)
    (root / "runs").mkdir()
    (root / "docs").mkdir()
    (root / "analysis" / "out" / "a10_panels.json").write_text(json.dumps({"panels": PANELS}))
    scout_rule.build_cells(root)
    mj.build(root)
    if setup:
        (root / "docs" / "A16-SETUP.md").write_text("answers, dated, with screenshots\n")
        mj.setup(root, seed_honoured=False, motion_setting="Low motion", end_frame=end_frame, hd=True,
                 prompt_verbatim=True, videos_per_job=4)
    return root


def public(tmp_path, monkeypatch, text=A16):
    p = tmp_path / "public" / "PREREGISTRATION.md"
    p.parent.mkdir(exist_ok=True)
    p.write_text(text, encoding="utf-8")
    monkeypatch.setenv("STILLDRAWN_PUBLIC_PREREG", str(p))


def clip(path, seconds=5, size="64x48", audio=False):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=white:s={size}:d={seconds}:r=24"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-map", "0:v", "-map", "1:a",
                "-c:a", "aac"]
    subprocess.run(cmd + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def incoming(root):
    d = root / mj.INCOMING
    d.mkdir(parents=True, exist_ok=True)
    return d


def ok(root, tmp_path, cell, **kw):
    f = clip(incoming(root) / f"{cell}-download.mp4", **{k: v for k, v in kw.items() if k in ("seconds", "size", "audio")})
    return mj.record(root, cell, "ok", job_id=f"job-{cell}", file=f, model_version="V7 video",
                     frame_size=kw.get("frame_size", "64x48"), download_option="raw",
                     settings_shown={"motion": "Low motion"}, out=lambda s: None)


def test_the_job_list_is_the_scout_then_the_arm_panel_by_panel(tmp_path):
    root = tree(tmp_path, setup=False)
    jobs = json.loads((root / mj.JOBS_JSON).read_text())["jobs"]
    assert len(jobs) == 54 and [j["cell_id"] for j in jobs[:6]] == SCOUT
    assert [j["cell_id"] for j in jobs[6:10]] == [f"ladder-act-black-2_{lv}_mjv" for lv in ("still", "low", "mid", "high")]
    assert jobs[0]["end_frame"] == "cu-line-1" and jobs[3]["end_frame"] is None
    pack = str(HERE / "motion-prompts.md")
    assert jobs[0]["prompt"] == _prompt_from_file(pack, "FLINT") and jobs[3]["prompt"] == _prompt_from_file(pack, "BURST")
    assert jobs[6]["prompt"] == _prompt_from_file(str(HERE / "motion-ladder.md"), "STILL")
    s = jobs[0]["settings"]
    assert s["resolution"] == "HD (720p)" and s["duration_s"] == 5 and s["extend"] == "never"
    assert s["seed"] == "unknown at registration (A16.4.1)" and s["motion"] == "unknown at registration (A16.4.2)"
    assert s["end_frame_taken"] == "unknown at registration (A16.4.3)"


def test_the_shipped_job_list_is_what_build_writes(tmp_path):
    shipped = mj.ROOT / mj.JOBS_JSON
    if not shipped.exists():
        pytest.skip("no analysis/out/a16_jobs.json in this tree")
    root = tmp_path / "r"
    (root / "analysis" / "out").mkdir(parents=True)
    for name in ("a10_panels.json", "scout_cells.json"):
        shutil.copyfile(mj.ROOT / "analysis" / "out" / name, root / "analysis" / "out" / name)
    mj.build(root)
    assert (root / mj.JOBS_JSON).read_bytes() == shipped.read_bytes()


def test_next_refuses_until_a16_is_public_and_while_a16_4_is_unanswered(tmp_path, monkeypatch):
    root = tree(tmp_path, setup=False)
    public(tmp_path, monkeypatch, "### A15 — 2026-11-20: kling\n")
    with pytest.raises(SystemExit) as e:
        mj.next_job(root, out=lambda s: None)
    assert "A16" in str(e.value)
    public(tmp_path, monkeypatch)
    with pytest.raises(SystemExit) as e:
        mj.next_job(root, out=lambda s: None)
    assert "a16_setup.json" in str(e.value)


def test_setup_needs_its_record_and_is_fixed_once_written(tmp_path):
    root = tree(tmp_path, setup=False)
    with pytest.raises(SystemExit) as e:
        mj.setup(root, seed_honoured=True, motion_setting="Low", end_frame=True, hd=True, prompt_verbatim=True,
                 videos_per_job=1)
    assert "docs/A16-SETUP.md" in str(e.value)
    (root / "docs" / "A16-SETUP.md").write_text("x\n")
    mj.setup(root, seed_honoured=True, motion_setting="Low", end_frame=True, hd=True, prompt_verbatim=True,
             videos_per_job=1)
    with pytest.raises(SystemExit) as e:
        mj.setup(root, seed_honoured=False, motion_setting="Low", end_frame=True, hd=True, prompt_verbatim=True,
                 videos_per_job=1)
    assert "fixed" in str(e.value)


@pytest.mark.parametrize("field", ["hd", "prompt_verbatim"])
def test_nothing_runs_without_hd_or_the_verbatim_prompt(tmp_path, monkeypatch, field):
    root = tree(tmp_path, setup=False)
    (root / "docs" / "A16-SETUP.md").write_text("x\n")
    answers = dict(seed_honoured=False, motion_setting="Low", end_frame=True, hd=True, prompt_verbatim=True,
                   videos_per_job=1)
    answers[field] = False
    mj.setup(root, **answers)
    public(tmp_path, monkeypatch)
    with pytest.raises(SystemExit) as e:
        mj.next_job(root, out=lambda s: None)
    assert "nothing runs" in str(e.value)


def test_next_prints_the_job_with_the_answers_filled_and_blocks_until_it_is_recorded(tmp_path, monkeypatch):
    root = tree(tmp_path)
    public(tmp_path, monkeypatch)
    lines = []
    job = mj.next_job(root, out=lines.append)
    assert job["cell_id"] == SCOUT[0]
    text = "\n".join(lines)
    assert SCOUT[0] in text and job["prompt"] in text and "cu-line-1" in text and "Low motion" in text
    assert "seed: none (A16.4.1: not honoured)" in text
    with pytest.raises(SystemExit) as e:
        mj.next_job(root, out=lambda s: None)
    assert SCOUT[0] in str(e.value) and "record" in str(e.value)


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_an_ok_job_is_checked_and_written_as_a_manifest_line_before_the_next_is_printed(tmp_path, monkeypatch):
    root = tree(tmp_path)
    public(tmp_path, monkeypatch)
    mj.next_job(root, out=lambda s: None)
    line = ok(root, tmp_path, SCOUT[0], audio=True)
    saved = json.loads((root / "runs" / "manifest.jsonl").read_text().splitlines()[-1])
    assert saved == line and line["cell_id"] == SCOUT[0] and line["engine"] == "midjourney"
    assert line["job_id"] == f"job-{SCOUT[0]}" and line["model_version"] == "V7 video" and line["ratio"] == "64x48"
    assert line["last_panel"] == "dataset/panels/cu-line-1.png" and line["seed"] is None
    assert line["route"] == "Midjourney web app, by hand (A16.3.1)" and line["check"]["plays"] is True
    assert line["audio"]["stripped"] is True and line["out"] == f"runs/midjourney/{SCOUT[0]}.mp4"
    assert (root / "runs" / "midjourney" / f"{SCOUT[0]}.mp4").exists()
    assert mj.next_job(root, out=lambda s: None)["cell_id"] == SCOUT[1]


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_a_wrong_length_is_a_failed_job_and_a_wrong_size_is_void(tmp_path, monkeypatch):
    root = tree(tmp_path)
    public(tmp_path, monkeypatch)
    mj.next_job(root, out=lambda s: None)
    assert ok(root, tmp_path, SCOUT[0], seconds=3)["outcome"] == "failed"
    mj.next_job(root, out=lambda s: None)
    assert ok(root, tmp_path, SCOUT[0], frame_size="1280x720")["outcome"] == "void"
    assert not (root / "runs" / "manifest.jsonl").exists()


def test_two_voids_on_a_cell_stop_the_run(tmp_path, monkeypatch):
    root = tree(tmp_path)
    public(tmp_path, monkeypatch)
    for _ in range(2):
        mj.next_job(root, out=lambda s: None)
        mj.record(root, SCOUT[0], "void", job_id="j", reason="wrong image uploaded", out=lambda s: None)
    with pytest.raises(SystemExit) as e:
        mj.next_job(root, out=lambda s: None)
    assert "second void" in str(e.value) and SCOUT[0] in str(e.value)


def test_three_failed_attempts_stop_the_run(tmp_path, monkeypatch):
    root = tree(tmp_path)
    public(tmp_path, monkeypatch)
    for _ in range(3):
        mj.next_job(root, out=lambda s: None)
        mj.record(root, SCOUT[0], "failed", job_id="j", reason="the job stalled", out=lambda s: None)
    with pytest.raises(SystemExit) as e:
        mj.next_job(root, out=lambda s: None)
    assert "three failed" in str(e.value)


def test_refused_twice_is_a_refused_line_and_the_scout_moves_on(tmp_path, monkeypatch):
    root = tree(tmp_path)
    public(tmp_path, monkeypatch)
    for _ in range(2):
        mj.next_job(root, out=lambda s: None)
        mj.record(root, SCOUT[0], "refused", job_id="j", reason="Banned prompt detected", out=lambda s: None)
    rec = json.loads((root / "runs" / "manifest.jsonl").read_text())
    assert rec["cell_id"] == SCOUT[0] and rec["refused"] is True and rec["refusal"] == "Banned prompt detected"
    assert mj.next_job(root, out=lambda s: None)["cell_id"] == SCOUT[1]


def test_without_an_end_frame_the_flint_jobs_are_na_and_the_scout_is_its_three_bursts(tmp_path, monkeypatch):
    root = tree(tmp_path, end_frame=False)
    public(tmp_path, monkeypatch)
    lines = []
    assert mj.next_job(root, out=lines.append)["cell_id"] == SCOUT[3]


def test_a_record_must_name_the_printed_job(tmp_path, monkeypatch):
    root = tree(tmp_path)
    public(tmp_path, monkeypatch)
    with pytest.raises(SystemExit):
        mj.record(root, SCOUT[0], "void", job_id="j", reason="x", out=lambda s: None)     # nothing printed
    mj.next_job(root, out=lambda s: None)
    with pytest.raises(SystemExit) as e:
        mj.record(root, SCOUT[1], "void", job_id="j", reason="x", out=lambda s: None)
    assert SCOUT[0] in str(e.value)


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_arm_jobs_need_the_scouts_exact_logged_pass(tmp_path, monkeypatch):
    root = tree(tmp_path)
    public(tmp_path, monkeypatch)
    for cell in SCOUT:
        mj.next_job(root, out=lambda s: None)
        ok(root, tmp_path, cell)
    with pytest.raises(SystemExit) as e:
        mj.next_job(root, out=lambda s: None)
    assert "a16_scout.json" in str(e.value)
    (root / ladder.ARMS["midjourney"]["scout"]).write_text(
        json.dumps({"reading": ladder.ARMS["midjourney"]["scout_passed"]}))
    assert mj.next_job(root, out=lambda s: None)["cell_id"] == "ladder-act-black-2_still_mjv"


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_a_new_model_version_stops_the_run(tmp_path, monkeypatch):
    root = tree(tmp_path)
    public(tmp_path, monkeypatch)
    mj.next_job(root, out=lambda s: None)
    ok(root, tmp_path, SCOUT[0])
    mj.next_job(root, out=lambda s: None)
    f = clip(incoming(root) / "second.mp4")
    with pytest.raises(SystemExit) as e:
        mj.record(root, SCOUT[1], "ok", job_id="j2", file=f, model_version="V8 video", frame_size="64x48",
                  download_option="raw", settings_shown={}, out=lambda s: None)
    assert "V8 video" in str(e.value) and "never mixed" in str(e.value)
    with pytest.raises(SystemExit):
        mj.next_job(root, out=lambda s: None)



def test_setup_refuses_until_a16_is_public(tmp_path, monkeypatch):
    root = tree(tmp_path, setup=False)
    (root / "docs" / "A16-SETUP.md").write_text("x\n")
    public(tmp_path, monkeypatch, "### A15 — 2026-11-20: kling\n")
    with pytest.raises(SystemExit) as e:
        mj.setup(root, seed_honoured=True, motion_setting="Low", end_frame=True, hd=True, prompt_verbatim=True,
                 videos_per_job=1)
    assert "A16" in str(e.value) and not (root / ladder.ARMS["midjourney"]["setup"]).exists()



@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_a_version_change_between_the_scout_and_the_arm_stops_the_arm_at_its_first_job(tmp_path, monkeypatch):
    root = tree(tmp_path)
    for cell in SCOUT:
        mj.next_job(root, out=lambda s: None)
        ok(root, tmp_path, cell)                                          # the scout: "V7 video"
    (root / ladder.ARMS["midjourney"]["scout"]).write_text(
        json.dumps({"reading": ladder.ARMS["midjourney"]["scout_passed"]}))
    assert mj.next_job(root, out=lambda s: None)["cell_id"] == "ladder-act-black-2_still_mjv"
    f = clip(incoming(root) / "arm1.mp4")
    with pytest.raises(SystemExit) as e:
        mj.record(root, "ladder-act-black-2_still_mjv", "ok", job_id="a1", file=f, model_version="V8 video",
                  frame_size="64x48", download_option="raw", settings_shown={}, out=lambda s: None)
    assert "never mixed" in str(e.value) and "V8 video" in str(e.value)
    assert not (root / "runs" / "midjourney" / "ladder-act-black-2_still_mjv.mp4").exists()
    with pytest.raises(SystemExit):
        mj.next_job(root, out=lambda s: None)


def test_a_refused_line_carries_the_version_string_the_job_returned(tmp_path):
    root = tree(tmp_path)
    mj.next_job(root, out=lambda s: None)
    mj.record(root, SCOUT[0], "refused", job_id="j1", reason="Banned prompt detected", model_version="V7 video",
              out=lambda s: None)
    mj.next_job(root, out=lambda s: None)
    mj.record(root, SCOUT[0], "refused", job_id="j2", reason="Banned prompt detected", out=lambda s: None)
    rec = json.loads((root / "runs" / "manifest.jsonl").read_text())
    assert rec["refused"] is True and rec["model_version"] == "V7 video"


# ---- downloads land in runs/midjourney/incoming/, record copies from there
def test_downloads_land_in_incoming_which_git_ignores():
    assert mj.INCOMING == "runs/midjourney/incoming"
    assert "runs/midjourney/incoming/" in (HERE.parent / ".gitignore").read_text().splitlines()


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg and ffprobe needed")
def test_record_refuses_a_download_outside_incoming(tmp_path, monkeypatch):
    root = tree(tmp_path)
    mj.next_job(root, out=lambda s: None)
    f = clip(tmp_path / "loose.mp4")
    with pytest.raises(SystemExit) as e:
        mj.record(root, SCOUT[0], "ok", job_id="j1", file=f, model_version="V7 video", frame_size="64x48",
                  download_option="raw", settings_shown={}, out=lambda s: None)
    assert "runs/midjourney/incoming/" in str(e.value)
    assert not (root / "runs" / "midjourney" / f"{SCOUT[0]}.mp4").exists()
    assert not (root / mj.LOG).exists() or all(x.get("event") != "recorded" for x in mj.log_entries(root))
    g = clip(incoming(root) / "first.mp4")
    with pytest.raises(SystemExit) as e:
        mj.record(root, SCOUT[0], "ok", job_id="j1", file=g, model_version="V7 video", frame_size="64x48",
                  download_option="raw", settings_shown={}, others=[f], out=lambda s: None)
    assert "runs/midjourney/incoming/" in str(e.value)
    line = mj.record(root, SCOUT[0], "ok", job_id="j1", file=g, model_version="V7 video", frame_size="64x48",
                     download_option="raw", settings_shown={}, out=lambda s: None)
    assert line["out"] == f"runs/midjourney/{SCOUT[0]}.mp4" and g.exists()


def test_a_changed_setup_doc_stops_the_next_job(tmp_path, monkeypatch):
    root = tree(tmp_path)
    public(tmp_path, monkeypatch)
    (root / "docs" / "A16-SETUP.md").write_text("answers, dated, with screenshots\nedited after they were recorded\n")
    with pytest.raises(SystemExit) as e:
        mj.next_job(root, out=lambda s: None)
    assert str(e.value).startswith("REFUSING: docs/A16-SETUP.md has changed since its verdict was recorded")
    assert not (root / mj.LOG).exists()
