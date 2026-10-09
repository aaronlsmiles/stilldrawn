#!/usr/bin/env python3
"""How many cells does a league-position scout actually need? (£0, existing data)

Question: if we run a NEW engine on only k of the 33 frozen cells, how often
does its median put it in the same league position as running all 33 would?

Method — leave-one-engine-out simulation on the corpus we already have:
  * treat each of the five engines in turn as "the unknown new engine";
  * draw a stratified sample of k of its cells (balanced across content class
    and motion class, which is what a declared scout would use);
  * compute its median headline from those k cells only;
  * compute the other four engines' medians from ALL their cells;
  * rank the unknown against them, and compare to the rank it gets from its
    own full 33 cells.

Accuracy = fraction of trials where the k-cell scout puts the engine in the
right position. Reported per k and per headline metric, so the scout can be
sized to a stated confidence rather than guessed.
"""
import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent / "out"
KS = [4, 6, 9, 12, 15, 18, 24]
TRIALS = 4000
SEED = 20260814
METRICS = ["line_chamfer_mean_px", "style_terminal", "edge_abs_slope"]
ENGINES = ["gen4_turbo", "h3-fal", "gen4.5", "wan22", "ltx23"]


def stratified_sample(cells, k, rng):
    """Sample k cells spread across (content_class, motion) strata."""
    by = defaultdict(list)
    for c in cells:
        by[(c["content_class"], c["motion"])].append(c)
    strata = list(by.values())
    rng.shuffle(strata)
    for s in strata:
        rng.shuffle(s)
    out, i = [], 0
    while len(out) < k:
        added = False
        for s in strata:
            if i < len(s) and len(out) < k:
                out.append(s[i]); added = True
        if not added:
            break
        i += 1
    return out


def main():
    rows = [r for r in json.loads((OUT / "results_table.json").read_text())
            if r["motion"] != "FLINT"]
    by_engine = defaultdict(list)
    for r in rows:
        by_engine[r["engine"]].append(r)

    report = {"trials": TRIALS, "seed": SEED, "per_metric": {}}
    md = ["# Scout sizing — how many cells to place an engine in the league?", "",
          f"Leave-one-engine-out simulation, {TRIALS} trials per cell, stratified "
          f"sampling across content × motion. Accuracy = fraction of trials in "
          f"which a k-cell scout gives the engine its true league position.", ""]

    for metric in METRICS:
        full = {e: float(np.median([r[metric] for r in by_engine[e]
                                    if r[metric] is not None])) for e in ENGINES}
        true_rank = {e: sorted(full, key=lambda x: full[x]).index(e) for e in ENGINES}
        md += [f"## {metric}", "",
               "| k cells | accuracy | cost at Seedance std |", "|---|---|---|"]
        report["per_metric"][metric] = {}
        for k in KS:
            rng = random.Random(SEED + k)
            hits = 0
            for _ in range(TRIALS):
                e = rng.choice(ENGINES)
                cells = [c for c in by_engine[e] if c[metric] is not None]
                samp = stratified_sample(cells, min(k, len(cells)), rng)
                m = float(np.median([c[metric] for c in samp]))
                others = {o: full[o] for o in ENGINES if o != e}
                rank = sum(1 for v in others.values() if v < m)
                hits += (rank == true_rank[e])
            acc = hits / TRIALS
            report["per_metric"][metric][k] = acc
            md.append(f"| {k} | {acc:.0%} | ${k*1.512:.2f} ≈ £{k*1.512/1.28:.2f} |")
        md.append("")

    # headline recommendation: smallest k with >=80% on all three metrics
    rec = None
    for k in KS:
        if all(report["per_metric"][m][k] >= 0.80 for m in METRICS):
            rec = k
            break
    report["recommended_k"] = rec
    md += ["## Recommendation", "",
           (f"Smallest k reaching ≥80% accuracy on all three metrics: **{rec} cells** "
            f"(${rec*1.512:.2f} ≈ £{rec*1.512/1.28:.2f} at Seedance standard tier)."
            if rec else
            "No k below 24 reaches 80% on all three metrics — a partial matrix is "
            "not a reliable league instrument, and the full 33 cells are the "
            "honest purchase."), "",
           "Caveat: this simulates a *known* engine's own cells. A genuinely new "
           "engine could be more variable across cells than any of the five, in "
           "which case these accuracies are optimistic."]

    (OUT / "scout_sizing.md").write_text("\n".join(md) + "\n")
    (OUT / "scout_sizing.json").write_text(json.dumps(report, indent=1))
    print("\n".join(md[3:]))


if __name__ == "__main__":
    main()
