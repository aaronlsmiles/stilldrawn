#!/usr/bin/env python3
"""Does the engine league table rank stability, or rank stillness?

*** EXPLORATORY — post-hoc. See PREREGISTRATION.md amendment A6. ***

The five frozen metrics are all optimised by a clip that does not move, so a
stability ranking alone cannot separate an engine that holds the inked register
from an engine that barely animates. This script pairs each cell's frozen
stability headlines with the post-hoc motion magnitude from `metrics/motion.py`
(runs/metrics-motion/) and asks three questions:

  Q1  Do engines differ in motion magnitude, and does the league leader move
      least? (Descriptive, per engine, on the 33-cell primary basis.)
  Q2  Within an engine, does a cell's motion predict its stability scores?
      (Spearman rho per engine per metric — a within-engine association means
      the metric is partly measuring stillness rather than register survival.)
  Q3  Does the league ordering survive conditioning on motion? Two ways:
      (a) partial Spearman of engine rank vs metric, controlling motion;
      (b) a matched-motion comparison restricted to cells in a common motion
          band, so engines are compared at comparable degrees of movement.

Also reported: the same association on the A3 ground series, because a live
alternative explanation for the ground effect is that a darker paper ground
suppresses motion rather than improving register.

The registered prediction (A6, before running): the league ordering is at least
partly explained by motion. Either outcome is reportable.

Outputs: analysis/out/motion_confound.json (+ a readable summary on stdout).
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MOTION_DIR = ROOT / "runs" / "metrics-motion"
TABLE = Path(__file__).resolve().parent / "out" / "results_table.csv"
OUT = Path(__file__).resolve().parent / "out" / "motion_confound.json"

HEADLINES = [
    "line_chamfer_mean_px",
    "tone_variance",
    "edge_abs_slope",
    "style_terminal",
    "closure_abs_terminal",
]
# Lower is better ("more stable") for every frozen headline.


# At or below this n the p-value is exact: every permutation is enumerated.
EXACT_MAX_N = 9


def spearman(x, y):
    """Spearman rho + two-sided p. Returns (rho, p, n).

    p is an exact permutation p for n <= EXACT_MAX_N (the five-engine and
    five-step ground correlations) and the t(n-2) tail above it. The first
    release used a normal tail throughout, which overstated significance by
    two orders of magnitude at n = 5 (see docs/ERRATA.md)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    n = x.size
    if n < 4 or np.ptp(x) == 0 or np.ptp(y) == 0:
        # Too few points, or one side constant — rho is undefined, not zero.
        return None, None, int(n)
    rx = _rank(x)
    ry = _rank(y)
    rho = float(np.corrcoef(rx, ry)[0, 1])
    if not np.isfinite(rho) or abs(rho) >= 1.0:
        return rho if np.isfinite(rho) else None, 0.0 if np.isfinite(rho) else None, int(n)
    if n <= EXACT_MAX_N:
        from itertools import permutations

        hits = total = 0
        for perm in permutations(ry):
            r = np.corrcoef(rx, perm)[0, 1]
            hits += abs(r) >= abs(rho) - 1e-12
            total += 1
        return rho, hits / total, int(n)
    from scipy.stats import t as t_dist

    t = rho * np.sqrt((n - 2) / (1 - rho**2))
    p = 2 * t_dist.sf(abs(t), n - 2)
    return rho, float(p), int(n)


def _rank(a):
    """Average ranks, ties shared."""
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(a.size, dtype=float)
    ranks[order] = np.arange(1, a.size + 1, dtype=float)
    # average ties
    vals, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    for i, c in enumerate(counts):
        if c > 1:
            m = inv == i
            ranks[m] = ranks[m].mean()
    return ranks


def partial_spearman(x, y, z):
    """Spearman of x,y controlling z — correlation of rank residuals."""
    x, y, z = (np.asarray(v, dtype=float) for v in (x, y, z))
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    x, y, z = x[ok], y[ok], z[ok]
    if x.size < 5:
        return None, int(x.size)
    rx, ry, rz = _rank(x), _rank(y), _rank(z)

    def resid(a, b):
        b1 = np.vstack([b, np.ones_like(b)]).T
        coef, *_ = np.linalg.lstsq(b1, a, rcond=None)
        return a - b1 @ coef

    return float(np.corrcoef(resid(rx, rz), resid(ry, rz))[0, 1]), int(x.size)


def load_rows():
    """Standard cells only (the 33-cell primary basis). FLINT cells are
    excluded: their vs-frame-0 scalars measure the intended transport plus
    drift, so they never enter a cross-engine comparison. The first release
    pooled H3's six FLINT cells in (n = 39; see docs/ERRATA.md)."""
    import csv

    rows = []
    with TABLE.open() as fh:
        for r in csv.DictReader(fh):
            if r.get("flint_pair"):
                continue
            rows.append(r)
    return rows


def load_motion():
    motion = {}
    for p in sorted(MOTION_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        motion[p.stem] = {
            "median_px": d["motion"]["headline_median_px"],
            "median_norm": d["motion"]["headline_median_norm"],
            "backend": d["backend"],
        }
    return motion


def fnum(v):
    try:
        f = float(v)
        return f if np.isfinite(f) else np.nan
    except (TypeError, ValueError):
        return np.nan


def main():
    rows = load_rows()
    motion = load_motion()

    # Join. The table's cell_id matches the clip stem for every engine.
    joined, missing = [], []
    for r in rows:
        m = motion.get(r["cell_id"])
        if m is None:
            missing.append(r["cell_id"])
            continue
        r = dict(r)
        r["motion_norm"] = m["median_norm"]
        r["motion_px"] = m["median_px"]
        joined.append(r)

    engines = sorted({r["engine"] for r in joined})
    out = {
        "status": "EXPLORATORY — post-hoc, PREREGISTRATION.md amendment A6",
        "n_cells_joined": len(joined),
        "n_cells_missing_motion": len(missing),
        "missing_examples": missing[:10],
        "motion_backend": next(iter(motion.values()))["backend"] if motion else None,
    }

    # --- Q1: motion by engine -------------------------------------------------
    q1 = {}
    for e in engines:
        vals = np.array([r["motion_norm"] for r in joined if r["engine"] == e], dtype=float)
        med = np.array([fnum(r["line_chamfer_mean_px"]) for r in joined if r["engine"] == e])
        q1[e] = {
            "n": int(vals.size),
            "motion_median_norm": float(np.median(vals)),
            "motion_iqr": [float(np.percentile(vals, 25)), float(np.percentile(vals, 75))],
            "chamfer_median_px": float(np.nanmedian(med)),
        }
    out["q1_motion_by_engine"] = q1

    order_motion = sorted(engines, key=lambda e: q1[e]["motion_median_norm"])
    order_chamfer = sorted(engines, key=lambda e: q1[e]["chamfer_median_px"])
    out["q1_ordering"] = {
        "engines_by_motion_ascending": order_motion,
        "engines_by_chamfer_ascending": order_chamfer,
        "note": "if these orderings agree, the stability league is tracking stillness",
    }
    rho, p, n = spearman(
        [q1[e]["motion_median_norm"] for e in engines],
        [q1[e]["chamfer_median_px"] for e in engines],
    )
    out["q1_engine_level_rho_motion_vs_chamfer"] = {"rho": rho, "p": p, "n_engines": n}

    # --- Q2: within-engine association ---------------------------------------
    q2 = {}
    for e in engines:
        sub = [r for r in joined if r["engine"] == e]
        q2[e] = {}
        for h in HEADLINES:
            rho, p, n = spearman([r["motion_norm"] for r in sub], [fnum(r[h]) for r in sub])
            q2[e][h] = {"rho": rho, "p": p, "n": n}
    out["q2_within_engine_motion_vs_metric"] = q2

    pooled = {}
    for h in HEADLINES:
        rho, p, n = spearman([r["motion_norm"] for r in joined], [fnum(r[h]) for r in joined])
        pooled[h] = {"rho": rho, "p": p, "n": n}
    out["q2_pooled"] = pooled

    # --- Q3: does the ordering survive conditioning on motion? ---------------
    # (a) partial correlation of engine motion-rank vs metric, controlling motion,
    #     computed cell-wise with engine coded by its league position.
    league_pos = {e: i for i, e in enumerate(order_chamfer)}
    q3a = {}
    for h in HEADLINES:
        pr, n = partial_spearman(
            [league_pos[r["engine"]] for r in joined],
            [fnum(r[h]) for r in joined],
            [r["motion_norm"] for r in joined],
        )
        raw, _, _ = spearman([league_pos[r["engine"]] for r in joined], [fnum(r[h]) for r in joined])
        q3a[h] = {"rho_raw": raw, "rho_controlling_motion": pr, "n": n}
    out["q3a_engine_effect_controlling_motion"] = q3a

    # (b) matched-motion band: the overlap of all engines' interquartile ranges,
    #     so every engine is compared at comparable movement.
    lo = max(q1[e]["motion_iqr"][0] for e in engines)
    hi = min(q1[e]["motion_iqr"][1] for e in engines)
    band = {"lo": float(lo), "hi": float(hi), "valid": bool(lo < hi)}
    if band["valid"]:
        banded = {}
        for e in engines:
            vals = [
                fnum(r["line_chamfer_mean_px"])
                for r in joined
                if r["engine"] == e and lo <= r["motion_norm"] <= hi
            ]
            vals = [v for v in vals if np.isfinite(v)]
            banded[e] = {
                "n": len(vals),
                "chamfer_median_px": float(np.median(vals)) if vals else None,
            }
        band["per_engine"] = banded
        usable = {e: v for e, v in banded.items() if v["chamfer_median_px"] is not None and v["n"] >= 3}
        band["ordering_in_band"] = sorted(usable, key=lambda e: usable[e]["chamfer_median_px"])
        band["n_engines_usable"] = len(usable)
    out["q3b_matched_motion_band"] = band

    # --- Q4: the ground series — is the ground effect a motion effect? -------
    # Live alternative explanation for A3: a darker paper ground suppresses
    # motion rather than improving register. If motion falls with k, the ground
    # result is confounded the same way the league is.
    KS = [1.00, 0.90, 0.80, 0.65, 0.52]
    ENGINE_TAGS = {"gen4_turbo": "gen4t", "gen4.5": "gen45", "h3-fal": "h3", "wan22": "wan22", "ltx23": "ltx23"}
    q4 = {}
    for engine, tag in ENGINE_TAGS.items():
        ks, mot, cham = [], [], []
        for k in KS:
            stem = f"ground-cu-line-1-v{int(round(k * 100)):03d}_idle_{tag}"
            mp = MOTION_DIR / f"{stem}.json"
            gp = ROOT / "runs" / "metrics-ground" / f"{stem}.json"
            if not mp.exists() or not gp.exists():
                continue
            md = json.loads(mp.read_text())
            gd = json.loads(gp.read_text())
            try:
                c = gd["metrics"]["line_drift"]["vs_frame0"]["chamfer_px"]["mean"]
            except (KeyError, TypeError):
                c = np.nan
            ks.append(k)
            mot.append(md["motion"]["headline_median_norm"])
            cham.append(fnum(c))
        if len(ks) < 4:
            q4[engine] = {"n": len(ks), "note": "insufficient points"}
            continue
        rho_km, p_km, _ = spearman(ks, mot)
        rho_kc, p_kc, _ = spearman(ks, cham)
        pr, _ = partial_spearman(ks, cham, mot)
        q4[engine] = {
            "n": len(ks),
            "k": ks,
            "motion_norm": [round(v, 6) for v in mot],
            "chamfer_px": [None if not np.isfinite(v) else round(v, 3) for v in cham],
            "rho_k_vs_motion": rho_km,
            "p_k_vs_motion": p_km,
            "rho_k_vs_chamfer": rho_kc,
            "rho_k_vs_chamfer_controlling_motion": pr,
        }
    out["q4_ground_series"] = q4

    # --- Q5: can the ordering be rescued without new generation? ------------
    # Three £0 candidate bridges, tested rather than assumed:
    #   (a) PAIRWISE matched-motion bands. Q3b failed for all five at once; a
    #       pair may still overlap, which would licence partial orderings.
    #   (b) Model-based matching: fit drift ~ motion per engine, compare the
    #       fitted drift at a common motion level. Flags extrapolation, because
    #       an engine whose motion never reaches the target is being guessed at.
    #   (c) Pareto view: an engine that is both more stable AND more mobile
    #       dominates unambiguously; everything else is a trade-off, not a rank.
    per_engine = {
        e: {
            "motion": np.array([r["motion_norm"] for r in joined if r["engine"] == e], dtype=float),
            "drift": np.array([fnum(r["line_chamfer_mean_px"]) for r in joined if r["engine"] == e]),
        }
        for e in engines
    }

    pairwise = {}
    for i, a in enumerate(engines):
        for b in engines[i + 1 :]:
            qa, qb = q1[a]["motion_iqr"], q1[b]["motion_iqr"]
            lo, hi = max(qa[0], qb[0]), min(qa[1], qb[1])
            rec = {"lo": float(lo), "hi": float(hi), "overlaps": bool(lo < hi)}
            if rec["overlaps"]:
                for e in (a, b):
                    d = per_engine[e]
                    m = (d["motion"] >= lo) & (d["motion"] <= hi) & np.isfinite(d["drift"])
                    rec[e] = {
                        "n": int(m.sum()),
                        "drift_median": float(np.median(d["drift"][m])) if m.sum() else None,
                    }
                na, nb = rec[a]["n"], rec[b]["n"]
                rec["usable"] = bool(na >= 5 and nb >= 5)
                if rec["usable"]:
                    rec["winner_in_band"] = a if rec[a]["drift_median"] < rec[b]["drift_median"] else b
            pairwise[f"{a}|{b}"] = rec
    out["q5a_pairwise_matched_bands"] = pairwise

    # (b) fitted drift at a common motion level = median motion over all cells
    target = float(np.median([r["motion_norm"] for r in joined]))
    fitted = {"target_motion_norm": target}
    for e in engines:
        d = per_engine[e]
        ok = np.isfinite(d["drift"]) & np.isfinite(d["motion"])
        x, y = d["motion"][ok], d["drift"][ok]
        if x.size < 5 or np.ptp(x) == 0:
            fitted[e] = {"note": "insufficient motion variance to fit"}
            continue
        slope, intercept = np.polyfit(x, y, 1)
        lo, hi = float(x.min()), float(x.max())
        fitted[e] = {
            "n": int(x.size),
            "slope": float(slope),
            "fitted_drift_at_target": float(slope * target + intercept),
            "motion_range": [lo, hi],
            "extrapolating": bool(target < lo or target > hi),
        }
    ranked = [
        (e, v["fitted_drift_at_target"])
        for e, v in fitted.items()
        if isinstance(v, dict) and "fitted_drift_at_target" in v
    ]
    fitted["ordering_at_target"] = [e for e, _ in sorted(ranked, key=lambda t: t[1])]
    fitted["ordering_is_partly_extrapolated"] = [
        e for e, v in fitted.items()
        if isinstance(v, dict) and v.get("extrapolating")
    ]
    out["q5b_fitted_at_common_motion"] = fitted

    # (c) Pareto frontier: maximise motion, minimise drift.
    pts = {e: (q1[e]["motion_median_norm"], q1[e]["chamfer_median_px"]) for e in engines}
    dominated = {}
    for e, (me, de) in pts.items():
        doms = [o for o, (mo, do) in pts.items() if o != e and mo >= me and do <= de and (mo > me or do < de)]
        dominated[e] = doms
    out["q5c_pareto"] = {
        "dominated_by": dominated,
        "frontier": sorted([e for e, d in dominated.items() if not d]),
        "note": "engines on the frontier are not rankable against each other without a motion-quality trade-off being stated",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))

    # --- readable summary ----------------------------------------------------
    print("EXPLORATORY (A6) — motion confound\n" + "=" * 58)
    print(f"joined {len(joined)} cells; {len(missing)} without motion yet\n")
    print("Q1  motion and stability by engine (33-cell primary basis)")
    print(f"    {'engine':<12} {'n':>4} {'motion(norm)':>13} {'chamfer(px)':>12}")
    for e in order_chamfer:
        v = q1[e]
        print(f"    {e:<12} {v['n']:>4} {v['motion_median_norm']:>13.5f} {v['chamfer_median_px']:>12.3f}")
    print(f"\n    by motion  (least first): {' < '.join(order_motion)}")
    print(f"    by chamfer (best first):  {' < '.join(order_chamfer)}")
    r = out["q1_engine_level_rho_motion_vs_chamfer"]
    print(f"    engine-level rho(motion, chamfer) = {r['rho']} (p={r['p']}, n={r['n_engines']})")

    print("\nQ2  within-engine rho(motion, metric) — positive means the metric")
    print("    scores worse as the clip moves more, i.e. it is partly measuring stillness")
    print(f"    {'metric':<24} " + " ".join(f"{e[:9]:>10}" for e in order_chamfer))
    for h in HEADLINES:
        cells = []
        for e in order_chamfer:
            rr = q2[e][h]["rho"]
            cells.append(f"{rr:>10.3f}" if rr is not None else f"{'--':>10}")
        print(f"    {h:<24} " + " ".join(cells))
    print("\n    pooled across engines:")
    for h in HEADLINES:
        v = pooled[h]
        if v["rho"] is not None:
            print(f"      {h:<24} rho={v['rho']:+.3f}  p={v['p']:.4g}  n={v['n']}")

    print("\nQ3a engine effect before vs after controlling motion")
    for h in HEADLINES:
        v = q3a[h]
        if v["rho_raw"] is not None and v["rho_controlling_motion"] is not None:
            print(f"      {h:<24} raw={v['rho_raw']:+.3f}  controlled={v['rho_controlling_motion']:+.3f}")

    print("\nQ3b matched-motion band (overlap of all engines' IQRs)")
    if band["valid"]:
        print(f"      band = [{band['lo']:.5f}, {band['hi']:.5f}]  ({band['n_engines_usable']} engines usable)")
        for e, v in band["per_engine"].items():
            cm = v["chamfer_median_px"]
            print(f"      {e:<12} n={v['n']:>3}  chamfer={cm:.3f}" if cm is not None else f"      {e:<12} n={v['n']:>3}  chamfer=--")
        print(f"      ordering within band: {' < '.join(band['ordering_in_band'])}")
    else:
        print("      no common band — engines do not overlap in motion IQR, which is")
        print("      itself the finding: they are not comparable at matched movement.")

    print("\nQ4  A3 ground series — does motion fall as the ground darkens?")
    print("    (if rho(k, motion) is strongly positive, less white ground = less motion,")
    print("     and the ground effect on chamfer may be a motion effect)")
    for engine, v in q4.items():
        if v.get("n", 0) < 4:
            print(f"      {engine:<12} insufficient points (n={v.get('n', 0)})")
            continue
        pr = v["rho_k_vs_chamfer_controlling_motion"]
        print(f"      {engine:<12} rho(k,motion)={v['rho_k_vs_motion']:+.3f}  "
              f"rho(k,chamfer)={v['rho_k_vs_chamfer']:+.3f}  "
              f"controlled={pr:+.3f}" if pr is not None else
              f"      {engine:<12} rho(k,motion)={v['rho_k_vs_motion']:+.3f}")

    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
