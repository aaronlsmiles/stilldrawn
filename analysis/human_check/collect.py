#!/usr/bin/env python3
"""Frozen §6 human-check analysis — runs once rating JSONs arrive.

Input: analysis/human_check/ratings/ratings-<RATER>.json (the files raters
send back), analysis/human_check/mapping.json (opaque id -> cell_id),
analysis/out/results_table.json (metric headlines).

Frozen analysis (docs/PREREGISTRATION.md §6): Spearman ρ between each
metric's headline scalar and the mean human rating, with bootstrap 95% CIs;
inter-rater reliability via Krippendorff's α. Metrics that fail to track
perception are reported as such — a finding, not a failure. Expected SIGN:
negative ρ (higher metric = more degradation = lower rating); reported as
computed, never flipped.

Note for the round that first runs this on real data: cross-check the α
implementation against the `krippendorff` PyPI package before any number
lands in the paper (implementation here follows the standard coincidence-
matrix formulation with the ordinal distance metric).

Bootstrap seed: 20260813 (recorded; resamples the 20 cells).

Refactored in Nov 2026 (amendment A11) into importable parts, `guard_strays`,
`load_matrices`, `analyse` and `run`, so that A11's analysis
(analysis/human_check2/collect.py) runs the same code. The output is unchanged byte
for byte (analysis/test_human_check_collect.py).
"""
import json
from collections import Counter  # noqa: F401  (kept from the frozen script)
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "out"
SEED = 20260813
HEADLINES = ["line_chamfer_mean_px", "tone_variance", "edge_abs_slope",
             "style_terminal", "closure_abs_terminal"]


def krippendorff_alpha_ordinal(matrix):
    """matrix: raters x items, values 1..5 or np.nan. Standard coincidence-
    matrix α with ordinal distance."""
    m = np.asarray(matrix, dtype=float)
    values = sorted({int(v) for v in m[~np.isnan(m)]})
    vi = {v: k for k, v in enumerate(values)}
    V = len(values)
    coin = np.zeros((V, V))
    for item in m.T:
        vals = item[~np.isnan(item)]
        mu = len(vals)
        if mu < 2:
            continue
        # coincidence contributions: each ordered pair of distinct positions
        idx = [vi[int(v)] for v in vals]
        for i, a in enumerate(idx):
            for j, b in enumerate(idx):
                if i != j:
                    coin[a, b] += 1.0 / (mu - 1)
    n_c = coin.sum(axis=1)
    n_total = n_c.sum()
    if n_total == 0:
        return None

    def delta(c, k):
        lo, hi = min(c, k), max(c, k)
        s = n_c[lo:hi + 1].sum() - (n_c[lo] + n_c[hi]) / 2.0
        return s * s

    Do = sum(coin[c, k] * delta(c, k) for c in range(V) for k in range(V) if c != k)
    De = sum(n_c[c] * n_c[k] * delta(c, k) for c in range(V) for k in range(V) if c != k) / (n_total - 1)
    return None if De == 0 else 1.0 - Do / De


def guard_strays(here=HERE):
    """Refuse when a rating or baseline file sits where the analysis would not read it."""
    here = Path(here)
    # Guard added 2026-08-17. A duplicate `answers/` directory held a second
    # copy of rater 1's file for two days; nothing read it. The danger is not
    # the duplicate but the silence: a returned file dropped anywhere other
    # than ratings/ would be ignored and the analysis would run with a rater
    # missing, reporting a smaller n without ever saying a file was skipped.
    # Fail loudly instead. `pilot/` is exempt — it is deliberately quarantined
    # (R13) and must never be pooled.
    stray = [p for p in here.rglob("ratings-*.json")
             if p.parent != here / "ratings" and p.parent != here / "pilot"]
    if stray:
        raise SystemExit(
            "rating file(s) found outside ratings/ — refusing to run, because "
            "these would be silently excluded:\n"
            + "\n".join(f"  {p}" for p in stray)
            + f"\nMove them into {here/'ratings'}/ (or into pilot/ if they are "
              "not study data) and re-run.")

    # Same guard for A8 baseline files. `baseline-kit/` is exempt: it is the
    # build output the rater opens, so the file legitimately appears there
    # first and is copied into baselines/.
    stray_b = [p for p in here.rglob("baseline-*.json")
               if p.parent not in (here / "baselines", here / "baseline-kit")]
    if stray_b:
        raise SystemExit(
            "baseline file(s) outside baselines/ — refusing to run:\n"
            + "\n".join(f"  {p}" for p in stray_b)
            + f"\nMove them into {here/'baselines'}/ and re-run.")


def load_matrices(rating_files, opaque_ids, axes=("register", "sameness")):
    """(raters, {axis: raters x items matrix}) in the order of `rating_files` and `opaque_ids`."""
    raters, mats = [], {a: [] for a in axes}
    for f in rating_files:
        d = json.loads(Path(f).read_text())
        raters.append(d["rater"])
        for axis in axes:
            # A6 kits carry both axes; a pre-A6 file would carry "score" only
            got = {r["clip"]: r.get(axis, r.get("score")) for r in d["ratings"]}
            mats[axis].append([got.get(o, np.nan) for o in opaque_ids])
    return raters, {a: np.array(v, dtype=float) for a, v in mats.items()}


def analyse(matrices, cells, rows, seed=SEED, b=10000):
    """Per axis: Krippendorff's α and, per headline, Spearman ρ with a bootstrap 95% CI.
    One generator, default_rng(seed), runs through the axes and metrics in order."""
    rng = np.random.default_rng(seed)
    per_axis = {}
    for axis, matrix in matrices.items():
        mean_rating = np.nanmean(matrix, axis=0)
        per_axis[axis] = {
            "krippendorff_alpha_ordinal": krippendorff_alpha_ordinal(matrix),
            "per_metric": {}}
        for metric in HEADLINES:
            pairs = [(rows[c][metric], mr) for c, mr in zip(cells, mean_rating)
                     if rows[c][metric] is not None and not np.isnan(mr)]
            if len(pairs) < 4:
                per_axis[axis]["per_metric"][metric] = None
                continue
            x, y = map(np.array, zip(*pairs))
            rho, p = stats.spearmanr(x, y)
            boots = []
            for _ in range(b):
                idx = rng.integers(0, len(x), len(x))
                if len(set(x[idx])) > 1 and len(set(y[idx])) > 1:
                    boots.append(stats.spearmanr(x[idx], y[idx]).statistic)
            lo, hi = np.percentile(boots, [2.5, 97.5])
            per_axis[axis]["per_metric"][metric] = {
                "n_cells": len(pairs), "spearman_rho": float(rho), "p": float(p),
                "ci95": [float(lo), float(hi)], "bootstrap_n": len(boots), "seed": seed}
    return per_axis


def run(here=HERE, out_dir=OUT, out=None):
    """The frozen §6 analysis end to end. Returns (results, path written)."""
    here, out_dir = Path(here), Path(out_dir)
    mapping = json.loads((here / "mapping.json").read_text())
    o2c = mapping["opaque_to_cell"]
    rows = {r["cell_id"]: r for r in json.loads((out_dir / "results_table.json").read_text())}

    rating_files = sorted((here / "ratings").glob("ratings-*.json"))
    if not rating_files:
        raise SystemExit("no rating files yet — drop ratings-<RATER>.json into "
                         f"{here/'ratings'}/ and re-run")
    guard_strays(here)

    opaque_ids = sorted(o2c)
    raters, matrices = load_matrices(rating_files, opaque_ids)
    results = {"n_raters": len(raters), "raters": raters, "instrument": "A6",
               "per_axis": analyse(matrices, [o2c[o] for o in opaque_ids], rows)}
    path = Path(out) if out else here / "human_check_results.json"
    path.write_text(json.dumps(results, indent=1))
    return results, path


def main():
    results, path = run()
    print(json.dumps(results, indent=1))
    print(f"-> {path}")


if __name__ == "__main__":
    main()
