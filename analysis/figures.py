#!/usr/bin/env python3
"""Figures for the StillDrawn results (frozen §8 tables + exploratory covariate).

Colourblind-safe categorical palette (validated order, light surface):
motion classes and engines each get a FIXED colour assignment used identically
in every figure. All multi-decade axes are log-scaled. Outputs 150dpi PNGs to
analysis/out/figures/.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent / "out"
FIG = OUT / "figures"

# palette (fixed assignment, never cycled)
MOTION_C = {"IDLE": "#2a78d6", "BURST": "#eb6834", "CAMPUSH": "#1baf7a", "FLINT": "#4a3aa7"}
ENGINE_C = {"gen4_turbo": "#2a78d6", "h3-fal": "#eb6834", "gen4.5": "#1baf7a",
            "wan22": "#eda100", "ltx23": "#e87ba4"}
SURFACE, INK, INK2, MUTED, GRID, BASE = ("#fcfcfb", "#0b0b0b", "#52514e",
                                         "#898781", "#e1e0d9", "#c3c2b7")
ENGINES = ["gen4_turbo", "h3-fal", "gen4.5", "wan22", "ltx23"]
MOTIONS = ["IDLE", "BURST", "CAMPUSH", "FLINT"]
HEADLINES = [
    ("line_chamfer_mean_px", "line drift\nmean chamfer (px)"),
    ("tone_variance", "tone spectral\nband-energy var"),
    ("edge_abs_slope", "edge decay\n|norm. slope|"),
    ("style_terminal", "style drift\nterminal dist"),
    ("closure_abs_terminal", "closure\n|terminal drift|"),
]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": BASE, "axes.labelcolor": INK2,
    "text.color": INK, "xtick.color": MUTED, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "font.size": 9,
})


def load():
    return json.loads((OUT / "results_table.json").read_text())


def _vals(rows, **kw):
    sel = [r for r in rows if all(r[k] == v for k, v in kw.items())]
    return sel


def fig1_league(rows):
    """Dot-range small multiples: engines x motion classes per headline metric."""
    fig, axes = plt.subplots(1, 5, figsize=(13.5, 3.6), sharey=True)
    for ax, (metric, label) in zip(axes, HEADLINES):
        ax.set_title(label, fontsize=9, color=INK, loc="left")
        ax.set_xscale("log")
        for yi, e in enumerate(ENGINES):
            for mi, m in enumerate(MOTIONS):
                v = [r[metric] for r in _vals(rows, engine=e, motion=m)
                     if r[metric] is not None and r[metric] > 0]
                if not v:
                    continue
                y = yi + (mi - 1) * 0.22
                ax.plot([min(v), max(v)], [y, y], color=MOTION_C[m], lw=1.6,
                        alpha=0.45, solid_capstyle="round", zorder=2)
                ax.plot(float(np.mean(v)), y, "o", ms=5.5, color=MOTION_C[m],
                        mec=SURFACE, mew=0.8, zorder=3)
        ax.set_ylim(-0.75, len(ENGINES) - 0.25)
        ax.invert_yaxis()
        ax.tick_params(axis="x", labelsize=7.5)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
    axes[0].set_yticks(range(len(ENGINES)), ENGINES)
    handles = [plt.Line2D([], [], marker="o", ls="-", color=MOTION_C[m], label=m,
                          ms=5.5, mec=SURFACE) for m in MOTIONS]
    fig.legend(handles=handles, loc="upper right", ncol=4, frameon=False,
               bbox_to_anchor=(0.99, 1.04), fontsize=8)
    fig.suptitle("Headline scalars by engine × motion class — dot = mean, bar = min–max  "
                 "(FLINT: H3-only first-to-last cells; vs-frame-0 scalars include the intended transport)",
                 x=0.005, ha="left", fontsize=8.5, color=INK2, y=1.02)
    fig.tight_layout()
    fig.savefig(FIG / "fig1_league.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig2_prereg(rows, test):
    """Frozen §8: establishing vs pooled cu+act strips, per engine, both metrics."""
    metrics = [("edge_abs_slope", "edge decay |normalised slope|"),
               ("style_terminal", "style drift terminal distance")]
    rng = np.random.default_rng(20260812)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
    for ax, (metric, label) in zip(axes, metrics):
        ax.set_xscale("log")
        ax.set_title(label, fontsize=9.5, color=INK, loc="left")
        for yi, e in enumerate(ENGINES):
            er = [r for r in rows if r["engine"] == e and r["motion"] != "FLINT"]
            est = [r[metric] for r in er if r["content_class"] == "est" and r[metric]]
            rest = [r[metric] for r in er if r["content_class"] in ("cu", "act") and r[metric]]
            jit = lambda n: rng.uniform(-0.10, 0.10, n)
            ax.scatter(rest, yi - 0.16 + jit(len(rest)), s=14, color=MUTED,
                       alpha=0.75, lw=0, zorder=2)
            ax.scatter(est, yi + 0.16 + jit(len(est)), s=16, color="#2a78d6",
                       alpha=0.9, lw=0, zorder=3)
            t = test["results"]["primary_33cell"][e][metric]
            ax.annotate(f"p={t['p_one_sided']:.2f}  r={t['rank_biserial']:+.2f}",
                        xy=(1.0, yi), xycoords=("axes fraction", "data"),
                        xytext=(4, 0), textcoords="offset points",
                        fontsize=7.5, color=INK2, va="center")
        ax.set_ylim(-0.7, len(ENGINES) - 0.3)
        ax.invert_yaxis()
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
    axes[0].set_yticks(range(len(ENGINES)), ENGINES)
    handles = [plt.Line2D([], [], marker="o", ls="", color="#2a78d6", label="establishing (n=12)"),
               plt.Line2D([], [], marker="o", ls="", color=MUTED, label="close-up + action (n=21)")]
    fig.legend(handles=handles, loc="upper right", ncol=2, frameon=False,
               bbox_to_anchor=(0.98, 1.05), fontsize=8)
    fig.suptitle("Pre-registered §8 test: establishing > pooled others — one-sided Mann–Whitney U, α=0.05. "
                 "All 10 tests NULL.", x=0.005, ha="left", fontsize=9, color=INK2, y=1.02)
    fig.tight_layout()
    fig.savefig(FIG / "fig2_prereg.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig3_covariate(rows):
    """Exploratory: paper-white p90 vs style terminal, line-only cells, per engine."""
    from scipy import stats as st
    fig, axes = plt.subplots(1, 5, figsize=(13.5, 2.9), sharex=True, sharey=True)
    for ax, e in zip(axes, ENGINES):
        er = [r for r in rows if r["engine"] == e and r["treatment"] == "line"
              and r["motion"] != "FLINT" and r["style_terminal"] is not None]
        x = [r["paper_white_p90"] for r in er]
        y = [r["style_terminal"] for r in er]
        ax.set_yscale("log")
        ax.scatter(x, y, s=22, color="#2a78d6", alpha=0.9, lw=0)
        rho, _ = st.spearmanr(x, y)
        ax.set_title(f"{e}   ρ={rho:+.2f}", fontsize=9, color=INK, loc="left")
        ax.tick_params(labelsize=7.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].set_ylabel("style terminal (log)", fontsize=8)
    axes[2].set_xlabel("source-panel paper-white p90 (1.0 = true white ground)", fontsize=8.5)
    fig.suptitle("EXPLORATORY (not pre-registered): grey-ground covariate — line-only cells (n=9/engine). "
                 "Greyer ground = larger style drift on every engine.",
                 x=0.005, ha="left", fontsize=9, color=INK2, y=1.06)
    fig.tight_layout()
    fig.savefig(FIG / "fig3_covariate.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig4_series():
    """The discriminator cell: style-drift series for cu-line-2_burst on all engines."""
    ROOT = Path(__file__).resolve().parent.parent
    suffix = {"gen4_turbo": "gen4t", "h3-fal": "h3", "gen4.5": "gen45",
              "wan22": "wan22", "ltx23": "ltx23"}
    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    for e in ENGINES:
        d = json.loads((ROOT / "runs" / "metrics" / f"cu-line-2_burst_{suffix[e]}.json").read_text())
        s = d["metrics"]["style_drift"]["series"]
        t = np.linspace(0, 5.0, len(s))            # all clips are 5 s
        ax.plot(t, s, color=ENGINE_C[e], lw=2, label=e, solid_capstyle="round")
        if e in ("gen4_turbo", "wan22"):   # others collide at the right edge; legend carries them
            ax.annotate(e, xy=(t[-1], s[-1]), xytext=(5, 0), textcoords="offset points",
                        fontsize=8, color=ENGINE_C[e], va="center")
    ax.set_xlim(0, 5.6)
    ax.set_xlabel("time (s)", fontsize=8.5)
    ax.set_ylabel("DINOv2 cosine distance vs frame 0", fontsize=8.5)
    ax.set_title("The discriminator cell — cu-line-2 BURST, style-drift trajectory per engine",
                 fontsize=9.5, color=INK, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    for s_ in ("top", "right"):
        ax.spines[s_].set_visible(False)
    fig.tight_layout()
    fig.savefig(FIG / "fig4_series.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    FIG.mkdir(exist_ok=True)
    rows = load()
    test = json.loads((OUT / "prereg_test.json").read_text())
    fig1_league(rows)
    fig2_prereg(rows, test)
    fig3_covariate(rows)
    fig4_series()
    print("figures ->", FIG)
