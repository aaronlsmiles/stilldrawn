#!/usr/bin/env python3
"""Repeat-stability probe analysis (extension, authorised 2026-08-13).

Named question (LEDGER authorization): are the cross-engine rankings stable
across repeated generations, and are the named taxonomy modes deterministic
properties of (panel, prompt, engine) or stochastic draws?

Inputs: runs/metrics/*.json (primary corpus, run 1) and runs/metrics-r2/*.json
(repeat probe; cell ids suffixed -r2). Hosted engines only unless local
repeats are added later. Outputs analysis/out/repeat_stability.{md,json}.

Analyses (descriptive — this is an extension, not part of frozen §8):
  1. Engine-league stability: per headline, median across each engine's
     repeated cells in run 1 vs run 2; Spearman rank correlation of the
     engine ordering across runs.
  2. Per-cell repeatability: |r1 − r2| per headline per engine (median and
     max absolute difference, plus Spearman of per-cell values r1 vs r2 —
     "does a cell that drifts badly once drift badly again?").
  3. Taxonomy-mode reproducibility: for the named exemplar cells, r1 vs r2
     headline scalars side by side + a flag when the repeat lands in a
     clearly different regime (>3x or <1/3x on its firing metric) —
     candidates for frame-strip review before any reproducibility claim.
"""
import json
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "out"
R2 = ROOT / "runs" / "metrics-r2"

HEADLINES = ["line_chamfer_mean_px", "tone_variance", "edge_abs_slope",
             "style_terminal", "closure_abs_terminal"]

# taxonomy exemplars with a hosted-engine repeat (docs/TAXONOMY.md) and the
# metric channel each mode is expected to fire (or stay quiet) on
EXEMPLARS = {
    "cu-line-2_burst_h3": ("A1 enrichment", "tone_variance"),
    "est-black-3_burst_gen4t": ("A2 transposition", "edge_abs_slope"),
    "cu-line-2_burst_ltx23": ("A2 transposition", "edge_abs_slope"),  # local; skipped unless local r2 exists
    "est-black-2_idle_h3": ("A3 partial collapse", "style_terminal"),
    "est-tone-1_burst_gen45": ("B1 insertion (train)", "style_terminal"),
    "cu-line-1_idle_h3": ("B2 pseudo-text", "line_chamfer_mean_px"),
    "cu-black-3_burst_h3": ("B2 pseudo-text", "line_chamfer_mean_px"),
    "est-tone-2_campush_h3": ("B3 evacuation", "closure_abs_terminal"),
    "act-line-3_campush_gen45": ("B3 evacuation", "closure_abs_terminal"),
    "cu-line-2_burst_gen4t": ("C1 framing escape", "line_chamfer_mean_px"),
    "act-tone-1_burst_gen45": ("C1/B3 whiteout", "style_terminal"),
}


def headline_scalars(d):
    m = d["metrics"]
    style = m["style_drift"] if "error" not in m["style_drift"] else {}
    ct = m["closure_proxy"].get("drift_terminal")
    return {
        "line_chamfer_mean_px": m["line_drift"]["vs_frame0"]["chamfer_px"]["mean"],
        "tone_variance": m["tone_spectral_drift"].get("variance"),
        "edge_abs_slope": m["edge_decay"].get("abs_slope_norm"),
        "style_terminal": style.get("terminal"),
        "closure_abs_terminal": abs(ct) if ct is not None else None,
    }


def main():
    r1 = {r["cell_id"]: r for r in json.loads((OUT / "results_table.json").read_text())}
    r2 = {}
    for f in sorted(R2.glob("*.json")):
        cell = f.name[:-len("-r2.json")] if f.stem.endswith("-r2") else f.stem
        r2[cell] = headline_scalars(json.loads(f.read_text()))
    if not r2:
        raise SystemExit(f"no repeat metrics in {R2} yet")

    engines = sorted({r1[c]["engine"] for c in r2 if c in r1})
    report = {"n_repeat_cells": len(r2), "engines": engines}
    md = ["# Repeat-stability probe (extension, 2026-08-13)", "",
          f"{len(r2)} repeat cells scored across {engines}.", ""]

    # 1. league stability
    md += ["## 1. Engine-league stability (medians, repeated cells only)", "",
           "| headline | ordering r1 | ordering r2 | Spearman |", "|---|---|---|---|"]
    league = {}
    for h in HEADLINES:
        med1, med2 = {}, {}
        for e in engines:
            cells = [c for c in r2 if c in r1 and r1[c]["engine"] == e]
            v1 = [r1[c][h] for c in cells if r1[c][h] is not None]
            v2 = [r2[c][h] for c in cells if r2[c][h] is not None]
            if v1 and v2:
                med1[e], med2[e] = float(np.median(v1)), float(np.median(v2))
        common = [e for e in engines if e in med1 and e in med2]
        o1 = sorted(common, key=lambda e: med1[e])
        o2 = sorted(common, key=lambda e: med2[e])
        rho = float(stats.spearmanr([med1[e] for e in common],
                                    [med2[e] for e in common]).statistic) if len(common) > 2 else None
        league[h] = {"medians_r1": med1, "medians_r2": med2, "spearman": rho}
        md.append(f"| {h} | {'<'.join(o1)} | {'<'.join(o2)} | "
                  f"{'—' if rho is None else f'{rho:+.2f}'} |")
    report["league"] = league

    # 2. per-cell repeatability
    md += ["", "## 2. Per-cell repeatability", "",
           "| engine | headline | n | Spearman(r1,r2) | median |Δ| | max |Δ| |",
           "|---|---|---|---|---|---|"]
    percell = {}
    for e in engines:
        for h in HEADLINES:
            pairs = [(r1[c][h], r2[c][h]) for c in r2
                     if c in r1 and r1[c]["engine"] == e
                     and r1[c][h] is not None and r2[c][h] is not None]
            if len(pairs) < 4:
                continue
            x, y = map(np.array, zip(*pairs))
            rho = float(stats.spearmanr(x, y).statistic)
            d = np.abs(x - y)
            percell.setdefault(e, {})[h] = {
                "n": len(pairs), "spearman": rho,
                "median_abs_delta": float(np.median(d)), "max_abs_delta": float(d.max())}
            md.append(f"| {e} | {h} | {len(pairs)} | {rho:+.2f} | "
                      f"{np.median(d):.3g} | {d.max():.3g} |")
    report["per_cell"] = percell

    # 3. exemplar reproducibility
    md += ["", "## 3. Taxonomy-exemplar reproducibility", "",
           "| cell | mode | firing metric | r1 | r2 | regime |", "|---|---|---|---|---|---|"]
    ex = {}
    for cell, (mode, metric) in EXEMPLARS.items():
        if cell not in r2 or cell not in r1:
            continue
        v1, v2 = r1[cell][metric], r2[cell][metric]
        if v1 is None or v2 is None:
            regime = "undefined"
        else:
            ratio = (v2 / v1) if v1 else float("inf")
            regime = ("SAME" if 1 / 3 <= ratio <= 3 else "DIFFERENT — review strips")
        ex[cell] = {"mode": mode, "metric": metric, "r1": v1, "r2": v2, "regime": regime}
        md.append(f"| {cell} | {mode} | {metric} | {v1 if v1 is None else f'{v1:.3g}'} | "
                  f"{v2 if v2 is None else f'{v2:.3g}'} | {regime} |")
    report["exemplars"] = ex
    md += ["", "Regime SAME = repeat lands within 3x on the mode's firing metric; "
           "DIFFERENT cells get frame-strip review before any reproducibility "
           "claim is made either way. Scalar agreement is necessary, not "
           "sufficient — the strips decide."]

    (OUT / "repeat_stability.json").write_text(json.dumps(report, indent=1))
    (OUT / "repeat_stability.md").write_text("\n".join(md) + "\n")
    print(f"-> {OUT/'repeat_stability.md'} ({len(r2)} repeat cells)")


if __name__ == "__main__":
    main()
