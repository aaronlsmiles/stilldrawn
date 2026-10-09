#!/usr/bin/env python3
"""Amendment A5 Option 1b — the Seedance scout (6 clips, frozen composition).

Composition is declared in the amendment and hard-coded here so nothing can be
selected after seeing data:
  * 3 FLINT pairs — the first three frozen §5 pairs in manifest order
  * 3 single-image draws on act-black-3 BURST — A4's highest-hazard cell

Every clip counts toward Options 1 and 2 if we proceed (the scout is a prefix
of Option 3, not an extra cost). Clips land in runs/seedance/, metrics in
runs/metrics-seedance/ — the primary corpus is untouched.

  seedance_scout.py plan | run | metrics
"""
import argparse
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
VENV_PY = pathlib.Path(__import__("os").environ.get("STILLDRAWN_PY", __import__("sys").executable))
if not VENV_PY.exists():
    VENV_PY = pathlib.Path(sys.executable)

ENGINE, TAG, RATIO = "seedance", "sd2", "1280:720"
RATE = 0.3024 * 5          # $/clip, 5 s at 720p standard

# The six frozen §5 FLINT pairs (seed-42 draw, recovered from matrix.py).
# The first three were the A5 Option-1b scout; the remaining three complete
# Option 1 (Aaron's go recorded 2026-08-14). Order preserved so the scout's
# three are unambiguous in the record.
FLINT = [("cu-line-2", "cu-line-1"),        # scout
         ("act-line-2", "act-tone-3"),      # scout
         ("est-line-2", "est-black-3"),     # scout
         ("cu-tone-3", "cu-line-3"),        # Option 1 completion
         ("act-tone-1", "act-black-3"),     # Option 1 completion
         ("est-tone-2", "est-tone-1")]      # Option 1 completion
# A5 clause 2 — three draws on the highest-hazard A4 cell
HAZARD = [("act-black-3", "BURST", k) for k in (1, 2, 3)]
METRICS_DIR = ROOT / "runs/metrics-seedance"


def cells():
    out = [(f"flint-{a}--{b}_{TAG}", a, "FLINT", b) for a, b in FLINT]
    out += [(f"{p}_{m.lower()}_{TAG}-h{k}", p, m, None) for p, m, k in HAZARD]
    return out


def plan():
    todo = [c for c in cells()
            if not (ROOT / "runs" / ENGINE / f"{c[0]}.mp4").exists()]
    for cid, panel, motion, last in cells():
        done = (ROOT / "runs" / ENGINE / f"{cid}.mp4").exists()
        print(f"  [{'x' if done else ' '}] {cid:<42} {motion}"
              f"{' -> ' + last if last else ''}")
    print(f"\n{len(todo)} to run · ${len(todo) * RATE:.2f} · £{len(todo) * RATE / 1.28:.2f}")
    return todo


def run():
    for cid, panel, motion, last in cells():
        out = ROOT / "runs" / ENGINE / f"{cid}.mp4"
        if out.exists():
            print(f"skip {cid}")
            continue
        cmd = [str(VENV_PY), str(HERE / "gen_video.py"), "--engine", ENGINE,
               "--panel", str(ROOT / "dataset/panels" / f"{panel}.png"),
               "--motion", motion, "--cell-id", cid, "--ratio", RATIO]
        if last:
            cmd += ["--last-panel", str(ROOT / "dataset/panels" / f"{last}.png")]
        print(f"[A5] {cid}", flush=True)
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"  FAILED ({e.returncode}) — recorded, not retried "
                  f"(a refusal is an outcome; A4/A5 coding rule)")


def metrics():
    METRICS_DIR.mkdir(exist_ok=True)
    for cid, panel, motion, last in cells():
        clip = ROOT / "runs" / ENGINE / f"{cid}.mp4"
        mj = METRICS_DIR / f"{cid}.json"
        if not clip.exists() or mj.exists():
            continue
        subprocess.run([str(VENV_PY), str(ROOT / "metrics/inkstab.py"), str(clip),
                        "--panel", str(ROOT / "dataset/panels" / f"{panel}.png"),
                        "--lineart", str(ROOT / "dataset/lineart" / f"{panel}-lines.png"),
                        "--out", str(mj)], check=True, timeout=1800)
        print(f"metrics -> {mj.name}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["plan", "run", "metrics"])
    {"plan": plan, "run": run, "metrics": metrics}[p.parse_args().mode]()
