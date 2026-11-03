#!/usr/bin/env python3
"""A9 Test 2: with line drift measured only where the requested motion should not
reach, does Gen-4.5's gap to Wan 2.2 shrink by at least half?

*** EXPLORATORY AND POST-HOC (amendment A9). Every number here is labelled so. ***

    python analysis/a9_masked_drift.py

Inputs: `runs/metrics-masked/*.json` (written by `metrics/masked.py a9-run`, one
extraction per clip: the whole-frame value and both mask sets at margins 16, 32 and
64 px) and `analysis/out/a9_eligible.csv` (rows eligible under both mask sets at
m = 32, fixed before any mask value existed).

Per condition (mask set x margin): D_e = engine median over its eligible clips, both
columns from the same clips; a clip whose frame 0 has fewer than 500 line px in R
leaves both columns. g = log2(D_Gen-4.5 / D_Wan), s = 1 - g_masked / g_whole,
delta_g = g_whole - g_masked, Kendall tau_b between the engines' whole-frame and
masked medians. Bootstrap over eligible panels (an A1 panel carries both its rows),
B = 10,000, numpy.random.default_rng(20261030), percentile 95% intervals.

Edge behaviour (registered, not tunable):
- A clip with no scorable frame scores +inf. masked.py stores +inf as `chamfer_px: null` because JSON
  has no infinity (with `no_scorable_frame: true` for the masked values). A whole-frame `chamfer_px`
  that is null is +inf in the same way: it is the registered score of such a clip, not a missing
  value, so it stays in the medians (at the top) instead of dropping out. Every other number must be
  finite and >= 0, or the script exits naming the file and field.
- `m_empty` (per mask set, written by masked.py) is true when a drawn mask fills no pixel on a clip's
  grid, so R is the whole grid; such clips are kept, and each condition reports `n_m_empty` per engine.
- A median that is +inf makes g or s undefined (None in the JSON); each condition reports, per
  engine, `n_unscorable_masked` and `n_unscorable_whole` (kept clips scored +inf).
- Bootstrap replicates with g_whole < 0 stay in the s and delta_g intervals (registered behaviour;
  only non-finite values are dropped, so g_whole = 0, where s is undefined, leaves the s interval)
  and are counted in n_g_whole_le_0.
- In the verdict, s = None counts as neither high nor low (neither >= 0.5 nor < 0.25).
- Kendall tau_b is computed from integer pair counts, so a perfectly concordant pair of orders gives
  exactly 1.0; the verdict tests `== 1.0`, with no tolerance.

Inputs are checked before anything is computed: exactly 109 clip files (22 rows x 5 engines, less
Turbo's refused cu-tone-3_idle cell), unique cell ids of the form <panel>_<motion>_<suffix>, the
five engines, one clip per (row, engine), and the rows equal to the 22 rows of a9_eligible.csv.

Outputs: analysis/out/a9_masked_drift.json, a9_masked_drift.md, figures/a9_masked_drift.png; the
paths and sha256 of the three are printed. All text is read and written as UTF-8 with LF newlines.
The figure is built without pyplot, from matplotlib's bundled defaults (a user's matplotlibrc is ignored), in
DejaVu Sans, with no version string in the PNG. The outputs are byte-for-byte reproducible under Python 3.12.10, numpy 2.5.2, matplotlib 3.11.1, Pillow 12.3.0 (the stack is recorded in the JSON under `environment`).
"""
import csv
import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import matplotlib
import numpy as np
import PIL

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261030
B = 10_000
MARGINS = (16, 32, 64)
PRIMARY_MARGIN = 32
SETS = ("aaron", "agent")
MIN_F0_LINE_PX = 500
G_WHOLE_MIN = 1.0
LEAGUE_ORDER = ("wan22", "gen4_turbo", "ltx23", "gen4.5", "h3-fal")      # frozen league order, never a rank
ENGINE_NAMES = {"wan22": "Wan 2.2", "gen4_turbo": "Gen-4 Turbo", "ltx23": "LTX-2.3",
                "gen4.5": "Gen-4.5", "h3-fal": "MiniMax H3"}
SPLITS = {"all": ("idle", "burst"), "idle": ("idle",), "burst": ("burst",)}
N_ROWS = 22
N_CLIPS = 109                      # 22 rows x 5 engines, less Turbo's refused idle cell
MOTIONS = ("idle", "burst")
SUFFIX = {"wan22": "wan22", "gen4_turbo": "gen4t", "ltx23": "ltx23", "gen4.5": "gen45", "h3-fal": "h3"}
REFUSED_CELL = ("cu-tone-3_idle", "gen4_turbo")      # (row, engine): the one cell Runway refused
RULES = {
    "supported": "s >= 0.5 under both mask sets and the lower endpoint of the bootstrap 95% percentile interval for s "
                 "(Aaron's masks) is strictly above 0 (an endpoint of exactly 0 fails)",
    "mask-dependent": "s >= 0.5 under one mask set only",
    "killed": "Kendall tau_b = 1 under both mask sets and s < 0.25 under both",
    "not supported": "any other outcome",
    "not testable": "g_whole < 1.0 on the eligible cells (under either mask set)",
    "scope": "verdict at m = 32 on the idle + burst cells; the full grid and the idle-only and burst-only "
             "splits are reported without a verdict",
}


def num(x):
    """JSON-safe float: None for nan or infinity."""
    return None if x is None or not math.isfinite(x) else float(x)


def environment():
    return {"python": platform.python_version(), "numpy": np.__version__,
            "matplotlib": matplotlib.__version__, "pillow": PIL.__version__}


def _pow2(g):
    """2 ** g, or None if g is not finite or the result overflows."""
    if not math.isfinite(g):
        return None
    try:
        return float(2.0 ** g)
    except OverflowError:
        return None


# -------------------------------------------------------------------- inputs
def _get(d, name, *path):
    cur = d
    try:
        for k in path:
            cur = cur[k]
    except (KeyError, TypeError, IndexError):
        raise SystemExit(f"{name}: missing field {'.'.join(path)}") from None
    return cur


def _distance(raw, name, field):
    """A chamfer value: a finite number >= 0 (a bool, string, list, NaN or infinity is refused)."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw) or raw < 0:
        raise SystemExit(f"{name}: {field} must be a finite number >= 0, found {raw!r}")
    return float(raw)


def _text(d, name, key):
    v = _get(d, name, key)
    if not isinstance(v, str) or not v:
        raise SystemExit(f"{name}: {key} must be a non-empty string, found {v!r}")
    return v


def _read_clip(f):
    name = f.name
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"{name}: not valid JSON ({e})") from None
    except (OSError, ValueError) as e:                                  # includes UnicodeDecodeError
        raise SystemExit(f"{name}: unreadable ({type(e).__name__}: {e})") from None
    try:
        masked = {}
        for s in SETS:
            for m in MARGINS:
                base = ("masked", s, f"m{m}")
                nsf = _get(d, name, *base, "no_scorable_frame")
                if not isinstance(nsf, bool):
                    raise SystemExit(f"{name}: {'.'.join(base)}.no_scorable_frame must be true or false, found {nsf!r}")
                raw = _get(d, name, *base, "chamfer_px")
                v = math.inf if nsf else _distance(raw, name, ".".join(base) + ".chamfer_px")
                f0 = _get(d, name, *base, "f0_line_px_in_R")
                if isinstance(f0, bool) or not isinstance(f0, int) or f0 < 0:
                    raise SystemExit(f"{name}: {'.'.join(base)}.f0_line_px_in_R must be an integer >= 0, found {f0!r}")
                masked[(s, m)] = (v, f0)
        m_empty = {}
        for s in SETS:
            v = _get(d, name, "m_empty", s)
            if not isinstance(v, bool):
                raise SystemExit(f"{name}: m_empty.{s} must be true or false, found {v!r}")
            m_empty[s] = v
        w = _get(d, name, "whole_frame", "chamfer_px")
        panel, motion = _text(d, name, "panel"), _text(d, name, "motion")
        return {"cell_id": _text(d, name, "cell_id"), "panel": panel, "motion": motion,
                "engine": _text(d, name, "engine"), "row": f"{panel}_{motion}",
                "whole": math.inf if w is None else _distance(w, name, "whole_frame.chamfer_px"),
                "masked": masked, "m_empty": m_empty}
    except (KeyError, TypeError, ValueError) as e:                      # anything the checks above missed
        raise SystemExit(f"{name}: malformed ({type(e).__name__}: {e})") from None


def load_clips(root):
    files = sorted((Path(root) / "runs" / "metrics-masked").glob("*.json"))
    if not files:
        raise SystemExit("no runs/metrics-masked/*.json: run `metrics/masked.py a9-run` (after registration)")
    return sorted((_read_clip(f) for f in files), key=lambda c: c["cell_id"])


def _read_eligibility(path):
    """(every row key, the eligible row keys) from a9_eligible.csv, checked."""
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if not {"row", "eligible"} <= set(reader.fieldnames or ()):
            raise SystemExit(f"{Path(path).name}: columns row and eligible are required")
    if len(rows) != N_ROWS:
        raise SystemExit(f"{Path(path).name}: expected {N_ROWS} rows, found {len(rows)}")
    keys = [r["row"] for r in rows]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        raise SystemExit(f"{Path(path).name}: duplicate rows {dup}")
    bad = [r["row"] for r in rows if r["eligible"] not in ("true", "false")]
    if bad:
        raise SystemExit(f"{Path(path).name}: eligible must be true or false (rows {bad})")
    return sorted(keys), sorted(r["row"] for r in rows if r["eligible"] == "true")


def load_eligible(path):
    return _read_eligibility(path)[1]


def validate_inputs(clips, row_keys):
    """Refuse, before any statistic is computed, unless the clip files are exactly the registered
    set: 109 clips with unique cell ids, the five engines, idle and burst only, rows equal to the 22
    rows of a9_eligible.csv, one clip per (row, engine), each cell id <panel>_<motion>_<suffix>,
    and the only missing (row, engine) cell is Turbo's refused cu-tone-3_idle."""
    if len(clips) != N_CLIPS:
        raise SystemExit(f"runs/metrics-masked: expected {N_CLIPS} clip files, found {len(clips)}")
    ids = [c["cell_id"] for c in clips]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise SystemExit(f"runs/metrics-masked: duplicate cell ids {dup}")
    engines = {c["engine"] for c in clips}
    if engines != set(LEAGUE_ORDER):
        raise SystemExit(f"runs/metrics-masked: engines must be exactly {list(LEAGUE_ORDER)}; "
                         f"missing {sorted(set(LEAGUE_ORDER) - engines)}, unexpected {sorted(engines - set(LEAGUE_ORDER))}")
    odd = sorted(c["cell_id"] for c in clips if c["motion"] not in MOTIONS)
    if odd:
        raise SystemExit(f"runs/metrics-masked: motion must be idle or burst (clips {odd})")
    clip_rows, known = {c["row"] for c in clips}, set(row_keys)
    unknown = sorted(clip_rows - known)
    if unknown:
        raise SystemExit(f"rows {unknown} of the clip files are not in a9_eligible.csv")
    empty = sorted(known - clip_rows)
    if empty:
        raise SystemExit(f"a9_eligible.csv rows without clips: {empty}")
    pairs = [(c["row"], c["engine"]) for c in clips]
    twice = sorted({f"{r} x {e}" for r, e in pairs if pairs.count((r, e)) > 1})
    if twice:
        raise SystemExit(f"runs/metrics-masked: duplicate (row, engine) pairs {twice}")
    wrong = sorted(f"cell_id {c['cell_id']!r} should be {c['row'] + '_' + SUFFIX[c['engine']]!r}"
                   for c in clips if c["cell_id"] != f"{c['row']}_{SUFFIX[c['engine']]}")
    if wrong:
        raise SystemExit("runs/metrics-masked: " + "; ".join(wrong[:5]) + (f" (and {len(wrong) - 5} more)" if len(wrong) > 5 else ""))
    missing = sorted(f"{r} x {e}" for r in known for e in LEAGUE_ORDER if (r, e) not in set(pairs))
    allowed = f"{REFUSED_CELL[0]} x {REFUSED_CELL[1]}"
    if missing != [allowed]:
        raise SystemExit(f"runs/metrics-masked: missing cells {missing}; the only cell allowed to be missing is "
                         f"{allowed} (Runway refused it)")


# ------------------------------------------------------------------- numbers
def gap(D):
    """log2(D_Gen-4.5 / D_Wan). Zero and infinite medians give -inf, +inf or nan by the limits of the
    ratio (0/0 and inf/inf are nan); nothing is ever passed to log2 that is not a positive finite ratio."""
    w, g = float(D["wan22"]), float(D["gen4.5"])
    if math.isnan(w) or math.isnan(g) or (w == 0 and g == 0) or (math.isinf(w) and math.isinf(g)):
        return math.nan
    if g == 0 or math.isinf(w):
        return -math.inf
    if w == 0 or math.isinf(g):
        return math.inf
    q = g / w
    if math.isinf(q) or q == 0:                                  # the ratio over- or underflows
        return math.log2(g) - math.log2(w)
    return math.log2(q)


def kendall_tau_b(x, y):
    if not all(math.isfinite(v) for v in list(x) + list(y)):
        return None
    conc = disc = tx = ty = 0
    for i in range(len(x)):
        for j in range(i + 1, len(x)):
            dx, dy = np.sign(x[i] - x[j]), np.sign(y[i] - y[j])
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                tx += 1
            elif dy == 0:
                ty += 1
            elif dx == dy:
                conc += 1
            else:
                disc += 1
    den = math.sqrt((conc + disc + tx) * (conc + disc + ty))
    return None if den == 0 else (conc - disc) / den


def shrink(g_whole, g_masked):
    if not (math.isfinite(g_whole) and math.isfinite(g_masked)) or g_whole == 0:
        return math.nan
    return 1 - g_masked / g_whole


def condition_clips(clips, eligible, mask_set, margin, motions):
    """(kept, excluded): clips on eligible rows of the given classes; a clip whose frame 0
    has fewer than 500 line px in R is excluded from both columns."""
    kept, excluded = [], []
    for c in clips:
        if c["row"] not in eligible or c["motion"] not in motions:
            continue
        v, f0 = c["masked"][(mask_set, margin)]
        rec = {"cell_id": c["cell_id"], "panel": c["panel"], "engine": c["engine"], "whole": c["whole"], "masked": v,
               "m_empty": c["m_empty"][mask_set]}
        (kept if f0 >= MIN_F0_LINE_PX else excluded).append(rec)
    return kept, excluded


def medians(kept):
    D_w, D_m = {}, {}
    for e in LEAGUE_ORDER:
        mine = [c for c in kept if c["engine"] == e]
        D_w[e] = float(np.median([c["whole"] for c in mine])) if mine else math.nan
        D_m[e] = float(np.median([c["masked"] for c in mine])) if mine else math.nan
    return D_w, D_m


def panel_draws(panels, b=B):
    """B x n_panels resample indices, one fresh generator per split, so every condition in
    a split sees the same resamples."""
    return np.random.default_rng(SEED).integers(0, len(panels), size=(b, len(panels)))


def per_engine_arrays(kept, panels):
    """engine -> (panel index, whole values, masked values) of its kept clips."""
    idx = {p: i for i, p in enumerate(panels)}
    out = {}
    for e in LEAGUE_ORDER:
        mine = [c for c in kept if c["engine"] == e]
        out[e] = (np.array([idx[c["panel"]] for c in mine], dtype=int),
                  np.array([c["whole"] for c in mine]), np.array([c["masked"] for c in mine]))
    return out


def replicate(arrays, counts):
    """Engine medians for one resample: each clip enters as often as its panel was drawn,
    so an A1 panel brings both of its rows."""
    Dw, Dm = {}, {}
    for e, (pi, w, m) in arrays.items():
        wt = counts[pi]
        if wt.sum() == 0:
            Dw[e] = Dm[e] = math.nan
            continue
        Dw[e] = float(np.median(np.repeat(w, wt)))
        Dm[e] = float(np.median(np.repeat(m, wt)))
    return Dw, Dm


def bootstrap(kept, panels, draws):
    arrays = per_engine_arrays(kept, panels)
    s_vals, dg_vals, gw_vals = [], [], []
    for row in draws:
        Dw, Dm = replicate(arrays, np.bincount(row, minlength=len(panels)))
        gw, gm = gap(Dw), gap(Dm)
        gw_vals.append(gw)
        s_vals.append(shrink(gw, gm))
        dg_vals.append(gw - gm if math.isfinite(gw) and math.isfinite(gm) else math.nan)
    s_arr, dg_arr, gw_arr = np.array(s_vals), np.array(dg_vals), np.array(gw_vals)

    def ci(a):
        f = a[np.isfinite(a)]
        return [float(v) for v in np.percentile(f, [2.5, 97.5])] if f.size else None

    return {"B": int(len(draws)), "seed": SEED, "s_ci95": ci(s_arr), "delta_g_ci95": ci(dg_arr),
            "n_s_finite": int(np.isfinite(s_arr).sum()), "n_delta_g_finite": int(np.isfinite(dg_arr).sum()),
            "n_g_whole_le_0": int((gw_arr <= 0).sum())}


def analyse_condition(clips, eligible, mask_set, margin, motions, panels, draws):
    kept, excluded = condition_clips(clips, eligible, mask_set, margin, motions)
    D_w, D_m = medians(kept)
    g_w, g_m = gap(D_w), gap(D_m)
    s = shrink(g_w, g_m)
    return {
        "mask_set": mask_set, "margin_px": margin,
        "n_clips": {e: sum(c["engine"] == e for c in kept) for e in LEAGUE_ORDER},
        "excluded_lt500": sorted(c["cell_id"] for c in excluded),
        "D_whole_px": {e: num(D_w[e]) for e in LEAGUE_ORDER},
        "D_masked_px": {e: num(D_m[e]) for e in LEAGUE_ORDER},
        "g_whole": num(g_w), "g_masked": num(g_m),
        "ratio_whole": _pow2(g_w), "ratio_masked": _pow2(g_m),
        "n_unscorable_masked": {e: sum(c["engine"] == e and math.isinf(c["masked"]) for c in kept) for e in LEAGUE_ORDER},
        "n_m_empty": {e: sum(c["engine"] == e and c["m_empty"] for c in kept) for e in LEAGUE_ORDER},
        "n_unscorable_whole": {e: sum(c["engine"] == e and math.isinf(c["whole"]) for c in kept) for e in LEAGUE_ORDER},
        "s": num(s), "delta_g": num(g_w - g_m) if math.isfinite(g_w) and math.isfinite(g_m) else None,
        "kendall_tau_b": kendall_tau_b([D_w[e] for e in LEAGUE_ORDER], [D_m[e] for e in LEAGUE_ORDER]),
        "bootstrap": bootstrap(kept, panels, draws),
    }


def verdict(cA, cG):
    """The registered verdict from the m = 32 conditions (Aaron's set, the blind set)."""
    if any(c["g_whole"] is None or c["g_whole"] < G_WHOLE_MIN for c in (cA, cG)):
        return "not testable"
    sA, sG = cA["s"], cG["s"]
    hiA, hiG = sA is not None and sA >= 0.5, sG is not None and sG >= 0.5
    # registered: the lower endpoint of the bootstrap 95% interval for s (Aaron's masks) is strictly > 0;
    # an endpoint of exactly 0, an interval wholly below 0, or a missing or non-finite interval fails
    ci = (cA.get("bootstrap") or {}).get("s_ci95")
    ci_low_positive = (isinstance(ci, (list, tuple)) and len(ci) == 2 and all(math.isfinite(v) for v in ci)
                       and ci[0] > 0)
    if hiA and hiG and ci_low_positive:
        return "supported"
    if hiA != hiG:
        return "mask-dependent"
    # tau_b comes from integer pair counts: concordant pairs only, no ties, is c / sqrt(c * c), exactly 1.0
    tau1 = all(c["kendall_tau_b"] is not None and c["kendall_tau_b"] == 1.0 for c in (cA, cG))
    if tau1 and all(s is not None and s < 0.25 for s in (sA, sG)):
        return "killed"
    return "not supported"


def analyse(clips, eligible, b=B):
    grid = {}
    for split, motions in SPLITS.items():
        panels = sorted({c["panel"] for c in clips if c["row"] in eligible and c["motion"] in motions})
        draws = panel_draws(panels, b=b)
        grid[split] = [analyse_condition(clips, eligible, s, m, motions, panels, draws)
                       for s in SETS for m in MARGINS]
    pick = {(c["mask_set"], c["margin_px"]): c for c in grid["all"]}
    cA, cG = pick[("aaron", PRIMARY_MARGIN)], pick[("agent", PRIMARY_MARGIN)]
    return {
        "amendment": "A9", "test": "Test 2: masked drift", "status": "exploratory, post-hoc",
        "verdict": verdict(cA, cG), "rules": RULES,
        "engine_order": list(LEAGUE_ORDER), "eligible_rows": eligible, "n_eligible_rows": len(eligible),
        "min_f0_line_px_in_R": MIN_F0_LINE_PX, "bootstrap": {"B": b, "seed": SEED, "unit": "panel"},
        "grid": grid, "environment": environment(),
    }


# -------------------------------------------------------------------- output
def _f(v, nd=3):
    return "n/a" if v is None else f"{v:.{nd}f}"


def headline(c):
    n = sum(c["n_clips"].values())
    rw, rm, s, ci = c["ratio_whole"], c["ratio_masked"], c["s"], c["bootstrap"]["s_ci95"]
    if rw is None or rm is None:
        return f"Post-hoc (A9): on {n} cells the Gen-4.5/Wan ratio is undefined under these masks."
    verb = "falls" if rm < rw else "rises" if rm > rw else "stays"
    ci_txt = f"95% CI {_f(ci[0], 2)} to {_f(ci[1], 2)}" if ci else "no CI"
    return (f"Post-hoc (A9): on {n} cells, Gen-4.5/Wan {verb} from {rw:.1f}× to {rm:.1f}× outside the region the "
            f"prompt allows to move (s = {_f(s, 2)}, {ci_txt}). The frozen league is unchanged; this qualifies "
            f"how its gap is read.")


def markdown(res):
    pick = {(c["mask_set"], c["margin_px"]): c for c in res["grid"]["all"]}
    L = ["# A9 Test 2: masked drift", "",
         "Post-hoc (A9), exploratory. Rows are in frozen-league order; there is no rank column. Masked",
         "medians appear only beside whole-frame medians on the same cells.", "",
         f"**Verdict (m = 32, both mask sets): {res['verdict']}.**", ""]
    for s in SETS:
        L.append(f"- {s}'s masks: " + headline(pick[(s, PRIMARY_MARGIN)]))
    L += ["", f"Eligible rows: {res['n_eligible_rows']} of {N_ROWS}. Bootstrap: {res['bootstrap']['B']} panel "
              f"resamples, seed {res['bootstrap']['seed']}.", ""]
    for split, conds in res["grid"].items():
        L += [f"## Split: {split}" + (" (the registered verdict's cells)" if split == "all" else " (no verdict)"), ""]
        for c in conds:
            bs = c["bootstrap"]
            L += [f"### {c['mask_set']} masks, m = {c['margin_px']} px", "",
                  "| engine | clips | whole-frame median (px) | masked median (px) |", "|---|---|---|---|"]
            for e in LEAGUE_ORDER:
                L.append(f"| {ENGINE_NAMES[e]} | {c['n_clips'][e]} | {_f(c['D_whole_px'][e])} | "
                         f"{_f(c['D_masked_px'][e])} |")
            sci, dci = bs["s_ci95"], bs["delta_g_ci95"]
            unsc = [f"{ENGINE_NAMES[e]}: masked {c['n_unscorable_masked'][e]}, whole-frame {c['n_unscorable_whole'][e]}"
                    for e in LEAGUE_ORDER if c["n_unscorable_masked"][e] or c["n_unscorable_whole"][e]]
            if unsc:
                L += ["", "Clips with no scorable frame (scored +inf, so inside the medians and the clip counts): "
                      + "; ".join(unsc) + "."]
            empty = [f"{ENGINE_NAMES[e]}: {c['n_m_empty'][e]}" for e in LEAGUE_ORDER if c["n_m_empty"][e]]
            if empty:
                L += ["", "Clips whose drawn mask fills no pixel (R is the whole grid; kept, and inside the clip "
                          "counts): " + "; ".join(empty) + "."]
            L += ["", f"g_whole {_f(c['g_whole'])}, g_masked {_f(c['g_masked'])}, s {_f(c['s'])} "
                      f"(95% CI {_f(sci[0]) if sci else 'n/a'} to {_f(sci[1]) if sci else 'n/a'}), "
                      f"delta g {_f(c['delta_g'])} (95% CI {_f(dci[0]) if dci else 'n/a'} to "
                      f"{_f(dci[1]) if dci else 'n/a'}), Kendall tau_b {_f(c['kendall_tau_b'])}; "
                      f"replicates with g_whole <= 0: {bs['n_g_whole_le_0']}.",
                  f"Excluded (frame 0 under {MIN_F0_LINE_PX} line px in R): "
                  + (", ".join(f"`{x}`" for x in c["excluded_lt500"]) or "none") + ".", ""]
    return "\n".join(L)


def figure(res, path):
    """Drawn without pyplot, from matplotlib's bundled defaults (the user's matplotlibrc is ignored),
    DejaVu Sans, a fixed PNG compression level and no Software or other text chunk."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    rc = {k: v for k, v in matplotlib.rcParamsDefault.items() if k != "backend"}
    rc["font.family"] = ["DejaVu Sans"]
    pick = {(c["mask_set"], c["margin_px"]): c for c in res["grid"]["all"]}
    with matplotlib.rc_context(rc):
        fig = Figure(figsize=(8, 3.8), layout="tight")
        FigureCanvasAgg(fig)
        axes = fig.subplots(1, 2, sharey=True)
        for ax, s in zip(axes, SETS):
            c = pick[(s, PRIMARY_MARGIN)]
            for e in LEAGUE_ORDER:
                w, m = c["D_whole_px"][e], c["D_masked_px"][e]
                if w is None or m is None:
                    continue
                ax.plot([0, 1], [w, m], "-o", color="black" if e in ("gen4.5", "wan22") else "0.6", lw=1.2)
                ax.annotate(ENGINE_NAMES[e], (1, m), xytext=(6, 0), textcoords="offset points", va="center", fontsize=8)
            ax.set_xticks([0, 1], ["whole frame", f"masked (m = {PRIMARY_MARGIN})"])
            ax.set_xlim(-0.2, 1.6)
            ax.set_yscale("log")
            ax.set_title(f"{s}'s masks", fontsize=10)
        axes[0].set_ylabel("engine median line drift (px)")
        fig.suptitle("A9 Test 2, post-hoc: same cells, two measurements", fontsize=10)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, format="png", dpi=150, metadata={"Software": None}, pil_kwargs={"compress_level": 6})


def run(root=ROOT, out_dir=None, b=B):
    root = Path(root)
    out_dir = Path(out_dir) if out_dir else root / "analysis" / "out"
    clips = load_clips(root)
    row_keys, eligible = _read_eligibility(root / "analysis" / "out" / "a9_eligible.csv")
    validate_inputs(clips, row_keys)
    res = analyse(clips, eligible, b=b)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = [out_dir / "a9_masked_drift.json", out_dir / "a9_masked_drift.md",
               out_dir / "figures" / "a9_masked_drift.png"]
    outputs[0].write_text(json.dumps(res, indent=1, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    outputs[1].write_text(markdown(res), encoding="utf-8", newline="\n")
    figure(res, outputs[2])
    for f in outputs:
        print(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f}")
    return res


def main():
    res = run()
    print(f"A9 Test 2: {res['verdict']} -> analysis/out/a9_masked_drift.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
