#!/usr/bin/env python3
"""A13: adherence at power. At clip level, does a clip that drifts more do the requested motion more fully?

*** A13-H4 is CONFIRMATORY (amendment A13). Everything else here is reported without a verdict. ***

    python analysis/a13_adherence.py                   # refuses until A13 is public
    python analysis/a13_adherence.py --count-only      # completeness and attention only (the top-up decision)
    python analysis/a13_adherence.py --fixtures DIR    # a synthetic tree (tests); no registration check

Inputs, under the root analysed: analysis/adherence_a13/mapping.json (codes -> public cell ids, the
repeats, the attention clips); analysis/adherence_a13/ratings/ratings-R<n>.json, one per rater slot
(written by the rating app's fetch; the release ships them slimmed to scores and attention answers);
analysis/out/results_table.json (released line drift, read by A9's load_cells, which also fixes the
110 cells and their 22 rows); and runs/metrics-motion/<cell>.json for the 110 clips (released motion,
read by A9's load_motion for the AUC).

In order:
  0. checks, each refusing the run: mapping.json is A13's, with 55 codes and 2 repeats per study and
     the repeats' originals as its attention clips, its cells exactly A9's 110 primary burst and
     camera-push cells in the right study; no rating file anywhere under analysis/adherence_a13/
     except in ratings/ (it would be silently skipped); every rating file names one of A13's slots
     R24-R39 (A13_SLOTS), no slot twice, instrument A13, only the study's codes in `ratings` and its
     attention clips in `attention`, each at most once; --fixtures refuses the repository and any tree
     in or under the private one;
  1. completeness: all 110 first showings and all 4 repeats answered 1-5, else the rater is excluded
     as incomplete (listed, counted);
  2. attention (EXCLUDE_IF): an item fails when the repeat's score differs from the first showing's
     by ATTENTION_POINTS or more; under "both_in_a_study" a rater who fails both items of either study
     is excluded (listed, counted). Rules 1 and 2 run before any correlation. No rule on time.
  3. A13-H4: Spearman rho between each clip's released line_chamfer_mean_px and its mean score over
     the included raters, 110 clips; one-sided p from B permutations of the mean scores within the 22
     rows (a panel and a motion class), numpy.random.default_rng(SEED), p = (k + 1) / (B + 1)
     (rank_stats.within_strata). Supported iff p <= 0.05, and rho > 0 while H4_REQUIRE_POSITIVE;
  4. secondary, no verdict: the engine-level rho(S, miss rate) on the pooled ratings (A9 Test 1's
     statistic), per-engine miss rates with Wilson intervals, Krippendorff's ordinal alpha (all clips
     and per study), A9's quadratic-weighted kappa (mean over pairs of complete raters, per study), and
     A9's motion AUC on these clips, a clip being a miss when its mean score is <= 2;
  5. flags, which exclude nothing: fewer than MIN_RATERS included; alpha over all clips < ALPHA_FLAG.
     --count-only also says whether the one top-up is due (fewer than TOPUP_BELOW included).

Outputs: analysis/out/a13_adherence.json and .md, rounded to 12 significant digits (A9's rule); the
release build re-runs this and compares them byte for byte. The ordinal mixed model (--mixed, R)
writes analysis/out/a13_mixed.json, which the release ships but does not re-run. "Converged" means a zero
optimizer code with R and its packages as analysis/a13-r-lock.txt pins them; a model that does not
converge is a recorded outcome ("converged": false, the code, the optimizer and its message or the error,
no coefficient), and the report states which outcome the file holds, or that it is stale (fitted on other
raters than the included ones).
"""
import argparse
import csv
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "harness"))
import a9_adherence as a9  # noqa: E402  (A9's cells, steadiness, exact test, Wilson, rounding)
import rank_stats as rs  # noqa: E402
from registration import require_public  # noqa: E402

_spec = importlib.util.spec_from_file_location("a6_collect", HERE / "human_check" / "collect.py")
a6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a6)

SEED = 20261104
B = 10_000
ALPHA = 0.05
STUDIES = ("burst", "push")
STUDY_LABEL = {"burst": "burst", "push": "camera push"}     # how the report names each study, everywhere
N_FIRST, N_REPEATS = 55, 2
ATTENTION_POINTS = 2
EXCLUDE_IF = "both_in_a_study"      # registered in A13.4.2; "any_item" is the alternative
H4_REQUIRE_POSITIVE = True          # registered in A13.4.3
MIN_RATERS = 8                      # the kill rule's flag (A13.5.1)
TOPUP_BELOW = 10                    # the one top-up is due below this many included raters (A13.5.1, as A11)
ALPHA_FLAG = 0.3
SLOT = re.compile(r"R[0-9]+")
A13_SLOTS = frozenset(f"R{n}" for n in range(24, 40))   # R24-R35 main, R36-R39 the one top-up (A13.3.5, A13.5.1)
PRIVATE_MARKER = Path("analysis") / "adherence" / "private-terms.txt"
# The kappa of A13.4.4(c) reads every complete rater (kappas()), so neither rule excludes from it.
KAPPA_EXCEPTION = ("is excluded from every statistic except the κ of A13.4.4(c), which measures the instrument "
                   "over all complete raters")
ATTENTION_RULE = {
    "both_in_a_study": (f"per study, an attention item fails when the repeat's score differs from the first "
                        f"showing's by {ATTENTION_POINTS} or more points; a rater who fails both items of either "
                        f"study {KAPPA_EXCEPTION}"),
    "any_item": (f"an attention item fails when the repeat's score differs from the first showing's by "
                 f"{ATTENTION_POINTS} or more points; a rater who fails any item {KAPPA_EXCEPTION}"),
}


def score(v):
    return isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5


def fmt(x, nd=3):
    return "—" if x is None else f"{x:.{nd}f}"


def check_fixtures(root):
    """Refuse the repository, and any tree that is or sits under the private one: the tree or a folder above
    it carries the private marker (as registration.private_tree reads it)."""
    root = Path(root).resolve()
    if root == ROOT.resolve():
        raise SystemExit("--fixtures refuses the repository itself")
    if any((d / PRIVATE_MARKER).is_file() for d in (root, *root.parents)):
        raise SystemExit("--fixtures refuses a private tree (it or a folder above it carries "
                         "analysis/adherence/private-terms.txt)")


def load_mapping(folder):
    try:
        m = json.loads((folder / "mapping.json").read_text())
    except (OSError, ValueError) as e:
        raise SystemExit(f"mapping.json: unreadable ({e}); refusing to run") from None
    if m.get("instrument") != "A13":
        raise SystemExit("mapping.json: instrument is not A13; refusing to run")
    for s in STUDIES:
        st = (m.get("studies") or {}).get(s) or {}
        c2c, reps = st.get("code_to_cell") or {}, st.get("repeats") or []
        if len(c2c) != N_FIRST or len(reps) != N_REPEATS:
            raise SystemExit(f"mapping.json: {s} needs {N_FIRST} codes and {N_REPEATS} repeats; refusing to run")
        att = (m.get("attention_clips") or {}).get(s)
        if att != [r.get("of") for r in reps] or not set(att) <= set(c2c) or len(set(att)) != N_REPEATS:
            raise SystemExit(f"mapping.json: {s}'s attention clips must be its two repeats' originals; refusing to run")
    return m


def check_file(f, d, m):
    slot = d.get("rater")
    if not isinstance(slot, str) or not SLOT.fullmatch(slot):
        raise SystemExit(f"{f.name}: the rater slot is not R followed by digits; refusing to run")
    if slot not in A13_SLOTS:
        raise SystemExit(f"{f.name}: rater slot {slot} is outside A13's slots R24 to R39; refusing to run")
    if d.get("instrument") != "A13":
        raise SystemExit(f"{f.name}: instrument is not A13; refusing to run")
    for s in STUDIES:
        part = (d.get("studies") or {}).get(s) or {}
        for key, allowed in (("ratings", set(m["studies"][s]["code_to_cell"])),
                             ("attention", set(m["attention_clips"][s]))):
            codes = [r.get("clip") for r in part.get(key) or []]
            if len(codes) != len(set(codes)):
                raise SystemExit(f"{f.name}: {s} {key} holds a code twice; refusing to run")
            if not set(codes) <= allowed:
                raise SystemExit(f"{f.name}: {s} {key} holds a code outside the mapping; refusing to run")


def complete(d, m):
    """Every first showing (110) and every repeat (4) answered with an integer 1-5."""
    for s in STUDIES:
        part = (d.get("studies") or {}).get(s) or {}
        got = {r.get("clip"): r.get("score") for r in part.get("ratings") or []}
        rep = {r.get("clip"): r.get("score") for r in part.get("attention") or []}
        if not all(score(got.get(c)) for c in m["studies"][s]["code_to_cell"]):
            return False
        if not all(score(rep.get(c)) for c in m["attention_clips"][s]):
            return False
    return True


def attention(d, m, points=ATTENTION_POINTS):
    """{study: {"items": n, "failed": k}}, read on the recorded repeats (complete() guarantees both)."""
    out = {}
    for s in STUDIES:
        part = d["studies"][s]
        first = {r["clip"]: r["score"] for r in part["ratings"]}
        rep = {r["clip"]: r["score"] for r in part["attention"]}
        items = [c for c in m["attention_clips"][s] if c in rep]
        out[s] = {"items": len(items), "failed": sum(abs(rep[c] - first[c]) >= points for c in items)}
    return out


def excluded_by_attention(att, mode):
    if mode == "both_in_a_study":
        return any(a["items"] == a["failed"] == N_REPEATS for a in att.values())
    if mode == "any_item":
        return any(a["failed"] > 0 for a in att.values())
    raise ValueError(f"EXCLUDE_IF {mode!r}")


def row_of(cell):
    """A9's row: a panel and a motion class (22 rows of five engines, on 20 drawings)."""
    return f"{cell['panel']}|{cell['study']}"


def h4_reading(rho, p, require_positive):
    if rho is None or p is None:
        return "undefined (no variation)"
    if p <= ALPHA and (rho > 0 or not require_positive):
        return "supported"
    if p <= ALPHA:
        return "not supported (p <= 0.05 but rho <= 0)"
    return "not supported"


def h4(cells, cell_ids, mean, seed=SEED, b=B):
    w = rs.within_strata([cells[c]["drift"] for c in cell_ids], [float(v) for v in mean],
                         [row_of(cells[c]) for c in cell_ids], seed, b)
    rho, p = w["rho"], w["p_pooled_within_strata_perm"]
    return {"n_clips": len(cell_ids), "n_rows": w["strata"], "rho": rho, "p_one_sided": p,
            "permutations": b, "seed": seed,
            "permuted": "the clips' mean scores, within rows (a panel and a motion class)",
            "rule": "Spearman rho > 0, one-sided, alpha 0.05; supported iff p <= 0.05"
                    + (" and rho > 0" if H4_REQUIRE_POSITIVE else ""),
            "reading": h4_reading(rho, p, H4_REQUIRE_POSITIVE),
            "rho_within_rows": w["rho_within"], "p_within_rows": w["p_within"]}


def engine_level(cells, cell_ids, X):
    """A9 Test 1's statistic on the pooled ratings of the included raters: S_e (A9's steadiness, the
    engine's median released drift over its 22 cells) against its miss rate (a miss is a score <= 2),
    exact one-sided p over the 120 orderings. No verdict: with five engines only rho <= -0.9 reaches 0.05."""
    S = a9.steadiness(cells)
    per = {}
    for e in a9.LEAGUE_ORDER:
        v = X[:, [k for k, c in enumerate(cell_ids) if cells[c]["engine"] == e]].ravel()
        v = v[~np.isnan(v)]
        n, k = int(v.size), int(np.sum(v <= a9.MISS_MAX))
        per[e] = {"name": a9.ENGINE_NAMES[e], "S_px": S[e], "n_ratings": n, "misses": k,
                  "miss_rate": k / n if n else None, "wilson95": a9.wilson(k, n)}
    rates = [per[e]["miss_rate"] for e in a9.LEAGUE_ORDER]
    rho, p = (None, None) if None in rates else a9.exact_one_sided_p([S[e] for e in a9.LEAGUE_ORDER], rates)
    return {"miss": f"score <= {a9.MISS_MAX}", "per_engine": per, "rho": rho, "p_exact_one_sided": p,
            "note": "A9 Test 1's statistic on all included raters' ratings pooled; no verdict (five engines)"}


def alphas(cells, cell_ids, X):
    by = {s: [k for k, c in enumerate(cell_ids) if cells[c]["study"] == s] for s in STUDIES}
    return {"all_clips": a6.krippendorff_alpha_ordinal(X),
            **{s: a6.krippendorff_alpha_ordinal(X[:, cols]) for s, cols in by.items()}}


def kappas(complete_docs, m):
    """A9's agreement statistic, defined before registration: the quadratic-weighted kappa
    (a9.weighted_kappa) for every pair of complete raters, per study, and its mean over the pairs where it
    is defined. Complete raters, not only included ones: agreement is a property of the instrument, and an
    attention-excluded rater's answers are part of what it produced. No verdict."""
    out = {}
    for s in STUDIES:
        codes = sorted(m["studies"][s]["code_to_cell"])
        vecs = []
        for d in complete_docs:
            got = {r["clip"]: r["score"] for r in d["studies"][s]["ratings"]}
            vecs.append([got[c] for c in codes])
        ks = [a9.weighted_kappa(vecs[i], vecs[j]) for i in range(len(vecs)) for j in range(i + 1, len(vecs))]
        defined = [k for k in ks if k is not None]
        out[s] = {"n_raters": len(vecs), "n_pairs": len(ks), "n_pairs_defined": len(defined),
                  "mean_kappa": float(np.mean(defined)) if defined else None}
    return out


def motion_auc(root, cells, cell_ids, X):
    """A9's objective check, on these 110 clips (a9.load_motion, a9.motion_check): per motion class,
    AUC = P(motion of a non-miss clip > motion of a miss clip), ties 1/2, on the released
    headline_median_norm (runs/metrics-motion/). A clip is a miss when its mean score over the included
    raters is <= 2: A9's per-rater miss carried to the clip, A13's unit. A9's readings, no verdict."""
    motion = a9.load_motion(root, set(cell_ids))
    mean = {c: float(v) for c, v in zip(cell_ids, X.mean(axis=0))}
    return {"miss": f"mean score over the included raters <= {a9.MISS_MAX}",
            "by_class": a9.motion_check(cells, mean, motion)}


STALE = "stale (re-run --mixed)"


def mixed_status(root, slots, n_clips):
    """The outcome analysis/out/a13_mixed.json records, for the report: "not run" (no file), "converged",
    "did not converge" (no coefficient), or STALE when the file was not fitted on exactly the included raters
    (its `raters` are not the included slots, its n_raters is not their number, or its n_ratings is not
    n_clips times it: counts alone would miss one rater swapped for another; ruled 9 Nov 2026); a stale fit is never
    reported as converged. A file fitted with a test-only optimizer control refuses the run."""
    f = Path(root) / "analysis" / "out" / "a13_mixed.json"
    if not f.exists():
        return "not run"
    try:
        mx = json.loads(f.read_text())
        converged = mx.get("converged")
    except (OSError, ValueError, AttributeError) as e:
        raise SystemExit(f"a13_mixed.json: unreadable ({e}); refusing to run") from None
    if mx.get("test_control") is not None:
        raise SystemExit(f"a13_mixed.json was fitted with a test-only optimizer control ({mx['test_control']}); "
                         "refusing to run")
    if not isinstance(converged, bool):
        raise SystemExit("a13_mixed.json: no true or false `converged`; refusing to run")
    fitted = mx.get("raters")
    if (not isinstance(fitted, list) or sorted(map(str, fitted)) != sorted(slots)
            or mx.get("n_raters") != len(slots) or mx.get("n_ratings") != n_clips * len(slots)):
        return STALE
    return "converged" if converged else "did not converge"


def secondaries(cells, cell_ids, X, root, m, complete_docs):
    return {"engine_level": engine_level(cells, cell_ids, X), "alpha": alphas(cells, cell_ids, X),
            "weighted_kappa": kappas(complete_docs, m), "motion_auc": motion_auc(root, cells, cell_ids, X)}


def markdown_secondary(sec):
    e, a, k, t = sec["engine_level"], sec["alpha"], sec["weighted_kappa"], sec["motion_auc"]
    L = ["## Beside it, no verdict", "",
         f"Engine level (A9 Test 1's statistic, all included raters pooled; a miss is a {e['miss']}): "
         f"ρ(S, miss rate) = {fmt(e['rho'])}, exact one-sided p = {fmt(e['p_exact_one_sided'], 4)}. "
         "With five engines only ρ ≤ −0.9 reaches p ≤ 0.05.", "",
         "| Engine | S (px) | Ratings | Misses | Miss rate | Wilson 95% |", "|---|---|---|---|---|---|"]
    for v in e["per_engine"].values():
        w = v["wilson95"]
        L.append(f"| {v['name']} | {fmt(v['S_px'])} | {v['n_ratings']} | {v['misses']} | {fmt(v['miss_rate'])} | "
                 + (f"[{fmt(w[0])}, {fmt(w[1])}]" if w else "—") + " |")
    lb, lp = STUDY_LABEL["burst"], STUDY_LABEL["push"]
    L += ["", f"Krippendorff's ordinal α: all 110 clips {fmt(a['all_clips'])}; {lb} {fmt(a['burst'])}; "
              f"{lp} {fmt(a['push'])}. A9's statistic, the quadratic-weighted κ, mean over pairs of "
              f"complete raters: {lb} {fmt(k['burst']['mean_kappa'])} ({k['burst']['n_pairs_defined']} pairs), "
              f"{lp} {fmt(k['push']['mean_kappa'])} ({k['push']['n_pairs_defined']} pairs).", "",
          f"A9's motion AUC on these clips (a miss: {t['miss']}; released headline_median_norm; A9's "
          "readings):", "", "| Study | Misses | Non-misses | AUC | Reading |", "|---|---|---|---|---|"]
    for s, b in t["by_class"].items():
        L.append(f"| {STUDY_LABEL[s]} | {b['n_miss']} | {b['n_nonmiss']} | {fmt(b['auc'])} | {b['reading']} |")
    mixed = {
        "converged": ("The ordinal mixed model, rating ~ drift + study + (1 | row) + (1 | rater), is in "
                      "`a13_mixed.json` (computed in R with `--mixed`; the release ships it and does not re-run it)."),
        "did not converge": "ordinal mixed model: did not converge (no verdict; error recorded)",
        "not run": ("The ordinal mixed model, rating ~ drift + study + (1 | row) + (1 | rater), has not been run "
                    "(`--mixed`, in R, writes `a13_mixed.json`)."),
        STALE: (f"ordinal mixed model: {STALE}; `a13_mixed.json` was fitted on other raters than the ones "
                "included here, so it is not reported."),
    }
    L += ["", mixed[sec["mixed_model"]], ""]
    return L


def sort_slots(xs):
    return sorted(xs, key=lambda s: int(s[1:]))


def guard_strays(folder):
    """Refuse when a rating file sits anywhere under the A13 folder except ratings/ (A6's guard_strays):
    the analysis reads only ratings/, so a file dropped elsewhere would be skipped in silence and the run
    would report a smaller n without saying why."""
    stray = sorted(p for p in folder.rglob("ratings-*.json") if p.parent != folder / "ratings")
    if stray:
        raise SystemExit("rating file(s) found outside ratings/; refusing to run, because these would be "
                         "silently excluded:\n"
                         + "\n".join(f"  {p.relative_to(folder.parent.parent)}" for p in stray)
                         + f"\nMove each into {folder / 'ratings'}/ or out of the A13 folder, and re-run.")


def load_ratings(folder, m):
    guard_strays(folder)
    files = sorted((folder / "ratings").glob("ratings-*.json"))
    if not files:
        raise SystemExit(f"no rating files yet in {folder / 'ratings'}")
    loaded, seen = [], {}
    for f in files:
        try:
            d = json.loads(f.read_text())
        except (OSError, ValueError) as e:
            raise SystemExit(f"{f.name}: unreadable ({e}); refusing to run") from None
        check_file(f, d, m)
        if d["rater"] in seen:
            raise SystemExit(f"rater slot {d['rater']} appears in two files ({seen[d['rater']]}, {f.name}); "
                             "refusing to run")
        seen[d["rater"]] = f.name
        loaded.append(d)
    return loaded


def sift(loaded, m):
    """(included docs in slot order, incomplete slots, attention-excluded slots, attention log)."""
    included, incomplete, failed, log = [], [], [], {}
    for d in loaded:
        if not complete(d, m):
            incomplete.append(d["rater"])
            continue
        att = attention(d, m)
        log[d["rater"]] = att
        if excluded_by_attention(att, EXCLUDE_IF):
            failed.append(d["rater"])
            continue
        included.append(d)
    return (sorted(included, key=lambda d: int(d["rater"][1:])), sort_slots(incomplete),
            sort_slots(failed), log)


def prepare(root, fixtures):
    root = Path(root)
    if fixtures:
        check_fixtures(root)
    else:
        require_public("A13", "analyse the A13 ratings", hint="Tests use --fixtures.")
    folder = root / "analysis" / "adherence_a13"
    m = load_mapping(folder)
    cells = a9.load_cells(root)
    mapped = {c for s in STUDIES for c in m["studies"][s]["code_to_cell"].values()}
    if mapped != set(cells):
        raise SystemExit("mapping.json's cells are not A9's 110 primary burst and camera-push cells; refusing to run")
    for s in STUDIES:
        if {cells[c]["study"] for c in m["studies"][s]["code_to_cell"].values()} != {s}:
            raise SystemExit(f"mapping.json: {s}'s codes map to another study's cells; refusing to run")
    return root, folder, m, cells


def matrix(docs, m, cell_ids):
    """Included raters x the 110 cells (sorted public ids): first-showing scores."""
    idx = {c: k for k, c in enumerate(cell_ids)}
    X = np.full((len(docs), len(cell_ids)), np.nan)
    for i, d in enumerate(docs):
        for s in STUDIES:
            c2c = m["studies"][s]["code_to_cell"]
            for r in d["studies"][s]["ratings"]:
                X[i, idx[c2c[r["clip"]]]] = r["score"]
    return X


def run(root=ROOT, write=True, fixtures=False, seed=SEED, b=B):
    root, folder, m, cells = prepare(root, fixtures)
    loaded = load_ratings(folder, m)
    included, incomplete, failed, log = sift(loaded, m)
    if not included:
        raise SystemExit("no rater is left after the completeness and attention rules")
    cell_ids = sorted(cells)
    X = matrix(included, m, cell_ids)
    alpha_all = a6.krippendorff_alpha_ordinal(X)
    flags = []
    if len(included) < MIN_RATERS:
        flags.append(f"fewer than {MIN_RATERS} included raters: analysed as they are, n = {len(included)}")
    if alpha_all is not None and alpha_all < ALPHA_FLAG:
        flags.append(f"Krippendorff's ordinal alpha over all clips {alpha_all:.3f} < {ALPHA_FLAG}: reported; "
                     "A13-H4 is tested either way")
    res = {
        "amendment": "A13", "status": "A13-H4 confirmatory; everything else reported without a verdict",
        "n_files": len(loaded), "included": [d["rater"] for d in included], "n_included": len(included),
        "incomplete": incomplete, "n_incomplete": len(incomplete),
        "excluded_attention": failed, "n_excluded_attention": len(failed),
        "attention_rule": ATTENTION_RULE[EXCLUDE_IF], "attention": log,
        "A13-H4": h4(cells, cell_ids, X.mean(axis=0), seed, b),
        "alpha_all_clips": alpha_all,
        "flags": flags,
        "secondary": {**secondaries(cells, cell_ids, X, root, m, [d for d in loaded if complete(d, m)]),
                      "mixed_model": mixed_status(root, [d["rater"] for d in included], len(cell_ids))},
    }
    res = a9._round_floats(res)
    if write:
        out = root / "analysis" / "out"
        (out / "a13_adherence.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        (out / "a13_adherence.md").write_text(markdown(res), encoding="utf-8")
    return res


def count_only(root=ROOT, fixtures=False):
    """The top-up decision's numbers: completeness and attention only, no statistic."""
    root, folder, m, _cells = prepare(root, fixtures)
    included, incomplete, failed, _log = sift(load_ratings(folder, m), m)
    return {"included": len(included), "incomplete": incomplete, "excluded_attention": failed,
            "top_up_due": len(included) < TOPUP_BELOW}


def mixed_rows(root=ROOT, fixtures=False):
    """(root, rows): one row per included rater's first showing: rating, drift, study, row, rater."""
    root, folder, m, cells = prepare(root, fixtures)
    included, *_rest = sift(load_ratings(folder, m), m)
    rows = []
    for d in included:
        for s in STUDIES:
            c2c = m["studies"][s]["code_to_cell"]
            for r in sorted(d["studies"][s]["ratings"], key=lambda x: x["clip"]):
                c = cells[c2c[r["clip"]]]
                rows.append({"rating": r["score"], "drift": c["drift"], "study": s, "row": row_of(c),
                             "rater": d["rater"]})
    return root, rows


def run_mixed(root=ROOT, fixtures=False, rscript="Rscript", lock=None, test_control=None):
    """Secondary, no verdict: analysis/a13_mixed.R on the included ratings; writes analysis/out/a13_mixed.json.
    A13_R_LIBS names the R library folder holding the versions analysis/a13-r-lock.txt pins (R refuses any
    other). A model that does not converge returns normally with "converged": false (a recorded outcome).
    `lock` and `test_control` ({"iter.max": 2}: optimizer settings) are for tests; neither is on the CLI."""
    lib = os.environ.get("A13_R_LIBS")
    if not lib:
        raise SystemExit("--mixed needs A13_R_LIBS: the R library folder holding the pinned ordinal "
                         "(analysis/a13-r-lock.txt)")
    root, rows = mixed_rows(root, fixtures)
    if not rows:
        raise SystemExit("no rater is left after the completeness and attention rules")
    out = Path(root) / "analysis" / "out" / "a13_mixed.json"
    with tempfile.TemporaryDirectory() as t:
        src = Path(t) / "a13_mixed_input.csv"
        with open(src, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["rating", "drift", "study", "row", "rater"])
            w.writeheader()
            w.writerows(rows)
        cmd = [rscript, "--vanilla", str(ROOT / "analysis" / "a13_mixed.R"), str(src), str(out),
               str(lock or ROOT / "analysis" / "a13-r-lock.txt"), lib]
        if test_control:
            cmd.append(",".join(f"{k}={v}" for k, v in sorted(test_control.items())))
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"the mixed model failed in R: {r.stderr.strip()[-400:]}")
    return json.loads(out.read_text())


def markdown(r):
    h = r["A13-H4"]
    L = ["# A13: adherence at power", "",
         "*A13-H4 is confirmatory (amendment A13). Everything else is reported without a verdict.*", "",
         "## Raters", "",
         f"Rating files: {r['n_files']}. Included: {r['n_included']} ({', '.join(r['included']) or 'none'}). "
         f"Incomplete: {r['n_incomplete']} ({', '.join(r['incomplete']) or 'none'}). "
         f"Excluded by the attention rule: {r['n_excluded_attention']} "
         f"({', '.join(r['excluded_attention']) or 'none'}).", "",
         f"Attention rule: {r['attention_rule']}.", ""]
    if r["flags"]:
        L += ["Flags: " + "; ".join(r["flags"]) + ".", ""]
    L += ["## A13-H4 (confirmatory)", "",
          f"Spearman ρ(released line drift, mean adherence score) over {h['n_clips']} clips = {fmt(h['rho'])}; "
          f"one-sided p = {fmt(h['p_one_sided'], 4)} from {h['permutations']:,} permutations of the mean scores "
          f"within the {h['n_rows']} rows (seed {h['seed']}). Rule: {h['rule']}. **Reading: {h['reading']}.**", "",
          f"Within rows only, no verdict: ρ = {fmt(h['rho_within_rows'])}, "
          f"one-sided p = {fmt(h['p_within_rows'], 4)}.", ""]
    L += markdown_secondary(r["secondary"])
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--fixtures", metavar="DIR", help="a synthetic tree (tests); no registration check")
    ap.add_argument("--count-only", action="store_true", help="completeness and attention only (the top-up decision)")
    ap.add_argument("--mixed", action="store_true", help="also the ordinal mixed model in R (writes a13_mixed.json)")
    a = ap.parse_args(argv)
    root = Path(a.fixtures) if a.fixtures else ROOT
    if a.count_only:
        c = count_only(root, fixtures=bool(a.fixtures))
        print(f"included {c['included']}; incomplete {', '.join(c['incomplete']) or 'none'}; "
              f"excluded by attention {', '.join(c['excluded_attention']) or 'none'}; "
              f"top-up due: {'yes' if c['top_up_due'] else 'no'} (no statistic computed)")
        return
    mx = run_mixed(root, fixtures=bool(a.fixtures)) if a.mixed else None   # first: the report states its outcome
    res = run(root, fixtures=bool(a.fixtures))
    h = res["A13-H4"]
    print(f"A13-H4: rho {fmt(h['rho'])}, p {fmt(h['p_one_sided'], 4)}: {h['reading']} "
          f"({res['n_included']} raters included)")
    if mx is not None and mx["converged"]:
        d = mx["drift"]
        print(f"mixed model (no verdict): drift {d['estimate']} (se {d['se']})")
    elif mx is not None:
        print("mixed model (no verdict): did not converge; the error is recorded in a13_mixed.json")


if __name__ == "__main__":
    main()
