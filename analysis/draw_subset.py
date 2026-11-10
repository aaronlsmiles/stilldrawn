#!/usr/bin/env python3
"""Draw a stratified human-check subset by fixed seed: §6's frozen 20 (the default) or A11's 40.

    python analysis/draw_subset.py                    # §6, frozen: writes analysis/out/human_subset.json
    python analysis/draw_subset.py --protocol a11     # A11 (the registered command): writes analysis/out/a11_subset.json

Each protocol is a preset in PROTOCOLS: its size, seed, minimums, exclusion list, sort key,
output path and record shape. The protocol name alone reproduces the registered run.
`--n`, `--seed` and the three `--min-*` flags are accepted only when they repeat the preset's
value (so the long form of a registered command still runs); any other value is refused.
`--table`, `--exclude` (A11 only) and `--out` are file locations, which differ between this
repository, the release tree and the tests: they default to the preset and may be pointed
elsewhere, except that `--out` refuses another protocol's default output.

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

Added for A11 (Nov 2026), with the frozen draw unchanged:
  * `--protocol a11`: 40 clips from the same 164 standard cells minus the 20 §6
    drew (A6's rated clips, the §6 record), every engine ≥ 6, every content class
    ≥ 12, every motion class ≥ 12, seed 20261104 (declared in amendment A11).
  * The sort before the shuffle. The frozen draw sorted the private cell ids, in
    which the creator-IP panel's cells come last; the public release renames that
    panel, so a plain sort there would start the shuffle from another order and
    draw other cells. `frozen_key` keeps the frozen order in either tree (the
    creator-IP cells last, everything else as itself), so §6's draw is unchanged
    in this repository (tested byte for byte) and reproduces in the release. A11
    sorts by public id (`public_key`), and writes its cells in that order.
  * Guards: minimums the pool cannot meet are refused before drawing, and the
    reseed loop stops after MAX_RESEEDS seeds.
"""
import argparse
import json
import random
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

OUT = Path(__file__).resolve().parent / "out"
TABLE = OUT / "results_table.json"
SEED = 20260813
N = 20
MIN_ENGINE, MIN_CLASS, MIN_MOTION = 3, 6, 6
ENGINES = ["gen4_turbo", "h3-fal", "gen4.5", "wan22", "ltx23"]
CLASSES = ["cu", "act", "est"]
MOTIONS = ["IDLE", "BURST", "CAMPUSH"]
DIMS = (("engine", ENGINES), ("content_class", CLASSES), ("motion", MOTIONS))
MAX_RESEEDS = 1000
FROZEN_PROTOCOL = "docs/PREREGISTRATION.md §6 (frozen)"
FROZEN_POOL = "164 standard cells (FLINT excluded — see docstring), refused cell naturally absent"
ALGORITHM = "seeded Fisher-Yates over sorted cell_ids + greedy feasibility-checked take (draw_subset.py)"
_CREATOR_IP = re.compile(r"^[a-z]{3}-act-tank-1(?=_)")


def public_key(cell_id):
    """The cell id in its public form (the creator-IP panel as `cip-act-tank-1`)."""
    return _CREATOR_IP.sub("cip-act-tank-1", cell_id)


def frozen_key(cell_id):
    """§6's order in either tree: the creator-IP cells after every other cell, as their private
    ids sorted when the frozen draw was made; every other id sorts as itself."""
    return _CREATOR_IP.sub("~-act-tank-1", cell_id)


def satisfiable(picked, remaining_pool, n=N, mins=(MIN_ENGINE, MIN_CLASS, MIN_MOTION)):
    """Can the mins still be met given picks so far + what's left?"""
    slots = n - len(picked)
    if slots < 0:
        return False
    for (dim, groups), need in zip(DIMS, mins):
        have = Counter(r[dim] for r in picked)
        deficit = sum(max(0, need - have[g]) for g in groups)
        if deficit > slots:
            return False
        for g in groups:
            avail = sum(1 for r in remaining_pool if r[dim] == g)
            if have[g] + avail < need:
                return False
    return True


def draw(pool, seed, n=N, mins=(MIN_ENGINE, MIN_CLASS, MIN_MOTION), key=frozen_key):
    rng = random.Random(seed)
    order = sorted(pool, key=lambda r: key(r["cell_id"]))
    rng.shuffle(order)
    picked = []
    for i, cand in enumerate(order):
        rest = order[i + 1:]
        if len(picked) == n:
            break
        trial = picked + [cand]
        if satisfiable(trial, rest, n, mins):
            picked = trial
    return picked if len(picked) == n else None


def check_feasible(pool, n, mins):
    """Refuse, before any draw, minimums that no draw of n from this pool could meet."""
    if n > len(pool):
        raise SystemExit(f"n = {n} exceeds the pool of {len(pool)} cells")
    for (dim, groups), need in zip(DIMS, mins):
        if need * len(groups) > n:
            raise SystemExit(f"{dim}: {len(groups)} groups x minimum {need} = {need * len(groups)} > n = {n}")
        for g in groups:
            have = sum(1 for r in pool if r[dim] == g)
            if have < need:
                raise SystemExit(f"{dim} {g}: the pool holds {have} cells, fewer than the minimum {need}")


def select(pool, proto):
    """The draw with its reseed loop: (seed used, picked rows). Stops after MAX_RESEEDS seeds."""
    check_feasible(pool, proto.n, proto.mins)
    for seed in range(proto.seed, proto.seed + MAX_RESEEDS):
        picked = draw(pool, seed, proto.n, proto.mins, proto.key)
        if picked is not None:
            return seed, picked
    raise SystemExit(f"no draw met the minimums for seeds {proto.seed}..{proto.seed + MAX_RESEEDS - 1}")


def s6_record(proto, seed_used, pool, excluded, exclude_path, counts, cells):
    out = {
        "protocol": FROZEN_PROTOCOL,
        "drawn": "2026-08-13",
        "seed_declared": proto.seed,
        "seed_used": seed_used,
        "n": proto.n,
        "pool": FROZEN_POOL,
        "algorithm": ALGORITHM,
        "strata_counts": counts,
        "cells": cells,
    }
    # No trailing newline: §6's record was written that way in August 2026 and is frozen byte for byte.
    return json.dumps(out, indent=1)


def a11_record(proto, seed_used, pool, excluded, exclude_path, counts, cells):
    source = Path(exclude_path).name if exclude_path else None
    base = "the 164 of §6 (FLINT excluded, the refused cell absent)"
    pool_text = (f"{len(pool)} standard cells: {base} minus the {len(excluded)} listed in {source}"
                 if excluded else f"{len(pool)} standard cells: {base}; nothing excluded")
    out = {
        "protocol": "docs/PREREGISTRATION.md A11",
        "seed_declared": proto.seed,
        "seed_used": seed_used,
        "n": proto.n,
        "pool": pool_text,
        "excluded_from": source,
        "n_excluded": len(excluded),
        "minimums": dict(zip(("engine", "content_class", "motion"), proto.mins)),
        "sort_key": "public id (draw_subset.public_key), before the shuffle and in this list",
        "algorithm": ALGORITHM,
        "strata_counts": counts,
        "cells": cells,
    }
    # A trailing newline, as an ordinary text file; only §6's frozen record lacks one.
    return json.dumps(out, indent=1) + "\n"


@dataclass(frozen=True)
class Protocol:
    n: int
    seed: int
    mins: tuple  # (engine, content_class, motion)
    exclude: Optional[Path]  # None: the protocol excludes nothing and refuses --exclude
    key: Callable[[str], str]
    out: Path
    record: Callable[..., str]


PROTOCOLS = {
    "s6": Protocol(n=N, seed=SEED, mins=(MIN_ENGINE, MIN_CLASS, MIN_MOTION), exclude=None,
                   key=frozen_key, out=OUT / "human_subset.json", record=s6_record),
    "a11": Protocol(n=40, seed=20261104, mins=(6, 12, 12), exclude=OUT / "human_subset.json",
                    key=public_key, out=OUT / "a11_subset.json", record=a11_record),
}


def load_exclude(path):
    data = json.loads(Path(path).read_text())
    ids = data.get("cells") if isinstance(data, dict) else data
    if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
        raise SystemExit(f"--exclude {path}: expected a list of cell ids, or an object with a 'cells' list")
    return ids


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Stratified human-check subset by fixed seed")
    ap.add_argument("--protocol", choices=sorted(PROTOCOLS), default="s6",
                    help="s6: the frozen §6 draw and its record (default); a11: amendment A11's draw")
    ap.add_argument("--n", type=int, help="must equal the protocol's preset")
    ap.add_argument("--seed", type=int, help="must equal the protocol's preset")
    ap.add_argument("--min-engine", type=int, help="must equal the protocol's preset")
    ap.add_argument("--min-class", type=int, help="must equal the protocol's preset")
    ap.add_argument("--min-motion", type=int, help="must equal the protocol's preset")
    ap.add_argument("--exclude", default=None,
                    help="a11 only (default: the §6 record): a list of cell ids, or an object with a 'cells' list")
    ap.add_argument("--table", default=str(TABLE))
    ap.add_argument("--out", default=None, help="default: the protocol's own output")
    a = ap.parse_args(argv)
    proto = PROTOCOLS[a.protocol]
    preset = {"n": proto.n, "seed": proto.seed, "min_engine": proto.mins[0],
              "min_class": proto.mins[1], "min_motion": proto.mins[2]}
    for name, want in preset.items():
        got = getattr(a, name)
        if got is not None and got != want:
            flag = "--" + name.replace("_", "-")
            raise SystemExit(f"{flag} {got}: protocol {a.protocol} is registered with {want}; presets cannot be changed")
    if proto.exclude is None and a.exclude is not None:
        raise SystemExit(f"--exclude: protocol {a.protocol} excludes nothing")
    exclude = a.exclude if a.exclude is not None else proto.exclude
    out = Path(a.out) if a.out is not None else proto.out
    for other, p in PROTOCOLS.items():
        if other != a.protocol and out.resolve() == p.out.resolve():
            raise SystemExit(f"--out {out}: that is protocol {other}'s record; refusing to overwrite it")
    return proto, a.table, exclude, out


def main(argv=None):
    proto, table, exclude_path, out_path = parse_args(argv)
    rows = json.loads(Path(table).read_text())
    pool = [r for r in rows if r["motion"] != "FLINT"]
    assert len(pool) == 164, f"expected 164 standard cells, got {len(pool)}"
    excluded = []
    if exclude_path is not None:
        excluded = load_exclude(exclude_path)
        ids = {r["cell_id"] for r in pool}
        unknown = [x for x in excluded if x not in ids]
        if unknown:
            raise SystemExit(f"--exclude: not standard cells of the table: {unknown}")
        # A11 excludes exactly §6's draw. Whatever file is named, its ids (in public form) must be
        # the §6 draw of this same table, so no other list can yield a record labelled A11.
        _, s6_picked = select(pool, PROTOCOLS["s6"])
        if sorted(map(public_key, excluded)) != sorted(public_key(r["cell_id"]) for r in s6_picked):
            raise SystemExit(f"--exclude {exclude_path}: its cells are not §6's draw from {table}")
        drop = set(excluded)
        pool = [r for r in pool if r["cell_id"] not in drop]

    seed, picked = select(pool, proto)
    picked.sort(key=lambda r: proto.key(r["cell_id"]))

    counts = {dim: dict(Counter(r[dim] for r in picked)) for dim, _ in DIMS}
    for (dim, groups), need in zip(DIMS, proto.mins):
        for g in groups:
            assert counts[dim].get(g, 0) >= need, (dim, g)

    cells = [r["cell_id"] for r in picked]
    out_path.write_text(proto.record(proto, seed, pool, excluded, exclude_path, counts, cells))
    print(f"seed {seed} -> {proto.n} cells")
    print(json.dumps(counts, indent=1))
    for c in cells:
        print(" ", c)


if __name__ == "__main__":
    main()
