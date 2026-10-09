#!/usr/bin/env python3
"""A3 ground-value series — dose–response figure + table (per amendment A3 §4).

Descriptive per-engine curves of the headline scalars vs ground scale k
(n=1 draw per step per engine — stated; the repeat probe showed per-draw
variance, so shapes are read for consistency across engines, not per-point
precision). Outputs fig5_ground.png + ground_response.md.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "out"
KS = [1.00, 0.90, 0.80, 0.65, 0.52]
ENGINE_C = {"gen4_turbo": ("#2a78d6", "gen4t"), "gen4.5": ("#1baf7a", "gen45"),
            "h3-fal": ("#eb6834", "h3"), "wan22": ("#eda100", "wan22"),
            "ltx23": ("#e87ba4", "ltx23")}
METRICS = [("line_chamfer", "line drift chamfer (px)", True),
           ("edge_abs", "edge decay |slope|", True),
           ("style_term", "style drift terminal", False)]
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": "#c3c2b7",
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "font.size": 9})


def series(engine_tag):
    rows = []
    for k in KS:
        f = ROOT / "runs/metrics-ground" / f"ground-cu-line-1-v{int(round(k*100)):03d}_idle_{engine_tag}.json"
        if not f.exists():
            return None
        m = json.loads(f.read_text())["metrics"]
        rows.append({"k": k,
                     "line_chamfer": m["line_drift"]["vs_frame0"]["chamfer_px"]["mean"],
                     "edge_abs": m["edge_decay"]["abs_slope_norm"],
                     "style_term": m["style_drift"].get("terminal")})
    return rows


def main():
    data = {}
    for eng, (c, tag) in ENGINE_C.items():
        s = series(tag)
        if s:
            data[eng] = s

    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.0))
    for ax, (key, label, logy) in zip(axes, METRICS):
        for eng, rows in data.items():
            c = ENGINE_C[eng][0]
            ax.plot([r["k"] for r in rows], [r[key] for r in rows], "o-",
                    color=c, lw=2, ms=5, label=eng, mec=SURFACE, mew=0.8)
        if logy:
            ax.set_yscale("log")
        ax.set_title(label, fontsize=9, loc="left", color=INK)
        ax.set_xlabel("ground scale k (1.0 = true white)", fontsize=8)
        ax.invert_xaxis()
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("A3 ground-value series — cu-line-1 variants, IDLE, one draw per step. "
                 "Readable on gen4_turbo (draw noise << effect); h3-fal's k=1.00 point is a "
                 "pathological draw, not a ground effect (see triplicate)",
                 x=0.005, ha="left", fontsize=9, color=INK2, y=1.03)
    fig.tight_layout()
    (OUT / "figures").mkdir(exist_ok=True)
    fig.savefig(OUT / "figures" / "fig5_ground.png", dpi=150, bbox_inches="tight")

    md = ["# A3 ground-value series — dose–response", "",
          "One draw per step per engine. **Interpretability rule (added 2026-08-13 after the "
          "repeat probe): a 5-point n=1 series is readable only where the engine's per-draw "
          "variance is small relative to the dose effect.** Per-cell median |Δ| between runs "
          "(repeat_stability.md §2) is the yardstick: gen4_turbo 0.88px chamfer vs a "
          "4.7→15.8px effect (readable); gen4.5 1.54px vs 5.8→12.3px (marginal); h3-fal "
          "2.72px median but 102px max swing (NOT readable — see the triplicate below).", "",
          "## Accidental triplicate — the same input drawn three times (h3-fal)", "",
          "`ground-cu-line-1-v100.png` is **pixel-identical** to `cu-line-1.png` "
          "(k=1.00 is the identity transform; verified max abs diff 0), so three "
          "independent draws of the same (panel, prompt, engine) exist:", "",
          "| draw | chamfer px | style terminal | edge \\|slope\\| |", "|---|---|---|---|",
          "| main run 1 | 103.13 | 0.315 | 0.206 |",
          "| repeat r2 | 1.45 | 0.197 | 0.034 |",
          "| A3 v100 | 51.73 | 0.166 | 0.094 |", "",
          "The corpus maximum and a near-perfect clip from identical inputs. This is the "
          "strongest single evidence for the hazard framing (R10/R11) — and it is why "
          "h3-fal's ground series below cannot be read as a dose–response: its k=1.00 point "
          "is a pathological draw, not a ground effect.", ""]
    for eng, rows in data.items():
        md += [f"## {eng}", "", "| k | chamfer px | edge |slope| | style terminal |", "|---|---|---|---|"]
        md += [f"| {r['k']:.2f} | {r['line_chamfer']:.2f} | {r['edge_abs']:.3f} | {r['style_term']:.3f} |"
               for r in rows]
        md.append("")
    (OUT / "ground_response.md").write_text("\n".join(md))
    print(f"engines with complete series: {sorted(data)}")
    print(f"-> {OUT/'figures'/'fig5_ground.png'}")


if __name__ == "__main__":
    main()
