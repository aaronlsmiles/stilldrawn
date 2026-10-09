#!/usr/bin/env python3
"""Draw the frozen §6 human-check subset — 20 clips, stratified, fixed seed.

Frozen constraints (docs/PREREGISTRATION.md §6, verbatim): "20 clips,
stratified: every engine appears ≥3×, every content class ≥6×, every motion
class ≥6×; selection by fixed seed (recorded) from the manifest."

Interpretation notes (recorded here because the frozen text does not spell
them out):
  * "every motion class" = the three standard classes (IDLE/BURST/CAMPUSH).
    With FLINT counted as a fourth class the constraint 4×6=24 > 20 is
    unsatisfiable, so §6 arithmetic itself implies the standard classes; the
    candidate pool is therefore the 164 standard cells (170 minus 6 FLINT).
    FLINT clips also rate differently by construction (content changes by
    design), which §6's single register question does not model.
  * The refused Turbo cell does not exist as a clip and is naturally absent.

Algorithm (deterministic given SEED): seeded Fisher–Yates shuffle of the
candidate cell_ids (sorted first for a stable start state), then take the
first 20 that never make any constraint unsatisfiable, greedily topping up
scarce strata; if the greedy pass fails (it cannot for these margins, but
belt-and-braces), reshuffle with seed+1 and retry. The seed, algorithm hash
inputs, and the draw are all recorded in the output JSON.

SEED = 20260813 (the date the draw was made; chosen before running, recorded
here and in the output).

Output: analysis/out/human_subset.json
"""
import json
import random
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
SEED = 20260813
N = 20
MIN_ENGINE, MIN_CLASS, MIN_MOTION = 3, 6, 6
ENGINES = ["gen4_turbo", "h3-fal", "gen4.5", "wan22", "ltx23"]
CLASSES = ["cu", "act", "est"]
MOTIONS = ["IDLE", "BURST", "CAMPUSH"]


def satisfiable(picked, remaining_pool):
    """Can the mins still be met given picks so far + what's left?"""
    slots = N - len(picked)
    if slots < 0:
        return False
    for dim, groups, need in (("engine", ENGINES, MIN_ENGINE),
                              ("content_class", CLASSES, MIN_CLASS),
                              ("motion", MOTIONS, MIN_MOTION)):
        have = Counter(r[dim] for r in picked)
        deficit = sum(max(0, need - have[g]) for g in groups)
        if deficit > slots:
            return False
        for g in groups:
            avail = sum(1 for r in remaining_pool if r[dim] == g)
            if have[g] + avail < need:
                return False
    return True


def draw(pool, seed):
    rng = random.Random(seed)
    order = sorted(pool, key=lambda r: r["cell_id"])
    rng.shuffle(order)
    picked = []
    for i, cand in enumerate(order):
        rest = order[i + 1:]
        if len(picked) == N:
            break
        trial = picked + [cand]
        if satisfiable(trial, rest):
            picked = trial
    return picked if len(picked) == N else None


def main():
    rows = json.loads((OUT / "results_table.json").read_text())
    pool = [r for r in rows if r["motion"] != "FLINT"]
    assert len(pool) == 164, f"expected 164 standard cells, got {len(pool)}"

    seed = SEED
    picked = None
    while picked is None:
        picked = draw(pool, seed)
        if picked is None:
            seed += 1
    picked.sort(key=lambda r: r["cell_id"])

    counts = {
        "engine": dict(Counter(r["engine"] for r in picked)),
        "content_class": dict(Counter(r["content_class"] for r in picked)),
        "motion": dict(Counter(r["motion"] for r in picked)),
    }
    for e in ENGINES:
        assert counts["engine"].get(e, 0) >= MIN_ENGINE, e
    for c in CLASSES:
        assert counts["content_class"].get(c, 0) >= MIN_CLASS, c
    for m in MOTIONS:
        assert counts["motion"].get(m, 0) >= MIN_MOTION, m

    out = {
        "protocol": "docs/PREREGISTRATION.md §6 (frozen)",
        "drawn": "2026-08-13",
        "seed_declared": SEED,
        "seed_used": seed,
        "n": N,
        "pool": "164 standard cells (FLINT excluded — see docstring), refused cell naturally absent",
        "algorithm": "seeded Fisher-Yates over sorted cell_ids + greedy feasibility-checked take (draw_subset.py)",
        "strata_counts": counts,
        "cells": [r["cell_id"] for r in picked],
    }
    (OUT / "human_subset.json").write_text(json.dumps(out, indent=1))
    print(f"seed {seed} -> {N} cells")
    print(json.dumps(counts, indent=1))
    for c in out["cells"]:
        print(" ", c)


if __name__ == "__main__":
    main()
