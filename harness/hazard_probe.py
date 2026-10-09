#!/usr/bin/env python3
"""Hazard-rate probe (amendment A4) — repeated draws of a few frozen cells.

A4 registers a 2x2 core: {cu-line-1, act-black-3} x {IDLE, BURST} on one
engine (h3-fal), n=10 draws per cell inclusive of draws already in the corpus.
Draws are suffixed -h<k>, clips land in runs/<engine>/, metrics in
runs/metrics-hazard/ — the primary 171-cell corpus directory is untouched.

  hazard_probe.py plan                    # what exists / what's still needed
  hazard_probe.py run    [--extended]     # generate the missing draws
  hazard_probe.py metrics                 # score whatever exists

Resumable and idempotent: existing clips and metric JSONs are skipped, so a
partial run (e.g. provider credit runs out) is continued by re-invoking.
"""
import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
VENV_PY = pathlib.Path(__import__("os").environ.get("STILLDRAWN_PY", __import__("sys").executable))
if not VENV_PY.exists():
    VENV_PY = pathlib.Path(sys.executable)

ENGINE = "h3-fal"
TAG = "h3"
N_TARGET = 10
RATIO = "1280:720"

# A4 clause 1 — core 2x2, declared before any draw
CORE = [("cu-line-1", "IDLE"), ("cu-line-1", "BURST"),
        ("act-black-3", "IDLE"), ("act-black-3", "BURST")]
# A4 clause 1 — the extension, also declared in advance
EXTENDED = [("act-line-2", "IDLE"), ("act-line-2", "BURST"),
            ("cu-black-3", "IDLE"), ("cu-black-3", "BURST")]

METRICS_DIR = ROOT / "runs/metrics-hazard"


def existing_draws(panel, motion):
    """Draws of this cell already in the corpus, across all metric dirs.

    The main run and the -r2 repeat each contribute one where the cell was
    part of that matrix; the A3 identity variant contributes one for
    cu-line-1 IDLE (pixel-identical panel — see ground_response.py)."""
    stem = f"{panel}_{motion.lower()}_{TAG}"
    found = []
    for d, suffix in ((ROOT / "runs/metrics", ""), (ROOT / "runs/metrics-r2", "-r2")):
        f = d / f"{stem}{suffix}.json"
        if f.exists():
            found.append(f)
    if (panel, motion) == ("cu-line-1", "IDLE"):
        f = ROOT / "runs/metrics-ground" / f"ground-cu-line-1-v100_idle_{TAG}.json"
        if f.exists():
            found.append(f)
    found += sorted(METRICS_DIR.glob(f"{stem}-h*.json"))
    return found


def cells(extended):
    return CORE + (EXTENDED if extended else [])


def plan(extended):
    total_new = 0
    print(f"{'cell':<28} {'have':>5} {'need':>5}")
    for panel, motion in cells(extended):
        have = len(existing_draws(panel, motion))
        need = max(0, N_TARGET - have)
        total_new += need
        print(f"{panel + '_' + motion.lower():<28} {have:>5} {need:>5}")
    print(f"\n{total_new} new draws · ~${total_new * 0.35:.2f} · "
          f"~£{total_new * 0.35 / 1.28:.2f} on {ENGINE}")
    return total_new


def run(extended):
    METRICS_DIR.mkdir(exist_ok=True)
    for panel, motion in cells(extended):
        have = len(existing_draws(panel, motion))
        for k in range(1, N_TARGET - have + 1):
            cell_id = f"{panel}_{motion.lower()}_{TAG}-h{k}"
            out = ROOT / "runs" / ENGINE / f"{cell_id}.mp4"
            if out.exists():
                continue
            cmd = [str(VENV_PY), str(HERE / "gen_video.py"), "--engine", ENGINE,
                   "--panel", str(ROOT / "dataset/panels" / f"{panel}.png"),
                   "--motion", motion, "--cell-id", cell_id, "--ratio", RATIO]
            print(f"[A4] {cell_id}")
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                print(f"  DRAW FAILED ({e.returncode}) — recorded as a failure, "
                      f"not retried (a refusal is itself an outcome; A4 rule 4)")


def metrics():
    METRICS_DIR.mkdir(exist_ok=True)
    done = 0
    for clip in sorted((ROOT / "runs" / ENGINE).glob("*-h[0-9]*.mp4")):
        mjson = METRICS_DIR / f"{clip.stem}.json"
        if mjson.exists():
            continue
        panel = clip.stem.rsplit("_", 2)[0]
        subprocess.run([str(VENV_PY), str(ROOT / "metrics/inkstab.py"), str(clip),
                        "--panel", str(ROOT / "dataset/panels" / f"{panel}.png"),
                        "--lineart", str(ROOT / "dataset/lineart" / f"{panel}-lines.png"),
                        "--out", str(mjson)], check=True, timeout=1800)
        done += 1
        print(f"metrics -> {mjson.name}")
    print(f"{done} scored")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["plan", "run", "metrics"])
    p.add_argument("--extended", action="store_true",
                   help="include the 4 declared extension cells (A4 clause 1)")
    a = p.parse_args()
    {"plan": plan, "run": run, "metrics": lambda _: metrics()}[a.mode](a.extended)
