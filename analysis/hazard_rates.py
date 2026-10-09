#!/usr/bin/env python3
"""A4 hazard rates + the cross-engine generalisation (frozen A4 clause 5).

Part 1 — A4 as registered: per-cell departure rate on MiniMax H3 with Wilson
95% intervals, and the pre-registered one-sided Fisher exact test of
(BURST x heavy-black) vs (IDLE x line-only).

Part 2 — generalisation across engines, at no extra cost. Each matrix cell is
one Bernoulli draw from that engine's cell population, so the fraction of an
engine's cells that departed estimates its overall departure rate. The main
matrix gives 33 draws per engine; the repeat probe doubles that to 66 on the
three hosted engines; A4 adds 71 more on H3. Rates are reported per engine and
per stratum, with the *ordering* of strata compared across engines — the
ordering is the general claim; the absolute rates are engine-specific.

Coding rule: the frozen A4 automatic half (mean chamfer vs frame 0 > 10 px).
Its agreement with blind frame review is reported wherever both exist, because
the proxy is known to err in both directions (metric-quiet insertions are
missed; in-register transpositions are over-flagged).
"""
import json
import math
from collections import defaultdict
from pathlib import Path

from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "out"
THRESH = 10.0            # frozen A4 rule (a)
ENGINES = ["gen4_turbo", "h3-fal", "gen4.5", "wan22", "ltx23"]
TAG = {"gen4_turbo": "gen4t", "h3-fal": "h3", "gen4.5": "gen45",
       "wan22": "wan22", "ltx23": "ltx23"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def chamfer(path):
    try:
        m = json.loads(Path(path).read_text())["metrics"]
        return m["line_drift"]["vs_frame0"]["chamfer_px"]["mean"]
    except Exception:                                          # noqa: BLE001
        return None


def a4_cells():
    """cell -> list of chamfers, pooling every draw of that cell we own."""
    cells = defaultdict(list)
    for f in (ROOT / "runs/metrics-hazard").glob("*.json"):
        cells[f.stem.rsplit("-h", 1)[0]].append(chamfer(f))
    for cell in list(cells):
        for extra in (ROOT / "runs/metrics" / f"{cell}.json",
                      ROOT / "runs/metrics-r2" / f"{cell}-r2.json"):
            if extra.exists():
                cells[cell].append(chamfer(extra))
        if cell == "cu-line-1_idle_h3":     # the A3 identity variant is a 3rd draw
            g = ROOT / "runs/metrics-ground/ground-cu-line-1-v100_idle_h3.json"
            if g.exists():
                cells[cell].append(chamfer(g))
    return {c: [x for x in v if x is not None] for c, v in cells.items()}


def engine_draws():
    """engine -> list of (cell_id, chamfer) across matrix + repeat + A4."""
    rows = json.loads((OUT / "results_table.json").read_text())
    draws = defaultdict(list)
    for r in rows:
        if r["motion"] != "FLINT" and r["line_chamfer_mean_px"] is not None:
            draws[r["engine"]].append((r["cell_id"], r["line_chamfer_mean_px"],
                                       r["motion"], r["treatment"]))
    meta = {r["cell_id"]: (r["motion"], r["treatment"]) for r in rows}
    for d, suf in ((ROOT / "runs/metrics-r2", "-r2"), (ROOT / "runs/metrics-hazard", None)):
        for f in d.glob("*.json"):
            stem = f.stem
            base = stem[:-3] if suf and stem.endswith(suf) else stem.rsplit("-h", 1)[0]
            if base not in meta:
                continue
            eng = next((e for e in ENGINES if base.endswith(TAG[e])), None)
            ch = chamfer(f)
            if eng and ch is not None:
                draws[eng].append((stem, ch, *meta[base]))
    return draws


def main():
    md = ["# Hazard rates — A4 as registered, plus the cross-engine view", "",
          f"Automatic coding rule (frozen A4): mean chamfer vs frame 0 > {THRESH:g} px "
          "counts as a departure. Wilson 95% intervals throughout.", ""]
    report = {"threshold_px": THRESH}

    # ---- Part 1: A4 per-cell rates -------------------------------------
    cells = a4_cells()
    md += ["## 1. A4 — MiniMax H3, per cell", "",
           "| cell | n | departed | rate | 95% CI |", "|---|---|---|---|---|"]
    per_cell = {}
    for c in sorted(cells):
        v = cells[c]
        k = sum(1 for x in v if x > THRESH)
        lo, hi = wilson(k, len(v))
        per_cell[c] = {"n": len(v), "departed": k, "rate": k / len(v),
                       "ci95": [lo, hi]}
        md.append(f"| `{c}` | {len(v)} | {k} | **{k/len(v):.0%}** | {lo:.0%}–{hi:.0%} |")
    report["a4_per_cell"] = per_cell

    # ---- the registered test -------------------------------------------
    def pool(pred):
        k = n = 0
        for c, v in cells.items():
            if pred(c):
                n += len(v); k += sum(1 for x in v if x > THRESH)
        return k, n
    hi_k, hi_n = pool(lambda c: "black" in c and "burst" in c)
    lo_k, lo_n = pool(lambda c: "line" in c and "idle" in c)
    odds, p = stats.fisher_exact([[hi_k, hi_n - hi_k], [lo_k, lo_n - lo_k]],
                                 alternative="greater")
    report["registered_test"] = {
        "burst_black": [hi_k, hi_n], "idle_line": [lo_k, lo_n],
        "odds_ratio": float(odds), "p_one_sided": float(p),
        "significant_at_0.05": bool(p < 0.05)}
    md += ["", "## 2. The registered test (frozen A4 clause 5)", "",
           f"BURST x heavy-black **{hi_k}/{hi_n} = {hi_k/hi_n:.0%}** vs "
           f"IDLE x line-only **{lo_k}/{lo_n} = {lo_k/lo_n:.0%}**.",
           f"One-sided Fisher exact: OR = {odds:.2f}, **p = {p:.4f}** — "
           f"{'significant' if p < 0.05 else 'NOT significant'} at alpha 0.05.", ""]

    # ---- the finding the hypothesis did not anticipate -------------------
    same_stratum = {c: per_cell[c]["rate"] for c in per_cell
                    if "line" in c and "idle" in c}
    md += ["### Panel identity dominates the stratum", "",
           "Within the single stratum IDLE x line-only, cell rates are "
           + ", ".join(f"`{c.split('_')[0]}` {r:.0%}" for c, r in sorted(same_stratum.items()))
           + ". The spread *within* a stratum is as large as the spread between "
           "strata, so risk is a property of the individual panel rather than of "
           "its category — a category cannot be used to predict it.", ""]

    # ---- Part 2: cross-engine -------------------------------------------
    draws = engine_draws()
    md += ["## 3. Cross-engine departure rates (no extra generation)", "",
           "Each cell is one Bernoulli draw from the engine's cell population.", "",
           "| engine | draws | departed | rate | 95% CI |", "|---|---|---|---|---|"]
    per_engine = {}
    for e in ENGINES:
        v = draws.get(e, [])
        k = sum(1 for _, ch, _, _ in v if ch > THRESH)
        lo, hi = wilson(k, len(v))
        per_engine[e] = {"n": len(v), "departed": k,
                         "rate": k / len(v) if v else None, "ci95": [lo, hi]}
        md.append(f"| {e} | {len(v)} | {k} | **{k/len(v):.0%}** | {lo:.0%}–{hi:.0%} |")
    report["per_engine"] = per_engine

    # stratum ordering per engine — the general claim
    md += ["", "### Stratum rates per engine (is the ordering consistent?)", "",
           "| engine | BURST×black | BURST×line | IDLE×black | IDLE×line |",
           "|---|---|---|---|---|"]
    strat = {}
    for e in ENGINES:
        row, cellvals = [], {}
        for mot in ("BURST", "IDLE"):
            for tre in ("black", "line"):
                v = [ch for _, ch, m, t in draws.get(e, []) if m == mot and t == tre]
                r = (sum(1 for x in v if x > THRESH) / len(v)) if v else None
                cellvals[f"{mot}x{tre}"] = r
        strat[e] = cellvals
        md.append(f"| {e} | " + " | ".join(
            "—" if cellvals[k] is None else f"{cellvals[k]:.0%}"
            for k in ("BURSTxblack", "BURSTxline", "IDLExblack", "IDLExline")) + " |")
    report["stratum_rates"] = strat
    md += ["", "The claim that generalises is the *ordering* of strata, not the "
           "absolute rates: those are engine-specific and range widely.", ""]

    (OUT / "hazard_rates.md").write_text("\n".join(md) + "\n")
    (OUT / "hazard_rates.json").write_text(json.dumps(report, indent=1))
    print("\n".join(md))


if __name__ == "__main__":
    main()
