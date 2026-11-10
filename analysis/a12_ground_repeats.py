#!/usr/bin/env python3
"""A12, the grey-ground series with a noise floor: three draws per step on three engines.

*** DESCRIPTIVE, with a registered read-out (amendment A12). ***

    python analysis/a12_ground_repeats.py                   # refuses until A12 is public
    python analysis/a12_ground_repeats.py --fixtures DIR    # a synthetic tree (tests); no registration check

Inputs: runs/metrics-ground/<stem>.json, the stem from harness/ground_series.draw_stem
(the one source of an A12 file name). Wan 2.2 and LTX-2.3: three fresh same-hardware draws,
`..._idle_<tag>-d1`, `-d2`, `-d3`. Gen-4 Turbo: A3's unsuffixed cell is draw 1 (hosted, same
hardware), plus `-d2` and `-d3`. Gen-4.5 and H3 are not extended (A12). On the local engines
A3's unsuffixed cell ran on other hardware: it is read as a separate point labelled `a3`,
reported beside the series and never in the noise floor or the Spearman rho (ruled 4 Nov 2026).

Per engine and metric (mean chamfer vs frame 0 is the read-out; edge |slope| and style
terminal alongside; tone left out, as the paper's limitations section explains): Spearman
rho of the metric against k over the series' points (15 when complete), with a two-sided
Monte Carlo permutation p (B = 10,000, numpy.random.default_rng(20261104), fresh per engine
and metric) as descriptive support; per level, the range across draws (max - min, at levels
with at least two draws); the noise floor = the median of those ranges; the dose effect =
median at k = 0.52 minus median at k = 1.00. The monotone claim is allowed only where
|dose effect| > 2 x the noise floor, its sign giving the direction (positive: the darker
ground drifts more); otherwise the reading is "not readable at three draws". A series with
any of its 15 points absent (no file, or a non-finite value for that metric) reads
"incomplete: N points missing" (its numbers are still reported). `rho_agrees` flags whether
rho's sign matches the dose effect's direction (rho < 0 with a positive dose, since k falls
as the ground darkens; None when rho or the dose is undefined or the dose is 0); it is reported, and noted in the Markdown when false, but does not
change the reading. No fourth draw is taken.

Model version and the same-machine read-out (decided 4 Nov 2026): each draw's model_version is read
from runs/manifest.jsonl (the last line of a cell id wins; None when the cell has no line) and
reported per draw, and A3's local point reports its own. gen_video.py appends the machine's
name (STILLDRAWN_HW) to a local engine's model_version as ` [<name>]`; per local engine the
distinct names over the series' draws are reported (a draw with a line but no name counts as
"(not recorded)"), with `hardware_mixed` true when there is more than one. The flag is
reported, and noted in the Markdown, but changes no reading. Gen-4 Turbo reports its model
versions only (`hardware` and `hardware_mixed` are None).

A lost machine (A12.3.1, ruled 10 Nov 2026): harness/ground_series.py abandon writes a lost
machine's series to the manifest as abandoned (`"abandoned": "machine lost"`), and the series is
re-run, once, on one fresh machine. An abandoned line is never a draw: it cancels any earlier line
of its cell and gives no model_version, and its clip (runs/abandoned/) and metrics are never read.
Per local engine, `series_rerun` is true when any cell of its series carries an abandoned line;
it is reported, and noted in the Markdown, but changes no reading (None on Gen-4 Turbo).

Outputs: analysis/out/a12_ground.json, a12_ground.md.
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
from ground_series import KS, LOCAL, draw_stem  # noqa: E402
from registration import require_public  # noqa: E402

SEED = 20261104
B = 10_000
DRAWS = (1, 2, 3)
ENGINES = {"gen4_turbo": "Gen-4 Turbo", "wan22": "Wan 2.2", "ltx23": "LTX-2.3"}
EXPECTED = len(KS) * len(DRAWS)
METRICS = {"chamfer": "mean chamfer vs frame 0 (px)", "edge": "edge |slope|", "style": "style drift, terminal"}
PRIMARY = "chamfer"
FLOOR_MULTIPLE = 2.0
MARKER = Path("analysis") / "adherence" / "private-terms.txt"
HW_RE = re.compile(r" \[([^\[\]]+)\]$")      # gen_video.py: model_version + " [<STILLDRAWN_HW>]"
NO_HW = "(not recorded)"
# KS (the five ground steps) and LOCAL (engines whose A3 cell is the separate `a3` point)
# come from harness/ground_series.py with draw_stem.


def num(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def fmt(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def metrics_dir(root):
    return Path(root) / "runs" / "metrics-ground"


def path_for(root, k, engine, draw):
    """The metric file of draw 1-3 of the A12 series."""
    return metrics_dir(root) / f"{draw_stem(k, engine, draw)}.json"


def a3_path(root, k, engine):
    """A3's unsuffixed cell (on a local engine, the separate `a3` point)."""
    return metrics_dir(root) / f"{draw_stem(k, engine, None)}.json"


def manifest_records(root):
    """runs/manifest.jsonl's records with a cell id, in order."""
    m = Path(root) / "runs" / "manifest.jsonl"
    if not m.exists():
        return []
    return [r for r in (json.loads(x) for x in m.read_text().splitlines() if x.strip()) if r.get("cell_id")]


def model_versions(root):
    """{cell_id: model_version} from runs/manifest.jsonl; the last line of a cell id wins. An
    abandoned line (A12.3.1) is not a draw: it removes its cell, and a later line restores it."""
    out = {}
    for r in manifest_records(root):
        if r.get("abandoned"):
            out.pop(r["cell_id"], None)
        else:
            out[r["cell_id"]] = r.get("model_version")
    return out


def series_rerun(root, engine):
    """A12.3.1: True when a cell of the local engine's series carries an abandoned line (its
    first machine was lost and the series re-run, once); None on a hosted engine."""
    if engine not in LOCAL:
        return None
    cells = {draw_stem(k, engine, d) for k in KS for d in DRAWS}
    return any(r.get("abandoned") and r["cell_id"] in cells for r in manifest_records(root))


def hardware_of(model_version):
    """The machine name gen_video.py appended to a local model_version, else NO_HW."""
    m = HW_RE.search(model_version or "")
    return m.group(1) if m else NO_HW


def versions(engine, draws):
    """Distinct model versions over the draws with a manifest line; per local engine, the
    distinct machine names and the hardware_mixed flag (None on a hosted engine)."""
    mvs = [d["model_version"] for d in draws if d["model_version"] is not None]
    hw = sorted({hardware_of(v) for v in mvs}) if engine in LOCAL else None
    return {"model_versions": sorted(set(mvs)),
            "n_draws_without_manifest_line": sum(d["model_version"] is None for d in draws),
            "hardware": hw, "hardware_mixed": None if hw is None else len(hw) > 1}


def draw_versions(engine, mv):
    """One row per series point, present or not: level, draw, cell id, model_version."""
    return [{"k": f"{k:.2f}", "draw": d, "cell_id": draw_stem(k, engine, d),
             "model_version": mv.get(draw_stem(k, engine, d))} for k in KS for d in DRAWS]


def read_point(p):
    m = json.loads(p.read_text())["metrics"]
    return {"chamfer": num(m["line_drift"]["vs_frame0"]["chamfer_px"]["mean"]),
            "edge": num(m["edge_decay"]["abs_slope_norm"]),
            "style": num(m["style_drift"].get("terminal"))}


def load(root):
    """{engine: [series points]}; A3's local cells are not among them."""
    pts = {e: [] for e in ENGINES}
    for e in ENGINES:
        for k in KS:
            for d in DRAWS:
                p = path_for(root, k, e, d)
                if p.exists():
                    pts[e].append({"k": k, "draw": d, **read_point(p)})
    return pts


def load_a3(root, engine, mv=None):
    """A3's local cell, beside the series, with its own model_version per level; None on
    Gen-4 Turbo, where it is draw 1."""
    if engine not in LOCAL:
        return None
    mv = model_versions(root) if mv is None else mv
    by_level = {}
    for k in KS:
        p = a3_path(root, k, engine)
        by_level[f"{k:.2f}"] = read_point(p) if p.exists() else None
    return {"label": "a3", "note": "A3's single draw on other hardware; never in the noise floor or rho",
            "n_present": sum(v is not None for v in by_level.values()), "by_level": by_level,
            "model_version": {f"{k:.2f}": mv.get(draw_stem(k, engine, None)) for k in KS}}


def missing_text(n):
    return f"incomplete: {n} point{'' if n == 1 else 's'} missing"


def readout(points, metric, seed=SEED, b=B):
    pts = [p for p in points if p[metric] is not None]
    ks = np.array([p["k"] for p in pts], dtype=float)
    vs = np.array([p[metric] for p in pts], dtype=float)
    rho = rs.spearman(ks, vs)
    p = rs.perm_p(ks, vs, rho, seed, b, "two-sided") if rho is not None else None
    by_level = {}
    for k in KS:
        v = [q[metric] for q in pts if q["k"] == k]
        by_level[f"{k:.2f}"] = {"n_draws": len(v), "median": float(np.median(v)) if v else None,
                                "range": float(max(v) - min(v)) if len(v) >= 2 else None}
    ranges = [lv["range"] for lv in by_level.values() if lv["range"] is not None]
    floor = float(np.median(ranges)) if ranges else None
    dark, white = by_level["0.52"]["median"], by_level["1.00"]["median"]
    dose = dark - white if dark is not None and white is not None else None
    if len(pts) < EXPECTED:
        reading = missing_text(EXPECTED - len(pts))
    elif dose is None or floor is None:                      # unreachable with 15 points; kept as a guard
        reading = "incomplete: a level lacks the draws the read-out needs"
    elif abs(dose) > FLOOR_MULTIPLE * floor:
        direction = "darker ground, more drift" if dose > 0 else "darker ground, less drift"
        reading = f"monotone claim allowed ({direction})"
    else:
        reading = "not readable at three draws"
    # rho runs against k (k falls as the ground darkens), so a positive dose should come with rho < 0
    agrees = None if rho is None or dose is None or dose == 0 else (rho < 0) == (dose > 0)
    return {"n_points": len(pts), "rho_vs_k": rho, "p_perm_two_sided": p, "by_level": by_level,
            "noise_floor": floor, "dose_effect": dose, "rho_agrees": agrees, "reading": reading}


def analyse(root, seed=SEED, b=B):
    pts = load(root)
    mv = model_versions(root)
    engines = {}
    for e in ENGINES:
        draws = draw_versions(e, mv)
        engines[e] = {"name": ENGINES[e], "n_points": len(pts[e]), "n_expected": EXPECTED,
                      "n_missing": EXPECTED - len(pts[e]),
                      "per_metric": {m: readout(pts[e], m, seed, b) for m in METRICS},
                      "a3": load_a3(root, e, mv), "draws": draws, **versions(e, draws),
                      "series_rerun": series_rerun(root, e)}
    return {"amendment": "A12", "status": "descriptive, registered read-out", "seed": seed,
            "permutations": b, "rule": f"|dose effect| > {FLOOR_MULTIPLE:g} x the median per-level range",
            "engines": engines}


def markdown(res):
    L = ["# A12 grey-ground series with a noise floor", "",
         "**Descriptive, with a registered read-out (amendment A12).** Three draws per ground step on "
         "three engines; A3's single-draw figures stand as reported. On Wan 2.2 and LTX-2.3, A3's cell "
         "ran on other hardware and is shown as the separate point `a3`, outside the noise floor and rho.", ""]
    for e, r in res["engines"].items():
        L += [f"## {r['name']} ({r['n_points']} of {r['n_expected']} files)", ""]
        for m, label in METRICS.items():
            x = r["per_metric"][m]
            note = "" if x["rho_agrees"] is not False else " (rho's sign does not agree with the dose effect's direction)"
            L.append(f"- {label}{' (the read-out)' if m == PRIMARY else ''}, {x['n_points']} points: "
                     f"rho vs k {fmt(x['rho_vs_k'], 2)}, permutation p (descriptive) "
                     f"{fmt(x['p_perm_two_sided'], 4)}, noise floor {fmt(x['noise_floor'])}, "
                     f"dose effect {fmt(x['dose_effect'])}: **{x['reading']}**{note}")
        a3 = r["a3"]
        if a3 is None:
            L += ["", "| k | draws | median chamfer | range across draws |", "|---|---|---|---|"]
        else:
            L += ["", "| k | draws | median chamfer | range across draws | a3 chamfer (other hardware) |",
                  "|---|---|---|---|---|"]
        for k, lv in r["per_metric"][PRIMARY]["by_level"].items():
            row = f"| {k} | {lv['n_draws']} | {fmt(lv['median'])} | {fmt(lv['range'])} |"
            if a3 is not None:
                pt = a3["by_level"][k]
                row += f" {fmt(None if pt is None else pt[PRIMARY])} |"
            L.append(row)
        L.append("")
        L += model_version_lines(r)
    return "\n".join(L)


def model_version_lines(r):
    """The engine's model versions per draw (runs/manifest.jsonl), A3's point's own, and the
    same-machine note. Reported only: no reading above depends on them."""
    L = []
    if r["series_rerun"]:
        L += ["**Note, series re-run:** the first machine was lost before this series reached the study "
              "Mac, so the series was re-run, once, on one fresh machine at the same cell ids and seeds "
              "(A12.3.1); if that machine was lost too, the series reads incomplete above. The lost "
              "machine's draws are abandoned: never measured, analysed or released. The readings above are "
              "unchanged.", ""]
    if r["hardware_mixed"]:
        L += [f"**Note, hardware mixed:** this series' draws carry more than one machine name "
              f"({'; '.join(r['hardware'])}), so the same-machine claim does not hold for it. "
              "The readings above are unchanged.", ""]
    elif r["hardware"]:
        L += [f"Machine: {r['hardware'][0]} (every draw with a manifest line).", ""]
    L += ["| k | draw | model_version (runs/manifest.jsonl) |", "|---|---|---|"]
    L += [f"| {d['k']} | {d['draw']} | {d['model_version'] or 'n/a'} |" for d in r["draws"]]
    if r["a3"] is not None:
        a3 = sorted({v for v in r["a3"]["model_version"].values() if v})
        L += ["", f"a3 point's model_version: {'; '.join(a3) if a3 else 'n/a'}."]
    L.append("")
    return L


def fixture_root(arg):
    """The fixture root, or exit: never the repository or any folder under it (the release
    tree carries no marker), never a folder in a private tree (the folder or any folder above
    it carries the private marker), as a10_ladder.check_fixtures."""
    root = Path(arg).expanduser().resolve()
    repo = ROOT.resolve()
    in_private = any((d / MARKER).is_file() for d in (root, *root.parents))
    if root == repo or repo in root.parents or in_private:
        raise SystemExit("REFUSING --fixtures: the folder is the repository, inside it, or inside a private "
                         f"tree (it or a folder above it carries {MARKER}). Fixtures live outside it.")
    return root


def main(argv=None):
    ap = argparse.ArgumentParser(description="A12 grey-ground series with a noise floor")
    ap.add_argument("--fixtures", help="a synthetic tree laid out like the repository; skips the registration check")
    a = ap.parse_args(argv)
    if a.fixtures:
        root = fixture_root(a.fixtures)
    else:
        root = ROOT
        require_public("A12", "read the A12 ground draws", hint="Tests use --fixtures.")
    res = analyse(root)
    out = root / "analysis" / "out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "a12_ground.json").write_text(json.dumps(res, indent=1, allow_nan=False) + "\n")
    (out / "a12_ground.md").write_text(markdown(res) + "\n")
    print(markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
