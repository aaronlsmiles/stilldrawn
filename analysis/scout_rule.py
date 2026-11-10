#!/usr/bin/env python3
"""The scout's decision rule (A15.5; A16.7 applies it verbatim to Midjourney), and its inputs.

    python analysis/scout_rule.py --floor                 # writes analysis/out/scout_floor.json (before registration)
    python analysis/scout_rule.py --cells                 # writes analysis/out/scout_cells.json (before registration)
    python analysis/scout_rule.py --arm kling_4           # reads the rule once (refuses until A15 is public)
    python analysis/scout_rule.py --arm midjourney        # the same for A16 (refuses until A16 is public)
    python analysis/scout_rule.py --arm kling_4 --fixtures DIR   # a synthetic tree (tests); no registration check

The motion floor (A15.5, 0.00160571): the median `headline_median_norm` over the frozen corpus's
primary IDLE cells of all five engines, from the released runs/metrics-motion/ files: --floor reads
the public release tree (--tree; default the stilldrawn folder beside this repository) and refuses
a private one, so the file carries public ids and is the same bytes in the release. A primary cell is one with a runs/metrics/ file; FLINT, -r2 repeats and A4's -h draws
(not among the five engine tags), A3's ground variants and A5's Seedance cells are left out, as
in A10.1. `--floor` writes the value with every cell it used.

The cells (A15.4, A16.6): A5's composition, three FLINT pairs (`flint-<first>--<last>_<tag>`) and
three BURST draws of `act-black-3` (`act-black-3_burst_<tag>-h1` to `-h3`), for Kling (tag
kling4) and Midjourney (tag mjv).

The rule, read once, when every scout cell has a clip (with its manifest line) or a refused line
in runs/manifest.jsonl, after the metrics step (harness/scout.py metrics: inkstab JSONs in
runs/metrics-scout/, motion JSONs in runs/metrics-motion-scout/); a cell with neither clip nor
refused line means nothing is read yet. The metrics step's record
(analysis/out/a15_scout_metrics.json, a16_scout_metrics.json; harness/scout.py metrics) must name
every delivered clip, or the rule refuses ("metrics step not complete") and writes nothing. A
tool failure is recorded with its reason; the clip reads "not measurable" (reading 2) only after
one confirming re-run of the metrics step has failed on it again (until then: "metrics step not
complete: <n> clips await a confirming re-run"), and the recorded reasons are printed beside the
reading. A non-finite value in a metric file also reads "not measurable". A metric file deleted
or changed since the record is refused. Readings, in this order, the registered
strings (harness/ladder.py ARMS and SCOUT_FAILED, the same the arm's run gate and
analysis/a10_ladder.py check):
  1. "scout failed: refused (R of N cells)" if two or more cells are refused;
  2. "scout failed: not measurable (<cell ids>)" if a clip not refused lacks a finite mean chamfer
     vs frame 0 or a finite motion value (a missing metric file included); the ids joined by ", ";
  3. "scout failed: does not move on request (B of 3 BURST draws above the floor)" if fewer than
     two BURST draws have realised motion above the floor (a refused one counts as not above);
  4. otherwise the arm's pass reading.
On Midjourney, if A16.4.3 found no end-frame conditioning, the FLINT cells are n/a and the scout
is its three BURST draws (N = 3); A16.4's answers are read from analysis/out/a16_setup.json, and
nothing is read until it exists. The reading is written, with every input, the floor and each
cell's seed, to analysis/out/a15_scout.json (a16_scout.json), and its FINDINGS line is printed.
A written reading is final: the rule is never read again (A15.7.1). `--rerun` (the release build's
re-run) re-derives a shipped reading in the release tree, with its recorded date, and is refused
in a private tree. The metrics record's sha256s are of each file's release form (harness/scout.py
release_sha256), so the same record holds in both trees.
"""
import argparse
import datetime as _dt
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "harness"))
from ladder import ARMS, scout_failed  # noqa: E402
from scout import release_sha256  # noqa: E402
from registration import require_public  # noqa: E402

FLOOR_JSON = "analysis/out/scout_floor.json"
CELLS_JSON = "analysis/out/scout_cells.json"
FIVE = ("gen4t", "gen45", "h3", "wan22", "ltx23")
FLINT_PAIRS = (("cu-line-2", "cu-line-1"), ("act-line-2", "act-tone-3"), ("est-line-2", "est-black-3"))
BURST_PANEL = "act-black-3"
CLIP_DIR = {"kling_4": "kling_4", "midjourney": "midjourney"}
INK_DIR = "runs/metrics-scout"
MOTION_DIR = "runs/metrics-motion-scout"
PRIVATE_MARKER = Path("analysis") / "adherence" / "private-terms.txt"


def num(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def private_tree(root):
    """True when the folder, or one above it, carries the private repository's marker."""
    root = Path(root).resolve()
    return any((d / PRIVATE_MARKER).is_file() for d in (root, *root.parents))


def public_tree():
    """The public release tree beside this repository (the folder the release build refreshes); from a
    worktree, the one beside the main checkout (git's common dir), as tools/p69_safe.py finds it."""
    beside = ROOT.parent / "stilldrawn"
    if beside.is_dir():
        return beside
    try:
        common = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return beside
    return Path(common).resolve().parent.parent / "stilldrawn"


def build_floor(root=None, out_root=None):
    """The motion floor (A15.5): the median realised motion of the frozen corpus's primary IDLE cells,
    from the RELEASED files: `root` is the public tree (default: the one beside this repository), never
    a private one, so the file carries public ids and is the same bytes in both forms. Written to
    out_root (default: this repository) / analysis/out/scout_floor.json."""
    root = Path(root) if root is not None else public_tree()
    if private_tree(root):
        raise SystemExit(f"REFUSING --floor from {root}: a private tree. A15.5 computes the floor from the released "
                         "runs/metrics-motion files: point --tree at the public release tree")
    primary = {p.stem for p in (root / "runs" / "metrics").glob("*.json")}
    cells = {}
    for p in sorted((root / "runs" / "metrics-motion").glob("*_idle_*.json")):
        parts = p.stem.rsplit("_", 2)
        if len(parts) != 3 or parts[1] != "idle" or parts[2] not in FIVE or p.stem.startswith("flint-"):
            continue
        if p.stem not in primary:
            continue
        v = num(json.loads(p.read_text())["motion"]["headline_median_norm"])
        if v is not None:
            cells[p.stem] = v
    if not cells:
        raise SystemExit("no primary IDLE motion files found: the floor cannot be computed")
    rec = {"rule": "A15.5: median headline_median_norm over the frozen corpus's primary IDLE cells of the five "
                   "engines (runs/metrics-motion/ with a runs/metrics/ file; FLINT, -r2 and -h draws excluded)",
           "floor": float(np.median(list(cells.values()))), "n": len(cells),
           "engines": {t: sum(1 for c in cells if c.endswith(f"_{t}")) for t in sorted(FIVE)}, "cells": cells}
    out = Path(out_root or ROOT) / FLOOR_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def build_cells(root=ROOT):
    """A5's composition for each arm (A15.4, A16.6)."""
    rec = {"rule": "A5's composition (A15.4, A16.6): three FLINT pairs and three BURST draws of act-black-3"}
    for arm in ("kling_4", "midjourney"):
        tag = ARMS[arm]["tag"]
        rec[arm] = ([{"cell_id": f"flint-{a}--{b}_{tag}", "motion": "FLINT", "panel": a, "last_panel": b}
                     for a, b in FLINT_PAIRS]
                    + [{"cell_id": f"{BURST_PANEL}_burst_{tag}-h{k}", "motion": "BURST", "panel": BURST_PANEL,
                        "draw": k} for k in (1, 2, 3)])
    out = Path(root) / CELLS_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def scout_cells(arm, root):
    """The arm's scout cells; Midjourney's FLINT cells drop out when A16.4.3 found no end frame."""
    root = Path(root)
    p = root / CELLS_JSON
    if not p.exists():
        raise SystemExit(f"{CELLS_JSON} is missing: run `scout_rule.py --cells` first")
    cells = json.loads(p.read_text())[arm]
    if arm == "midjourney":
        sp = root / ARMS[arm]["setup"]
        if not sp.exists():
            raise SystemExit(f"{ARMS[arm]['setup']} is missing: A16.4's answers (the end frame among them, "
                             "A16.4.3) are recorded before the scout, and the rule is not read without them")
        if json.loads(sp.read_text()).get("end_frame") is False:
            cells = [c for c in cells if c["motion"] == "BURST"]
    return cells


def manifest_lines(root):
    m = Path(root) / "runs" / "manifest.jsonl"
    out = {}
    if m.exists():
        for x in m.read_text().splitlines():
            if x.strip():
                r = json.loads(x)
                out[r.get("cell_id")] = r                  # the last line of a cell wins
    return out


def check_metrics_record(arm, root, delivered):
    """Refuse unless the metrics step's record names every delivered clip, its files are as recorded
    (none deleted or changed since), and every clip a tool failed on has had its confirming re-run.
    Returns the record's cells."""
    if not delivered:
        return {}
    name = ARMS[arm]["scout_metrics"]
    p = Path(root) / name
    if not p.exists():
        raise SystemExit(f"metrics step not complete: {name} is missing (harness/scout.py metrics --engine {arm} "
                         "writes it); nothing is read")
    rec = json.loads(p.read_text())["cells"]
    absent = [cid for cid in delivered if cid not in rec]
    if absent:
        raise SystemExit(f"metrics step not complete: {', '.join(absent)} delivered but not in {name}; run the "
                         "metrics step again; nothing is read")
    awaiting = []
    for cid in delivered:
        for kind in ("inkstab", "motion"):
            e = rec[cid][kind]
            f = Path(root) / e["path"]
            if e["sha256"] is not None and not f.exists():
                raise SystemExit(f"{cid}: its {kind} file was deleted since the metrics step ({name}); restore it or "
                                 "run the metrics step again; nothing is read")
            if f.exists() and (e["sha256"] is None or release_sha256(f, root) != e["sha256"]):
                raise SystemExit(f"{cid}: its {kind} file has changed since the metrics step ({name}); run the "
                                 "metrics step again; nothing is read")
        if any(rec[cid][k]["sha256"] is None for k in ("inkstab", "motion")) and not rec[cid].get("retried"):
            awaiting.append(cid)
    if awaiting:
        raise SystemExit(f"metrics step not complete: {len(awaiting)} clips await a confirming re-run "
                         f"({', '.join(awaiting)}); run the metrics step again; nothing is read")
    return rec


def decide(cells, inputs, floor, passed):
    """The registered reading for one scout, in A15.5's order."""
    refused = [c["cell_id"] for c in cells if inputs[c["cell_id"]]["refused"]]
    if len(refused) >= 2:
        return f"scout failed: refused ({len(refused)} of {len(cells)} cells)"
    unmeasured = [c["cell_id"] for c in cells if not inputs[c["cell_id"]]["refused"]
                  and (inputs[c["cell_id"]]["chamfer"] is None or inputs[c["cell_id"]]["motion_value"] is None)]
    if unmeasured:
        return f"scout failed: not measurable ({', '.join(unmeasured)})"
    above = sum(1 for c in cells if c["motion"] == "BURST" and inputs[c["cell_id"]]["above_floor"])
    if above < 2:
        return f"scout failed: does not move on request ({above} of 3 BURST draws above the floor)"
    return passed


def read_scout(arm, root=ROOT, today=None, out=print, rerun=False):
    root = Path(root)
    arm_cfg = ARMS[arm]
    target = root / arm_cfg["scout"]
    if target.exists() and not rerun:
        raise SystemExit(f"{arm_cfg['scout']} exists: the scout's reading is final (A15.7.1); it is never read again")
    fp = root / FLOOR_JSON
    if not fp.exists():
        raise SystemExit(f"{FLOOR_JSON} is missing: the floor is computed before registration (scout_rule.py --floor)")
    floor = json.loads(fp.read_text())["floor"]
    cells = scout_cells(arm, root)
    lines = manifest_lines(root)
    inputs, waiting = {}, []
    for c in cells:
        cid = c["cell_id"]
        line = lines.get(cid)
        if line and line.get("refused"):
            inputs[cid] = {"motion": c["motion"], "refused": True, "chamfer": None, "motion_value": None,
                           "above_floor": False if c["motion"] == "BURST" else None, "seed": line.get("seed")}
            continue
        clip = root / "runs" / CLIP_DIR[arm] / f"{cid}.mp4"
        ink, mot = root / INK_DIR / f"{cid}.json", root / MOTION_DIR / f"{cid}.json"
        if not line or not clip.exists():
            waiting.append(cid)                      # no clip and no refused line yet: not read yet
            continue
        # A delivered clip is past the metrics step: a missing metric file means the frozen tools gave
        # no value, and the clip reads "not measurable" (reading 2), as ruled before registration.
        m = json.loads(ink.read_text()).get("metrics", {}) if ink.exists() else {}
        chamfer = num(m.get("line_drift", {}).get("vs_frame0", {}).get("chamfer_px", {}).get("mean"))
        motion = num(json.loads(mot.read_text()).get("motion", {}).get("headline_median_norm")) if mot.exists() else None
        inputs[cid] = {"motion": c["motion"], "refused": False, "chamfer": chamfer, "motion_value": motion,
                       "above_floor": (motion > floor) if (c["motion"] == "BURST" and motion is not None) else
                       (False if c["motion"] == "BURST" else None), "seed": line.get("seed"),
                       "metrics_file_missing": not (ink.exists() and mot.exists())}
    if waiting:
        raise SystemExit(f"the rule is not read yet: {', '.join(waiting)} lack a clip with its manifest line or a "
                         "refused line (A15.5)")
    recorded = check_metrics_record(arm, root, [cid for cid, v in inputs.items() if not v["refused"]])
    for cid, v in inputs.items():
        if not v["refused"]:
            v["failures"] = recorded.get(cid, {}).get("failures", [])
    reading = decide(cells, inputs, floor, arm_cfg["scout_passed"])
    if not (reading == arm_cfg["scout_passed"] or scout_failed(reading)):
        raise SystemExit(f"internal: {reading!r} is not a registered reading")
    date = today or _dt.date.today().isoformat()
    rec = {"amendment": arm_cfg["amendment"], "arm": arm, "rule": arm_cfg["scout_rule"], "reading": reading,
           "floor": floor, "floor_file": FLOOR_JSON, "floor_sha256": hashlib.sha256(fp.read_bytes()).hexdigest(),
           "n_cells": len(cells), "cells": inputs, "date": date}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rec, indent=1) + "\n")
    out(f"FINDINGS: {arm_cfg['amendment']} scout ({arm}), {date}: {reading} "
        f"[{arm_cfg['scout']}; floor {floor:.6g}]")
    if reading.startswith("scout failed: not measurable"):
        for cid, v in inputs.items():
            for f in v.get("failures", []):
                out(f"  {cid}: {f['tool']}: {f['reason']} (run {f['run']})")
    return rec


def rerun_scout(arm, root=ROOT, out=print):
    """Re-derive a shipped reading in the RELEASE tree, keeping the date it was read, so the release
    build can compare the file byte for byte. Refused in a private tree, where a
    written reading is final."""
    root = Path(root)
    if private_tree(root):
        raise SystemExit("REFUSING --rerun in a private tree: a written reading is final there (A15.7.1); --rerun "
                         "re-derives it in the release tree only")
    target = root / ARMS[arm]["scout"]
    if not target.exists():
        raise SystemExit(f"--rerun: {ARMS[arm]['scout']} is missing: there is no reading to re-derive")
    return read_scout(arm, root, today=json.loads(target.read_text())["date"], out=out, rerun=True)


def check_fixtures(path):
    root = Path(path).expanduser().resolve()
    repo = ROOT.resolve()
    in_private = any((d / PRIVATE_MARKER).is_file() for d in (root, *root.parents))
    if root == repo or repo in root.parents or in_private:
        raise SystemExit("REFUSING --fixtures: the folder is the repository, inside it, or inside a private "
                         f"tree (it or a folder above it carries {PRIVATE_MARKER}). Fixtures live outside it.")
    return root


def main(argv=None):
    ap = argparse.ArgumentParser(description="The scout's decision rule (A15.5, A16.7)")
    ap.add_argument("--floor", action="store_true", help="write analysis/out/scout_floor.json from the public tree")
    ap.add_argument("--tree", help="--floor: the public release tree (default: the stilldrawn folder beside this one)")
    ap.add_argument("--cells", action="store_true", help="write analysis/out/scout_cells.json")
    ap.add_argument("--arm", choices=sorted(ARMS), help="read the rule for this arm's scout")
    ap.add_argument("--fixtures", help="a synthetic tree outside the repository; skips the registration check")
    ap.add_argument("--rerun", action="store_true",
                    help="--arm: re-derive the shipped reading in the release tree (the release build's re-run)")
    a = ap.parse_args(argv)
    if a.floor:
        rec = build_floor(a.tree)
        print(f"{FLOOR_JSON}: floor {rec['floor']:.6g} over {rec['n']} primary IDLE cells")
    if a.cells:
        build_cells()
        print(f"{CELLS_JSON}: written")
    if a.arm:
        if a.fixtures:
            root = check_fixtures(a.fixtures)
        else:
            root = ROOT
            require_public(ARMS[a.arm]["amendment"], f"read the {a.arm} scout's rule", hint="Tests use --fixtures.")
        if a.rerun:
            rerun_scout(a.arm, root)
        else:
            read_scout(a.arm, root)
    if not (a.floor or a.cells or a.arm):
        ap.error("nothing to do: --floor, --cells or --arm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
