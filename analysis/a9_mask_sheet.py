#!/usr/bin/env python3
"""Contact sheet of the two A9 mask sets over the source panels (panels only, never frames).

*** EXPLORATORY: post-hoc. See PREREGISTRATION.md amendment A9. ***

    python analysis/a9_mask_sheet.py        # -> analysis/out/figures/a9_masks.png

Two Test 2 rows per line; each row shows two tiles over its panel: the first set (Aaron's,
gold) and the second set (the blind drawer's, blue). Captions give the row id, the set and,
when analysis/out/a9_eligible.csv exists, the row's IoU and eligibility.
"""
import argparse
import csv
import functools
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
from a9_eligibility import layer_path, load_masks  # noqa: E402

TILE_W, TILE_H, CAPTION, GAP, HEADER = 384, 216, 40, 8, 40
CAPTION_PT = 14
CAPTION_MIN_PT = 7
PER_LINE = 2
COLOURS = {"aaron": (255, 196, 0), "agent": (64, 170, 255)}
NAMES = {"aaron": "AARON", "agent": "blind drawer"}
BG = (24, 24, 28)
INK = (235, 235, 240)


def sheet_size(n_rows):
    lines = -(-n_rows // PER_LINE)
    width = PER_LINE * 2 * TILE_W + (PER_LINE * 2 + 1) * GAP
    height = HEADER + lines * (TILE_H + CAPTION) + (lines + 1) * GAP
    return width, height


@functools.lru_cache(maxsize=None)
def _font(size=CAPTION_PT):
    return ImageFont.load_default(size=size)


def caption_lines(rid, name, stat):
    """Line 1: the row id. Line 2: the set name, plus IoU and eligibility when the CSV has the row."""
    second = NAMES[name]
    if stat is not None:
        eligible = "yes" if str(stat["eligible"]).lower() in ("true", "yes", "1") else "no"
        second += f" | IoU {float(stat['iou']):.4f} | eligible {eligible}"
    return [rid, second]


def caption_font(lines, max_w=TILE_W - 8):
    """The largest font size (down to CAPTION_MIN_PT) at which every line fits max_w."""
    for size in range(CAPTION_PT, CAPTION_MIN_PT - 1, -1):
        font = _font(size)
        if all(font.getlength(t) <= max_w for t in lines):
            return font
    return _font(CAPTION_MIN_PT)


def tile(panel, polygons, colour, nothing):
    """The panel fitted into TILE_W x TILE_H, its polygons filled and outlined."""
    im = panel.convert("RGB")
    scale = min(TILE_W / im.width, TILE_H / im.height)
    w, h = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    im = im.resize((w, h), Image.LANCZOS)
    canvas = Image.new("RGBA", (TILE_W, TILE_H), BG + (255,))
    ox, oy = (TILE_W - w) // 2, (TILE_H - h) // 2
    canvas.paste(im, (ox, oy))
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for poly in polygons:
        d.polygon([(ox + x * w, oy + y * h) for x, y in poly],
                  fill=colour + (90,), outline=colour + (255,), width=2)
    out = Image.alpha_composite(canvas, layer).convert("RGB")
    if nothing:
        d = ImageDraw.Draw(out)
        font = _font(CAPTION_PT)
        box = d.textbbox((ox + 6, oy + 6), "nothing may move", font=font)
        d.rectangle([box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3], fill=(0, 0, 0))
        d.text((ox + 6, oy + 6), "nothing may move", fill=colour, font=font)
    return out


def read_csv(path):
    if not Path(path).exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["row"]: r for r in csv.DictReader(f)}


def check_pairing(sets):
    a, g = sets["aaron"]["rows"], sets["agent"]["rows"]
    if sorted(a) != sorted(g):
        only = sorted(set(a) ^ set(g))
        raise SystemExit(f"[a9_mask_sheet] the two sets name different rows: {only}")
    for rid in a:
        if a[rid]["panel"] != g[rid]["panel"]:
            raise SystemExit(f"[a9_mask_sheet] {rid}: panel differs between sets "
                             f"({a[rid]['panel']} vs {g[rid]['panel']})")


def build_sheet(root, aaron_path, agent_path, csv_path):
    root = Path(root)
    sets = {"aaron": load_masks(aaron_path, "aaron"), "agent": load_masks(agent_path, "agent")}
    check_pairing(sets)
    ids = sorted(sets["aaron"]["rows"])
    stats = read_csv(csv_path)
    sheet = Image.new("RGB", sheet_size(len(ids)), BG)
    d = ImageDraw.Draw(sheet)
    d.text((GAP, 12), "A9 allowed-motion masks over the source panels: AARON gold, blind drawer blue",
           fill=INK, font=_font(CAPTION_PT))
    for k, rid in enumerate(ids):
        line, slot = divmod(k, PER_LINE)
        y = HEADER + GAP + line * (TILE_H + CAPTION + GAP)
        panel_id = sets["aaron"]["rows"][rid]["panel"]
        with Image.open(layer_path(root / "dataset" / "panels", panel_id, ".png")) as panel:
            for j, name in enumerate(("aaron", "agent")):
                r = sets[name]["rows"][rid]
                x = GAP + (slot * 2 + j) * (TILE_W + GAP)
                sheet.paste(tile(panel, r["allowed"], COLOURS[name], r["status"] == "nothing-allowed"), (x, y))
                lines = caption_lines(rid, name, stats.get(rid))
                font = caption_font(lines)
                for n, text in enumerate(lines):
                    d.text((x, y + TILE_H + 4 + n * 15), text, fill=INK, font=font)
    return sheet


def main():
    p = argparse.ArgumentParser(description="contact sheet of both A9 mask sets over the panels")
    p.add_argument("--root", default=str(ROOT))
    p.add_argument("--aaron", default="dataset/masks/allowed-aaron.json")
    p.add_argument("--agent", default="dataset/masks/allowed-agent.json")
    p.add_argument("--csv", default="analysis/out/a9_eligible.csv")
    p.add_argument("--out", default="analysis/out/figures/a9_masks.png")
    a = p.parse_args()
    root = Path(a.root)
    sheet = build_sheet(root, root / a.aaron, root / a.agent, root / a.csv)
    out = root / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    # PIL writes no text chunks unless pnginfo is passed; fixed compression keeps bytes stable.
    sheet.save(out, format="PNG", compress_level=6)
    print(f"[a9_mask_sheet] {sheet.size[0]} x {sheet.size[1]} -> {a.out}")


if __name__ == "__main__":
    main()
