#!/usr/bin/env python3
"""A16: the hand-run job log for Midjourney's image-to-video, scout and arm (A16.3 to A16.5).

    python harness/mj_log.py build                  # writes analysis/out/a16_jobs.json (before registration)
    python harness/mj_log.py setup --seed-honoured no --motion-setting "..." --end-frame yes --hd yes \
        --prompt-verbatim yes --videos-per-job 4     # A16.4's answers, once, after docs/A16-SETUP.md
    python harness/mj_log.py next                   # prints the next job (refuses until A16 is public)
    python harness/mj_log.py record --cell C --outcome ok --job-id ID --file F --model-version V \
        --frame-size WxH --download-option ... [--settings-shown JSON] [--other F ...]
    python harness/mj_log.py record --cell C --outcome void|refused|failed --job-id ID --reason "..."

Jobs (A16.2, A16.6, A16.8): the six scout jobs in A5's composition (analysis/out/scout_cells.json),
then the 48 arm jobs panel by panel in the order of A10's cell list, each with its cell id, panel,
end frame (FLINT), the frozen prompt verbatim and its settings (A16.3.2); the A16.4 fields are
marked unknown at registration. A16.4's answers are recorded once, after docs/A16-SETUP.md
exists, in analysis/out/a16_setup.json, and never changed (A16.9.2); `next` refuses while they are
absent, and nothing runs if HD is not available or the frozen prompt is not taken verbatim
(A16.4.4, A16.4.5). Without an end frame (A16.4.3) the FLINT jobs are n/a and skipped.

The run (A16.5): `next` prints one job and blocks the next until it is recorded. `record`:
- ok: the downloaded file is checked (it plays; it lasts 5 s within one frame; it has the frame
  size the job page shows). A file that does not play or is the wrong length is a failed job; a
  wrong frame size is a void job. A passing file goes to runs/midjourney/<cell>.mp4 (any audio
  stripped by stream copy, the delivered file kept privately in runs/delivered/midjourney/, its
  sha256 recorded, A16.3.5), and the manifest line of A16.3.3 is written. A model version other
  than the arm's earlier clips' stops the run (A16.9.3): versions are never mixed.
- void: recorded with its reason; the cell is printed once more; a second void stops the run.
- refused: recorded; resubmitted once; refused twice, the cell's refused line is written.
- failed: recorded; resubmitted; three failed attempts on one cell stop the run.
Downloads land in runs/midjourney/incoming/ (A16.5.1; gitignored, never shipped) and `record` copies
from there: a --file or --other outside it is refused before anything is recorded.
Further videos of a job (A16.3.4) are kept privately and recorded by sha256 (--other). Arm jobs
are printed only after the scout's exact logged pass (harness/ladder.py's gate, A16.7, A16.8).
The log is runs/a16_job_log.jsonl. Tripwire: `next` and `record` refuse until A16 is in the
PUBLIC pre-registration.
"""
import argparse
import datetime as _dt
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from gen_video import audio_streams, video_md5  # noqa: E402
from ladder import (ARMS, cells as ladder_cells, load_panels, require_record_doc_unchanged,  # noqa: E402
                    require_scout_pass)
from pack_parser import _prompt_from_file  # noqa: E402
from registration import require_public  # noqa: E402

ENGINE = "midjourney"
ARM = ARMS[ENGINE]
JOBS_JSON = "analysis/out/a16_jobs.json"
SCOUT_CELLS = "analysis/out/scout_cells.json"
SETUP_DOC = "docs/A16-SETUP.md"
LOG = "runs/a16_job_log.jsonl"
CLIPS = "runs/midjourney"
INCOMING = "runs/midjourney/incoming"      # where downloads land (A16.5.1); never tracked, never released
KEPT = "runs/delivered/midjourney"
PACK, LADDER_PACK = HERE / "motion-prompts.md", HERE / "motion-ladder.md"
DURATION = 5
SEED = 20260812
UNKNOWN = "unknown at registration ({})"
ROUTE = "Midjourney web app, by hand (A16.3.1)"


def settings(flint):
    s = {"mode": "manual: the frozen prompt pasted verbatim, never a mode that writes its own",
         "resolution": "HD (720p)", "duration_s": DURATION, "videos": "one clip, never extended", "extend": "never",
         "personalisation": "off", "style_references": "off", "moodboards": "off",
         "motion": UNKNOWN.format("A16.4.2"), "seed": UNKNOWN.format("A16.4.1"),
         "other_settings": "Midjourney's defaults, recorded as the job page shows them"}
    if flint:
        s["end_frame_taken"] = UNKNOWN.format("A16.4.3")
    return s


def build(root=ROOT):
    """The 54 jobs in run order: the scout, then the arm panel by panel (A16.2, A16.6, A16.8)."""
    root = pathlib.Path(root)
    scout = json.loads((root / SCOUT_CELLS).read_text())[ENGINE]
    jobs = []
    for c in scout:
        jobs.append({"phase": "scout", "cell_id": c["cell_id"], "panel": c["panel"], "end_frame": c.get("last_panel"),
                     "motion": c["motion"], "prompt": _prompt_from_file(str(PACK), c["motion"]),
                     "prompt_pack": "harness/motion-prompts.md", "settings": settings(c["motion"] == "FLINT")})
    for c in ladder_cells(ENGINE, load_panels(root)):
        jobs.append({"phase": "arm", "cell_id": c["cell_id"], "panel": c["panel"], "end_frame": None,
                     "motion": c["level"], "prompt": _prompt_from_file(str(LADDER_PACK), c["level"]),
                     "prompt_pack": "harness/motion-ladder.md", "settings": settings(False)})
    rec = {"amendment": "A16", "engine": ENGINE, "route": ROUTE, "order": "the scout, then the arm panel by panel "
           "in the order of A10's cell list (A16.8)", "jobs": [{"n": i + 1, **j} for i, j in enumerate(jobs)]}
    out = root / JOBS_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def setup(root=ROOT, *, seed_honoured, motion_setting, end_frame, hd, prompt_verbatim, videos_per_job, today=None):
    """Record A16.4's answers once, after docs/A16-SETUP.md holds them with their screenshots. They are
    found out after registration (A16.1, A16.10), so this refuses until A16 is public."""
    root = pathlib.Path(root)
    require_public("A16", "record A16.4's answers", hint="A16.4's answers are found out after registration.")
    doc = root / SETUP_DOC
    if not doc.is_file():
        raise SystemExit(f"{SETUP_DOC} is missing: A16.4's answers are recorded there, dated, with screenshots, "
                         "before they are entered here")
    rec = {"seed_honoured": bool(seed_honoured), "motion_setting": motion_setting, "end_frame": bool(end_frame),
           "hd_available": bool(hd), "prompt_verbatim": bool(prompt_verbatim), "videos_per_job": videos_per_job,
           "record": SETUP_DOC, "record_sha256": hashlib.sha256(doc.read_bytes()).hexdigest()}
    out = root / ARM["setup"]
    if out.exists():
        old = json.loads(out.read_text())
        if {k: v for k, v in old.items() if k != "date"} != rec:
            raise SystemExit(f"{ARM['setup']} exists: A16.4's answers, once recorded, are fixed (A16.9.2)")
        return old
    rec["date"] = today or _dt.date.today().isoformat()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def load_setup(root):
    p = pathlib.Path(root) / ARM["setup"]
    if not p.exists():
        raise SystemExit(f"{ARM['setup']} is missing: A16.4's answers are found out and recorded before the "
                         "scout's first job (`mj_log.py setup`); no job is printed without them")
    s = json.loads(p.read_text())
    require_record_doc_unchanged(root, SETUP_DOC, ARM["setup"])   # the answers stand on the doc they were read from
    if not s["hd_available"]:
        raise SystemExit("HD (720p) video is not available on the plan: nothing runs at another resolution, and "
                         "Aaron is told (A16.4.4)")
    if not s["prompt_verbatim"]:
        raise SystemExit("the interface does not take the frozen prompt verbatim: nothing runs, and Aaron is told; "
                         "the frozen prompt is never edited (A16.4.5)")
    return s


def log_entries(root):
    p = pathlib.Path(root) / LOG
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def append(root, path, rec):
    p = pathlib.Path(root) / path
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def manifest(root):
    p = pathlib.Path(root) / "runs" / "manifest.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def pending(root):
    """The printed job not yet recorded, or None."""
    open_job = None
    for e in log_entries(root):
        if e["event"] == "printed":
            open_job = e
        elif e["event"] == "recorded" and open_job and e["cell_id"] == open_job["cell_id"]:
            open_job = None
    return open_job


def stops(root):
    """Why the run has stopped (A16.5.2, A16.5.4, A16.9.3), or None."""
    counts = {}
    for e in log_entries(root):
        if e["event"] == "stopped":
            return e["reason"]
        if e["event"] == "recorded":
            key = (e["cell_id"], e["outcome"])
            counts[key] = counts.get(key, 0) + 1
            if e["outcome"] == "void" and counts[key] >= 2:
                return f"a second void on {e['cell_id']} (A16.5.2): the run stops and Aaron is told"
            if e["outcome"] == "failed" and counts[key] >= 3:
                return f"three failed attempts on {e['cell_id']} (A16.5.4): the run stops and Aaron is told"
    return None


def jobs(root):
    return json.loads((pathlib.Path(root) / JOBS_JSON).read_text())["jobs"]


def next_job(root=ROOT, out=print):
    """Print the next job, filled with A16.4's answers, and log it; refuse while one is unrecorded."""
    root = pathlib.Path(root)
    require_public("A16", "print a Midjourney job", hint="`mj_log.py build` needs no registration.")
    s = load_setup(root)
    why = stops(root)
    if why:
        raise SystemExit(f"REFUSING: the run has stopped: {why}")
    p = pending(root)
    if p:
        raise SystemExit(f"job {p['n']} ({p['cell_id']}) was printed and is not recorded: record it first "
                         "(`mj_log.py record`), then the next job is printed (A16.5.1)")
    done = {x["cell_id"] for x in manifest(root)}
    todo = [j for j in jobs(root) if j["cell_id"] not in done and not (j["motion"] == "FLINT" and not s["end_frame"])]
    if not todo:
        out("every A16 job is recorded")
        return None
    job = dict(todo[0])
    if job["phase"] == "arm":
        require_scout_pass(ENGINE, root)
    filled = dict(job["settings"])
    filled["seed"] = f"{SEED} (A16.4.1: honoured)" if s["seed_honoured"] else "none (A16.4.1: not honoured)"
    filled["motion"] = f"{s['motion_setting']} (A16.4.2)"
    if "end_frame_taken" in filled:
        filled["end_frame_taken"] = "yes (A16.4.3)"
    job["settings"] = filled
    out(f"Job {job['n']} ({job['phase']}): {job['cell_id']}")
    out(f"  start frame: dataset/panels/{job['panel']}.png")
    if job["end_frame"]:
        out(f"  end frame: dataset/panels/{job['end_frame']}.png")
    out(f"  prompt (paste verbatim): {job['prompt']}")
    for k, v in filled.items():
        out(f"  {k}: {v}")
    append(root, LOG, {"event": "printed", "n": job["n"], "cell_id": job["cell_id"],
                       "time": _dt.datetime.now().isoformat(timespec="seconds")})
    return job


def probe(path):
    """(plays, duration_s, fps, 'WxH') of a downloaded file."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True)
    plays = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
                           capture_output=True).returncode == 0
    if r.returncode != 0:
        return False, None, None, None
    info = json.loads(r.stdout)
    st = (info.get("streams") or [{}])[0]
    num, _, den = (st.get("r_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    dur = float((info.get("format") or {}).get("duration") or 0)
    size = f"{st['width']}x{st['height']}" if "width" in st else None
    return plays and size is not None, dur, fps, size


def sha256(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def keep(root, src, name):
    dst = pathlib.Path(root) / KEPT / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return str(dst.relative_to(root))


def record(root=ROOT, cell=None, outcome=None, *, job_id, file=None, model_version=None, frame_size=None,
           download_option=None, settings_shown=None, reason=None, others=(), out=print):
    """Record the printed job's outcome (A16.5); returns the manifest line (ok) or the log entry."""
    root = pathlib.Path(root)
    require_public("A16", "record a Midjourney job")
    p = pending(root)
    if not p:
        raise SystemExit("no job is printed: `mj_log.py next` prints the job first (A16.5.1)")
    if cell != p["cell_id"]:
        raise SystemExit(f"job {p['n']} printed is {p['cell_id']}, not {cell}: record the printed job")
    if outcome not in ("ok", "void", "refused", "failed"):
        raise SystemExit(f"--outcome {outcome!r}: ok, void, refused or failed (A16.5)")
    inbox = (root / INCOMING).resolve()
    for f in ([file] if file else []) + list(others):
        if not pathlib.Path(f).resolve().is_relative_to(inbox):
            raise SystemExit(f"{f}: downloads land in {INCOMING}/ and are recorded from there (A16.5.1); "
                             "nothing recorded")
    job = next(j for j in jobs(root) if j["n"] == p["n"])
    s = load_setup(root)
    now = _dt.datetime.now()
    entry = {"event": "recorded", "n": p["n"], "cell_id": cell, "outcome": outcome, "job_id": job_id,
             "reason": reason, "model_version": model_version, "time": now.isoformat(timespec="seconds"),
             "others": [{"sha256": sha256(f), "kept": keep(root, f, f"{cell}.other{i + 1}.mp4")}
                        for i, f in enumerate(others)]}
    if outcome == "ok":
        earlier = {x.get("model_version") for x in manifest(root) if x.get("engine") == ENGINE and not x.get("refused")}
        if earlier and model_version not in earlier:
            append(root, LOG, {**entry, "outcome": "stopped"})
            append(root, LOG, {"event": "stopped", "reason": f"model version {model_version!r} after "
                               f"{sorted(earlier)} (A16.9.3)"})
            raise SystemExit(f"{cell}: Midjourney labels this job {model_version!r}, not {sorted(earlier)}: the run "
                             "stops and Aaron is told; versions are never mixed (A16.9.3)")
        plays, dur, fps, size = probe(file)
        tol = 1 / fps if fps else 0
        check = {"plays": plays, "duration_s": dur, "fps": fps, "frame_size": size, "recorded_frame_size": frame_size,
                 "duration_ok": plays and abs(dur - DURATION) <= tol, "size_ok": size == frame_size}
        entry["check"], entry["delivered_sha256"] = check, sha256(file)
        if not check["duration_ok"]:
            entry.update(outcome="failed", reason="no playable video of the right duration (A16.5.4)",
                         kept=keep(root, file, f"{cell}.failed.mp4"))
        elif not check["size_ok"]:
            entry.update(outcome="void", reason=f"frame size {size}, not the recorded {frame_size} (A16.5.2)",
                         kept=keep(root, file, f"{cell}.void.mp4"))
        if entry["outcome"] != "ok":
            append(root, LOG, entry)
            out(f"{cell}: recorded as {entry['outcome']}: {entry['reason']}")
            return entry
        dst = root / CLIPS / f"{cell}.mp4"
        if dst.exists():
            raise SystemExit(f"{dst} exists: a cell's draw is its first job that passes the check (A16.5.5)")
        dst.parent.mkdir(parents=True, exist_ok=True)
        audio = {"delivered_audio_streams": audio_streams(file), "stripped": False}
        if audio["delivered_audio_streams"]:
            tmp = dst.with_name(dst.stem + ".tmp.mp4")
            r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(file), "-map", "0:v:0", "-c", "copy", str(tmp)],
                               capture_output=True, text=True)
            if r.returncode != 0 or video_md5(tmp) != video_md5(file) or audio_streams(tmp):
                tmp.unlink(missing_ok=True)
                raise SystemExit(f"{cell}: the audio strip failed its check; nothing recorded")
            tmp.replace(dst)
            audio.update(stripped=True, video_packet_md5=video_md5(dst), delivered_kept=keep(root, file, f"{cell}.mp4"))
        else:
            shutil.copyfile(file, dst)
        line = {"cell_id": cell, "panel": f"dataset/panels/{job['panel']}.png", "motion_class": job["motion"],
                "prompt": job["prompt"], "engine": ENGINE, "model_version": model_version,
                "seed": SEED if s["seed_honoured"] else None, "duration_s": round(dur, 3), "ratio": size,
                "requested_ratio": ARM["ratio"], "wall_s": None, "cost_usd": 0.0, "date": now.date().isoformat(),
                "out": str(dst.relative_to(root))}
        if job["end_frame"]:
            line["last_panel"] = f"dataset/panels/{job['end_frame']}.png"
        if job["phase"] == "arm":
            line["prompt_pack"] = job["prompt_pack"]
        line.update(route=ROUTE, job_id=job_id, time=now.isoformat(timespec="seconds"),
                    settings_shown=settings_shown or {}, download_option=download_option,
                    delivered_sha256=entry["delivered_sha256"], check=check, audio=audio, others=entry["others"])
        append(root, "runs/manifest.jsonl", line)
        append(root, LOG, entry)
        out(f"{cell}: ok; manifest line written")
        return line
    append(root, LOG, entry)
    if outcome == "refused":
        refusals = sum(1 for e in log_entries(root) if e["event"] == "recorded" and e["cell_id"] == cell
                       and e["outcome"] == "refused")
        if refusals >= 2:
            versions = [e.get("model_version") for e in log_entries(root) if e["event"] == "recorded"
                        and e["cell_id"] == cell and e["outcome"] == "refused" and e.get("model_version")]
            model_version = model_version or (versions[-1] if versions else None)   # as the job returned it
            append(root, "runs/manifest.jsonl", {
                "cell_id": cell, "panel": f"dataset/panels/{job['panel']}.png", "motion_class": job["motion"],
                "prompt": job["prompt"], "engine": ENGINE, "model_version": model_version,
                "seed": SEED if s["seed_honoured"] else None, "duration_s": DURATION, "ratio": ARM["ratio"],
                "cost_usd": 0.0, "date": now.date().isoformat(), "out": None, "refused": True, "refusal": reason})
            out(f"{cell}: refused on both attempts; recorded as refused (A16.5.3)")
            return entry
    out(f"{cell}: recorded as {outcome}; the cell is printed again")
    return entry


def main(argv=None):
    yes = {"yes": True, "no": False}
    p = argparse.ArgumentParser(description="A16: the hand-run Midjourney job log")
    p.add_argument("mode", choices=["build", "setup", "next", "record"])
    p.add_argument("--seed-honoured", choices=yes)
    p.add_argument("--motion-setting")
    p.add_argument("--end-frame", choices=yes)
    p.add_argument("--hd", choices=yes)
    p.add_argument("--prompt-verbatim", choices=yes)
    p.add_argument("--videos-per-job")
    p.add_argument("--cell")
    p.add_argument("--outcome", choices=["ok", "void", "refused", "failed"])
    p.add_argument("--job-id")
    p.add_argument("--file")
    p.add_argument("--model-version")
    p.add_argument("--frame-size")
    p.add_argument("--download-option")
    p.add_argument("--settings-shown", default="{}")
    p.add_argument("--reason")
    p.add_argument("--other", action="append", default=[])
    a = p.parse_args(argv)
    if a.mode == "build":
        rec = build()
        print(f"{JOBS_JSON}: {len(rec['jobs'])} jobs")
    elif a.mode == "setup":
        need = (a.seed_honoured, a.motion_setting, a.end_frame, a.hd, a.prompt_verbatim, a.videos_per_job)
        if any(x is None for x in need):
            p.error("setup needs every A16.4 answer")
        setup(seed_honoured=yes[a.seed_honoured], motion_setting=a.motion_setting, end_frame=yes[a.end_frame],
              hd=yes[a.hd], prompt_verbatim=yes[a.prompt_verbatim], videos_per_job=a.videos_per_job)
    elif a.mode == "next":
        next_job()
    else:
        record(cell=a.cell, outcome=a.outcome, job_id=a.job_id, file=a.file, model_version=a.model_version,
               frame_size=a.frame_size, download_option=a.download_option,
               settings_shown=json.loads(a.settings_shown), reason=a.reason, others=a.other)
    return 0


if __name__ == "__main__":
    sys.exit(main())
