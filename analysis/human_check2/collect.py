#!/usr/bin/env python3
"""A11's human-check analysis: §6 at power (40 clips, up to 12 raters), with H3.

*** H3 is CONFIRMATORY (amendment A11); everything else is reported as §6, A6 and A8 report it. ***

    python analysis/human_check2/collect.py                  # refuses until A11 is public
    python analysis/human_check2/collect.py --fixtures DIR   # a synthetic tree (tests); no registration check

A thin wrapper over the A6 analysis: it imports analysis/human_check/collect.py by file
path and runs the same functions on this folder's mapping and ratings, so the per-question
numbers are computed exactly as A6's were. In order:

  0. checks, each refusing the run (naming the file): mapping.json lists exactly two
     attention clips, both among its clip codes (A11); baseline_mapping.json exists
     (A11); every rating file names its rater slot, no slot appears in two files, the
     file's instrument is the run's, and its `ratings` and `attention` lists hold only the
     mapping's clip codes and attention clips respectively, each at most once;
  1. completeness: a rating file must answer every shown item on both questions, the
     first showing of every clip and the repeat (the file's `attention` list) of every
     attention clip (42 items in A11), else the rater is excluded as incomplete (listed
     and counted; a missing or invalid repeat answer counts here; ruled 4 Nov 2026);
  2. attention: for each attention clip in mapping.json, the second answers are
     compared with the first (so only ever on two recorded repeats); an item fails when
     either question differs by 2 or more scale points, and a rater who fails every item
     (both) is excluded (the opaque slots listed and counted). Rules 1 and 2 run before any correlation.
     No time-based exclusion of any kind: timings and telemetry play no part (A7, A8);
  3. A6's analysis on the included raters, unchanged: per question, Krippendorff's
     ordinal alpha and, per frozen headline, Spearman rho against the mean rating with a
     bootstrap 95% CI (one numpy.random.default_rng(SEED) through questions and metrics).
     Only where A6's code would stop on a bootstrap with no finite resample (a constant
     side), the same loop, drawing the same numbers, reports that metric with
     `ci95: None` (and `spearman_rho: None`) instead; any other failure is re-raised;
  4. H3: rho(edge |slope|, mean "same image" rating) <= -0.4, one-sided. Bootstrap over
     clips, B = 10,000, a fresh default_rng(SEED); p = (#{rho* >= -0.4} + 1) /
     (n_finite + 1); supported iff p <= 0.05. Reported with rho, the percentile 95% CI and
     the one-sided upper bound (the 95th percentile); `ci95: None` when no resample is
     finite. The reading follows p, also where the one-sided upper bound sits on the
     other side of the bound at the margin. The reading against -0.5 is reported as
     secondary, from the same resamples;
  5. secondary (declared): the register question again on the clips whose panel's
     baseline mean (A8's Q3, included raters) is at least 2.5 (A8's difference-score
     remedy is not re-run);
  6. Krippendorff's alpha of the baseline question over the panel codes of
     baseline_mapping.json (with each panel's mean and number of answers); flags for alpha(sameness) < 0.3 and for fewer than 10
     included raters (both reported; H3 is tested either way).

On this folder, or on any folder whose mapping.json says instrument "A11", it refuses
until amendment A11's heading is in the PUBLIC pre-registration (harness/registration.py).
The only escape is explicit: --fixtures (run(..., fixtures=True)), which refuses the
repository itself and any folder inside a private tree (one carrying
analysis/adherence/private-terms.txt).

SEED = 20261104 (A11). Outputs: human_check2_results.json and .md, written to the
human_check2/ folder analysed (this folder; a fixture tree's own under --fixtures).
"""
import argparse
import importlib.util
import json
import sys
import warnings
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE.parent / "out"
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(ROOT / "harness"))
import rank_stats as rs  # noqa: E402
from registration import require_public  # noqa: E402

_spec = importlib.util.spec_from_file_location("a6_collect", HERE.parent / "human_check" / "collect.py")
a6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a6)

SEED = 20261104
B = 10_000
ALPHA = 0.05
H3_BOUND = -0.4            # registered (A11)
H3_SECONDARY_BOUND = -0.5  # reported, secondary
ATTENTION_POINTS = 2
BASELINE_MIN = 2.5
ALPHA_FLAG = 0.3
MIN_RATERS = 10
QUESTIONS = ("register", "sameness")
PRIVATE_MARKER = Path("analysis") / "adherence" / "private-terms.txt"


def fmt(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def score(v):
    """A valid answer: an int from 1 to 5 (bool is not one)."""
    return isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5


def in_private_tree(path):
    p = Path(path).expanduser().resolve()
    return any((d / PRIVATE_MARKER).is_file() for d in (p, *p.parents))


def check_fixtures(path):
    """The fixture root, or exit: never the repository or any folder under it (the release tree
    carries no marker), never a folder in a private tree."""
    root = Path(path).expanduser().resolve()
    repo = Path(ROOT).resolve()
    if root == repo or repo in root.parents or in_private_tree(root):
        raise SystemExit("REFUSING --fixtures: the folder is the repository, inside it, or inside a private "
                         f"tree (it or a folder above it carries {PRIVATE_MARKER}). Fixtures live outside it.")
    return root


def complete(d, codes, attention_clips=()):
    """Every shown item answered validly on both questions: each clip's first showing and
    the repeat of each attention clip (42 items in A11)."""
    got = {r.get("clip"): r for r in d.get("ratings", [])}
    rep = {r.get("clip"): r for r in d.get("attention", []) or []}
    return (all(c in got and all(score(got[c].get(q)) for q in QUESTIONS) for c in codes)
            and all(c in rep and all(score(rep[c].get(q)) for q in QUESTIONS) for c in attention_clips))


def attention_failures(d, attention_clips, points=ATTENTION_POINTS):
    """(items administered, items failed) for one rater. An item is administered when the
    file holds a valid second answer to both questions."""
    first = {r.get("clip"): r for r in d.get("ratings", [])}
    repeat = {r.get("clip"): r for r in d.get("attention", []) or []}
    items = failed = 0
    for c in attention_clips:
        if c not in first or c not in repeat or not all(score(repeat[c].get(q)) for q in QUESTIONS):
            continue
        items += 1
        if any(abs(repeat[c][q] - first[c][q]) >= points for q in QUESTIONS):
            failed += 1
    return items, failed


def baseline_scores(d, here):
    """{panel code: hand_drawn}, from the rating file or, as A8 did for one rater, baselines/."""
    bl = d.get("baseline")
    if not bl:
        f = Path(here) / "baselines" / f"baseline-{d['rater']}.json"
        bl = json.loads(f.read_text())["baseline"] if f.exists() else []
    return {x["panel"]: x["hand_drawn"] for x in bl if score(x.get("hand_drawn"))}


def _analyse_tolerant(matrices, cells, rows, seed=a6.SEED, b=10000):
    """A6's analyse, line for line and drawing the same numbers, except that a metric whose
    bootstrap has no finite resample reports ci95 None (and an undefined rho as None)
    instead of stopping. Used only where A6's code stops."""
    rng = np.random.default_rng(seed)
    per_axis = {}
    for axis, matrix in matrices.items():
        mean_rating = np.nanmean(matrix, axis=0)
        per_axis[axis] = {
            "krippendorff_alpha_ordinal": a6.krippendorff_alpha_ordinal(matrix),
            "per_metric": {}}
        for metric in a6.HEADLINES:
            pairs = [(rows[c][metric], mr) for c, mr in zip(cells, mean_rating)
                     if rows[c][metric] is not None and not np.isnan(mr)]
            if len(pairs) < 4:
                per_axis[axis]["per_metric"][metric] = None
                continue
            x, y = map(np.array, zip(*pairs))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", stats.ConstantInputWarning)
                rho, p = stats.spearmanr(x, y)
            boots = []
            for _ in range(b):
                idx = rng.integers(0, len(x), len(x))
                if len(set(x[idx])) > 1 and len(set(y[idx])) > 1:
                    boots.append(stats.spearmanr(x[idx], y[idx]).statistic)
            ci = [float(v) for v in np.percentile(boots, [2.5, 97.5])] if boots else None
            per_axis[axis]["per_metric"][metric] = {
                "n_cells": len(pairs),
                "spearman_rho": None if np.isnan(rho) else float(rho),
                "p": None if np.isnan(p) else float(p),
                "ci95": ci, "bootstrap_n": len(boots), "seed": seed}
    return per_axis


def analyse(matrices, cells, rows, seed, b):
    """A6's analyse; the tolerant copy only when A6's stops on an empty bootstrap."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", stats.ConstantInputWarning)
            return a6.analyse(matrices, cells, rows, seed=seed, b=b)
    except IndexError:
        res = _analyse_tolerant(matrices, cells, rows, seed=seed, b=b)
        if not any(v is not None and v["ci95"] is None for a in res.values() for v in a["per_metric"].values()):
            raise   # not the empty-bootstrap case the copy exists for
        return res


def h3(x, y, seed=SEED, b=B):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    rho = rs.spearman(x, y)
    out = {"n": int(x.size), "rho": rho, "bound": H3_BOUND,
           "test": "one-sided bootstrap: p = (#{rho* >= -0.4} + 1) / (n_finite + 1); supported iff p <= 0.05",
           "p_bootstrap_one_sided": None, "ci95": None, "upper_one_sided_95": None, "bootstrap_n": 0,
           "reading": None,
           "secondary": {"bound": H3_SECONDARY_BOUND, "p_bootstrap_one_sided": None, "reading": None}}
    if rho is None:
        out["reading"] = out["secondary"]["reading"] = "undefined (fewer than 4 clips, or no variation)"
        return out
    boots = rs.bootstrap(x, y, seed, b)
    if boots.size == 0:
        out["reading"] = out["secondary"]["reading"] = "undefined (no finite bootstrap replicate)"
        return out

    def p_at(bound):
        return (int(np.sum(boots >= bound)) + 1) / (boots.size + 1)

    p, p2 = p_at(H3_BOUND), p_at(H3_SECONDARY_BOUND)
    out.update({"p_bootstrap_one_sided": p, "ci95": rs.percentile_ci(boots),
                "upper_one_sided_95": float(np.percentile(boots, 95)), "bootstrap_n": int(boots.size),
                "reading": "supported" if p <= ALPHA else "not supported",
                "secondary": {"bound": H3_SECONDARY_BOUND, "p_bootstrap_one_sided": p2,
                              "reading": "supported" if p2 <= ALPHA else "not supported"}})
    return out


def check_file(f, d, instrument, codes, attention_clips):
    """Refuse (naming the file) a rating file that breaks the contract."""
    if d.get("instrument") != instrument:
        raise SystemExit(f"{f.name}: instrument {d.get('instrument')!r}, not {instrument!r}; refusing to run")
    for key, allowed in (("ratings", set(codes)), ("attention", set(attention_clips))):
        clips = [r.get("clip") for r in d.get(key, []) or []]
        if any(c not in allowed for c in clips):
            raise SystemExit(f"{f.name}: `{key}` holds a clip code outside the mapping's "
                             f"{'clip codes' if key == 'ratings' else 'attention clips'}; refusing to run")
        if len(clips) != len(set(clips)):
            raise SystemExit(f"{f.name}: `{key}` holds a clip twice; refusing to run")


def run(here=HERE, out_dir=OUT, seed=SEED, b=B, instrument="A11", write=True, fixtures=False):
    here, out_dir = Path(here), Path(out_dir)
    mapping = json.loads((here / "mapping.json").read_text())
    if fixtures:
        check_fixtures(here)
    elif mapping.get("instrument") == "A11" or here.resolve() == HERE:
        require_public("A11", "analyse the A11 ratings", hint="Tests use --fixtures.")
    if mapping.get("instrument", instrument) != instrument:
        raise SystemExit(f"mapping.json is for {mapping.get('instrument')!r}, not {instrument!r}; refusing to run")
    o2c = mapping["opaque_to_cell"]
    codes = sorted(o2c)
    attention_clips = mapping.get("attention_clips", [])
    if not set(attention_clips) <= set(codes) or (instrument == "A11" and len(set(attention_clips)) != 2) \
            or len(attention_clips) != len(set(attention_clips)):
        raise SystemExit("mapping.json: attention_clips must be two distinct clip codes of the mapping; "
                         "refusing to run")
    bmap = here / "baseline_mapping.json"
    if instrument == "A11" and not bmap.exists():
        raise SystemExit(f"{bmap.name} is missing; refusing to run")
    bdoc = json.loads(bmap.read_text()) if bmap.exists() else {}
    clip_to_panel = bdoc.get("clip_to_panel", {})
    panel_codes = list(bdoc.get("panel_opaque_to_name", {}))
    rows = {r["cell_id"]: r for r in json.loads((out_dir / "results_table.json").read_text())}
    files = sorted((here / "ratings").glob("ratings-*.json"))
    if not files:
        raise SystemExit(f"no rating files yet in {here / 'ratings'}/")
    a6.guard_strays(here)

    loaded, seen = [], {}
    for f in files:
        d = json.loads(f.read_text())
        slot = d.get("rater")
        if not isinstance(slot, str) or not slot:
            raise SystemExit(f"{f.name} names no rater slot; refusing to run")
        if slot in seen:
            raise SystemExit(f"rater slot {slot} appears in two files ({seen[slot]}, {f.name}); refusing to run")
        seen[slot] = f.name
        check_file(f, d, instrument, codes, attention_clips)
        loaded.append((f, d))

    included, docs, incomplete, failed_attention, attention_log = [], [], [], [], {}
    for f, d in loaded:
        if not complete(d, codes, attention_clips):
            incomplete.append(d["rater"])
            continue
        items, failed = attention_failures(d, attention_clips)
        attention_log[d["rater"]] = {"items": items, "failed": failed}
        if attention_clips and failed == items == len(attention_clips):
            failed_attention.append(d["rater"])
            continue
        included.append(f)
        docs.append(d)
    if not included:
        raise SystemExit("no rater is left after the completeness and attention rules")

    raters, matrices = a6.load_matrices(included, codes)
    cells = [o2c[c] for c in codes]
    per_axis = analyse(matrices, cells, rows, seed=seed, b=b)

    mean_same = np.nanmean(matrices["sameness"], axis=0)
    pairs = [(rows[c]["edge_abs_slope"], m) for c, m in zip(cells, mean_same)
             if rows[c]["edge_abs_slope"] is not None and not np.isnan(m)]
    h3_result = h3([p[0] for p in pairs], [p[1] for p in pairs], seed, b)

    scores = [baseline_scores(d, here) for d in docs]
    unknown = sorted({p for s in scores for p in s} - set(panel_codes))
    if unknown:
        raise SystemExit(f"baseline answers for {len(unknown)} panel code(s) not in baseline_mapping.json "
                         f"({', '.join(unknown)}); refusing to run")
    means, counts = {}, {}
    for p in panel_codes:
        vals = [s[p] for s in scores if p in s]
        means[p], counts[p] = (float(np.mean(vals)) if vals else None), len(vals)
    bmatrix = np.array([[s.get(p, np.nan) for p in panel_codes] for s in scores], dtype=float)
    keep = [i for i, c in enumerate(codes)
            if means.get(clip_to_panel.get(c)) is not None and means[clip_to_panel[c]] >= BASELINE_MIN]
    filtered = analyse({"register": matrices["register"][:, keep]}, [cells[i] for i in keep], rows,
                       seed=seed, b=b)

    alpha_same = per_axis["sameness"]["krippendorff_alpha_ordinal"]
    results = {
        "instrument": instrument, "seed": seed, "bootstrap": b,
        "n_rating_files": len(files),
        "excluded_incomplete": incomplete, "n_excluded_incomplete": len(incomplete),
        "excluded_attention": failed_attention, "n_excluded_attention": len(failed_attention),
        "attention_rule": (f"an item fails at {ATTENTION_POINTS} or more scale points' difference on either "
                           "question at the repeat; a rater who fails both items is excluded"),
        "attention": attention_log,
        "n_raters": len(raters), "raters": raters,
        "per_axis": per_axis,
        "h3": h3_result,
        "register_baseline_filtered": {
            "status": "secondary (declared in A11)",
            "rule": f"clips whose panel's baseline mean is at least {BASELINE_MIN}",
            "n_clips": len(keep),
            "excluded_panels": [p for p in panel_codes if means[p] is not None and means[p] < BASELINE_MIN],
            "panels_without_baseline": [p for p in panel_codes if means[p] is None],
            "register": filtered["register"]},
        "baseline": {"n_panels": len(panel_codes), "mean_by_panel": means, "n_by_panel": counts,
                     "krippendorff_alpha_ordinal": a6.krippendorff_alpha_ordinal(bmatrix) if panel_codes else None},
        "flags": {"alpha_sameness_below_0.3": bool(alpha_same is not None and alpha_same < ALPHA_FLAG),
                  "fewer_than_10_raters": len(raters) < MIN_RATERS},
    }
    if write:
        (here / "human_check2_results.json").write_text(json.dumps(results, indent=1, allow_nan=False) + "\n")
        (here / "human_check2_results.md").write_text(markdown(results) + "\n")
    return results


def ci_text(ci):
    return "n/a" if not ci else f"[{ci[0]:.2f}, {ci[1]:.2f}]"


def markdown(r):
    h = r["h3"]
    s = h["secondary"]
    L = [f"# Human check 2 ({r['instrument']}): results", "",
         f"Rating files {r['n_rating_files']}; raters included {r['n_raters']} ({', '.join(r['raters'])}); "
         f"excluded by the attention rule: {r['n_excluded_attention']} "
         f"({', '.join(r['excluded_attention']) or 'none'}); "
         f"excluded as incomplete: {r['n_excluded_incomplete']} "
         f"({', '.join(r['excluded_incomplete']) or 'none'}).", "",
         "## H3 (confirmatory): edge |slope| against the mean \"same image\" rating", "",
         f"- rho {fmt(h.get('rho'), 2)} on {h['n']} clips; one-sided bootstrap p (rho* >= {h['bound']}) "
         f"{fmt(h.get('p_bootstrap_one_sided'), 4)}; 95% CI {ci_text(h.get('ci95'))}; one-sided upper bound "
         f"{fmt(h.get('upper_one_sided_95'), 2)}: **{h['reading']}** (the reading follows p; at the "
         "margin the one-sided upper bound can sit on the other side of the bound)",
         f"- secondary, against {s['bound']}: p {fmt(s.get('p_bootstrap_one_sided'), 4)}, {s['reading']}", "",
         "## Per question (A6's analysis, unchanged)", "",
         "| Question | alpha | Metric | n | rho | 95% CI |", "|---|---|---|---|---|---|"]
    for q, d in r["per_axis"].items():
        for m, v in d["per_metric"].items():
            if v:
                L.append(f"| {q} | {fmt(d['krippendorff_alpha_ordinal'], 2)} | {m} | {v['n_cells']} | "
                         f"{fmt(v['spearman_rho'], 2)} | {ci_text(v['ci95'])} |")
            else:
                L.append(f"| {q} | {fmt(d['krippendorff_alpha_ordinal'], 2)} | {m} | n/a | n/a | n/a |")
    f = r["register_baseline_filtered"]
    L += ["", f"## Register, panels with a baseline mean of at least 2.5 ({f['status']}; {f['n_clips']} clips; "
              f"panels excluded: {', '.join(f['excluded_panels']) or 'none'})", ""]
    for m, v in f["register"]["per_metric"].items():
        L.append(f"- {m}: " + ("n/a" if not v else
                               f"rho {fmt(v['spearman_rho'], 2)} {ci_text(v['ci95'])}, n {v['n_cells']}"))
    L += ["", f"Baseline alpha {fmt(r['baseline']['krippendorff_alpha_ordinal'], 2)} over "
              f"{r['baseline']['n_panels']} panels. Flags: {json.dumps(r['flags'])}."]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="A11 human-check analysis")
    ap.add_argument("--fixtures", help="a synthetic tree laid out like the repository, outside it; "
                                       "skips the registration check")
    a = ap.parse_args(argv)
    if a.fixtures:
        root = check_fixtures(a.fixtures)
        here, out_dir = root / "analysis" / "human_check2", root / "analysis" / "out"
    else:
        require_public("A11", "analyse the A11 ratings", hint="Tests use --fixtures.")
        here, out_dir = HERE, OUT
    res = run(here=here, out_dir=out_dir, fixtures=bool(a.fixtures))
    print(markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
