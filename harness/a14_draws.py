#!/usr/bin/env python3
"""A14: Seedance 2.0 through Runway, A4's four-cell core at five fresh draws per cell (driver).

    python harness/a14_draws.py build                             # writes analysis/out/a14_cells.json
    python harness/a14_draws.py route --verdict match|mismatch    # records the route check (A14.3.3)
    python harness/a14_draws.py run --dry-run                     # lists the draws; calls nothing
    python harness/a14_draws.py run [--limit N]                   # generates (refuses until A14 is public)
    python harness/a14_draws.py metrics                           # inkstab + motion for each A14 clip
    python harness/a14_draws.py adopt --cell C --file F --task T [--record "runway route record: {...}"]
                                         # records a paid draw a run left behind (gen_video.adopt)

Cells (A14.3.1): A4's four-cell core, `cu-line-1` and `act-black-3` x {IDLE, BURST}, five fresh
Runway draws per cell: `<panel>_<motion>_sd2r-h<k>`, h1 to h5, and h4 to h8 on `act-black-3` BURST,
numbered after A5's three fal draws of that cell (20 clips, whatever the route verdict). A5's
scout draws are listed apart; they are coded beside the 20, never generated. Draw -h<k> is sent
seed 20260812 + k (A14.3.2). Each draw is one gen_video.py call on `seedance2` (1280:720, 5 s, `audio: false`, first
frame only: gen_video's own route and settings check), with the frozen pack's IDLE or BURST
prompt. Clips go to runs/seedance2/, inkstab JSONs to runs/metrics-seedance/, motion JSONs
(metrics/motion.py, A6's definitions) to runs/metrics-motion-seedance/.

Route check (A14.3.3) before the first submission: Runway's documentation for `seedance2` is
captured into docs/A14-ROUTE.md; `route --verdict` records the verdict read from it, with the
capture's sha256, in analysis/out/a14_route.json, and a recorded verdict is never changed. `run`
refuses until it exists. A mismatch adds no draw and changes nothing in the batch (A14.3.4): it is
recorded and reported as a finding in its own right, and the pooled 8-draw figure is not computed
(analysis/a14_seedance.py).

Refusals (A14.3.5): harness/ladder.py's loop (drive): one identical resubmission; a refused line
only when both attempts end in a Runway FAILED task outcome; any other double failure, a
CANCELLED task among them, stops the run without a line. Resumable from the manifest. After each
new clip its manifest line is read. The first draw runs alone (`run --limit 1`, refused otherwise)
and is watched; its Runway task record is the reference, captured into
analysis/out/a14_route.json beside the verdict before the next submission (at the start of the
next run if the run died in between): its `model` field; otherwise every Runway-reported field
whose name contains "model" or "version", by name; otherwise none, and the in-run check cannot
fire, the route verdict being the only model check. The harness's own version string is never
compared. A later draw whose record reports a captured field, present and different, is a route
mismatch found during the run (A14.3.4), and generation stops for good. A record that lacks a
captured field is a harness fault, not a mismatch: the run stops, and resumes once
`note-absent --cell C --reason ...` records why in a14_route.json.

A run that stops with "left a clip behind" was paid for: `adopt` writes the draw's manifest line from
the file Runway delivered and the task id, with gen_video's checks (settings, tripwire, frame size,
video-packet md5 against the clip left in place, the audio strip), and the draw is never resubmitted.
The first draw needs --record (the route record the run printed on stderr), whose Runway task record
is the reference; a later draw adopted without it lacks the captured fields, a harness fault as above.

Tripwire: `run` refuses until amendment A14 is in the PUBLIC pre-registration
(harness/registration.py); gen_video.py checks the same before any seedance2 call.
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from gen_video import runway_model_version  # noqa: E402
from ladder import LIMIT_HELP, VENV_PY, drive, require_record_doc_unchanged  # noqa: E402
from pack_parser import _prompt_from_file  # noqa: E402
from registration import require_public  # noqa: E402

ENGINE = "seedance2"
TAG = "sd2r"
PACK = HERE / "motion-prompts.md"
PACK_REL = "harness/motion-prompts.md"
CELLS_JSON = "analysis/out/a14_cells.json"
ROUTE_JSON = "analysis/out/a14_route.json"
ROUTE_DOC = "docs/A14-ROUTE.md"
BASE_SEED = 20260812                                   # draw -h<k> is sent BASE_SEED + k (A14.3.2)
RATIO = "1280:720"
DESIGN = (("cu-line-1", "IDLE", (1, 2, 3, 4, 5)), ("cu-line-1", "BURST", (1, 2, 3, 4, 5)),
          ("act-black-3", "IDLE", (1, 2, 3, 4, 5)), ("act-black-3", "BURST", (4, 5, 6, 7, 8)))
MISMATCH_RULE = ("A14.3.4: a route mismatch at the check adds no draw and changes nothing in the batch; it is "
                 "recorded and reported as a finding in its own right, the prediction is read on the five Runway "
                 "draws -h4 to -h8 as on a match, and A5's scout is never pooled with them: the pooled 8-draw "
                 "figure is not computed")
SCOUT = tuple(f"act-black-3_burst_sd2-h{k}" for k in (1, 2, 3))   # A5's fal draws (runs/seedance/)
VERDICTS = ("match", "mismatch")
METRICS_DIR = "runs/metrics-seedance"
MOTION_DIR = "runs/metrics-motion-seedance"


def cell(panel, motion, k):
    return {"cell_id": f"{panel}_{motion.lower()}_{TAG}-h{k}", "panel": panel, "motion": motion,
            "draw": k, "seed": BASE_SEED + k}


def cells():
    return [cell(p, m, k) for p, m, ks in DESIGN for k in ks]


def prompts():
    return {m: _prompt_from_file(str(PACK), m) for m in ("IDLE", "BURST")}


def pack_sha256():
    """The frozen pack's sha256 in its release form. The release writes the benchmark's released name
    where the pack's title line carries its working name, so the file has two byte forms (the prompts,
    as the frozen parser reads them, are one). The cell list records the released form, which is the
    one a reader of the release can check."""
    text = PACK.read_text(encoding="utf-8")
    # In the release each pair below reads as one name twice: the build rewrote this line too, and the
    # pack there already carries the released name, so the function returns the file's own hash.
    for working, released in (("StillDrawn", "StillDrawn"), ("stilldrawn", "stilldrawn"), ("STILLDRAWN", "STILLDRAWN")):
        text = text.replace(working, released)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build(root=ROOT):
    """Write A14's cell list: the 20 Runway draws, and A5's three scout draws apart."""
    root = pathlib.Path(root)
    rec = {"amendment": "A14", "engine": ENGINE, "pack": PACK_REL,
           "pack_sha256": pack_sha256(), "prompts": prompts(),
           "ratio": RATIO, "duration_s": 5, "audio": False,
           "seed_rule": "draw -h<k> is sent 20260812 + k (A14.3.2)", "cells": cells(),
           "mismatch_rule": MISMATCH_RULE,
           "scout": [{"cell_id": c, "route": "fal (A5)", "clip": f"runs/seedance/{c}.mp4"} for c in SCOUT]}
    out = root / CELLS_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def load_cells(root):
    p = pathlib.Path(root) / CELLS_JSON
    if not p.exists():
        raise SystemExit(f"{CELLS_JSON} is missing: run `a14_draws.py build` first")
    return json.loads(p.read_text())


def route(verdict, root=ROOT, today=None):
    """Record the route check's verdict, read by hand from docs/A14-ROUTE.md (A14.3.3). The check comes
    after registration (A14.7), so this refuses until A14 is public."""
    root = pathlib.Path(root)
    require_public("A14", "record A14's route check", hint="The route check comes after registration (A14.7).")
    if verdict not in VERDICTS:
        raise SystemExit(f"--verdict {verdict!r}: one of {', '.join(VERDICTS)}")
    doc = root / ROUTE_DOC
    if not doc.is_file():
        raise SystemExit(f"{ROUTE_DOC} is missing: capture Runway's seedance2 documentation there first "
                         "(A14.3.3), then record the verdict read from it")
    out = root / ROUTE_JSON
    if out.exists():
        rec = json.loads(out.read_text())
        if rec["verdict"] != verdict:
            raise SystemExit(f"{ROUTE_JSON} already records {rec['verdict']!r}: a recorded route verdict is "
                             "never changed")
        return rec
    rec = {"verdict": verdict, "record": ROUTE_DOC, "record_sha256": hashlib.sha256(doc.read_bytes()).hexdigest(),
           "date": (today or _dt.date.today()).isoformat(), "mismatch_rule": MISMATCH_RULE}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def manifest_lines(root):
    m = pathlib.Path(root) / "runs" / "manifest.jsonl"
    return [json.loads(x) for x in m.read_text().splitlines() if x.strip()] if m.exists() else []


CANNOT_FIRE = ("cannot fire: the first draw's task record carries no model field and no field named model or "
               "version; the route verdict (A14.3.3) is the only model check")


def task_reference(line):
    """The reference from the watched first draw's RUNWAY task record (A14.3.4): its `model` field if present;
    otherwise every Runway-reported field whose name contains "model" or "version", by name; otherwise none,
    and the in-run check cannot fire. The harness's own version string (model_version) is never used."""
    task = line.get("task") or {}
    if "model" in task:
        fields, how = {"model": task["model"]}, "the model field"
    else:
        fields = {k: v for k, v in task.items() if "model" in k.lower() or "version" in k.lower()}
        how = "Runway-reported fields named model or version" if fields else CANNOT_FIRE
    return {"captured_from": line["cell_id"], "fields": fields, "check": how}


def other_model(line, ref):
    """The first captured field a manifest line's task record reports, present and different, as text;
    else None. A field the record lacks is not a mismatch (absent_fields)."""
    if not ref or not ref.get("fields"):
        return None
    task = line.get("task") or {}
    for name, value in ref["fields"].items():
        if name in task and task[name] != value:
            return f"{name}={task[name]!r}"
    return None


def absent_fields(line, ref):
    """The captured fields a manifest line's task record lacks (a harness fault, never a mismatch)."""
    task = line.get("task") or {}
    return [name for name in (ref or {}).get("fields", {}) if name not in task]


def write_route(rp, rec):
    tmp = rp.with_name(rp.name + ".tmp")
    tmp.write_text(json.dumps(rec, indent=1) + "\n")
    os.replace(tmp, rp)


def unexplained_absences(root, ids):
    """[(cell id, fields)] of A14 lines lacking a captured field with no note in a14_route.json."""
    rp = pathlib.Path(root) / ROUTE_JSON
    rec = json.loads(rp.read_text()) if rp.exists() else {}
    ref, notes = rec.get("task_reference"), rec.get("absent_field_notes", {})
    return [(x["cell_id"], absent_fields(x, ref)) for x in manifest_lines(root)
            if x.get("cell_id") in ids and not x.get("refused") and x.get("cell_id") != (ref or {}).get("captured_from")
            and absent_fields(x, ref) and x["cell_id"] not in notes]


def note_absent(cell, reason, root=ROOT):
    """Record, in a14_route.json, why a draw's task record lacked a captured field, so the run can resume."""
    rp = pathlib.Path(root) / ROUTE_JSON
    rec = json.loads(rp.read_text())
    line = [x for x in manifest_lines(root) if x.get("cell_id") == cell][-1:]
    if not line or not absent_fields(line[0], rec.get("task_reference")):
        raise SystemExit(f"{cell}: its task record lacks no captured field; there is nothing to note")
    rec.setdefault("absent_field_notes", {})[cell] = reason
    write_route(rp, rec)
    return rec["absent_field_notes"]


HARNESS_FAULT = ("harness fault, not a route mismatch: {what}. Record why in {route} (`a14_draws.py note-absent "
                 "--cell C --reason ...`), then re-run: it resumes; if the absence cannot be explained, the run "
                 "stays stopped and Aaron is told (A14.3.4)")


def first_draw_line(root, ids):
    """The first A14 clip line in the manifest (the first draw made), or None."""
    return next((x for x in manifest_lines(root) if x.get("cell_id") in ids and not x.get("refused")), None)


def ensure_reference(root, ids, today=None):
    """The reference, captured into a14_route.json (written whole, by rename) from the first draw's line if
    not yet there: on the step after that line is written, or, if a run died in between, at the start of
    the next run, before any submission, so a later clip can never become the reference."""
    rp = pathlib.Path(root) / ROUTE_JSON
    rec = json.loads(rp.read_text())
    if "task_reference" in rec:
        return rec["task_reference"]
    first = first_draw_line(root, ids)
    if first is None:
        return None
    rec["task_reference"] = dict(task_reference(first), date=(today or _dt.date.today().isoformat()))
    write_route(rp, rec)
    return rec["task_reference"]


def route_reference(root):
    p = pathlib.Path(root) / ROUTE_JSON
    return json.loads(p.read_text()).get("task_reference") if p.exists() else None


def found_during_run(root, ids):
    """(cell id, what differs) of the first A14 line that differs from the captured reference, or None."""
    ref = route_reference(root)
    for line in manifest_lines(root):
        if line.get("cell_id") in ids and line.get("cell_id") != (ref or {}).get("captured_from") \
                and not line.get("refused") and other_model(line, ref):
            return line["cell_id"], other_model(line, ref)
    return None


def gen_cmd(c, root=ROOT):
    root = pathlib.Path(root)
    return [str(VENV_PY), str(HERE / "gen_video.py"), "--engine", ENGINE,
            "--panel", str(root / "dataset" / "panels" / f"{c['panel']}.png"),
            "--motion", c["motion"], "--cell-id", c["cell_id"], "--seed", str(c["seed"])]


def refusal_line(c, prompt, reason):
    """A refused draw, in the shape of the manifest's refused lines, with the seed both attempts were sent."""
    return {"cell_id": c["cell_id"], "panel": f"dataset/panels/{c['panel']}.png", "motion_class": c["motion"],
            "prompt": prompt, "engine": ENGINE, "model_version": runway_model_version(ENGINE), "seed": c["seed"],
            "duration_s": 5, "ratio": RATIO, "cost_usd": 0.0, "date": _dt.date.today().isoformat(), "out": None,
            "refused": True, "refusal": reason}


def run(root=ROOT, dry_run=False, limit=0, runner=subprocess.run, out=print, err=sys.stderr.write):
    root = pathlib.Path(root)
    if limit < 0:
        raise SystemExit(f"--limit {limit}: must be 0 (no limit) or more")
    rec = load_cells(root)
    texts = rec["prompts"]
    if dry_run:
        for c in rec["cells"]:
            out(f"{c['cell_id']}\tseed {c['seed']}\t{c['motion']}\t{texts[c['motion']]}")
        out(f"{len(rec['cells'])} draws, whatever the route verdict (dry run: nothing submitted)")
        return {"new": 0, "skipped": 0, "refused": 0}
    require_public("A14", "generate A14's seedance2 draws", hint="`a14_draws.py run --dry-run` lists them.")
    rp = root / ROUTE_JSON
    if not rp.exists():
        raise SystemExit(f"REFUSING to generate: {ROUTE_JSON} is missing. The route check (A14.3.3) comes "
                         f"before the first submission: capture {ROUTE_DOC}, then `a14_draws.py route --verdict`.")
    require_record_doc_unchanged(root, ROUTE_DOC, ROUTE_JSON)   # the verdict stands on the capture it was read from
    todo = rec["cells"]                                         # the same 20 on a match and on a mismatch (A14.3.4)
    ids = {c["cell_id"] for c in todo}
    ref = ensure_reference(root, ids)            # a run that died after the first draw: captured here, first
    if ref is None and limit != 1:
        raise SystemExit("REFUSING: the first draw runs alone and is watched (A14.3.4): `a14_draws.py run --limit 1` "
                         "first; its Runway task record becomes the in-run check's reference")
    hit = found_during_run(root, ids)
    if hit:
        raise SystemExit(f"REFUSING to generate: {hit[0]} names {hit[1]!r}, not the captured reference: a route "
                         "mismatch found during the run (A14.3.4). Generation stopped for good; Aaron is told.")
    gaps = unexplained_absences(root, ids)
    if gaps:
        raise SystemExit("REFUSING to generate: " + HARNESS_FAULT.format(
            what="; ".join(f"{cid}'s task record lacks {', '.join(f)}" for cid, f in gaps), route=ROUTE_JSON))

    def check(c):
        ref = ensure_reference(root, ids)        # the first draw's line becomes the reference in this step
        line = [x for x in manifest_lines(root) if x.get("cell_id") == c["cell_id"]][-1:]
        if not line or not ref or c["cell_id"] == ref["captured_from"]:
            return
        missing = absent_fields(line[0], ref)
        if missing and not other_model(line[0], ref):
            raise SystemExit(f"{c['cell_id']}: " + HARNESS_FAULT.format(
                what=f"its task record lacks the captured field {', '.join(missing)}", route=ROUTE_JSON))
        named = other_model(line[0], ref)
        if named:
            raise SystemExit(f"{c['cell_id']}: its task record reports {named}, not the reference {ref['fields']} "
                             f"(captured from {ref['captured_from']}): route mismatch found during the run "
                             "(A14.3.4). Generation stops here; tell Aaron.")

    return drive(todo, ENGINE, root, lambda c: gen_cmd(c, root),
                 lambda c, reason: refusal_line(c, texts[c["motion"]], reason),
                 limit=limit, label="A14", after=check, runner=runner, out=out, err=err,
                 adopt_cmd=("a14_draws.py", ""))


def adopt(cell_id, file, task_id, root=ROOT, record=None):
    """Record a draw whose run stopped with its clip left behind, from the file Runway delivered and the
    task id (gen_video.adopt's checks), so the paid draw is never submitted again. The first draw's Runway
    task record is A14.3.4's reference, so adopting the first draw needs `record` (the `runway route
    record:` line the run printed); a later draw adopted without it lacks the captured fields, which the
    run treats as a harness fault (note-absent)."""
    import gen_video
    root = pathlib.Path(root)
    rec = load_cells(root)
    route_rec = json.loads((root / ROUTE_JSON).read_text()) if (root / ROUTE_JSON).exists() else {}
    todo = rec["cells"]
    c = next((x for x in todo if x["cell_id"] == cell_id), None)
    if c is None:
        raise SystemExit(f"{cell_id} is not one of A14's draws ({CELLS_JSON})")
    if record is None and "task_reference" not in route_rec \
            and first_draw_line(root, {x["cell_id"] for x in todo}) is None:
        raise SystemExit(f"{cell_id} would be A14's first draw, whose Runway task record is the reference (A14.3.4): "
                         "pass --record with the `runway route record:` line the run printed")
    # The arguments are the ones the run was given: parsed from gen_cmd's own command line, so the two cannot drift.
    args = gen_video.build_parser().parse_args(gen_cmd(c, root)[2:])
    return gen_video.adopt(args, file, task_id, record=record)


def metrics(root=ROOT, dry_run=False, runner=subprocess.run, out=print):
    """inkstab (frozen) and motion (A6) for each A14 clip that exists and lacks its JSON."""
    root = pathlib.Path(root)
    rec = load_cells(root)
    done = 0
    for c in rec["cells"]:
        clip = root / "runs" / ENGINE / f"{c['cell_id']}.mp4"
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
            runner(cmd, check=True, timeout=1800)
        done += bool(jobs)
    out(f"A14: metrics {'listed' if dry_run else 'run'} for {done} clips")
    return done


def main(argv=None):
    p = argparse.ArgumentParser(description="A14: seedance2 draws through Runway")
    p.add_argument("mode", choices=["build", "route", "run", "metrics", "note-absent", "adopt"])
    p.add_argument("--file", help="adopt: the file Runway delivered for the cell")
    p.add_argument("--task", help="adopt: the task id the run printed")
    p.add_argument("--record", help="adopt: the `runway route record:` line the run printed (needed for the first draw)")
    p.add_argument("--record-file", help="adopt: a file holding that line (or its JSON), instead of --record")
    p.add_argument("--cell", help="adopt: the draw whose clip was left behind; note-absent: the draw whose task "
                                  "record lacked a captured field")
    p.add_argument("--reason", help="note-absent: why the field was absent")
    p.add_argument("--verdict", choices=VERDICTS, help="route: the verdict read from docs/A14-ROUTE.md")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=0, help=f"run: {LIMIT_HELP}")
    a = p.parse_args(argv)
    if a.mode == "build":
        rec = build()
        print(f"{CELLS_JSON}: {len(rec['cells'])} draws")
    elif a.mode == "route":
        if not a.verdict:
            p.error("route needs --verdict")
        print(json.dumps(route(a.verdict)))
    elif a.mode == "adopt":
        if not (a.cell and a.file and a.task):
            p.error("adopt needs --cell, --file and --task")
        import gen_video
        print(json.dumps(adopt(a.cell, a.file, a.task, record=gen_video.record_from_args(a.record, a.record_file))))
    elif a.mode == "note-absent":
        if not (a.cell and a.reason):
            p.error("note-absent needs --cell and --reason")
        print(json.dumps(note_absent(a.cell, a.reason)))
    elif a.mode == "run":
        run(dry_run=a.dry_run, limit=a.limit)
    else:
        metrics(dry_run=a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
