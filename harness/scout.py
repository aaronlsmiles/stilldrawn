#!/usr/bin/env python3
"""The six-clip scout of A15 (Kling), with A5's composition (driver). A16's Midjourney scout runs
by hand, through harness/mj_log.py; this driver refuses it.

    python harness/scout.py route --engine kling_4 --verdict offered|not-offered   # A15.3.5, once
    python harness/scout.py run --engine kling_4 --dry-run   # lists the six cells; calls nothing
    python harness/scout.py run --engine kling_4 --limit 1   # the first cell alone, watched
    python harness/scout.py run --engine kling_4 --limit 2   # the remaining FLINT cells, then --limit 1 for the first BURST
    python harness/scout.py run --engine kling_4             # the rest (refuses until A15 is public)
    python harness/scout.py metrics --engine kling_4         # inkstab + motion for each scout clip
    python harness/scout.py adopt --engine kling_4 --cell C --file F --task T [--record ...]
                                                             # records a paid clip a run left behind

Cells (A15.4): analysis/out/scout_cells.json (written by analysis/scout_rule.py --cells): three
FLINT pairs, `flint-cu-line-2--cu-line-1_kling4`, `flint-act-line-2--act-tone-3_kling4`,
`flint-est-line-2--est-black-3_kling4` (first panel as the first frame, last panel as the last),
and `act-black-3_burst_kling4-h1` to `-h3`, with the frozen pack's FLINT and BURST prompts. Each
cell is one gen_video.py call on `kling_4` (`--ratio auto_720p`, 5 s, no seed; A15.3), clips in
runs/kling_4/. Inkstab JSONs go to runs/metrics-scout/, motion JSONs to runs/metrics-motion-scout/,
each clip measured against its first panel. The scout never writes A10's or A15's cell files,
and its clips never enter A10.

The metrics step writes analysis/out/a15_scout_metrics.json (a16_scout_metrics.json for
Midjourney's clips): every delivered clip it measured, with the path and sha256 of each metric
file in its release form (release_sha256), or a null sha256 when the frozen tool wrote none. A tool failure is recorded with its
reason and the step goes on; the next run of the step tries that clip again and marks it
`retried`, so a null sha256 counts as "not measurable" only after one confirming re-run has
failed too. analysis/scout_rule.py reads the rule only when the record names every delivered
clip and no failed clip awaits its confirming re-run.

Route (A15.3.5): Runway's kling_4 documentation is captured into docs/A15-ROUTE.md; `route --verdict`
records whether 5 s at auto_720p is offered, with the capture's sha256, in analysis/out/a15_route.json
(refused until A15 is public; never changed). `run` refuses without it and on "not-offered". The first
cell runs alone (`run --limit 1`, refused otherwise until a scout clip exists) and is watched; so is the first BURST
cell (the first single-image request): until a BURST clip is delivered, `--limit` must stop the run before it
(1 to the number of FLINT cells still without a line), then be 1.

Refusals (A15.3.6): harness/ladder.py's loop (drive), as A10.3.4 registers it. Resumable from the
manifest. A paid clip a run left behind is recorded with `adopt` (gen_video.adopt's checks). Tripwire: refuses until A15 is in the PUBLIC pre-registration. One scout (A15.7.1):
once its reading is written (analysis/out/a15_scout.json), nothing more runs.
"""
import argparse
import datetime as _dt
import hashlib
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from ladder import (ARMS, LIMIT_HELP, RATIOS, VENV_PY, drive, hosted_model, manifest_cells,  # noqa: E402
                    require_record_doc_unchanged)
from pack_parser import _prompt_from_file  # noqa: E402
from registration import require_public  # noqa: E402

PACK = HERE / "motion-prompts.md"
CELLS_JSON = "analysis/out/scout_cells.json"
METRICS_DIR = "runs/metrics-scout"
MOTION_DIR = "runs/metrics-motion-scout"
CLIP_DIR = {"kling_4": "kling_4", "midjourney": "midjourney"}
# A15.3.5: Runway's kling_4 documentation captured before the scout; its verdict recorded here.
ROUTE = {"kling_4": ("docs/A15-ROUTE.md", "analysis/out/a15_route.json")}
VERDICTS = ("offered", "not-offered")         # whether 5 s at auto_720p is offered (A15.3.5)


def load_cells(engine, root=ROOT):
    p = pathlib.Path(root) / CELLS_JSON
    if not p.exists():
        raise SystemExit(f"{CELLS_JSON} is missing: run `analysis/scout_rule.py --cells` first")
    return json.loads(p.read_text())[engine]


def prompts():
    return {m: _prompt_from_file(str(PACK), m) for m in ("FLINT", "BURST")}


def gen_cmd(c, engine, root=ROOT):
    root = pathlib.Path(root)
    cmd = [str(VENV_PY), str(HERE / "gen_video.py"), "--engine", engine,
           "--panel", str(root / "dataset" / "panels" / f"{c['panel']}.png"),
           "--motion", c["motion"], "--cell-id", c["cell_id"], "--ratio", RATIOS[engine]]
    if c.get("last_panel"):
        cmd += ["--last-panel", str(root / "dataset" / "panels" / f"{c['last_panel']}.png")]
    return cmd


def refusal_line(c, engine, prompt, reason):
    """A refused scout cell, in the shape of the manifest's refused lines (Kling takes no seed)."""
    line = {"cell_id": c["cell_id"], "panel": f"dataset/panels/{c['panel']}.png", "motion_class": c["motion"],
            "prompt": prompt, "engine": engine, "model_version": hosted_model(engine), "seed": None,
            "duration_s": 5, "ratio": RATIOS[engine], "cost_usd": 0.0, "date": _dt.date.today().isoformat(),
            "out": None, "refused": True, "refusal": reason}
    if c.get("last_panel"):
        line["last_panel"] = f"dataset/panels/{c['last_panel']}.png"
    return line


def route(engine, verdict, root=ROOT, today=None):
    """Record the A15 route check (A15.3.5): the verdict read by hand from docs/A15-ROUTE.md, with that
    capture's sha256; refused until A15 is public; never changed once recorded."""
    root = pathlib.Path(root)
    if engine not in ROUTE:
        raise SystemExit(f"route: {engine} has no route record here (A16's answers go to docs/A16-SETUP.md)")
    if verdict not in VERDICTS:
        raise SystemExit(f"--verdict {verdict!r}: one of {', '.join(VERDICTS)}")
    require_public(ARMS[engine]["amendment"], f"record the {engine} route check")
    doc_rel, out_rel = ROUTE[engine]
    doc = root / doc_rel
    if not doc.is_file():
        raise SystemExit(f"{doc_rel} is missing: capture Runway's {engine} documentation there first (A15.3.5)")
    out = root / out_rel
    if out.exists():
        rec = json.loads(out.read_text())
        if rec["verdict"] != verdict:
            raise SystemExit(f"{out_rel} already records {rec['verdict']!r}: a route verdict is never changed")
        return rec
    rec = {"verdict": verdict, "record": doc_rel, "record_sha256": hashlib.sha256(doc.read_bytes()).hexdigest(),
           "date": (today or _dt.date.today()).isoformat()}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def adopt(engine, cell_id, file, task_id, root=ROOT, record=None):
    """Record a scout cell whose run stopped with its clip left behind, from the file Runway delivered and
    the task id (gen_video.adopt's checks)."""
    import gen_video
    root = pathlib.Path(root)
    if engine == "midjourney":
        raise SystemExit("adopt: A16's scout runs by hand; its jobs are recorded through harness/mj_log.py")
    c = next((x for x in load_cells(engine, root) if x["cell_id"] == cell_id), None)
    if c is None:
        raise SystemExit(f"{cell_id} is not one of the {engine} scout's cells")
    # The arguments are the ones the run was given: parsed from gen_cmd's own command line, so the two cannot drift.
    args = gen_video.build_parser().parse_args(gen_cmd(c, engine, root)[2:])
    return gen_video.adopt(args, file, task_id, record=record)


def run(engine, root=ROOT, dry_run=False, limit=0, runner=subprocess.run, out=print, err=sys.stderr.write):
    root = pathlib.Path(root)
    todo, texts = load_cells(engine, root), prompts()
    if dry_run:
        for c in todo:
            out(f"{c['cell_id']}\t{c['motion']}\t{texts[c['motion']]}")
        out(f"{engine}: {len(todo)} scout cells (dry run: nothing submitted, no registration check)")
        return {"new": 0, "skipped": 0, "refused": 0}
    arm = ARMS[engine]
    require_public(arm["amendment"], f"generate the {engine} scout",
                   hint="`scout.py run --dry-run` lists the cells without it.")
    if engine == "midjourney":
        raise SystemExit("REFUSING midjourney here: A16's scout runs by hand, job by job, through "
                         "harness/mj_log.py (A16.5), not through this driver")
    if (root / arm["scout"]).exists():
        raise SystemExit(f"REFUSING: {arm['scout']} exists, so the scout's reading is written and final "
                         f"(A15.7.1); nothing more runs on the scout")
    doc_rel, route_rel = ROUTE[engine]
    if not (root / route_rel).exists():
        raise SystemExit(f"REFUSING: {route_rel} is missing: the route check (A15.3.5) comes before the scout's "
                         f"first submission: capture {doc_rel}, then `scout.py route --engine {engine} --verdict`")
    if json.loads((root / route_rel).read_text())["verdict"] != "offered":
        raise SystemExit(f"REFUSING: {route_rel} records that 5 s at auto_720p is not offered: nothing runs, and "
                         "Aaron is told (A15.3.5)")
    require_record_doc_unchanged(root, doc_rel, route_rel)   # the verdict stands on the capture it was read from
    ids = {c["cell_id"] for c in todo}
    motions = [c["motion"] for c in todo]
    if "BURST" in motions and "FLINT" in motions[motions.index("BURST"):]:
        raise SystemExit(f"{CELLS_JSON}: the FLINT cells must precede the BURST cells in the cell order (the "
                         "watched-cell rule counts on it); not running")
    made, refused = manifest_cells(root)
    started = bool(made & ids)
    if not started and limit != 1:
        raise SystemExit("REFUSING: the scout's first cell runs alone and is watched, as A14's first draw is: "
                         "`scout.py run --engine kling_4 --limit 1` first")
    # A15.3.5: the first cell of each request shape is watched. The FLINT cells send two conditioning
    # images, the BURST cells one, so until a BURST clip is delivered the run stops before the first BURST
    # cell, and that cell then runs alone (a refused one repeats the watch).
    burst = {c["cell_id"] for c in todo if c["motion"] == "BURST"}
    if started and not made & burst:
        lined = made | refused
        pending = sum(1 for c in todo if c["motion"] == "FLINT" and c["cell_id"] not in lined)
        if pending and not 1 <= limit <= pending:
            raise SystemExit(f"REFUSING: the first BURST cell is watched too (A15.3.5: the first cell of each request "
                             f"shape runs alone): with {pending} FLINT cell(s) still to run, pass `--limit` from 1 to "
                             f"{pending} so the run stops before it")
        if not pending and limit != 1:
            raise SystemExit("REFUSING: the first BURST cell runs alone and is watched (A15.3.5: the first cell of "
                             "each request shape): `scout.py run --engine kling_4 --limit 1`")
    return drive(todo, CLIP_DIR[engine], root, lambda c: gen_cmd(c, engine, root),
                 lambda c, reason: refusal_line(c, engine, texts[c["motion"]], reason),
                 limit=limit, label=f"{arm['amendment']} scout", runner=runner, out=out, err=err,
                 adopt_cmd=("scout.py", f" --engine {engine}"))


def release_sha256(path, root=ROOT):
    """sha256 of a metric file in its release form: the tree's own absolute prefix, which the frozen
    tools write into their JSON and the release build strips from shipped text, removed first. A
    file without it (the release tree's own) hashes as it is, so the record matches in both trees."""
    data = pathlib.Path(path).read_bytes()
    for prefix in {f"{pathlib.Path(root)}/", f"{pathlib.Path(root).resolve()}/"}:
        data = data.replace(prefix.encode(), b"")
    return hashlib.sha256(data).hexdigest()


def metrics_record(engine, root=ROOT, failures=None, attempted=(), today=None):
    """Write the metrics step's record: every delivered clip, with each metric file's path and sha256
    (null when the file does not exist), the tool failures recorded on it so far with their reasons
    and the run they happened in, and `retried`: set once a run of the step has tried again a clip
    that an earlier run left without a file."""
    root = pathlib.Path(root)
    out = root / ARMS[engine]["scout_metrics"]
    prev = json.loads(out.read_text()) if out.exists() else {}
    run = prev.get("runs", 0) + 1

    def entry(folder, cid):
        f = root / folder / f"{cid}.json"
        return {"path": f"{folder}/{cid}.json", "sha256": release_sha256(f, root) if f.exists() else None}
    cells = {}
    for c in load_cells(engine, root):
        cid = c["cell_id"]
        if not (root / "runs" / CLIP_DIR[engine] / f"{cid}.mp4").exists():
            continue
        before = prev.get("cells", {}).get(cid, {})
        had_null = bool(before) and any(before.get(k, {}).get("sha256") is None for k in ("inkstab", "motion"))
        cells[cid] = {"inkstab": entry(METRICS_DIR, cid), "motion": entry(MOTION_DIR, cid),
                      "failures": list(before.get("failures", [])) + [dict(f, run=run) for f in (failures or {}).get(cid, [])],
                      "retried": bool(before.get("retried")) or (had_null and cid in attempted)}
    rec = {"amendment": ARMS[engine]["amendment"], "engine": engine,
           "date": today or _dt.date.today().isoformat(), "runs": run, "cells": cells}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def metrics(engine, root=ROOT, dry_run=False, runner=subprocess.run, out=print):
    """inkstab (frozen) and motion (A6) for each scout clip that exists and lacks its JSON; each clip is
    measured against its first panel, as A5's FLINT clips were. A tool that fails on a clip is
    recorded and the step goes on; then the record of every delivered clip is written."""
    root = pathlib.Path(root)
    done, failures, attempted = 0, {}, set()
    for c in load_cells(engine, root):
        clip = root / "runs" / CLIP_DIR[engine] / f"{c['cell_id']}.mp4"
        if not clip.exists():
            continue
        jobs = []
        mj = root / METRICS_DIR / f"{c['cell_id']}.json"
        if not mj.exists():
            jobs.append([str(VENV_PY), str(root / "metrics" / "inkstab.py"), str(clip),
                         "--panel", str(root / "dataset" / "panels" / f"{c['panel']}.png"),
                         "--lineart", str(root / "dataset" / "lineart" / f"{c['panel']}-lines.png"),
                         "--out", str(mj)])
        vj = root / MOTION_DIR / f"{c['cell_id']}.json"
        if not vj.exists():
            jobs.append([str(VENV_PY), str(root / "metrics" / "motion.py"), str(clip), "--out", str(vj)])
        for cmd in jobs:
            if dry_run:
                out(" ".join(cmd))
                continue
            pathlib.Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
            attempted.add(c["cell_id"])
            try:
                runner(cmd, check=True, timeout=1800)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                reason = (f"CalledProcessError: exit {e.returncode}" if isinstance(e, subprocess.CalledProcessError)
                          else f"TimeoutExpired: after {e.timeout} s")
                failures.setdefault(c["cell_id"], []).append({"tool": pathlib.Path(cmd[1]).name, "reason": reason})
                out(f"  {c['cell_id']}: {pathlib.Path(cmd[1]).name} failed ({reason}); recorded, and a confirming "
                    "re-run of the metrics step follows before the scout's rule can read it (A15.5)")
        done += bool(jobs)
    if not dry_run:
        metrics_record(engine, root, failures=failures, attempted=attempted)
    out(f"{engine} scout: metrics {'listed' if dry_run else 'run'} for {done} clips")
    return done


def main(argv=None):
    p = argparse.ArgumentParser(description="The scout (A15.4; A16's runs by hand)")
    p.add_argument("mode", choices=["run", "metrics", "route", "adopt"])
    p.add_argument("--engine", choices=sorted(ARMS), required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=0, help=f"run: {LIMIT_HELP} (1 for the first cell)")
    p.add_argument("--verdict", choices=VERDICTS, help="route: whether 5 s at auto_720p is offered")
    p.add_argument("--cell", help="adopt: the cell whose clip was left behind")
    p.add_argument("--file", help="adopt: the file Runway delivered for it")
    p.add_argument("--task", help="adopt: the task id the run printed")
    p.add_argument("--record", help="adopt: the `runway route record:` line the run printed, if kept")
    p.add_argument("--record-file", help="adopt: a file holding that line (or its JSON), instead of --record")
    a = p.parse_args(argv)
    if a.mode == "route":
        if not a.verdict:
            p.error("route needs --verdict")
        print(json.dumps(route(a.engine, a.verdict)))
    elif a.mode == "adopt":
        if not (a.cell and a.file and a.task):
            p.error("adopt needs --cell, --file and --task")
        import gen_video
        print(json.dumps(adopt(a.engine, a.cell, a.file, a.task,
                               record=gen_video.record_from_args(a.record, a.record_file))))
    elif a.mode == "run":
        run(a.engine, dry_run=a.dry_run, limit=a.limit)
    else:
        metrics(a.engine, dry_run=a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
