#!/usr/bin/env python3
"""A10, motion by construction: is line stability a function of how much the clip moves?

*** CONFIRMATORY (amendment A10). ***

    python analysis/a10_ladder.py                       # refuses until A10 is public
    python analysis/a10_ladder.py --manipulation-only   # the motion medians by level, nothing else
    python analysis/a10_ladder.py --fixtures DIR        # a synthetic tree (tests); no registration check

Inputs: runs/metrics-ladder/<cell>.json (inkstab, frozen definitions) and
runs/metrics-motion-ladder/<cell>.json (motion.py, A6's definitions) for the cells
`ladder-<panel>_<level>_<tag>` of Wan 2.2, LTX-2.3 and Gen-4.5; refused cells from
runs/manifest.jsonl. Realised motion (headline_median_norm) is the regressor; the prompt
level is only the manipulation.

Cells: the expected cells are those of analysis/out/a10_cells.json (the registered cell
list); without that file (synthetic trees), every ladder cell with a metrics file or a
refusal. Per engine, missing = expected - refused - complete, where a complete cell has a
finite motion value and a finite mean chamfer. A missing cell is never dropped silently:
it is listed, and every verdict it could touch (that engine's A10-H1; A10-H2 when the engine is
Gen-4.5 or Wan 2.2) reads "incomplete: N cells missing" instead. Refused cells (prereg
§5) are listed and are not missing.

Manipulation check, per engine, read first: the median realised motion per level over
every non-refused cell with a motion value (the same rows in the full run and in
--manipulation-only). It passes when at least 2 of the 3 steps STILL -> LOW -> MID -> HIGH
rise and HIGH's median exceeds STILL's. An engine that fails it reads "manipulation
failed" (numbers still reported, no verdict).

A10-H1, per engine: Spearman rho(realised motion, mean chamfer vs frame 0) > 0, one-sided,
alpha 0.05, Monte Carlo permutation p = (k + 1) / (B + 1) over B = 10,000 permutations of
the chamfer ranks, numpy.random.default_rng(20261104) fresh for each engine and metric.
Secondary, without a verdict: the same for edge |slope| (abs_slope_norm) and style
terminal. Every rho carries a percentile bootstrap 95% CI over cells (B = 10,000, the
same seed).

A10-H1 within panel, secondary, without a verdict (how much of the association lies
between panels): per engine, over the cells with motion and mean chamfer, the same pooled
rho with a one-sided p from B = 10,000 permutations of mean chamfer inside each panel
(12 strata of 4 levels), and the within-panel rho (the correlation of ranks taken inside
each panel, centred on the panel's mean rank) with its one-sided p from the same
permutations; numpy.random.default_rng(20261104), fresh per engine.

The labels are A10-H1 and A10-H2 because A9 uses H1 and H2 in the same pre-registration.

A10-H2: the band is the overlap of Gen-4.5's and Wan 2.2's realised-motion IQRs (np.percentile,
linear) over their ladder cells; g = log2(median chamfer Gen-4.5 / median chamfer Wan 2.2),
g_band over the cells inside the band (inclusive at both edges), g_whole over every cell of
the two engines with a chamfer value. Readings, in this order: incomplete if a cell of
either engine is missing; not testable, Wan 2.2 does not move on request, if Wan's HIGH
upper quartile is below every other engine's STILL median (the engines compared are
recorded); not testable if either engine has fewer than 8 cells; undefined if the Wan 2.2
check cannot be made (no Wan HIGH cells, or another engine without STILL cells); not
testable if fewer than 8 cells of either engine are in the band (band too thin); not
testable if g_whole <= 0 or undefined (no whole-ladder gap); undefined if g_band is
undefined (a median chamfer in the band is not positive); supported if
g_band <= 0.5 * g_whole; not supported otherwise. Reported beside it, without a verdict:
the band's panel make-up (in-band cells per panel, for each of the two engines). A9's masked result is a different
condition and is never pooled with this one.

Model version and the same-machine read-out (decided 4 Nov 2026), reported without changing any
reading: per engine, the distinct model_version strings over its expected, non-refused cells
(runs/manifest.jsonl, the last line of a cell id wins) and the count of such cells without a
line. gen_video.py appends the machine's name (STILLDRAWN_HW) to a local engine's model_version
as ` [<name>]`; on Wan 2.2 and LTX-2.3 the distinct names are reported (a line without a name
counts as "(not recorded)"), with `hardware_mixed` true when there is more than one, and a
note in the Markdown. Gen-4.5 is hosted: `hardware` and `hardware_mixed` are None.

Further engines (A15 Kling, A16 Midjourney), CONFIRMATORY for A10-H1 only, each reported
under its own amendment's heading (ruled 8 Nov 2026): never in A10's summary, its tables,
its figure, A10-H2 or its kill rules, so A10's outputs are the same with or without them. An arm
is read when its cell list exists (analysis/out/a15_cells.json, a16_cells.json: the shape of
a10_cells.json, from harness/ladder.py build --arm). Its status, in this order: outside
--fixtures, "not analysed: A15 not public" (A16 likewise) until its amendment is in the PUBLIC
pre-registration (harness/registration.py); "not run: <the scout's logged reading>" when the
scout's reading (analysis/out/a15_scout.json or a16_scout.json, {"reading": ...}, written when
the scout is read, A15.5) is one of A15.5's failure readings; when it is the exact pass reading
A15.5 or A16.7 registers, or there is no reading yet, it is analysed as A10 analyses its
three engines (coverage, the manipulation check, A10-H1 with A10's reading strings, its
secondaries and the within-panel split, model versions; a fresh default_rng(20261104) per
metric), and its reading is its A10-H1 reading ("incomplete: N cells missing" until its cells
exist). Any other reading is refused. The readings are harness/ladder.py's (ARMS, SCOUT_FAILED),
the same that gate an arm's run. An arm's cells found in the tree without its cell list are
listed as not analysed.

--fixtures refuses the repository itself, any folder under it, and any folder inside a
private tree (one carrying analysis/adherence/private-terms.txt), so it can never read the
real runs/ or write the real analysis/out/ past the registration check.

Outputs: analysis/out/a10_ladder.json, a10_ladder.md, figures/a10_ladder.png.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "harness"))
import rank_stats as rs  # noqa: E402
from registration import is_public, require_public  # noqa: E402
from ladder import ARMS as RUN_ARMS, scout_failed  # noqa: E402  (the registered scout readings, one source)

SEED = 20261104
B = 10_000
ALPHA = 0.05
LEVELS = ("STILL", "LOW", "MID", "HIGH")
ENGINES = ("wan22", "ltx23", "gen45")                 # frozen league order among the three; never a rank
NAMES = {"wan22": "Wan 2.2", "ltx23": "LTX-2.3", "gen45": "Gen-4.5"}
# Further engines: A10-H1 only, each under its own amendment, never in A10's summary or verdicts.
# The scout's file, rule and exact pass reading come from harness/ladder.py's ARMS, so the run
# gate and this analysis accept the same registered readings (A15.5, A16.7) and no other.
ARMS = {tag: {"amendment": RUN_ARMS[engine]["amendment"], "name": name,
              "scout_rule": RUN_ARMS[engine]["scout_rule"], "cells": Path(RUN_ARMS[engine]["cells"]),
              "scout": Path(RUN_ARMS[engine]["scout"]), "scout_passed": RUN_ARMS[engine]["scout_passed"]}
        for tag, engine, name in (("kling4", "kling_4", "Kling"), ("mjv", "midjourney", "Midjourney"))}
TAGS = ENGINES + tuple(ARMS)
METRICS = {"chamfer": "mean chamfer vs frame 0 (px)", "edge": "edge |slope| (abs_slope_norm)",
           "style": "style drift, terminal"}
MIN_RISING = 2
BAND_MIN = 8
GAP = ("gen45", "wan22")                              # A10-H2: Gen-4.5 over Wan 2.2
CELLS_FILE = Path("analysis") / "out" / "a10_cells.json"
PRIVATE_MARKER = Path("analysis") / "adherence" / "private-terms.txt"
LOCAL = ("wan22", "ltx23")                           # local engines: their model_version names the machine
HW_RE = re.compile(r" \[([^\[\]]+)\]$")      # gen_video.py: model_version + " [<STILLDRAWN_HW>]"
NO_HW = "(not recorded)"


def num(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def fmt(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def cells_phrase(n):
    return f"{n} cell{'' if n == 1 else 's'} missing"


def parse_cell(stem, tags=ENGINES):
    """`ladder-<panel>_<level>_<tag>` -> (panel, LEVEL, tag) for a tag in `tags`, or None."""
    if not stem.startswith("ladder-"):
        return None
    parts = stem[len("ladder-"):].rsplit("_", 2)
    if len(parts) != 3 or parts[1].upper() not in LEVELS or parts[2] not in tags:
        return None
    return parts[0], parts[1].upper(), parts[2]


def load_refused(root):
    m = Path(root) / "runs" / "manifest.jsonl"
    if not m.exists():
        return []
    out = set()
    for line in m.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("refused") and str(r.get("cell_id", "")).startswith("ladder-"):
                out.add(r["cell_id"])
    return sorted(out)


def model_versions(root):
    """{cell_id: model_version} from runs/manifest.jsonl; the last line of a cell id wins."""
    m = Path(root) / "runs" / "manifest.jsonl"
    out = {}
    if m.exists():
        for line in m.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("cell_id"):
                    out[r["cell_id"]] = r.get("model_version")
    return out


def hardware_of(model_version):
    """The machine name gen_video.py appended to a local model_version, else NO_HW."""
    m = HW_RE.search(model_version or "")
    return m.group(1) if m else NO_HW


def versions(engine, cells, mv):
    """Distinct model versions over an engine's expected, non-refused cells; on a local engine,
    the distinct machine names and the hardware_mixed flag (None on Gen-4.5). No verdict."""
    got = [mv.get(c) for c in cells]
    mvs = [v for v in got if v is not None]
    hw = sorted({hardware_of(v) for v in mvs}) if engine in LOCAL else None
    return {"model_versions": sorted(set(mvs)), "n_cells_without_manifest_line": sum(v is None for v in got),
            "hardware": hw, "hardware_mixed": None if hw is None else len(hw) > 1}


def tree_cells(root, tags=ENGINES):
    """Every ladder cell of `tags` with a motion or inkstab file in the tree."""
    found = set()
    for d in ("metrics-motion-ladder", "metrics-ladder"):
        for p in (Path(root) / "runs" / d).glob("ladder-*.json"):
            if parse_cell(p.stem, tags):
                found.add(p.stem)
    return found


def expected_cells(root, refused):
    """({engine: sorted cell ids}, source). The registered list when present, else the tree's."""
    root = Path(root)
    exp = {e: set() for e in ENGINES}
    p = root / CELLS_FILE
    if p.exists():
        for ids in json.loads(p.read_text())["cells"].values():
            for c in ids:
                parsed = parse_cell(c)
                if parsed is None:
                    raise SystemExit(f"{CELLS_FILE}: unrecognised ladder cell id {c!r}")
                exp[parsed[2]].add(c)
        source = str(CELLS_FILE)
    else:
        for c in tree_cells(root) | {c for c in refused if parse_cell(c)}:
            exp[parse_cell(c)[2]].add(c)
        source = "the tree (no analysis/out/a10_cells.json): every ladder cell with a metrics file or a refusal"
    return {e: sorted(v) for e, v in exp.items()}, source


def load(root, expected, refused, motion_only=False):
    """{engine tag: [{cell, panel, level, motion, chamfer, edge, style}]} over the expected,
    non-refused cells that have a motion JSON. Without an inkstab JSON (or with motion_only),
    the drift values are None; coverage() counts such cells as missing."""
    root = Path(root)
    refused = set(refused)
    data = {e: [] for e in expected}
    for e in expected:
        for cell in expected[e]:
            mp = root / "runs" / "metrics-motion-ladder" / f"{cell}.json"
            if cell in refused or not mp.exists():
                continue
            panel, level, _ = parse_cell(cell, TAGS)
            rec = {"cell": cell, "panel": panel, "level": level,
                   "motion": num(json.loads(mp.read_text())["motion"]["headline_median_norm"]),
                   "chamfer": None, "edge": None, "style": None}
            ip = root / "runs" / "metrics-ladder" / f"{cell}.json"
            if not motion_only and ip.exists():
                m = json.loads(ip.read_text())["metrics"]
                rec["chamfer"] = num(m["line_drift"]["vs_frame0"]["chamfer_px"]["mean"])
                rec["edge"] = num(m["edge_decay"]["abs_slope_norm"])
                rec["style"] = num(m["style_drift"].get("terminal"))
            data[e].append(rec)
    return data


def coverage(expected, data, refused, unexpected=(), motion_only=False):
    """Per engine: expected, refused, complete and the missing cells (by what is missing)."""
    out = {}
    for e in expected:
        exp = set(expected[e])
        ref = sorted(c for c in refused if c in exp)
        need = exp - set(ref)
        have_motion = {r["cell"] for r in data[e] if r["motion"] is not None}
        complete = have_motion if motion_only else {r["cell"] for r in data[e]
                                                    if r["motion"] is not None and r["chamfer"] is not None}
        miss_motion = sorted(need - have_motion)
        miss_ink = [] if motion_only else sorted((need & have_motion) - complete)
        out[e] = {"expected": len(exp), "refused": ref, "complete": len(need & complete),
                  "missing": len(miss_motion) + len(miss_ink),
                  "missing_motion": miss_motion, "missing_inkstab": miss_ink,
                  "unexpected_not_analysed": sorted(c for c in unexpected if parse_cell(c, TAGS)[2] == e)}
    return out


def paired(rows, key):
    pts = [(r["motion"], r[key]) for r in rows if r.get("motion") is not None and r.get(key) is not None]
    return (np.array([p[0] for p in pts], dtype=float), np.array([p[1] for p in pts], dtype=float))


def correlate(rows, key, seed=SEED, b=B):
    x, y = paired(rows, key)
    rho = rs.spearman(x, y)
    out = {"n": int(x.size), "rho": rho, "p_perm_one_sided": None, "ci95": None, "bootstrap_n": 0}
    if rho is not None:
        out["p_perm_one_sided"] = rs.perm_p(x, y, rho, seed, b, "greater")
        boots = rs.bootstrap(x, y, seed, b)
        out["ci95"], out["bootstrap_n"] = rs.percentile_ci(boots), int(boots.size)
    return out


def manipulation(rows):
    med = {}
    for lv in LEVELS:
        v = [r["motion"] for r in rows if r["level"] == lv and r["motion"] is not None]
        med[lv] = float(np.median(v)) if v else None
    steps = list(zip(LEVELS, LEVELS[1:]))
    rising = sum(1 for a, b in steps if med[a] is not None and med[b] is not None and med[b] > med[a])
    passed = (rising >= MIN_RISING and med["STILL"] is not None and med["HIGH"] is not None
              and med["HIGH"] > med["STILL"])
    return {"median_motion_by_level": med, "n": sum(1 for r in rows if r["motion"] is not None),
            "rising_steps": rising, "of_steps": len(steps),
            "rule": f"at least {MIN_RISING} of {len(steps)} steps rise and HIGH > STILL", "passed": bool(passed)}


def h1(rows, manip, cov, seed=SEED, b=B):
    res = {m: correlate(rows, m, seed, b) for m in METRICS}
    c = res["chamfer"]
    if cov["missing"]:
        reading = f"incomplete: {cells_phrase(cov['missing'])}"
    elif not rows:
        reading = "no cells"
    elif not manip["passed"]:
        reading = "manipulation failed"
    elif c["rho"] is None:
        reading = "undefined (fewer than 4 cells, or no variation)"
    elif c["rho"] > 0 and c["p_perm_one_sided"] <= ALPHA:
        reading = "supported"
    else:
        reading = "null"
    return {"reading": reading, "per_metric": res}


def h1_within_panel(rows, seed=SEED, b=B):
    """Secondary, no verdict: the mean-chamfer rho split into between and within panels."""
    pts = [r for r in rows if r["motion"] is not None and r["chamfer"] is not None]
    out = rs.within_strata([r["motion"] for r in pts], [r["chamfer"] for r in pts],
                           [r["panel"] for r in pts], seed, b)
    return {"metric": "chamfer", "stratified_by": "panel", "verdict": "none (secondary)", **out}


def panel_counts(rows, band_rows):
    """{panel: in-band cells} over every panel of `rows`, zeros kept."""
    counts = {p: 0 for p in sorted({r["panel"] for r in rows})}
    for r in band_rows:
        counts[r["panel"]] += 1
    return counts


def log2_gap(xa, xw):
    if not xa or not xw:
        return None
    ma = float(np.median([r["chamfer"] for r in xa]))
    mw = float(np.median([r["chamfer"] for r in xw]))
    return math.log2(ma / mw) if ma > 0 and mw > 0 else None


def h2(data, cov):
    a, w = GAP
    out = {"pair": [NAMES[a], NAMES[w]],
           "statistic": "g = log2(median chamfer Gen-4.5 / median chamfer Wan 2.2)",
           "band_rule": "overlap of the two engines' realised-motion IQRs over their ladder cells, inclusive"}
    ga = [r for r in data[a] if r["motion"] is not None and r["chamfer"] is not None]
    gw = [r for r in data[w] if r["motion"] is not None and r["chamfer"] is not None]
    wan_high = [r["motion"] for r in data[w] if r["level"] == "HIGH" and r["motion"] is not None]
    stills = {e: [r["motion"] for r in data[e] if r["level"] == "STILL" and r["motion"] is not None]
              for e in ENGINES if e != w}
    still_medians = {NAMES[e]: float(np.median(v)) for e, v in stills.items() if v}
    lacking = [NAMES[e] for e, v in stills.items() if not v]
    q75 = float(np.percentile(wan_high, 75)) if wan_high else None
    out.update({"wan_high_q75": q75, "other_still_medians": still_medians,
                "wan_compared_with": sorted(still_medians), "wan_check_lacking_still": lacking})
    wan_defined = q75 is not None and not lacking
    kill = wan_defined and q75 < min(still_medians.values())
    # g_whole: every cell of the two engines with a chamfer value, whatever its motion value
    g_whole = log2_gap([r for r in data[a] if r["chamfer"] is not None],
                       [r for r in data[w] if r["chamfer"] is not None])
    out.update({"n_whole": {NAMES[a]: sum(r["chamfer"] is not None for r in data[a]),
                            NAMES[w]: sum(r["chamfer"] is not None for r in data[w])},
                "g_whole": g_whole})
    band_a = band_w = None
    if len(ga) >= BAND_MIN and len(gw) >= BAND_MIN:
        qa = [float(q) for q in np.percentile([r["motion"] for r in ga], [25, 75])]
        qw = [float(q) for q in np.percentile([r["motion"] for r in gw], [25, 75])]
        lo, hi = max(qa[0], qw[0]), min(qa[1], qw[1])
        band_a = [r for r in ga if lo <= r["motion"] <= hi]
        band_w = [r for r in gw if lo <= r["motion"] <= hi]
        out.update({"iqr": {NAMES[a]: qa, NAMES[w]: qw}, "band": [lo, hi] if lo <= hi else None,
                    "n_band": {NAMES[a]: len(band_a), NAMES[w]: len(band_w)},
                    "band_panels": {NAMES[a]: panel_counts(ga, band_a), NAMES[w]: panel_counts(gw, band_w)},
                    "g_band": log2_gap(band_a, band_w)})
    missing = cov[a]["missing"] + cov[w]["missing"]
    if missing:
        reading = f"incomplete: {cells_phrase(missing)} (Gen-4.5 and Wan 2.2)"
    elif kill:
        reading = "not testable: Wan 2.2 does not move on request"
    elif band_a is None:
        reading = "not testable: fewer than 8 cells of an engine"
    elif not wan_defined:
        why = "no Wan 2.2 HIGH cells" if q75 is None else f"no STILL cells for {', '.join(lacking)}"
        reading = f"undefined: the Wan 2.2 motion check cannot be made ({why})"
    elif len(band_a) < BAND_MIN or len(band_w) < BAND_MIN:
        reading = "not testable: band too thin (fewer than 8 cells of an engine in the common band)"
    elif g_whole is None or g_whole <= 0:
        reading = "not testable: no whole-ladder gap (g_whole <= 0)"
    elif out["g_band"] is None:
        reading = "undefined: g_band (a median chamfer in the band is not positive)"
    elif out["g_band"] <= 0.5 * g_whole:
        reading = "supported"
    else:
        reading = "not supported"
    out["reading"] = reading
    return out


def plottable(data):
    """({engine: [(motion, chamfer)]} with both positive, count of cells with both values but
    one of them not positive): the log axes cannot show those, so they are counted, not lost."""
    pts, dropped = {}, 0
    for e in ENGINES:
        pts[e] = []
        for r in data[e]:
            if r["motion"] is None or r["chamfer"] is None:
                continue
            if r["motion"] > 0 and r["chamfer"] > 0:
                pts[e].append((r["level"], r["motion"], r["chamfer"]))
            else:
                dropped += 1
    return pts, dropped


def arm_cells(root, tag):
    """An arm's registered cell ids, from its own cell list."""
    f = ARMS[tag]["cells"]
    ids = set()
    for group in json.loads((Path(root) / f).read_text())["cells"].values():
        for c in group:
            if parse_cell(c, (tag,)) is None:
                raise SystemExit(f"{f}: unrecognised {tag} ladder cell id {c!r}")
            ids.add(c)
    return sorted(ids)


def arm_status(root, tag, public=None):
    """(status, the scout's logged reading or None). `public` is None under --fixtures (no
    registration check); otherwise a function telling whether an amendment is public."""
    arm = ARMS[tag]
    if public is not None and not public(arm["amendment"]):
        return f"not analysed: {arm['amendment']} not public", None
    sp = Path(root) / arm["scout"]
    if not sp.exists():
        return "analysed", None
    reading = json.loads(sp.read_text()).get("reading")
    if reading == arm["scout_passed"]:
        return "analysed", reading
    if isinstance(reading, str) and scout_failed(reading):
        return f"not run: {reading}", reading
    raise SystemExit(f"{arm['scout']}: unrecognised scout reading {reading!r}: not {arm['scout_passed']!r} nor "
                     f"one of {arm['scout_rule']}'s failure readings")


def arm_result(root, tag, refused, mv, public=None, seed=SEED, b=B):
    """One arm, under its own amendment: its status and, when analysed, A10-H1 and the rest."""
    arm = ARMS[tag]
    ids = arm_cells(root, tag)
    status, scout = arm_status(root, tag, public)
    found = tree_cells(root, (tag,)) | {c for c in refused if parse_cell(c, (tag,))}
    out = {"name": arm["name"], "amendment": arm["amendment"], "scout_rule": arm["scout_rule"],
           "label": f"A10-H1 ({arm['name']}, {arm['amendment']})", "expected_from": str(arm["cells"]),
           "in_A10_H2": False, "scout_reading": scout, "status": status}
    if status != "analysed":
        out.update(reading=status, cells_found_not_analysed=sorted(found))
        return out
    expected = {tag: ids}
    data = load(root, expected, refused)
    cov = coverage(expected, data, refused, sorted(found - set(ids)))
    manip = manipulation(data[tag])
    h = h1(data[tag], manip, cov[tag], seed, b)
    refused_set = set(refused)
    out.update(reading=h["reading"], n_cells=len(data[tag]), cells=cov[tag], manipulation=manip,
               **{"A10-H1": h, "A10-H1-within-panel": h1_within_panel(data[tag], seed, b)},
               **versions(tag, [c for c in ids if c not in refused_set], mv))
    return out


def run(root, seed=SEED, b=B, public=None):
    """(result, rows): the rows are what the figure draws (A10's three engines only)."""
    root = Path(root)
    all_refused = load_refused(root)
    refused = [c for c in all_refused if parse_cell(c)]      # an arm's refusals stay in its own section
    expected, source = expected_cells(root, refused)
    exp_all = {c for v in expected.values() for c in v}
    unexpected = sorted(tree_cells(root) - exp_all)
    data = load(root, expected, refused)
    cov = coverage(expected, data, refused, unexpected)
    mv = model_versions(root)
    refused_set = set(refused)
    engines = {}
    for e in ENGINES:
        manip = manipulation(data[e])
        engines[e] = {"name": NAMES[e], "n_cells": len(data[e]), "cells": cov[e], "manipulation": manip,
                      "A10-H1": h1(data[e], manip, cov[e], seed, b),
                      "A10-H1-within-panel": h1_within_panel(data[e], seed, b),
                      **versions(e, [c for c in expected[e] if c not in refused_set], mv)}
    _, dropped = plottable(data)
    res = {"amendment": "A10", "status": "confirmatory", "seed": seed, "permutations": b,
           "bootstrap": b, "alpha": ALPHA, "expected_from": source, "refused": refused,
           "engines": engines, "A10-H2": h2(data, cov), "figure_not_plotted_nonpositive": dropped}
    arms = {t: arm_result(root, t, all_refused, mv, public, seed, b) for t in ARMS
            if (root / ARMS[t]["cells"]).exists()}
    if arms:
        res["arms"] = arms
    no_list = sorted(c for t in ARMS if t not in arms
                     for c in tree_cells(root, (t,)) | {c for c in all_refused if parse_cell(c, (t,))})
    if no_list:
        res["not_analysed_no_cell_list"] = no_list
    return res, data


def analyse(root, seed=SEED, b=B, public=None):
    return run(root, seed, b, public)[0]


def arms_markdown(res):
    """The further engines, under their own heading after A10's (empty when there are none)."""
    arms, no_list = res.get("arms", {}), res.get("not_analysed_no_cell_list", [])
    if not arms and not no_list:
        return []
    L = ["## Further engines (A15, A16): A10-H1 only, under their own amendments", "",
         "Never part of A10's summary or verdicts: A10-H2 and its kill rules read A10's three engines only.", ""]
    for a in arms.values():
        L += [f"### {a['label']}", "", f"- Reading: **{a['reading']}**", f"- Cell list: {a['expected_from']}"]
        if a["scout_reading"]:
            L.append(f"- Scout ({a['scout_rule']}): {a['scout_reading']}")
        if a["status"] != "analysed":
            if a["cells_found_not_analysed"]:
                L.append(f"- Cells found, not analysed: {', '.join(a['cells_found_not_analysed'])}.")
            L.append("")
            continue
        c, m = a["cells"], a["manipulation"]
        L.append(f"- Cells: expected {c['expected']}, refused {len(c['refused'])}, complete {c['complete']}, "
                 f"missing {c['missing']}.")
        for key, what in (("missing_motion", "missing a motion value"), ("missing_inkstab", "missing a mean chamfer"),
                          ("unexpected_not_analysed", "not in its cell list (not analysed)"), ("refused", "refused")):
            if c[key]:
                L.append(f"  - {what}: {', '.join(c[key])}.")
        med = m["median_motion_by_level"]
        L.append("- Manipulation check (read first): " + ", ".join(f"{lv} {fmt(med[lv], 5)}" for lv in LEVELS)
                 + f"; {m['rising_steps']} of {m['of_steps']} steps rise; {'passed' if m['passed'] else 'failed'}.")
        L += ["", "| Metric | n | rho | p (one-sided) | 95% CI | A10-H1 |", "|---|---|---|---|---|---|"]
        for k, label in METRICS.items():
            r = a["A10-H1"]["per_metric"][k]
            ci = "n/a" if not r["ci95"] else f"[{r['ci95'][0]:.2f}, {r['ci95'][1]:.2f}]"
            p = "n/a" if r["p_perm_one_sided"] is None else f"{r['p_perm_one_sided']:.4f}"
            verdict = a["A10-H1"]["reading"] if k == "chamfer" else "secondary"
            L.append(f"| {label} | {r['n']} | {fmt(r['rho'], 2)} | {p} | {ci} | {verdict} |")
        w = a["A10-H1-within-panel"]
        pw = ["n/a" if v is None else f"{v:.4f}" for v in (w["p_pooled_within_strata_perm"], w["p_within"])]
        L += ["", f"Within panel (secondary, no verdict): n {w['n']}, panels {w['strata']}, pooled rho "
                  f"{fmt(w['rho'], 2)} (p {pw[0]}), within-panel rho {fmt(w['rho_within'], 2)} (p {pw[1]}).",
              f"Model versions: {'; '.join(a['model_versions']) or 'n/a'}"
              + (f" ({a['n_cells_without_manifest_line']} cells without a manifest line)"
                 if a["n_cells_without_manifest_line"] else "") + ".", ""]
    if no_list:
        L += [f"Cells of a further engine without its cell list (not analysed): {', '.join(no_list)}.", ""]
    return L


def markdown(res):
    L = ["# A10 motion ladder: line stability as a function of realised motion", "",
         "**Confirmatory (amendment A10).** Realised motion is measured (motion.py, A6's definitions), "
         "never assumed from the prompt level. The frozen league and the §8 test are unchanged.", "",
         "## Cells", "", f"Expected cells: {res['expected_from']}.", "",
         "| Engine | expected | refused | complete | missing |", "|---|---|---|---|---|"]
    for e in ENGINES:
        c = res["engines"][e]["cells"]
        L.append(f"| {NAMES[e]} | {c['expected']} | {len(c['refused'])} | {c['complete']} | {c['missing']} |")
    L.append("")
    for e in ENGINES:
        c = res["engines"][e]["cells"]
        if c["missing_motion"]:
            L.append(f"- {NAMES[e]}, missing a motion value: {', '.join(c['missing_motion'])}.")
        if c["missing_inkstab"]:
            L.append(f"- {NAMES[e]}, missing a mean chamfer: {', '.join(c['missing_inkstab'])}.")
        if c["unexpected_not_analysed"]:
            L.append(f"- {NAMES[e]}, not in the registered list (not analysed): "
                     f"{', '.join(c['unexpected_not_analysed'])}.")
    L += ["", "Model versions (runs/manifest.jsonl, expected non-refused cells; reported only, no verdict "
              "depends on them):", ""]
    for e in ENGINES:
        r = res["engines"][e]
        mvs = "; ".join(r["model_versions"]) or "n/a"
        line = f"- {NAMES[e]}: {mvs}"
        if r["n_cells_without_manifest_line"]:
            line += f" ({r['n_cells_without_manifest_line']} cells without a manifest line)"
        if r["hardware"] is not None:
            line += f"; machine: {'; '.join(r['hardware']) or 'n/a'}"
        L.append(line + ".")
        if r["hardware_mixed"]:
            L.append(f"  **Note, hardware mixed:** {NAMES[e]}'s cells carry more than one machine name, so "
                     "the same-machine claim does not hold for it. No reading changes.")
    L += ["", "## Manipulation check (read first)", "",
          "| Engine | STILL | LOW | MID | HIGH | rising steps | passed |", "|---|---|---|---|---|---|---|"]
    for e in ENGINES:
        m = res["engines"][e]["manipulation"]
        med = m["median_motion_by_level"]
        L.append(f"| {NAMES[e]} | " + " | ".join(fmt(med[lv], 5) for lv in LEVELS)
                 + f" | {m['rising_steps']} of {m['of_steps']} | {'yes' if m['passed'] else 'no'} |")
    L += ["", "## A10-H1: rho(realised motion, drift), per engine", "",
          f"One-sided permutation p (B = {res['permutations']:,}); bootstrap 95% CI. "
          "Only mean chamfer carries the verdict.", "",
          "| Engine | Metric | n | rho | p (one-sided) | 95% CI | A10-H1 |", "|---|---|---|---|---|---|---|"]
    for e in ENGINES:
        h = res["engines"][e]["A10-H1"]
        for k, label in METRICS.items():
            c = h["per_metric"][k]
            ci = "n/a" if not c["ci95"] else f"[{c['ci95'][0]:.2f}, {c['ci95'][1]:.2f}]"
            p = "n/a" if c["p_perm_one_sided"] is None else f"{c['p_perm_one_sided']:.4f}"
            verdict = h["reading"] if k == "chamfer" else "secondary"
            L.append(f"| {NAMES[e]} | {label} | {c['n']} | {fmt(c['rho'], 2)} | {p} | {ci} | {verdict} |")
    L += ["", "### A10-H1 within panel (secondary, no verdict)", "",
          f"Mean chamfer only. Both p are one-sided, from the same B = {res['permutations']:,} permutations "
          "of mean chamfer inside each panel. A pooled rho that these permutations reproduce (a large p), "
          "beside a within-panel rho near 0, is an association between panels rather than within them.", "",
          "| Engine | n | panels | pooled rho | p (within-panel permutation) | within-panel rho | p |",
          "|---|---|---|---|---|---|---|"]
    for e in ENGINES:
        w = res["engines"][e]["A10-H1-within-panel"]
        pw = ["n/a" if v is None else f"{v:.4f}" for v in (w["p_pooled_within_strata_perm"], w["p_within"])]
        L.append(f"| {NAMES[e]} | {w['n']} | {w['strata']} | {fmt(w['rho'], 2)} | {pw[0]} | "
                 f"{fmt(w['rho_within'], 2)} | {pw[1]} |")
    gaps = [f"{NAMES[e]} ({cells_phrase(res['engines'][e]['cells']['missing'])})"
            for e in ENGINES if res["engines"][e]["cells"]["missing"]]
    if gaps:
        L += ["", f"Missing cells: {', '.join(gaps)}. These rows use the cells present; a panel short "
                  "of a level contributes fewer pairs, and the A10-H1 verdict is withheld (see Cells)."]
    g = res["A10-H2"]
    L += ["", "## A10-H2: the Gen-4.5 / Wan 2.2 gap on motion-matched cells", "",
          f"- Reading: **{g['reading']}**"]
    for key, label in (("band", "Common band (realised motion)"), ("n_band", "Cells in the band"),
                       ("band_panels", "Cells in the band, by panel (secondary)"),
                       ("n_whole", "Cells with a chamfer value, whole ladder"), ("g_band", "g_band"),
                       ("g_whole", "g_whole"), ("wan_high_q75", "Wan 2.2 HIGH upper quartile"),
                       ("other_still_medians", "Other engines' STILL medians"),
                       ("wan_check_lacking_still", "Engines without STILL cells (Wan 2.2 check)")):
        if key in g:
            L.append(f"- {label}: {json.dumps(g[key])}")
    L += ["", "A9's masked-region result is a different condition (a region, not a motion band); "
              "it is reported beside this one and never pooled with it.", ""]
    if res["refused"]:
        L += [f"Refused cells (prereg §5): {', '.join(res['refused'])}.", ""]
    if res["figure_not_plotted_nonpositive"]:
        L += [f"Figure: {res['figure_not_plotted_nonpositive']} cells with a motion or chamfer value "
              "of 0 or below are not drawn on the log axes; they are in every statistic above.", ""]
    return "\n".join(L + arms_markdown(res))


def figure(data, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colours = {"STILL": "#8f8f8a", "LOW": "#4a7fd4", "MID": "#d99a2b", "HIGH": "#c8423a"}
    pts, dropped = plottable(data)
    fig, axes = plt.subplots(1, len(ENGINES), figsize=(10.5, 3.2), sharey=True)
    for ax, e in zip(axes, ENGINES):
        for lv in LEVELS:
            xy = [(m, c) for level, m, c in pts[e] if level == lv]
            if xy:
                ax.scatter(*zip(*xy), s=14, color=colours[lv], label=lv)
        ax.set_title(NAMES[e], fontsize=9, loc="left")
        ax.set_xlabel("realised motion (normalised)", fontsize=8)
        if pts[e]:
            ax.set_xscale("log")
            ax.set_yscale("log")
    axes[0].set_ylabel("mean chamfer vs frame 0 (px)", fontsize=8)
    if any(pts.values()):
        axes[0].legend(frameon=False, fontsize=7)
    if dropped:
        fig.text(0.01, 0.01, f"{dropped} cells with a value of 0 or below are not drawn (log axes).", fontsize=7)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, metadata={"Software": None})
    plt.close(fig)


def check_fixtures(path):
    """The fixture root, or exit: never the repository or any folder under it (the release tree
    carries no marker), never a folder in a private tree."""
    root = Path(path).expanduser().resolve()
    repo = ROOT.resolve()
    in_private = any((d / PRIVATE_MARKER).is_file() for d in (root, *root.parents))
    if root == repo or repo in root.parents or in_private:
        raise SystemExit("REFUSING --fixtures: the folder is the repository, inside it, or inside a private "
                         f"tree (it or a folder above it carries {PRIVATE_MARKER}). Fixtures live outside it.")
    return root


def main(argv=None):
    ap = argparse.ArgumentParser(description="A10 motion ladder analysis (confirmatory)")
    ap.add_argument("--fixtures", help="a synthetic tree laid out like the repository, outside it; "
                                       "skips the registration check")
    ap.add_argument("--manipulation-only", action="store_true",
                    help="print the median realised motion by level and stop (read before any drift number)")
    a = ap.parse_args(argv)
    if a.fixtures:
        root, public = check_fixtures(a.fixtures), None
    else:
        root, public = ROOT, is_public          # each arm: read only once its own amendment is public
        require_public("A10", "analyse the ladder", hint="Tests use --fixtures.")
    if a.manipulation_only:
        refused = load_refused(root)
        expected, _ = expected_cells(root, refused)
        data = load(root, expected, refused, motion_only=True)
        cov = coverage(expected, data, refused, motion_only=True)
        for e in ENGINES:
            m = manipulation(data[e])
            med = m["median_motion_by_level"]
            print(f"{NAMES[e]}: " + "  ".join(f"{lv} {fmt(med[lv], 5)}" for lv in LEVELS)
                  + f"  ({m['rising_steps']} of {m['of_steps']} steps rise; "
                  + ("passed)" if m["passed"] else "FAILED)"))
            if cov[e]["missing"]:
                print(f"  {NAMES[e]}: incomplete, {cells_phrase(cov[e]['missing'])} "
                      f"(no motion value): {', '.join(cov[e]['missing_motion'])}")
        for t in ARMS:                                # then each arm, under its own amendment
            if not (root / ARMS[t]["cells"]).exists():
                continue
            label = f"{ARMS[t]['name']} ({ARMS[t]['amendment']})"
            status, _ = arm_status(root, t, public)
            if status != "analysed":
                print(f"{label}: {status}")
                continue
            exp = {t: arm_cells(root, t)}
            arm_data = load(root, exp, refused, motion_only=True)
            arm_cov = coverage(exp, arm_data, refused, motion_only=True)
            m = manipulation(arm_data[t])
            med = m["median_motion_by_level"]
            print(f"{label}: " + "  ".join(f"{lv} {fmt(med[lv], 5)}" for lv in LEVELS)
                  + f"  ({m['rising_steps']} of {m['of_steps']} steps rise; "
                  + ("passed)" if m["passed"] else "FAILED)"))
            if arm_cov[t]["missing"]:
                print(f"  {label}: incomplete, {cells_phrase(arm_cov[t]['missing'])} "
                      f"(no motion value): {', '.join(arm_cov[t]['missing_motion'])}")
        return 0
    res, data = run(root, public=public)
    out = root / "analysis" / "out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "a10_ladder.json").write_text(json.dumps(res, indent=1, allow_nan=False) + "\n")
    (out / "a10_ladder.md").write_text(markdown(res) + "\n")
    figure(data, out / "figures" / "a10_ladder.png")
    print(markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
