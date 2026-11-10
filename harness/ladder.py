#!/usr/bin/env python3
"""Motion ladder (amendment A10): cell builder, run driver and metrics driver.

    python harness/ladder.py build                           # writes analysis/out/a10_cells.json
    python harness/ladder.py build --arm kling_4             # writes analysis/out/a15_cells.json (A15)
    python harness/ladder.py run --engine wan22 --dry-run    # prints the 48 cells and their prompts
    python harness/ladder.py run --engine wan22              # generates (refuses until A10 is public)
    python harness/ladder.py run --engine gen4.5 --limit 21  # hosted: stop after 21 new clips
    python harness/ladder.py metrics --engine wan22          # inkstab + motion for each ladder clip
    python harness/ladder.py adopt --engine kling_4 --cell C --file F --task T [--record ...]
                                    # hosted only: records a paid clip a run left behind (gen_video.adopt)

Cells: the 12 panels of analysis/out/a10_panels.json x the four levels of
harness/motion-ladder.md (STILL, LOW, MID, HIGH), on Wan 2.2, LTX-2.3 and Gen-4.5: 48 per
engine, cell id `ladder-<panel>_<level>_<tag>`. Every clip is made by gen_video.py with
`--pack harness/motion-ladder.md`, so its manifest line records prompt_pack. Local engines
run at gen_video's default seed, 20260812, as prereg §5; Gen-4.5 is sent the same seed
(`--seed 20260812`: Runway takes one, and its word is "similar results", so the
seed fixes the request, not the bytes; one draw per cell), and its lines record it. Clips go
to runs/<engine>/, inkstab JSONs to runs/metrics-ladder/, motion JSONs (metrics/motion.py,
A6's definitions, unchanged) to runs/metrics-motion-ladder/. The primary corpus folders are
not touched.

Further engines (ARMS), each under its own amendment and cell file, never in a10_cells.json:
kling_4 (A15, tag `kling4`, `--ratio auto_720p`, no seed; its cells in
analysis/out/a15_cells.json, written by `build --arm kling_4`) and Midjourney (A16, tag `mjv`,
analysis/out/a16_cells.json). `run` on an arm also refuses unless its scout's logged reading
(analysis/out/a15_scout.json or a16_scout.json) is exactly the pass reading A15.5 or A16.7
registers (ARMS[...]["scout_passed"]); a missing file, a failure or any other text is refused.
Midjourney runs by hand (A16.5), so `run` refuses it here even after a pass; `build` and
`metrics` serve it. Refusal lines name the engine's own model_version (HOSTED_MODEL).

Resumable: a cell is skipped when its clip exists AND the manifest has its (non-refused)
line, or when its refusal is already in the manifest. A clip with no manifest line (an
orphan, or a half-written download) stops the run and is named. On a hosted arm it was
paid for: the message names `adopt --cell <id> --file <delivered path> --task <task id>`, never
a move-aside and re-run (that would submit the cell again). A manifest clip line whose clip
file is missing also stops the run (an incomplete copy, or a clip moved aside): restore the
file; the cell is never regenerated under the same id. A cell that fails is resubmitted once
(prereg §5), unless the failed attempt left a clip behind, which stops the run (same remedy). gen_video's stderr is captured and echoed. A hosted
cell is written to the manifest as refused only when BOTH attempts ended in a FAILED task
outcome from Runway (the `task <id> FAILED: ...` line of harness/runway_task.py, or of the older
client, recorded verbatim as the refusal); any other double failure (not signed in to op, an API error, a network drop, a
cell lock held by another driver, a CANCELLED task, which is a client action) stops the run without a manifest line, so
a re-run tries the cell again. A local cell that fails twice stops the run: that is a
harness fault, not a refusal.

Tripwire: `run` refuses until amendment A10 is in the PUBLIC pre-registration
(harness/registration.py), on an arm also until its own amendment is (kling_4: A15), and on a
local engine also until STILLDRAWN_HW names the machine,
so a resume on other hardware cannot mix machines unrecorded. `--dry-run` needs neither and
calls nothing. `metrics` reads only clips, which cannot exist before `run`.
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from gen_video import runway_model_version  # noqa: E402
from pack_parser import _prompt_from_file  # noqa: E402
from registration import require_public  # noqa: E402

VENV_PY = pathlib.Path(__import__("os").environ.get("STILLDRAWN_PY", __import__("sys").executable))
if not VENV_PY.exists():   # pod execution (A2): system python has the deps
    VENV_PY = pathlib.Path(sys.executable)

PACK = HERE / "motion-ladder.md"
PACK_REL = "harness/motion-ladder.md"
PANELS_JSON = "analysis/out/a10_panels.json"
CELLS_JSON = "analysis/out/a10_cells.json"
LEVELS = ("STILL", "LOW", "MID", "HIGH")
A10_TAG = {"wan22": "wan22", "ltx23": "ltx23", "gen4.5": "gen45"}     # A10's three engines
# Further engines in A10's motion test, each under its own amendment and its own cell file.
# `ratio` and `seed` are what each arm's frozen cell file records: Kling's are fixed (A15.3.2,
# A15.3.3); Midjourney's are left to A16.3.2 (HD from the start frame, no ratio requested) and
# A16.4.1 (the seed is found out after registration), so the file points there (ruled 8 Nov 2026).
# `scout` is where the scout's reading is logged ({"reading": ...}, written by
# analysis/scout_rule.py beside its FINDINGS entry); `scout_passed` is the exact pass reading
# A15.5 (reading 4) and A16.7 register. An arm makes no clip without that exact reading.
ARMS = {"kling_4": {"tag": "kling4", "amendment": "A15", "cells": "analysis/out/a15_cells.json",
                    "ratio": "auto_720p", "seed": None, "scout": "analysis/out/a15_scout.json",
                    "scout_rule": "A15.5", "scout_metrics": "analysis/out/a15_scout_metrics.json",
                    "scout_passed": "scout passed: Kling joins A10's motion test as a further engine"},
        "midjourney": {"tag": "mjv", "amendment": "A16", "cells": "analysis/out/a16_cells.json",
                       "ratio": "per A16.3.2", "seed": "per A16.4.1", "scout": "analysis/out/a16_scout.json",
                       "scout_rule": "A16.7", "setup": "analysis/out/a16_setup.json",   # A16.4's answers
                       "scout_metrics": "analysis/out/a16_scout_metrics.json",
                       "scout_passed": "scout passed: Midjourney joins A10's motion test as a further engine"}}
# A15.5's failure readings (A16.7 takes them verbatim), as logged: R of N cells refused; the
# unmeasurable cells' ids; B of 3 BURST draws above the floor, which fails only below two.
SCOUT_FAILED = (re.compile(r"scout failed: refused \(\d+ of \d+ cells\)"),
                re.compile(r"scout failed: not measurable \(.+\)"),
                re.compile(r"scout failed: does not move on request \((0|1) of 3 BURST draws above the floor\)"))
ENGINE_TAG = {**A10_TAG, **{e: arm["tag"] for e, arm in ARMS.items()}}
LOCAL = {"wan22", "ltx23"}
RATIO = "1280:720"
RATIOS = {"kling_4": ARMS["kling_4"]["ratio"]}   # sent to gen_video: kling_4 keeps the panel's framing
SEED_LOCAL = 20260812
SEED_HOSTED = {"gen4.5": 20260812}           # §5's seed, sent to Runway (ruled 7 Nov 2026); kling_4 takes none
METRICS_DIR = "runs/metrics-ladder"
MOTION_DIR = "runs/metrics-motion-ladder"
BY_HAND = "by hand"
HOSTED_MODEL = {"gen4.5": runway_model_version("gen4.5"), "kling_4": runway_model_version("kling_4"),
                "midjourney": BY_HAND}       # A16: no API; its job log writes its lines
# The Runway clients' task-level outcome (`task <id> <STATUS>: <record>`) with status FAILED:
# the only failure that may be recorded as a refusal. CANCELLED (a client action), ERROR, a
# timeout and the API-error lines do not match.
TASK_OUTCOME = re.compile(r"^task \S+ FAILED: .*$", re.M)
# One help text for `--limit` in every driver (the count includes a refused cell: it was a live call).
LIMIT_HELP = "stop after this many cells, delivered or refused (a refused cell counts)"


def require_record_doc_unchanged(root, doc_rel, verdict_rel):
    """Refuse when the record doc's current sha256 differs from the `record_sha256` its verdict file holds
    (analysis/out/a14_route.json, a15_route.json, a16_setup.json): the verdict was read from the doc as it
    was then. A missing doc, or a verdict file without the hash, is refused the same way."""
    root = pathlib.Path(root)
    doc = root / doc_rel
    recorded = json.loads((root / verdict_rel).read_text()).get("record_sha256")
    now = hashlib.sha256(doc.read_bytes()).hexdigest() if doc.is_file() else None
    if now is None or recorded is None or now != recorded:
        raise SystemExit(f"REFUSING: {doc_rel} has changed since its verdict was recorded (sha256 now "
                         f"{(now or 'missing')[:12]}, recorded {(recorded or 'none')[:12]} in {verdict_rel}): "
                         "the verdict stands on the document it was read from; nothing is submitted. Tell Aaron.")


def load_panels(root=ROOT):
    panels = json.loads((pathlib.Path(root) / PANELS_JSON).read_text())["panels"]
    if len(panels) != 12 or len(set(panels)) != 12:
        raise SystemExit(f"{PANELS_JSON}: expected 12 distinct panels, got {len(panels)}")
    return panels


def prompts(pack=PACK):
    return {lv: _prompt_from_file(str(pack), lv) for lv in LEVELS}


def ratio(engine):
    return RATIOS.get(engine, RATIO)


def scout_failed(reading):
    """True when `reading` is one of A15.5's failure readings, in full."""
    return any(rx.fullmatch(reading) for rx in SCOUT_FAILED)


def require_scout_pass(engine, root=ROOT):
    """Refuse an arm's run unless its scout's logged reading is exactly its pass reading."""
    arm = ARMS[engine]
    path = pathlib.Path(root) / arm["scout"]
    action = f"REFUSING to generate ladder clips on {engine}"
    if not path.is_file():
        raise SystemExit(f"{action}: {arm['scout']} is missing, so no scout pass is logged; the arm runs "
                         f"only after the scout reads {arm['scout_passed']!r} ({arm['scout_rule']}).")
    try:
        reading = json.loads(path.read_text(encoding="utf-8")).get("reading")
    except (ValueError, AttributeError):
        reading = None
    if reading != arm["scout_passed"]:
        raise SystemExit(f"{action}: the scout's logged reading in {arm['scout']} is {reading!r}, not "
                         f"{arm['scout_passed']!r} ({arm['scout_rule']}); the arm runs only after that exact pass.")
    return path


def hosted_model(engine):
    """The model_version a hosted engine's refusal line records; Midjourney is refused here."""
    mv = HOSTED_MODEL[engine]
    if mv == BY_HAND:
        raise SystemExit(f"REFUSING {engine} here: A16 runs Midjourney by hand, through its job log "
                         "(A16.5), not through this driver; no clip or line is written here")
    return mv


def cells(engine, panels):
    tag = ENGINE_TAG[engine]
    return [{"cell_id": f"ladder-{p}_{lv.lower()}_{tag}", "panel": p, "level": lv, "engine": engine}
            for p in panels for lv in LEVELS]


def build(root=ROOT, arm=None):
    """Write A10's cell list (its three engines) with the resolved prompts and the pack's hash;
    with `arm`, that engine's 48 cells to its own file instead (A15, A16), a10_cells.json
    untouched."""
    root = pathlib.Path(root)
    panels = load_panels(root)
    head = {"pack": PACK_REL, "pack_sha256": hashlib.sha256(PACK.read_bytes()).hexdigest(),
            "panels_from": PANELS_JSON,
            "panels_sha256": hashlib.sha256((root / PANELS_JSON).read_bytes()).hexdigest(),
            "panels": panels}
    if arm:
        rec = {"amendment": ARMS[arm]["amendment"], **head, "ratio": ARMS[arm]["ratio"],
               "seed": ARMS[arm]["seed"], "prompts": prompts(),
               "cells": {arm: [c["cell_id"] for c in cells(arm, panels)]}}
        out = root / ARMS[arm]["cells"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rec, indent=1) + "\n")
        return rec
    rec = {"amendment": "A10", **head, "ratio": RATIO,
           "seed_local_engines": SEED_LOCAL, "seed_hosted": SEED_HOSTED["gen4.5"], "prompts": prompts(),
           "cells": {e: [c["cell_id"] for c in cells(e, panels)] for e in A10_TAG}}
    out = root / CELLS_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def manifest_cells(root):
    """(made, refused): cell ids with a clip line in runs/manifest.jsonl, and with a refused line."""
    m = pathlib.Path(root) / "runs" / "manifest.jsonl"
    made, refused = set(), set()
    if not m.exists():
        return made, refused
    for line in m.read_text().splitlines():
        if line.strip():
            rec = json.loads(line)
            (refused if rec.get("refused") else made).add(rec["cell_id"])
    return made, refused


def task_outcome(stderr):
    """The Runway client's last task-level FAILED outcome line in `stderr`, or None."""
    hits = TASK_OUTCOME.findall(stderr or "")
    return hits[-1] if hits else None


def refusal_line(cell, prompt, reason):
    """A refused hosted cell, in the shape of the manifest's existing refused lines, under its
    own engine's model_version, with the seed both attempts were sent (None on kling_4)."""
    e = cell["engine"]
    return {"cell_id": cell["cell_id"], "panel": f"dataset/panels/{cell['panel']}.png",
            "motion_class": cell["level"], "prompt": prompt, "engine": e,
            "model_version": hosted_model(e), "seed": SEED_HOSTED.get(e), "duration_s": 5, "ratio": ratio(e),
            "cost_usd": 0.0, "date": _dt.date.today().isoformat(), "out": None,
            "refused": True, "refusal": reason, "prompt_pack": PACK_REL}


def gen_cmd(cell, root=ROOT):
    root = pathlib.Path(root)
    cmd = [str(VENV_PY), str(HERE / "gen_video.py"), "--engine", cell["engine"],
           "--panel", str(root / "dataset" / "panels" / f"{cell['panel']}.png"),
           "--motion", cell["level"], "--cell-id", cell["cell_id"], "--ratio", ratio(cell["engine"]),
           "--pack", str(PACK)]
    if cell["engine"] in SEED_HOSTED:
        cmd += ["--seed", str(SEED_HOSTED[cell["engine"]])]
    return cmd


def run(engine, root=ROOT, dry_run=False, limit=0, runner=subprocess.run, out=print,
        err=sys.stderr.write):
    root = pathlib.Path(root)
    if limit < 0:
        raise SystemExit(f"--limit {limit}: must be 0 (no limit) or more")
    texts = prompts()
    todo = cells(engine, load_panels(root))
    if dry_run:
        for c in todo:
            out(f"{c['cell_id']}\t{c['level']}\t{texts[c['level']]}")
        out(f"{engine}: {len(todo)} cells (dry run: nothing submitted, no registration check)")
        return {"new": 0, "skipped": 0, "refused": 0}
    require_public("A10", f"generate ladder clips on {engine}",
                   hint="`ladder.py run --dry-run` lists the cells without it.")
    if engine in ARMS:
        require_public(ARMS[engine]["amendment"], f"generate ladder clips on {engine}",
                       hint="`ladder.py run --dry-run` lists the cells without it.")
        require_scout_pass(engine, root)   # an arm clip only after its scout's exact logged pass
        hosted_model(engine)               # Midjourney runs by hand: refused here, before anything runs
    if engine in LOCAL and not os.environ.get("STILLDRAWN_HW"):
        raise SystemExit(f"REFUSING to generate ladder clips on {engine}: set "
                         "STILLDRAWN_HW to the machine's name, so every manifest line of "
                         "the ladder records it (gen_video.py model_version)")
    return drive(todo, engine, root, lambda c: gen_cmd(c, root),
                 lambda c, reason: refusal_line(c, texts[c["level"]], reason),
                 local=engine in LOCAL, limit=limit, label="A10", runner=runner, out=out, err=err,
                 adopt_cmd=("ladder.py", f" --engine {engine}") if engine in ARMS else None)


def stop_with_clip(clip, cell_id, what, adopt_cmd, local):
    """Stop the run on a clip left at a cell's path. A local clip is the harness's own: inspect it and move it
    aside. A hosted one was paid for, and moving it aside to re-run would submit the cell again: the
    remedy named is the driver's `adopt` (gen_video.adopt), or, where the driver cannot adopt, Aaron."""
    if local:
        raise SystemExit(f"{clip}: {what}. Inspect it and move it aside by hand.")
    if adopt_cmd:
        script, extra = adopt_cmd
        raise SystemExit(f"{clip}: {what}. It was paid for: do not move it aside and re-run (that submits the "
                         f"cell again). Inspect it, then record the file Runway delivered: `{script} adopt --cell "
                         f"{cell_id} --file <delivered path> --task <task id> [--record <line> | --record-file "
                         f"<path>]{extra}` (gen_video.adopt's checks); nothing was submitted for it.")
    raise SystemExit(f"{clip}: {what}. It was paid for and this driver cannot adopt it: do not move it aside and "
                     "re-run (that submits the cell again); tell Aaron.")


def drive(todo, engine, root, make_cmd, make_refusal, *, local=False, limit=0, label="A10", after=None,
          adopt_cmd=None, runner=subprocess.run, out=print, err=sys.stderr.write):
    """§5's run loop as A10.3.4 registers it, for any driver (A10's ladder, A14's draws, A15's scout).

    Over `todo` (dicts with "cell_id"), clips in runs/<engine>/: skip a cell whose clip exists with
    its (non-refused) manifest line, or whose refusal is recorded; stop on an orphan clip or on a
    clip line without its file; run make_cmd(cell), resubmitting once, identically, on failure,
    unless the failed attempt left a clip behind (stop). Both attempts FAILED at Runway (the task
    outcome line) is a refusal: make_refusal(cell, reason) is appended to the manifest. Any other
    double failure stops the run without a line (a local engine's always). `after(cell)` runs
    after each new clip and may stop the run. `limit` counts cells, delivered or refused (a refusal
    was a live call), so a refused first cell under `--limit 1` ends the run. `adopt_cmd` is the driver's
    adopt command as (script, extra flags), e.g. ("ladder.py", " --engine kling_4"), named when a paid clip is
    left behind.
    Returns {"new", "skipped", "refused"}."""
    root = pathlib.Path(root)
    made, refused = manifest_cells(root)
    new = skipped = n_refused = 0
    for c in todo:
        clip = root / "runs" / engine / f"{c['cell_id']}.mp4"
        if c["cell_id"] in refused or (clip.exists() and c["cell_id"] in made):
            skipped += 1
            continue
        if clip.exists():
            stop_with_clip(clip, c["cell_id"], f"the clip exists but the manifest has no line for "
                           f"{c['cell_id']} (an orphan or a half-written download)", adopt_cmd, local)
        if c["cell_id"] in made:
            raise SystemExit(f"{clip}: the manifest has a clip line for {c['cell_id']} but the file "
                             "is missing (an incomplete rsync, or moved aside?). Restore it; not "
                             "regenerating.")
        out(f"[{label}] {c['cell_id']}")
        errors, outcomes = [], []
        for attempt in (1, 2):
            try:
                res = runner(make_cmd(c), check=True, stderr=subprocess.PIPE, text=True)
                if getattr(res, "stderr", None):
                    err(res.stderr)
                break
            except subprocess.CalledProcessError as e:
                if e.stderr:
                    err(e.stderr)
                outcomes.append(task_outcome(e.stderr))
                errors.append(f"attempt {attempt}: exit {e.returncode}")
                if clip.exists():
                    stop_with_clip(clip, c["cell_id"], f"attempt {attempt} failed ({errors[-1]}) but left a clip "
                                   "behind (a partial download?); not resubmitting and not recording a refusal",
                           adopt_cmd, local)
                out(f"  failed ({errors[-1]})" + ("; resubmitting once (prereg §5)" if attempt == 1 else ""))
        else:
            if local:
                raise SystemExit(f"{c['cell_id']}: the local engine failed twice ({'; '.join(errors)}). "
                                 "That is a harness fault, not a refusal: fix it and re-run (it resumes).")
            if not all(outcomes):
                raise SystemExit(f"{c['cell_id']}: failed twice ({'; '.join(errors)}) without a "
                                 "task-level outcome from Runway on both attempts (op sign-in, API "
                                 "error, network, or a held cell lock?). Not recorded as refused: "
                                 "fix it and re-run (it resumes).")
            line = make_refusal(c, outcomes[-1])
            with (root / "runs" / "manifest.jsonl").open("a") as f:
                f.write(json.dumps(line) + "\n")
            n_refused += 1
            if limit and new + n_refused >= limit:      # a refusal was a live call: it counts toward --limit
                out(f"--limit {limit} reached")
                break
            continue
        new += 1
        if after:
            after(c)
        if limit and new + n_refused >= limit:
            out(f"--limit {limit} reached")
            break
    remaining = len(todo) - skipped - new - n_refused
    out(f"{engine}: {new} new, {skipped} skipped, {n_refused} refused, {remaining} remaining")
    return {"new": new, "skipped": skipped, "refused": n_refused}


def adopt(engine, cell_id, file, task_id, root=ROOT, record=None):
    """Record a hosted arm's ladder cell whose run stopped with its clip left behind, from the file Runway
    delivered and the task id (gen_video.adopt's checks), under the gates `run` applies: A10 and the arm's
    amendment public, and the arm's exact scout pass logged. A10's own engines (gen4.5, the local two) are
    not adopted here: the local cells are regenerated, and gen4.5's ladder was not built to take a clip back."""
    import gen_video
    root = pathlib.Path(root)
    if engine == "midjourney":
        raise SystemExit("adopt: Midjourney's ladder cells are recorded by hand (harness/mj_log.py), not adopted")
    if engine not in ARMS:
        raise SystemExit(f"adopt: {engine} is not an adoptable ladder arm (only "
                         f"{', '.join(sorted(a for a in ARMS if a != 'midjourney'))}; local cells are regenerated)")
    action = f"adopt a ladder clip on {engine}"
    require_public("A10", action)
    require_public(ARMS[engine]["amendment"], action)
    require_scout_pass(engine, root)
    c = next((x for x in cells(engine, load_panels(root)) if x["cell_id"] == cell_id), None)
    if c is None:
        raise SystemExit(f"{cell_id} is not a {engine} ladder cell")
    # The arguments are the ones the run was given: parsed from gen_cmd's own command line, so the two cannot drift.
    args = gen_video.build_parser().parse_args(gen_cmd(c, root)[2:])
    return gen_video.adopt(args, file, task_id, record=record)


def metrics(engine, root=ROOT, dry_run=False, runner=subprocess.run, out=print):
    """inkstab (frozen) and motion (A6) for each ladder clip that exists and lacks its JSON."""
    root = pathlib.Path(root)
    done = 0
    for c in cells(engine, load_panels(root)):
        clip = root / "runs" / engine / f"{c['cell_id']}.mp4"
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
    out(f"{engine}: metrics {'listed' if dry_run else 'run'} for {done} clips")
    return done


def main(argv=None):
    p = argparse.ArgumentParser(description="A10 motion ladder")
    p.add_argument("mode", choices=["build", "run", "metrics", "adopt"])
    p.add_argument("--cell", help="adopt: the cell whose clip was left behind")
    p.add_argument("--file", help="adopt: the file Runway delivered for it")
    p.add_argument("--task", help="adopt: the task id the run printed")
    p.add_argument("--record", help="adopt: the `runway route record:` line the run printed, if kept")
    p.add_argument("--record-file", help="adopt: a file holding that line (or its JSON), instead of --record")
    p.add_argument("--engine", choices=sorted(ENGINE_TAG))
    p.add_argument("--arm", choices=sorted(ARMS), help="build: write this engine's own cell file")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=0, help=f"run: {LIMIT_HELP}")
    a = p.parse_args(argv)
    if a.limit < 0:
        p.error("--limit must be 0 (no limit) or more")
    if a.mode == "build":
        rec = build(arm=a.arm)
        print(f"{ARMS[a.arm]['cells'] if a.arm else CELLS_JSON}: {sum(len(v) for v in rec['cells'].values())} "
              f"cells, {len(rec['cells'])} engines, pack sha256 {rec['pack_sha256']}")
        return 0
    if not a.engine:
        p.error(f"{a.mode} needs --engine")
    if a.mode == "run":
        run(a.engine, dry_run=a.dry_run, limit=a.limit)
    elif a.mode == "adopt":
        if not (a.cell and a.file and a.task):
            p.error("adopt needs --cell, --file and --task")
        import gen_video
        print(json.dumps(adopt(a.engine, a.cell, a.file, a.task,
                               record=gen_video.record_from_args(a.record, a.record_file))))
    else:
        metrics(a.engine, dry_run=a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
