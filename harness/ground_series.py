#!/usr/bin/env python3
"""Ground-value causal series (amendment A3) — variant builder + run driver.

`build`: derive the five ground-value variants of the base panel by global
linear luminance scale k ∈ {1.00, 0.90, 0.80, 0.65, 0.52}; write derived
recipe JSONs (source, transform verbatim, measured p90/black_frac) and copy
the source lineart layer per variant (a global value scale moves no geometry).

`run --engine E`: execute the 5 IDLE cells for one engine via gen_video.py
(frozen prompt path), metrics NOT run here (backfill with `metrics --engine E`
which writes to runs/metrics-ground/).
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
VENV_PY = pathlib.Path(__import__("os").environ.get("STILLDRAWN_PY", __import__("sys").executable))
if not VENV_PY.exists():   # pod execution (A2/A3): system python has the deps
    VENV_PY = pathlib.Path(sys.executable)

BASE = "cu-line-1"
KS = [1.00, 0.90, 0.80, 0.65, 0.52]
ENGINE_TAG = {"gen4_turbo": "gen4t", "gen4.5": "gen45", "h3-fal": "h3",
              "wan22": "wan22", "ltx23": "ltx23"}
RATIO = "1280:720"


def vid(k):
    return f"ground-{BASE}-v{int(round(k * 100)):03d}"


def p90_black(img):
    g = np.asarray(img.convert("L"), dtype=float) / 255.0
    return float(np.percentile(g, 90)), float((g < 0.1).mean())


def build():
    src = Image.open(ROOT / "dataset/panels" / f"{BASE}.png").convert("RGB")
    for k in KS:
        arr = np.asarray(src, dtype=float) * k
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        pid = vid(k)
        im.save(ROOT / "dataset/panels" / f"{pid}.png")
        shutil.copy(ROOT / "dataset/lineart" / f"{BASE}-lines.png",
                    ROOT / "dataset/lineart" / f"{pid}-lines.png")
        p90, bf = p90_black(im)
        (ROOT / "dataset/recipes" / f"{pid}.json").write_text(json.dumps({
            "derived_from": BASE,
            "transform": f"global linear luminance scale: pixel' = clip(pixel * {k})",
            "amendment": "A3 (2026-08-13, ground-value causal series)",
            "engine": "derived", "date": "2026-08-13",
            "paper_white_p90": round(p90, 3), "black_frac": round(bf, 3),
            "lineart": f"copied from {BASE} (global value scale moves no geometry)",
        }, indent=1))
        print(f"{pid}: p90={p90:.3f} black_frac={bf:.3f}")


def run(engine):
    tag = ENGINE_TAG[engine]
    for k in KS:
        pid = vid(k)
        cell = f"{pid}_idle_{tag}"
        out = ROOT / "runs" / engine / f"{cell}.mp4"
        if out.exists():
            print(f"skip {cell} (exists)")
            continue
        cmd = [str(VENV_PY), str(HERE / "gen_video.py"), "--engine", engine,
               "--panel", str(ROOT / "dataset/panels" / f"{pid}.png"),
               "--motion", "IDLE", "--cell-id", cell, "--ratio", RATIO]
        print(f"[A3] {cell}")
        subprocess.run(cmd, check=True)


def metrics(engine):
    tag = ENGINE_TAG[engine]
    mdir = ROOT / "runs/metrics-ground"
    mdir.mkdir(exist_ok=True)
    for k in KS:
        pid = vid(k)
        cell = f"{pid}_idle_{tag}"
        clip = ROOT / "runs" / engine / f"{cell}.mp4"
        mjson = mdir / f"{cell}.json"
        if not clip.exists() or mjson.exists():
            continue
        subprocess.run([str(VENV_PY), str(ROOT / "metrics/inkstab.py"), str(clip),
                        "--panel", str(ROOT / "dataset/panels" / f"{pid}.png"),
                        "--lineart", str(ROOT / "dataset/lineart" / f"{pid}-lines.png"),
                        "--out", str(mjson)], check=True, timeout=1800)
        print(f"metrics -> {mjson.name}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["build", "run", "metrics"])
    p.add_argument("--engine")
    a = p.parse_args()
    if a.mode == "build":
        build()
    elif a.mode == "run":
        run(a.engine)
    else:
        metrics(a.engine)
