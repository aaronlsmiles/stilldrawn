#!/usr/bin/env python3
"""Run-matrix driver — emits the frozen cell list and executes it per engine.

Cell assignment is FROZEN: docs/PREREGISTRATION.md §5 (27-cell rotation) +
amendment A1 (6 extension cells; Aaron's go recorded 2026-08-12). No run-time
editing: this module is the executable transcription of that text.

Usage
  matrix.py --list                       # print all cells (any engine)
  matrix.py --engine wan22               # run all cells for an engine (resumes)
  matrix.py --engine h3-fal              # includes the 6 FLINT cells (§5)
  matrix.py --engine wan22 --no-metrics  # skip inkstab pass per clip

Metrics run as clips land (plan 4.2): metrics/inkstab.py with the ComfyUI venv
python; failures are logged and do not stop the batch.
"""
import argparse
import json
import pathlib
import random
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
VENV_PY = pathlib.Path(__import__("os").environ.get("STILLDRAWN_PY", __import__("sys").executable))
if not VENV_PY.exists():   # pod execution (A2): system python has the deps
    VENV_PY = pathlib.Path(sys.executable)

# §5 rotation: cell order k = 0..8; panel -n gets motion (k + n - 1) mod 3.
CELL_ORDER = ["cu-line", "cu-tone", "cu-black",
              "act-line", "act-tone", "act-black",
              "est-line", "est-tone", "est-black"]
MOTIONS = ["IDLE", "BURST", "CAMPUSH"]

# Amendment A1: 3 motion cells each for the two extension panels.
A1_CELLS = [("cip-act-tank-1", m, "720:1280") for m in MOTIONS] + \
           [("chain-est-cosmic-1", m, "1280:720") for m in MOTIONS]

ENGINE_TAG = {"wan22": "wan22", "ltx23": "ltx23",
              "gen4_turbo": "gen4t", "gen4.5": "gen45", "h3-fal": "h3"}


def core_cells():
    """(panel_id, motion, ratio) for the 27 frozen rotation cells."""
    out = []
    for k, cell in enumerate(CELL_ORDER):
        for n in (1, 2, 3):
            motion = MOTIONS[(k + n - 1) % 3]
            out.append((f"{cell}-{n}", motion, "1280:720"))
    return out


def flint_cells():
    """6 first→last cells (H3 only): per content class, 2 disjoint ordered pairs
    drawn from the class's 9 core panels by fixed seed 42 — recorded in the
    manifest at submission (prereg §5)."""
    rng = random.Random(42)
    cells = []
    for cls in ("cu", "act", "est"):
        panels = [f"{cls}-{t}-{n}" for t in ("line", "tone", "black")
                  for n in (1, 2, 3)]
        picks = rng.sample(panels, 4)   # 2 disjoint ordered pairs
        cells.append((picks[0], picks[1]))
        cells.append((picks[2], picks[3]))
    return cells


def all_cells(engine):
    cells = core_cells() + A1_CELLS
    rows = []
    tag = ENGINE_TAG[engine]
    for panel, motion, ratio in cells:
        rows.append({"panel": panel, "motion": motion, "ratio": ratio,
                     "cell_id": f"{panel}_{motion.lower()}_{tag}"})
    if engine == "h3-fal":
        for first, last in flint_cells():
            rows.append({"panel": first, "last_panel": last, "motion": "FLINT",
                         "ratio": "1280:720",
                         "cell_id": f"flint-{first}--{last}_{tag}"})
    return rows


def repeat_rows(rows, tag):
    """Repeat-probe cells (extension: 'are rankings stable across repeats?',
    authorised 2026-08-13 — LEDGER authorizations). Distinct cell_ids so
    originals can never be overwritten; FLINT excluded (the probe targets the
    33 standard cells; FLINT sits outside cross-engine comparisons anyway);
    metric JSONs go to runs/metrics-<tag>/ so the primary corpus directory
    stays exactly the 171-cell frozen set."""
    out = []
    for r in rows:
        if r["motion"] == "FLINT":
            continue
        r2 = dict(r)
        r2["cell_id"] = f"{r['cell_id']}-{tag}"
        out.append(r2)
    return out


def run_metrics(cell_id, panel, out_path, metrics_dir="runs/metrics"):
    mjson = ROOT / metrics_dir / f"{cell_id}.json"
    mjson.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(VENV_PY), str(ROOT / "metrics/inkstab.py"), str(out_path),
           "--panel", str(ROOT / "dataset/panels" / f"{panel}.png"),
           "--lineart", str(ROOT / "dataset/lineart" / f"{panel}-lines.png"),
           "--out", str(mjson)]
    try:
        subprocess.run(cmd, check=True, timeout=1800)
        print(f"  metrics -> {mjson.name}")
    except Exception as e:   # noqa: BLE001 — a metric failure must not kill the batch
        print(f"  METRICS FAILED for {cell_id}: {e} (rerun standalone later)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--engine")
    p.add_argument("--list", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--no-metrics", action="store_true")
    p.add_argument("--metrics-only", action="store_true",
                   help="backfill inkstab metrics for cells whose .mp4 exists "
                        "(generation skips existing cells BEFORE run_metrics, so "
                        "a plain re-run never backfills)")
    p.add_argument("--repeat", default=None, metavar="TAG",
                   help="repeat-probe mode (e.g. r2): suffix every cell_id with "
                        "-TAG, skip FLINT, write metrics to runs/metrics-TAG/")
    a = p.parse_args()
    metrics_dir = f"runs/metrics-{a.repeat}" if a.repeat else "runs/metrics"

    if a.metrics_only:
        if not a.engine:
            sys.exit("--metrics-only needs --engine")
        done = 0
        rows = all_cells(a.engine)
        if a.repeat:
            rows = repeat_rows(rows, a.repeat)
        for r in rows:
            out = ROOT / "runs" / a.engine / f"{r['cell_id']}.mp4"
            mjson = ROOT / metrics_dir / f"{r['cell_id']}.json"
            if out.exists() and not mjson.exists():
                run_metrics(r["cell_id"], r["panel"], out, metrics_dir)
                done += 1
        print(f"{a.engine}: metrics backfilled for {done} cells")
        return

    if a.list or not a.engine:
        for eng in ENGINE_TAG:
            rows = all_cells(eng)
            print(f"{eng}: {len(rows)} cells")
            if a.list and eng == (a.engine or "wan22"):
                for r in rows:
                    print("  ", json.dumps(r))
        return

    rows = all_cells(a.engine)
    if a.repeat:
        rows = repeat_rows(rows, a.repeat)
    done = skipped = failed = 0
    t0 = time.time()
    for r in rows:
        out = ROOT / "runs" / a.engine / f"{r['cell_id']}.mp4"
        if out.exists():
            skipped += 1
            continue
        cmd = [str(VENV_PY), str(HERE / "gen_video.py"),
               "--engine", a.engine,
               "--panel", str(ROOT / "dataset/panels" / f"{r['panel']}.png"),
               "--motion", r["motion"], "--cell-id", r["cell_id"],
               "--ratio", r["ratio"]]
        if r.get("last_panel"):
            cmd += ["--last-panel",
                    str(ROOT / "dataset/panels" / f"{r['last_panel']}.png")]
        print(f"[{done + skipped + failed + 1}/{len(rows)}] {r['cell_id']}")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            failed += 1
            print(f"  CELL FAILED ({e.returncode}) — continuing; "
                  f"resubmit once per prereg §5, then record as refused")
            continue
        done += 1
        if not a.no_metrics:
            run_metrics(r["cell_id"], r["panel"], out, metrics_dir)
        if a.limit and done >= a.limit:
            break
    print(f"\n{a.engine}: {done} new, {skipped} already present, {failed} failed, "
          f"{(time.time() - t0) / 60:.0f} min wall")


if __name__ == "__main__":
    main()
