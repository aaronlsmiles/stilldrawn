#!/usr/bin/env python3
"""Motion-confound figure + table (amendment A6, EXPLORATORY).

Reads analysis/out/motion_confound.json and produces:

  fig6_motion.png   two panels —
      (a) per-cell motion vs line drift, coloured by engine, with each engine's
          median marked: the confound, cell by cell.
      (b) the engine-level Pareto view (median motion vs median drift). An
          engine is dominated only if another both moves more and drifts less.
          Non-dominated engines are not rankable without stating a trade-off.

  motion_confound.md  the readable table set: per-engine motion and drift, the
      pairwise matched-motion comparisons (including which pairs invert against
      the raw league), and the model-based matching that disagrees with them.

Run after analysis/motion_confound.py.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "out"
TABLE = OUT / "results_table.csv"
MOTION_DIR = ROOT / "runs" / "metrics-motion"

ENGINE_C = {"gen4_turbo": ("#2a78d6", "gen4t"), "gen4.5": ("#1baf7a", "gen45"),
            "h3-fal": ("#eb6834", "h3"), "wan22": ("#eda100", "wan22"),
            "ltx23": ("#e87ba4", "ltx23")}
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": "#c3c2b7",
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
})


def load_cells():
    import csv

    motion = {}
    for p in MOTION_DIR.glob("*.json"):
        motion[p.stem] = json.loads(p.read_text())["motion"]["headline_median_norm"]
    rows = []
    with TABLE.open() as fh:
        for r in csv.DictReader(fh):
            m = motion.get(r["cell_id"])
            if m is None:
                continue
            try:
                d = float(r["line_chamfer_mean_px"])
            except (TypeError, ValueError):
                continue
            if np.isfinite(d):
                rows.append((r["engine"], m, d))
    return rows


def main():
    data = json.loads((OUT / "motion_confound.json").read_text())
    q1 = data["q1_motion_by_engine"]
    rows = load_cells()

    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.0))

    # (a) per-cell scatter
    ax = axes[0]
    for e, (c, lab) in ENGINE_C.items():
        xs = [m for en, m, _ in rows if en == e]
        ys = [d for en, _, d in rows if en == e]
        ax.scatter(xs, ys, s=13, alpha=0.55, color=c, edgecolors="none", label=lab)
        if e in q1:
            ax.scatter([q1[e]["motion_median_norm"]], [q1[e]["chamfer_median_px"]],
                       s=95, marker="D", color=c, edgecolors=INK, linewidths=0.7, zorder=5)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("motion (normalised median flow, log)")
    ax.set_ylabel("line drift chamfer px (log)")
    ax.set_title("(a) the confound, cell by cell — diamonds are engine medians", loc="left")
    ax.legend(frameon=False, fontsize=7, loc="lower right", ncol=2)

    # (b) Pareto
    ax = axes[1]
    dominated = data["q5c_pareto"]["dominated_by"]
    # Hand-placed label offsets: the frontier runs bottom-left to top-right, so
    # labels sit below-right of frontier points and above-left of h3.
    OFFSETS = {"wan22": (9, -12), "gen4_turbo": (9, -12), "ltx23": (9, 5),
               "gen4.5": (-6, -16), "h3-fal": (-10, 10)}
    for e, (c, lab) in ENGINE_C.items():
        if e not in q1:
            continue
        x, y = q1[e]["motion_median_norm"], q1[e]["chamfer_median_px"]
        dom = bool(dominated.get(e))
        ax.scatter([x], [y], s=150, color=c, edgecolors=INK if not dom else MUTED,
                   linewidths=1.2 if not dom else 0.7, alpha=1.0 if not dom else 0.45, zorder=4)
        ax.annotate(f"{lab}{' (dominated)' if dom else ''}", (x, y),
                    textcoords="offset points", xytext=OFFSETS.get(e, (8, 5)),
                    fontsize=7.5, ha="right" if e in ("gen4.5", "h3-fal") else "left",
                    color=INK if not dom else MUTED)
    ax.margins(x=0.16, y=0.16)
    front = [e for e in data["q5c_pareto"]["frontier"] if e in q1]
    front.sort(key=lambda e: q1[e]["motion_median_norm"])
    ax.plot([q1[e]["motion_median_norm"] for e in front],
            [q1[e]["chamfer_median_px"] for e in front],
            color=MUTED, lw=0.9, ls="--", zorder=1)
    ax.set_xlabel("motion (normalised median flow) — more is better")
    ax.set_ylabel("line drift chamfer px — less is better")
    ax.set_title("(b) Pareto view — only h3 is dominated", loc="left")

    fig.suptitle("Motion confound (EXPLORATORY, amendment A6). Engine-level rho(motion, drift) = +0.90. "
                 "Engines on the frontier are not rankable without stating a motion/stability trade-off.",
                 fontsize=8, color=INK2, y=1.02)
    fig.tight_layout()
    (OUT / "figures").mkdir(exist_ok=True)
    fig.savefig(OUT / "figures" / "fig6_motion.png", dpi=150, bbox_inches="tight")
    print(f"wrote {OUT / 'figures' / 'fig6_motion.png'}")

    # --- markdown table set --------------------------------------------------
    md = ["# Motion confound — tables (EXPLORATORY, amendment A6)", "",
          "Post-hoc. May qualify a frozen result, never restate one.", "",
          "## Per engine", "",
          "| engine | n | motion (norm. median) | line drift (px) |",
          "|---|---:|---:|---:|"]
    for e in sorted(q1, key=lambda k: q1[k]["chamfer_median_px"]):
        v = q1[e]
        md.append(f"| {e} | {v['n']} | {v['motion_median_norm']:.5f} | {v['chamfer_median_px']:.3f} |")
    r = data["q1_engine_level_rho_motion_vs_chamfer"]
    md += ["", f"Engine-level Spearman rho(motion, drift) = **{r['rho']:.2f}** "
               f"(p = {r['p']:.4g}, n = {r['n_engines']} engines).", ""]

    md += ["## Route 1 — pairwise matched-motion bands", "",
           "Comparisons restricted to the overlap of each pair's motion IQR, so both",
           "engines are judged at comparable movement. `n` is cells surviving in band.", "",
           "| pair | status | in-band drift | winner at matched motion | vs raw league |",
           "|---|---|---|---|---|"]
    raw_order = [e for e in sorted(q1, key=lambda k: q1[k]["chamfer_median_px"])]
    for k, v in data["q5a_pairwise_matched_bands"].items():
        a, b = k.split("|")
        if not v["overlaps"]:
            md.append(f"| {a} vs {b} | **no overlap** | — | not comparable | — |")
            continue
        if not v.get("usable"):
            md.append(f"| {a} vs {b} | overlap too thin | — | not comparable | — |")
            continue
        da, db = v[a]["drift_median"], v[b]["drift_median"]
        win = v["winner_in_band"]
        raw_win = a if raw_order.index(a) < raw_order.index(b) else b
        flag = "same" if win == raw_win else "**INVERTS**"
        md.append(f"| {a} vs {b} | usable (n={v[a]['n']},{v[b]['n']}) | {da:.2f} vs {db:.2f} | {win} | {flag} |")

    f = data["q5b_fitted_at_common_motion"]
    md += ["", "## Route 2 — model-based matching", "",
           f"Per-engine linear fit of drift on motion, compared at a common motion "
           f"level ({f['target_motion_norm']:.5f}).", "",
           "| engine | fitted drift (px) | observed motion range | extrapolating |",
           "|---|---:|---|---|"]
    for e in f.get("ordering_at_target", []):
        v = f[e]
        md.append(f"| {e} | {v['fitted_drift_at_target']:.3f} | "
                  f"{v['motion_range'][0]:.5f}–{v['motion_range'][1]:.5f} | {v['extrapolating']} |")
    md += ["", f"Ordering at common motion: **{' < '.join(f.get('ordering_at_target', []))}** — "
               "which preserves the raw league and therefore *disagrees with Route 1*. "
               "Route 1 assumes nothing about functional form; Route 2 assumes drift is "
               "linear in motion and leans on sparse tails. The disagreement is the "
               "finding: the ordering is not robust to how motion is controlled.", ""]

    md += ["## Route 3 — Pareto", "",
           f"Frontier (not rankable without a stated trade-off): "
           f"**{', '.join(data['q5c_pareto']['frontier'])}**", ""]
    for e, dom in data["q5c_pareto"]["dominated_by"].items():
        if dom:
            md.append(f"- `{e}` is dominated by {', '.join(f'`{d}`' for d in dom)} "
                      f"— that engine both moves more and drifts less.")
    (OUT / "motion_confound.md").write_text("\n".join(md) + "\n")
    print(f"wrote {OUT / 'motion_confound.md'}")


if __name__ == "__main__":
    main()
