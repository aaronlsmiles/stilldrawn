#!/usr/bin/env python3
"""Opaque codes for A11's human check: clips c21-c60, panels from p15, two attention clips.

    python analysis/human_check2/build_mapping.py

Reads analysis/out/a11_subset.json (the 40 cells A11 drew) and writes, beside this file,
mapping.json (opaque clip code -> cell id, and the two attention clips) and
baseline_mapping.json (opaque panel code -> panel id, and clip code -> panel code). The
codes start after A6's (c01-c20, p01-p14), so no code means two things across the two
studies. Deterministic: random.Random(SEED) shuffles the cells (sorted by public id), then
the distinct panels (sorted by public id), then samples the two attention clips. The rating
app (clip-rating-study) reads both files; each rater's clip order is the app's and is
recorded in that rater's `order`.

SEED = 20261104 (A11's seed, declared in the amendment).
"""
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "out"
SEED = 20261104
FIRST_CLIP, FIRST_PANEL = 21, 15
N_CLIPS, N_ATTENTION = 40, 2
_TANK = re.compile(r"^[a-z]{3}-act-tank-1")


def public_key(cell_id):
    """The id in its public form (the creator-IP panel as `cip-act-tank-1`)."""
    return _TANK.sub("cip-act-tank-1", cell_id)


def panel_of(cell_id):
    return cell_id.rsplit("_", 2)[0]


def build(cells, seed=SEED):
    """(mapping, baseline mapping) for the 40 cells."""
    if len(cells) != N_CLIPS or len(set(cells)) != N_CLIPS:
        raise SystemExit(f"expected {N_CLIPS} distinct cells, got {len(cells)}")
    rng = random.Random(seed)
    order = sorted(cells, key=public_key)
    rng.shuffle(order)
    clip_code = {c: f"c{FIRST_CLIP + i:02d}" for i, c in enumerate(order)}
    panels = sorted({panel_of(c) for c in cells}, key=public_key)
    rng.shuffle(panels)
    panel_code = {p: f"p{FIRST_PANEL + i:02d}" for i, p in enumerate(panels)}
    attention = sorted(rng.sample(sorted(clip_code.values()), N_ATTENTION))
    by_code = sorted(cells, key=lambda c: clip_code[c])
    mapping = {
        "instrument": "A11", "seed": seed, "subset": "analysis/out/a11_subset.json",
        "opaque_to_cell": {clip_code[c]: c for c in by_code},
        "attention_clips": attention,
        "attention_rule": ("each attention clip is shown a second time to every rater and the second "
                           "answers are recorded under `attention` in the rating file; an attention "
                           "item fails at two or more scale points' difference on either question at "
                           "the repeat; a rater who fails both items is excluded before any correlation"),
        "code_scheme": (f"random.Random({seed}): cells sorted by public id, then shuffled; "
                        f"codes from c{FIRST_CLIP} in shuffled order"),
    }
    baseline = {
        "instrument": "A11-baseline", "seed": seed,
        "panel_opaque_to_name": {code: p for p, code in sorted(panel_code.items(), key=lambda kv: kv[1])},
        "clip_to_panel": {clip_code[c]: panel_code[panel_of(c)] for c in by_code},
        "code_scheme": (f"the same generator, after the clips: the distinct panels sorted by public id, "
                        f"then shuffled; codes from p{FIRST_PANEL}"),
    }
    return mapping, baseline


def main():
    cells = json.loads((OUT / "a11_subset.json").read_text())["cells"]
    mapping, baseline = build(cells)
    (HERE / "mapping.json").write_text(json.dumps(mapping, indent=1) + "\n")
    (HERE / "baseline_mapping.json").write_text(json.dumps(baseline, indent=1) + "\n")
    pcodes = list(baseline["panel_opaque_to_name"])
    print(f"clips c{FIRST_CLIP}-c{FIRST_CLIP + N_CLIPS - 1}; panels {pcodes[0]}-{pcodes[-1]} "
          f"({len(pcodes)} panels); attention clips {', '.join(mapping['attention_clips'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
