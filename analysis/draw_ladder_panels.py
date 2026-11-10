#!/usr/bin/env python3
"""Draw A10's twelve ladder panels from the 27-panel neutral core: seeded and stratified.

    python analysis/draw_ladder_panels.py            # writes analysis/out/a10_panels.json

Constraints (amendment A10, registered with this script): 12 of the 27 core panels; 4 per
content class (cu, act, est); 4 per ink treatment (line, tone, black); every class x
treatment cell at least once. That forces exactly three cells to give two panels, one in
each class row and one in each treatment column. The two A1 extension panels (the
creator-IP panel and the chain-made cosmic panel) are not in the pool: their class rows
are unbalanced.

Algorithm (deterministic given SEED): random.Random(SEED) chooses one of the six treatment
permutations (itertools order) for the doubled cells, paired with the classes cu, act,
est in that order; then, for each cell in class-major order (cu, act, est) x (line, tone,
black), rng.sample takes its one or two panels from the cell's three (numbered 1, 2, 3).
The draw is uniform over the 118,098 admissible draws (6 permutations of the doubled
cells x 3^9 cell fillings: three ways to take one panel of three, three ways to take two).
The record lists the panels sorted, the doubled cells, the seed, the strata counts and the
Python version (the stdlib random stream is only guaranteed within a Python version).

SEED = 20261104 (the day the plan for amendments A10 to A12 was approved; declared before the draw was run).
"""
import argparse
import itertools
import json
import random
import sys
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
SEED = 20261104
N = 12
CLASSES = ("cu", "act", "est")
TREATMENTS = ("line", "tone", "black")
ALGORITHM = ("random.Random(seed): one treatment permutation (itertools order) for the three doubled "
             "cells, then each cell's panels by rng.sample over its three, cells in class-major order "
             "(draw_ladder_panels.py); uniform over the 118,098 admissible draws (6 permutations of "
             "the doubled cells x 3^9 cell fillings)")


def core_panels():
    return [f"{c}-{t}-{n}" for c in CLASSES for t in TREATMENTS for n in (1, 2, 3)]


def draw(seed=SEED):
    """(12 panels sorted, the 3 doubled cells sorted as '<class>-<treatment>')."""
    rng = random.Random(seed)
    perm = rng.choice(list(itertools.permutations(TREATMENTS)))
    doubled = set(zip(CLASSES, perm))
    picked = []
    for c in CLASSES:
        for t in TREATMENTS:
            k = 2 if (c, t) in doubled else 1
            picked += rng.sample([f"{c}-{t}-{n}" for n in (1, 2, 3)], k)
    return sorted(picked), sorted(f"{c}-{t}" for c, t in doubled)


def strata(panels):
    cls = Counter(p.split("-")[0] for p in panels)
    trt = Counter(p.split("-")[1] for p in panels)
    cell = Counter("-".join(p.split("-")[:2]) for p in panels)
    return {"content_class": {c: cls[c] for c in CLASSES},
            "treatment": {t: trt[t] for t in TREATMENTS},
            "cell": {f"{c}-{t}": cell[f"{c}-{t}"] for c in CLASSES for t in TREATMENTS}}


def record(seed=SEED):
    panels, doubled = draw(seed)
    counts = strata(panels)
    if len(panels) != N or len(set(panels)) != N:
        raise SystemExit(f"draw broke the constraints: {N} distinct panels expected, got {panels}")
    if any(v != 4 for v in counts["content_class"].values()):
        raise SystemExit(f"draw broke the constraints: 4 per content class expected, got {counts}")
    if any(v != 4 for v in counts["treatment"].values()):
        raise SystemExit(f"draw broke the constraints: 4 per treatment expected, got {counts}")
    if any(v < 1 for v in counts["cell"].values()):
        raise SystemExit(f"draw broke the constraints: every cell at least once expected, got {counts}")
    return {"amendment": "A10", "seed": seed, "n": N, "python_version": sys.version.split()[0],
            "pool": "the 27 core panels of dataset/panel-pack.md; the two A1 extension panels excluded",
            "algorithm": ALGORITHM, "doubled_cells": doubled, "panels": panels, "strata_counts": counts}


def main(argv=None):
    ap = argparse.ArgumentParser(description="A10 ladder panel draw")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default=str(OUT / "a10_panels.json"))
    a = ap.parse_args(argv)
    rec = record(a.seed)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n")
    print(f"seed {a.seed} -> {', '.join(rec['panels'])}")
    print(f"doubled cells: {', '.join(rec['doubled_cells'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
