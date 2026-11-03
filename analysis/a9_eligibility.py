#!/usr/bin/env python3
"""A9.4 eligibility and mask agreement, from the line art and the two mask sets only.

*** EXPLORATORY: post-hoc. See PREREGISTRATION.md amendment A9. ***

    python analysis/a9_eligibility.py        # -> analysis/out/a9_eligible.csv

For each Test 2 row (a panel and a motion class; 22 rows on 20 panels), on the eligibility
grid of 1280 x 720 (720 x 1280 for a portrait panel):

  n_lines   line pixels of the row's line-art layer (dataset/lineart), binarised exactly as
            metrics/inkstab.py binarises a --lineart layer;
  M         the "may move" mask: each polygon (fractions of the panel) filled on the grid
            by metrics/masked.py's rasterise under the stretch mapping (x * width,
            y * height, boundary included). This script imports that function, so M is the
            same code as the registered run's;
  R         the measured region at margin m = 32, metrics/masked.py's region (the whole
            grid when nothing may move);
  n_R       line pixels inside R;
  eligible  n_R >= max(2000, 0.10 * n_lines) under both mask sets (decided in integers:
            10 * n_R >= max(20000, n_lines)).

Also, per row, the IoU of the two sets' M on the same grid (1.0 when both are empty). It reads
no clip, no frame and no metric output: line art and masks only, so it does not depend on the
per-engine mapping chosen by the reproduction gate.
"""
import argparse
import csv
import re
import sys
from pathlib import Path

import numpy as np
import skimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metrics"))
import inkstab  # noqa: E402  (frozen; only its greyscale conversion is used)
import masked  # noqa: E402  (the registered rasterisation, regions and mask-file reader)

SCHEMA = masked.MASK_SCHEMA
MARGIN = 32
MIN_LINE_PX = 2000
MIN_LINE_FRAC = 0.10
LANDSCAPE = (720, 1280)                 # (height, width)
REGISTERED = (11, 11, 20)               # idle rows, burst rows, distinct panels
ASPECT_TOL = 0.01
COLUMNS = ["row", "panel", "motion", "grid", "n_lines", "threshold",
           "status_aaron", "status_agent", "mask_px_aaron", "mask_px_agent",
           "n_R_aaron_m32", "n_R_agent_m32", "eligible_aaron", "eligible_agent", "eligible",
           "iou", "union_px"]
PUBLIC_ID = re.compile(r"^[a-z]+-(?P<tail>.+)$")


def grid_shape(panel_px):
    w, h = panel_px
    return (LANDSCAPE[1], LANDSCAPE[0]) if h > w else LANDSCAPE


def binarise_lineart(path, shape):
    """Line pixels of a black-on-white line-art layer, exactly as inkstab's --lineart branch."""
    import imageio.v3 as iio
    from skimage.filters import threshold_otsu
    from skimage.transform import resize
    lg = inkstab._grey(iio.imread(path))
    lg = 1.0 - lg                               # provided layers are black-on-white
    lg = resize(lg, shape, anti_aliasing=True)
    return lg > (threshold_otsu(lg) if lg.max() > lg.min() else 0.5)


def rasterise(polygons, shape):
    """M on a (height, width) grid: masked.rasterise under the stretch mapping."""
    h, w = shape
    return masked.rasterise(polygons, (w, h), shape, "stretch")


def region(mask, margin):
    """R = ~binary_dilation(M, disk(margin)); all-true for an empty M (masked.region)."""
    return masked.region(mask, margin)


def threshold(n_lines):
    return max(MIN_LINE_PX, MIN_LINE_FRAC * n_lines)


def is_eligible(n_r, n_lines):
    """n_R >= max(2000, 0.10 * n_lines), decided in integers."""
    return 10 * n_r >= max(10 * MIN_LINE_PX, n_lines)


def iou(a, b):
    union = int((a | b).sum())
    return 1.0 if union == 0 else int((a & b).sum()) / union


def layer_path(folder, public_id, suffix):
    """folder/<public_id><suffix>. In the private working tree one panel keeps its working
    prefix, so fall back to files whose stem maps to the same public id (masked.public_id);
    exactly one must match."""
    folder = Path(folder)
    exact = folder / f"{public_id}{suffix}"
    if exact.exists():
        return exact
    m = PUBLIC_ID.match(public_id)
    hits = [] if not m else sorted(
        p for p in folder.glob(f"*-{m['tail']}{suffix}")
        if masked.public_id(p.name[:-len(suffix)]) == public_id)
    if len(hits) != 1:
        raise FileNotFoundError(f"no unique {suffix} layer for panel {public_id} in {folder.name}")
    return hits[0]


def panel_px_on_disk(root, panel):
    from PIL import Image
    with Image.open(layer_path(Path(root) / "dataset" / "panels", panel, ".png")) as im:
        return [int(im.size[0]), int(im.size[1])]


def load_masks(path, expect_set):
    """The checked mask document (masked.read_masks) of the named set."""
    doc = masked.read_masks(path)[0]
    if doc["set"] != expect_set:
        raise ValueError(f"{Path(path).name}: set is {doc['set']!r}, expected {expect_set!r}")
    return doc


def check_aspect(layer, panel_px, panel):
    from PIL import Image
    with Image.open(layer) as im:
        lw, lh = im.size
    if abs((lw / lh) / (panel_px[0] / panel_px[1]) - 1) > ASPECT_TOL:
        raise ValueError(f"{panel}: line-art layer is {lw}x{lh}, its aspect ratio does not match "
                         f"panel_px {panel_px}")


def compute(root, aaron_path, agent_path, composition=None):
    """composition=None is the registered one (11 idle + 11 burst rows on 20 distinct panels);
    only tests pass another (idle, burst, panels), there is no command-line route to it."""
    root = Path(root)
    a, g = load_masks(aaron_path, "aaron"), load_masks(agent_path, "agent")
    if sorted(a["rows"]) != sorted(g["rows"]):
        raise ValueError("the two mask sets cover different rows")
    want = REGISTERED if composition is None else tuple(composition)
    motions = [r["motion"] for r in a["rows"].values()]
    found = (motions.count("idle"), motions.count("burst"), len({r["panel"] for r in a["rows"].values()}))
    if found != want or len(motions) != want[0] + want[1]:
        raise ValueError(f"expected {want[0]} idle and {want[1]} burst rows on {want[2]} distinct "
                         f"panels, found {found[0]} idle, {found[1]} burst, {found[2]} panels")
    out = []
    for rid in sorted(a["rows"]):
        ra, rg = a["rows"][rid], g["rows"][rid]
        if [ra["panel"], ra["motion"], ra["panel_px"]] != [rg["panel"], rg["motion"], rg["panel_px"]]:
            raise ValueError(f"{rid}: the two sets disagree on panel, motion or size")
        real = panel_px_on_disk(root, ra["panel"])
        if real != ra["panel_px"]:
            raise ValueError(f"{rid}: panel_px {ra['panel_px']} but the panel image is {real}")
        shape = grid_shape(ra["panel_px"])
        layer = layer_path(root / "dataset" / "lineart", ra["panel"], "-lines.png")
        check_aspect(layer, ra["panel_px"], ra["panel"])
        lines = binarise_lineart(layer, shape)
        n_lines = int(lines.sum())
        ma, mg = rasterise(ra["allowed"], shape), rasterise(rg["allowed"], shape)
        na = int((lines & region(ma, MARGIN)).sum())
        ng = int((lines & region(mg, MARGIN)).sum())
        ea, eg = is_eligible(na, n_lines), is_eligible(ng, n_lines)
        out.append({"row": rid, "panel": ra["panel"], "motion": ra["motion"],
                    "grid": f"{shape[1]}x{shape[0]}", "n_lines": n_lines,
                    "threshold": f"{threshold(n_lines):.1f}",   # display only: eligibility uses is_eligible
                    
                    "status_aaron": ra["status"], "status_agent": rg["status"],
                    "mask_px_aaron": int(ma.sum()), "mask_px_agent": int(mg.sum()),
                    "n_R_aaron_m32": na, "n_R_agent_m32": ng,
                    "eligible_aaron": ea, "eligible_agent": eg, "eligible": ea and eg,
                    "iou": f"{iou(ma, mg):.4f}", "union_px": int((ma | mg).sum())})
    return out


def write_csv(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([str(r[c]).lower() if isinstance(r[c], bool) else r[c] for c in COLUMNS])


def main():
    p = argparse.ArgumentParser(description="A9.4 eligibility and mask IoU (line art and masks only)")
    p.add_argument("--root", default=str(ROOT))
    p.add_argument("--aaron", default="dataset/masks/allowed-aaron.json")
    p.add_argument("--agent", default="dataset/masks/allowed-agent.json")
    p.add_argument("--out", default="analysis/out/a9_eligible.csv")
    a = p.parse_args()
    root = Path(a.root)
    rows = compute(root, root / a.aaron, root / a.agent)
    write_csv(rows, root / a.out)
    ious = sorted(float(r["iou"]) for r in rows)
    print(f"[a9_eligibility] eligible rows: {sum(r['eligible'] for r in rows)} / {len(rows)} "
          f"(first set {sum(r['eligible_aaron'] for r in rows)}, "
          f"second set {sum(r['eligible_agent'] for r in rows)}); "
          f"IoU min {ious[0]:.4f}, median {float(np.median(ious)):.4f} -> {a.out}; "
          f"numpy {np.__version__}, scikit-image {skimage.__version__}")


if __name__ == "__main__":
    main()
