#!/usr/bin/env python3
"""Extract exemplar frames + a viewing strip per cell.

For each requested cell: frame 0, middle, and last frame as PNGs plus a single
horizontal strip (source panel | f0 | mid | last) for visual review. Used for
the taxonomy outlier review and the results report — extraction only, no
image processing beyond resizing.

Usage: extract_frames.py CELL_ID [CELL_ID ...]   (cell ids as in the manifest)
"""
import json
import sys
from pathlib import Path

import imageio.v3 as iio
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "out" / "frames"

ENGINE_DIR = {
    "gen4t": "gen4_turbo",
    "h3": "h3-fal",
    "gen45": "gen4.5",
    "wan22": "wan22",
    "ltx23": "ltx23",
}
TILE_H = 300


def panel_for(cell_id: str) -> Path:
    body = cell_id.rsplit("_", 1)[0]
    if cell_id.startswith("flint-"):
        first = body[len("flint-"):].split("--")[0]
        return ROOT / "dataset" / "panels" / f"{first}.png"
    return ROOT / "dataset" / "panels" / f"{body.rsplit('_', 1)[0]}.png"


def extract(cell_id: str):
    suffix = cell_id.rsplit("_", 1)[1]
    clip = ROOT / "runs" / ENGINE_DIR[suffix] / f"{cell_id}.mp4"
    frames = iio.imread(clip, plugin="pyav")
    n = len(frames)
    picks = {"f0": 0, "mid": n // 2, "last": n - 1}

    cdir = OUT / cell_id
    cdir.mkdir(parents=True, exist_ok=True)
    tiles = []
    panel = Image.open(panel_for(cell_id)).convert("RGB")
    tiles.append(panel.resize((int(panel.width * TILE_H / panel.height), TILE_H)))
    for name, i in picks.items():
        img = Image.fromarray(frames[i])
        img.save(cdir / f"{name}.png")
        tiles.append(img.resize((int(img.width * TILE_H / img.height), TILE_H)))

    strip = Image.new("RGB", (sum(t.width for t in tiles) + 6 * (len(tiles) - 1), TILE_H), "#888888")
    x = 0
    for t in tiles:
        strip.paste(t, (x, 0))
        x += t.width + 6
    strip.save(cdir / "strip.png")
    print(f"{cell_id}: {n} frames -> {cdir}/strip.png")


if __name__ == "__main__":
    for cid in sys.argv[1:]:
        extract(cid)
