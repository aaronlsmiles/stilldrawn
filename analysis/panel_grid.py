#!/usr/bin/env python3
"""The paper's Figure 1: every benchmark panel at a glance.

Top: the 27 core panels in the dataset's 3 x 3 x 3 design, one row per content
class and one column group per ink treatment, so the treatments read light to
dark across the page. Bottom: the two chain-provenance panels (amendment A1)
and the five ground variants of the A3 series.

Reads dataset/panels/ only; writes analysis/out/figures/panel_grid.png.
"""
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PANELS = ROOT / "dataset" / "panels"
OUT = Path(__file__).resolve().parent / "out" / "figures" / "panel_grid.png"

CLASSES = [("cu", "character\nclose-up"), ("act", "action"), ("est", "establishing")]
TREATMENTS = [("line", "line-only"), ("tone", "screentone"), ("black", "heavy blacks")]
CORE = re.compile(r"^(cu|act|est)-(line|tone|black)-[123]\.png$")

DPI = 450
TEXTWIDTH = 6.14          # inches: A4 with 2.7 cm margins
GAP, GROUP_GAP = 0.03, 0.12
LEFT = 0.66               # room for the row labels
W = (TEXTWIDTH - LEFT - 6 * GAP - 2 * GROUP_GAP - 0.01) / 9   # landscape thumbnail width
ASPECT = 768 / 1344       # core panel height / width
H = W * ASPECT
FONT = dict(fontsize=6.5, family="serif")


def thumb(path, width_in):
    im = Image.open(path).convert("RGB")
    px = int(round(width_in * DPI))
    return np.asarray(im.resize((px, int(round(px * im.height / im.width))), Image.LANCZOS))


def place(fig, img, x, y, w, h):
    """Draw img with its lower-left corner at (x, y) inches."""
    fw, fh = fig.get_size_inches()
    ax = fig.add_axes([x / fw, y / fh, w / fw, h / fh])
    ax.imshow(img, interpolation="none")
    ax.set_xticks([]), ax.set_yticks([])
    for s in ax.spines.values():
        s.set_linewidth(0.3)
        s.set_color("0.55")


def main():
    files = {p.name: p for p in PANELS.glob("*.png")}
    core = sorted(n for n in files if CORE.match(n))
    ground = sorted((n for n in files if n.startswith("ground-")), reverse=True)  # k = 1.00 first
    chain = sorted(n for n in files
                   if not CORE.match(n) and not n.startswith(("ground-", "smoke-")))
    assert len(core) == 27 and len(ground) == 5 and len(chain) == 2, (len(core), len(ground), len(chain))

    col_x = []
    x = LEFT
    for g in range(3):
        for _ in range(3):
            col_x.append(x)
            x += W + GAP
        x += GROUP_GAP - GAP
    header, row_gap, band_gap, label_h = 0.14, 0.035, 0.10, 0.13
    height = header + 3 * H + 2 * row_gap + band_gap + H + label_h
    fig = plt.figure(figsize=(TEXTWIDTH, height))

    top = height - header
    for g, (_, tlabel) in enumerate(TREATMENTS):
        mid = (col_x[3 * g] + col_x[3 * g + 2] + W) / 2
        fig.text(mid / TEXTWIDTH, (top + 0.04) / height, tlabel, ha="center", va="bottom", **FONT)
    for r, (cls, clabel) in enumerate(CLASSES):
        y = top - (r + 1) * H - r * row_gap
        fig.text((LEFT - 0.05) / TEXTWIDTH, (y + H / 2) / height, clabel,
                 ha="right", va="center", **FONT)
        for g, (trt, _) in enumerate(TREATMENTS):
            for i in range(3):
                name = f"{cls}-{trt}-{i + 1}.png"
                place(fig, thumb(files[name], W), col_x[3 * g + i], y, W, H)

    y = label_h
    x = col_x[0]
    chain.sort(key=lambda n: Image.open(files[n]).height > Image.open(files[n]).width)  # landscape first
    for n in chain:
        im = Image.open(files[n])
        w = H * im.width / im.height
        place(fig, thumb(files[n], w), x, y, w, H)
        x += w + GAP
    fig.text(col_x[0] / TEXTWIDTH, (y - 0.04) / height, "chain-provenance panels (A1)",
             ha="left", va="top", **FONT)
    gx = col_x[4]
    for i, n in enumerate(ground):
        place(fig, thumb(files[n], W), gx + i * (W + GAP), y, W, H)
    k = [n.rsplit("-v", 1)[1][:3] for n in ground]
    fig.text(gx / TEXTWIDTH, (y - 0.04) / height,
             f"ground series (A3): paper luminance k = {int(k[0]) / 100:.2f} to {int(k[-1]) / 100:.2f}",
             ha="left", va="top", **FONT)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=DPI)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
