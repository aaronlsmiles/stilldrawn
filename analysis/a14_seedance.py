#!/usr/bin/env python3
"""A14: A5's Seedance hazard prediction read at five fresh draws.

*** CONFIRMATORY for one prediction only (A14.0). ***

    python analysis/a14_seedance.py --codes             # writes analysis/out/a14_codes.json (before registration)
    python analysis/a14_seedance.py --strips DIR        # the coded strips for the blind review (refuses until A14 is public)
    python analysis/a14_seedance.py                     # the analysis (refuses until A14 is public)
    python analysis/a14_seedance.py --fixtures DIR      # a synthetic tree (tests); no registration check

Inputs: analysis/out/a14_cells.json (harness/a14_draws.py build), a14_route.json (the route
check's verdict, A14.3.3), a14_codes.json, the blind review a14_review.json ({"reviewer": ...,
"codes": {code: "held" or one of the five named failures}}; a code outside the set, or any other
label, is refused), runs/manifest.jsonl, the clips
(runs/seedance2/, and A5's fal draws in runs/seedance/), inkstab JSONs in runs/metrics-seedance/,
motion JSONs in runs/metrics-motion-seedance/ (A5's in runs/metrics-motion/), and H3's published
per-cell rates in analysis/out/hazard_rates.json (A4).

Codes (A14.3.6): one set of opaque codes s01 to s23 over every draw the review codes, the 20
Runway draws and the scout's three, in an order drawn with numpy.random.default_rng(20261104),
whatever the route verdict. --strips copies each draw's strip
(analysis/out/frames/<cell>/strip.png, analysis/extract_frames.py) to DIR/<code>.png for every draw
with a clip (at most 23), coded blind in one sitting; a draw refused, or left without a clip by a
stopped run, is skipped and counted, and a draw with a clip but no strip is refused.

Coding (A14.3.6, A4's clause 4): a draw departed if (a) its mean chamfer vs frame 0 exceeds 10 px
(hazard_rates.THRESH) or (b) the blind review records one of the five named failures. A draw is
fully coded when its clip, its chamfer and its review code exist; a refused draw (manifest) is
neither departed nor held and reduces n.

The prediction (A14.4), on act-black-3 BURST: Runway's five fresh draws -h4 to -h8, whatever the
route verdict; the scout never enters it. Readings, the registered strings, in this order:
"not testable at five draws: route mismatch found during the run" (A14.3.4: a task record reporting
a captured field differently from the watched first draw's, harness/a14_draws.py; every draw is
then reported without a verdict, and this reading stands whatever is missing); "incomplete: N
draws missing"; "refused" when every draw of the cell is refused (kill rule A14.6.3, which also
gives any such cell "refused" and no rate); "not testable: fewer than 3 coded draws"; "prediction
holds: Seedance's departure rate is no lower than H3's" if k/n >= 8/10; otherwise "prediction
refuted: Seedance's departure rate is lower than H3's". Beside it, without a verdict: Wilson 95% intervals for both rates, a one-sided Fisher exact
p for H3's rate exceeding Seedance's, and the same reading under rule (a) alone. Also beside it,
secondary and without a verdict: the scout's three fal draws on their own (k of 3 under the full rule
and under rule (a) alone), and the pooled 8-draw figure (the scout's three and Runway's five) with
its rate and Wilson 95% interval under both codings. After a route mismatch at the check
(POOLED_NOT_COMPUTED), or one found during the run (POOLED_NOT_COMPUTED_RUN; the check's string when
both), the pooled figure is not computed; the scout is still reported.

Reported without a verdict (A14.5): per cell departures, n, rate and Wilson interval beside H3's;
A4's statistic (act-black-3 BURST against cu-line-1 IDLE, one-sided Fisher exact) under the full
rule and under rule (a) alone; rule (a) against rule (b) draw by draw and the number of
disagreements; per draw chamfer, edge |slope|, style terminal and realised motion, route,
model_version, date and seed; the route record; the distinct model_version strings among the
Runway draws, flagged when more than one. Outputs: analysis/out/a14_seedance.json and .md.
"""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "harness"))
import a14_draws as ad  # noqa: E402
from hazard_rates import THRESH, wilson  # noqa: E402
from registration import require_public  # noqa: E402

SEED = 20261104
CODES_JSON = "analysis/out/a14_codes.json"
REVIEW_JSON = "analysis/out/a14_review.json"
HAZARD_JSON = "analysis/out/hazard_rates.json"
FAILURES = ("subject replacement", "hard graphic cut", "pseudo-text", "evacuation", "monochrome break")
CELLS = (("cu-line-1", "IDLE"), ("cu-line-1", "BURST"), ("act-black-3", "IDLE"), ("act-black-3", "BURST"))
PREDICTED = "act-black-3_burst"
H3_RATE = (8, 10)                                   # A4's act-black-3 BURST on H3; checked against hazard_rates.json
PRIVATE_MARKER = Path("analysis") / "adherence" / "private-terms.txt"
HOLDS = "prediction holds: Seedance's departure rate is no lower than H3's"
REFUTED = "prediction refuted: Seedance's departure rate is lower than H3's"
FOUND = "not testable at five draws: route mismatch found during the run"
FEW = "not testable: fewer than 3 coded draws"
REFUSED = "refused"                            # A14.6.3: a cell whose every draw is refused
POOLED_NOT_COMPUTED = ("not computed: the route check recorded a mismatch, and A5's fal draws are never pooled "
                       "with Runway's (A14.3.4)")
POOLED_NOT_COMPUTED_RUN = ("not computed: a route mismatch was found during the run, and A5's fal draws are never "
                           "pooled across a model change (A14.3.4)")


def num(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def review_ids(rec):
    """Every draw the review codes: the 20 Runway draws and the scout's three."""
    return [c["cell_id"] for c in rec["scout"]] + [c["cell_id"] for c in rec["cells"]]


def build_codes(root=ROOT):
    """Opaque codes and the review order: one set over all 23 strips, whatever the route verdict (seed 20261104)."""
    root = Path(root)
    cells = sorted(review_ids(ad.load_cells(root)))
    order = np.random.default_rng(SEED).permutation(len(cells))
    rec = {"seed": SEED, "rule": "codes s01.. in review order; the order a permutation of the sorted cell ids by "
                                 "numpy.random.default_rng(20261104); one set for every strip the review codes, "
                                 "whatever the route verdict (A14.3.6)",
           "codes": {f"s{i + 1:02d}": cells[j] for i, j in enumerate(order)}}
    out = root / CODES_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1) + "\n")
    return rec


def codes_for(root):
    """{code: cell id}: the one code set."""
    p = Path(root) / CODES_JSON
    if not p.exists():
        raise SystemExit(f"{CODES_JSON} is missing: run `a14_seedance.py --codes` (before registration)")
    return json.loads(p.read_text())["codes"]


def route_of(root):
    p = Path(root) / ad.ROUTE_JSON
    if not p.exists():
        raise SystemExit(f"{ad.ROUTE_JSON} is missing: the route check (A14.3.3) is recorded before any draw")
    return json.loads(p.read_text())


def clip_path(root, cid, scout):
    return Path(root) / "runs" / ("seedance" if scout else ad.ENGINE) / f"{cid}.mp4"


def has_clip(root, cid, scout, line):
    """A draw has a clip when its manifest line exists, is not a refusal, and its clip file exists."""
    return bool(line) and not line.get("refused") and clip_path(root, cid, scout).exists()


def make_strips(root, dest):
    """Copy each coded draw's strip to dest/<code>.png: the folder the blind reviewer sees. A draw that is
    refused, or has no clip (a run stopped early), has no strip and is skipped; a draw WITH a clip whose strip
    is missing is refused. Returns (the codes copied, the codes skipped)."""
    root, dest = Path(root), Path(dest)
    codes = codes_for(root)
    scout = {c["cell_id"] for c in ad.load_cells(root)["scout"]}
    lines = manifest_last(root)
    take = {code: cid for code, cid in codes.items() if has_clip(root, cid, cid in scout, lines.get(cid))}
    missing = [cid for cid in take.values() if not (root / "analysis" / "out" / "frames" / cid / "strip.png").exists()]
    if missing:
        raise SystemExit(f"strips missing (analysis/extract_frames.py first): {', '.join(missing)}")
    dest.mkdir(parents=True, exist_ok=True)
    for code, cid in take.items():
        shutil.copyfile(root / "analysis" / "out" / "frames" / cid / "strip.png", dest / f"{code}.png")
    return sorted(take), sorted(set(codes) - set(take))


def manifest_last(root):
    m = Path(root) / "runs" / "manifest.jsonl"
    out = {}
    if m.exists():
        for x in m.read_text().splitlines():
            if x.strip():
                r = json.loads(x)
                out[r.get("cell_id")] = r
    return out


def draw_record(root, cid, scout, line, code, review):
    root = Path(root)
    ink = root / ad.METRICS_DIR / f"{cid}.json"
    mot = root / ("runs/metrics-motion" if scout else ad.MOTION_DIR) / f"{cid}.json"
    m = json.loads(ink.read_text()).get("metrics", {}) if ink.exists() else {}
    chamfer = num(m.get("line_drift", {}).get("vs_frame0", {}).get("chamfer_px", {}).get("mean"))
    refused = bool(line and line.get("refused"))
    rule_a = None if chamfer is None else chamfer > THRESH
    rule_b = None if review is None else review != "held"
    return {"cell_id": cid, "route": "fal (A5)" if scout else "Runway", "refused": refused,
            "clip": has_clip(root, cid, scout, line), "code": code, "review": review,
            "chamfer": chamfer, "edge_abs_slope": num(m.get("edge_decay", {}).get("abs_slope_norm")),
            "style_terminal": num(m.get("style_drift", {}).get("terminal")),
            "motion": num(json.loads(mot.read_text()).get("motion", {}).get("headline_median_norm"))
            if mot.exists() else None,
            "rule_a": rule_a, "rule_b": rule_b,
            "seed": (line or {}).get("seed"), "model_version": (line or {}).get("model_version"),
            "date": (line or {}).get("date")}


def coded(d, rule):
    """(fully coded, departed) under the full rule ("ab") or rule (a) alone ("a")."""
    if rule == "a":
        return d["clip"] and d["rule_a"] is not None, bool(d["rule_a"])
    full = d["clip"] and d["rule_a"] is not None and d["rule_b"] is not None
    return full, bool(d["rule_a"] or d["rule_b"])


def read_prediction(draws, rule, found):
    refused = [d["cell_id"] for d in draws if d["refused"]]
    live = [d for d in draws if not d["refused"]]
    missing = [d["cell_id"] for d in live if not coded(d, rule)[0]]
    done = [d for d in live if coded(d, rule)[0]]
    k, n = sum(coded(d, rule)[1] for d in done), len(done)
    if found:
        reading = FOUND
    elif missing:
        reading = f"incomplete: {len(missing)} draws missing"
    elif draws and len(refused) == len(draws):
        reading = REFUSED                      # kill rule A14.6.3, before "fewer than 3 coded draws"
    elif n < 3:
        reading = FEW
    elif k * H3_RATE[1] >= H3_RATE[0] * n:
        reading = HOLDS
    else:
        reading = REFUTED
    out = {"reading": reading, "draws": [d["cell_id"] for d in draws], "k": k, "n": n, "refused": refused,
           "missing": missing, "wilson95": list(wilson(k, n)) if n else None,
           "h3": {"k": H3_RATE[0], "n": H3_RATE[1], "wilson95": list(wilson(*H3_RATE))}}
    out["fisher_p_h3_greater"] = (float(stats.fisher_exact([[H3_RATE[0], H3_RATE[1] - H3_RATE[0]], [k, n - k]],
                                                           alternative="greater")[1]) if n else None)
    return out


def rate(draws, rule):
    done = [d for d in draws if not d["refused"] and coded(d, rule)[0]]
    k = sum(coded(d, rule)[1] for d in done)
    return k, len(done)


def figure(draws, rule):
    """Departures, n, rate and Wilson 95% interval over the fully coded draws, with what is refused or
    missing: a secondary figure, reported without a verdict."""
    k, n = rate(draws, rule)
    return {"k": k, "n": n, "rate": k / n if n else None, "wilson95": list(wilson(k, n)) if n else None,
            "refused": [d["cell_id"] for d in draws if d["refused"]],
            "missing": [d["cell_id"] for d in draws if not d["refused"] and not coded(d, rule)[0]]}


def a4_statistic(by_cell, rule):
    kb, nb = rate(by_cell["act-black-3_burst"], rule)
    ki, ni = rate(by_cell["cu-line-1_idle"], rule)
    p = (float(stats.fisher_exact([[kb, nb - kb], [ki, ni - ki]], alternative="greater")[1]) if nb and ni else None)
    return {"burst_black": [kb, nb], "idle_line": [ki, ni], "p_one_sided": p}


def analyse(root=ROOT):
    root = Path(root)
    rec = ad.load_cells(root)
    route = route_of(root)
    verdict = route["verdict"]
    codes = {cid: code for code, cid in codes_for(root).items()}
    rp = root / REVIEW_JSON
    review_rec = json.loads(rp.read_text()) if rp.exists() else {}
    review = review_rec.get("codes", {})
    outside = sorted(set(review) - set(codes.values()))
    if outside:
        raise SystemExit(f"{REVIEW_JSON}: codes outside {CODES_JSON}: {outside}")
    bad = sorted({v for v in review.values() if v != "held" and v not in FAILURES})
    if bad:
        raise SystemExit(f"{REVIEW_JSON}: unknown review labels {bad}; each strip is 'held' or one of {FAILURES}")
    lines = manifest_last(root)
    scout_ids = [c["cell_id"] for c in rec["scout"]]
    runway = rec["cells"]                       # the same 20 whatever the route verdict (A14.3.4)
    draws = {cid: draw_record(root, cid, cid in scout_ids, lines.get(cid), codes.get(cid),
                              review.get(codes.get(cid))) for cid in scout_ids + [c["cell_id"] for c in runway]}
    meta = {c["cell_id"]: c for c in runway}
    hit = ad.found_during_run(root, set(meta))
    found = {"cell_id": hit[0], "reported": hit[1], "reference": ad.route_reference(root)} if hit else None
    by_cell = {}
    for panel, motion in CELLS:
        key = f"{panel}_{motion.lower()}"
        by_cell[key] = [draws[cid] for cid, c in meta.items() if c["panel"] == panel and c["motion"] == motion]
    hz = json.loads((root / HAZARD_JSON).read_text())["a4_per_cell"]
    if (hz["act-black-3_burst_h3"]["departed"], hz["act-black-3_burst_h3"]["n"]) != H3_RATE:
        raise SystemExit(f"{HAZARD_JSON}: act-black-3_burst_h3 is not A4's published 8 of 10")
    cells = {}
    for key, ds in by_cell.items():
        k, n = rate(ds, "ab")
        h = hz[f"{key}_h3"]
        cells[key] = {"draws": [d["cell_id"] for d in ds], "k": k, "n": n, "rate": k / n if n else None,
                      "wilson95": list(wilson(k, n)) if n else None,
                      "h3": {"k": h["departed"], "n": h["n"], "rate": h["rate"]},
                      "reading": "no verdict (route mismatch found during the run)" if found else
                      REFUSED if ds and all(d["refused"] for d in ds) else "no verdict"}
    disagree = sorted(cid for cid, d in draws.items()
                      if d["rule_a"] is not None and d["rule_b"] is not None and d["rule_a"] != d["rule_b"])
    runway_versions = sorted({d["model_version"] for cid, d in draws.items()
                              if cid not in scout_ids and d["model_version"]})
    ref = ad.route_reference(root)
    notes = route.get("absent_field_notes", {})
    absent = [{"cell_id": x["cell_id"], "fields": ad.absent_fields(x, ref), "note": notes.get(x["cell_id"])}
              for x in lines.values() if x.get("cell_id") in meta and not x.get("refused")
              and x["cell_id"] != (ref or {}).get("captured_from") and ad.absent_fields(x, ref)]
    res = {"amendment": "A14", "status": "confirmatory (A5's prediction only)", "threshold_px": THRESH,
           "route": route, "found_during_run": found, "absent_fields": absent,
           "prediction": read_prediction(by_cell[PREDICTED], "ab", bool(found)),
           "prediction_rule_a_only": read_prediction(by_cell[PREDICTED], "a", bool(found)),
           "scout": scout_figures([draws[c] for c in scout_ids]),
           "pooled": pooled_figures([draws[c] for c in scout_ids] + by_cell[PREDICTED], verdict, bool(found)),
           "cells": cells,
           "a4_statistic": {"full_rule": a4_statistic(by_cell, "ab"), "rule_a_only": a4_statistic(by_cell, "a")},
           "disagreements": {"n": len(disagree), "draws": disagree},
           "model_versions": {"runway": runway_versions, "flag_more_than_one": len(runway_versions) > 1},
           "draws": draws, "reviewer": review_rec.get("reviewer")}
    return res


def scout_figures(scout):
    """A5's three fal draws on their own, under both codings: secondary, without a verdict (A14.4)."""
    return {"draws": [d["cell_id"] for d in scout], "full_rule": figure(scout, "ab"), "rule_a_only": figure(scout, "a")}


def pooled_figures(pooled, verdict, found=False):
    """The scout's three and Runway's five on act-black-3 BURST: secondary, without a verdict (A14.4). After a
    route mismatch, at the check or found during the run, it is not computed: the scout is never pooled across
    a known model change. The check's string is printed when both apply."""
    ids = [d["cell_id"] for d in pooled]
    if verdict == "mismatch":
        return {"computed": False, "draws": ids, "note": POOLED_NOT_COMPUTED}
    if found:
        return {"computed": False, "draws": ids, "note": POOLED_NOT_COMPUTED_RUN}
    return {"computed": True, "draws": ids, "full_rule": figure(pooled, "ab"), "rule_a_only": figure(pooled, "a")}


def markdown(res):
    p, pa = res["prediction"], res["prediction_rule_a_only"]
    fmt = (lambda iv: "n/a" if not iv else f"[{iv[0]:.2f}, {iv[1]:.2f}]")
    L = ["# A14: A5's Seedance prediction at five fresh draws", "",
         "**Confirmatory for A5's prediction only (A14.0).** Every other number is reported without a verdict.", "",
         f"Route check (A14.3.3): **{res['route']['verdict']}** ({res['route']['record']}, sha256 "
         f"{res['route']['record_sha256'][:12]}…).", ""]
    if res["found_during_run"]:
        L += [f"Route mismatch found during the run: {res['found_during_run']['cell_id']}'s task record reports "
              f"{res['found_during_run']['reported']}, not the reference captured from the first draw.", ""]
    L += ["## The prediction (act-black-3 BURST)", "", f"- Reading: **{p['reading']}**",
          f"- Draws: {', '.join(p['draws'])}", f"- Seedance: {p['k']} of {p['n']} departed, Wilson 95% {fmt(p['wilson95'])}",
          f"- H3 (A4): {p['h3']['k']} of {p['h3']['n']}, Wilson 95% {fmt(p['h3']['wilson95'])}",
          f"- One-sided Fisher exact p (H3's rate exceeding Seedance's): "
          f"{'n/a' if p['fisher_p_h3_greater'] is None else format(p['fisher_p_h3_greater'], '.4f')}",
          f"- Rule (a) alone: **{pa['reading']}** ({pa['k']} of {pa['n']})"]
    if p["refused"]:
        L.append(f"- Refused: {', '.join(p['refused'])}")
    if p["missing"]:
        L.append(f"- Missing: {', '.join(p['missing'])}")
    s, pl = res["scout"], res["pooled"]

    def gaps(*figs):                            # what a secondary figure leaves out, as the prediction block lists it
        refused = sorted({c for f in figs for c in f["refused"]})
        missing = sorted({c for f in figs for c in f["missing"]})
        return (f"; refused: {', '.join(refused)}" if refused else "") + (f"; missing: {', '.join(missing)}" if missing else "")

    L += ["", "## Beside the reading: secondary, without a verdict", "",
          f"- A5's scout (fal), on its own: {s['full_rule']['k']} of {s['full_rule']['n']} under the full rule; "
          f"{s['rule_a_only']['k']} of {s['rule_a_only']['n']} under rule (a) alone"
          + gaps(s["full_rule"], s["rule_a_only"])]
    if pl["computed"]:
        for name, f in (("full rule", pl["full_rule"]), ("rule (a) alone", pl["rule_a_only"])):
            r = "n/a" if f["rate"] is None else f"{f['rate']:.2f}"
            L.append(f"- Pooled, the scout's three and Runway's five, {name}: {f['k']} of {f['n']}, rate {r}, "
                     f"Wilson 95% {fmt(f['wilson95'])}" + gaps(f))
    else:
        L.append(f"- Pooled, the scout's three and Runway's five: {pl['note']}")
    L += ["", "## Per cell (no verdict)", "", "| Cell | Seedance | rate | Wilson 95% | H3 (A4) |", "|---|---|---|---|---|"]
    for key, c in res["cells"].items():
        r = "n/a" if c["rate"] is None else f"{c['rate']:.2f}"
        L.append(f"| {key} | {c['k']} of {c['n']} | {r} | {fmt(c['wilson95'])} | {c['h3']['k']} of {c['h3']['n']} |")
    for name, a4 in (("full rule", res["a4_statistic"]["full_rule"]), ("rule (a) alone", res["a4_statistic"]["rule_a_only"])):
        pv = "n/a" if a4["p_one_sided"] is None else f"{a4['p_one_sided']:.4f}"
        L.append(f"\nA4's statistic, {name}: BURST x heavy-black {a4['burst_black'][0]} of {a4['burst_black'][1]} "
                 f"against IDLE x line-only {a4['idle_line'][0]} of {a4['idle_line'][1]}, one-sided Fisher p {pv}.")
    L += ["", f"Rule (a) against rule (b): {res['disagreements']['n']} disagreements"
              + (f" ({', '.join(res['disagreements']['draws'])})." if res["disagreements"]["n"] else "."),
          "", f"Model versions (Runway draws): {'; '.join(res['model_versions']['runway']) or 'n/a'}"
          + (" **(more than one: noted, no reading changes)**" if res["model_versions"]["flag_more_than_one"] else ""),
          "", "## Per draw", "", "| Draw | route | code | review | chamfer | rule (a) | rule (b) | motion | seed |",
          "|---|---|---|---|---|---|---|---|---|"]
    for cid, d in res["draws"].items():
        ch = "n/a" if d["chamfer"] is None else f"{d['chamfer']:.2f}"
        mo = "n/a" if d["motion"] is None else f"{d['motion']:.5f}"
        L.append(f"| {cid} | {d['route']} | {d['code'] or 'n/a'} | {'refused' if d['refused'] else d['review'] or 'n/a'} | "
                 f"{ch} | {d['rule_a']} | {d['rule_b']} | {mo} | {d['seed']} |")
    return "\n".join(L) + "\n"


def check_fixtures(path):
    root = Path(path).expanduser().resolve()
    repo = ROOT.resolve()
    in_private = any((d / PRIVATE_MARKER).is_file() for d in (root, *root.parents))
    if root == repo or repo in root.parents or in_private:
        raise SystemExit("REFUSING --fixtures: the folder is the repository, inside it, or inside a private "
                         f"tree (it or a folder above it carries {PRIVATE_MARKER}). Fixtures live outside it.")
    return root


def main(argv=None):
    ap = argparse.ArgumentParser(description="A14 analysis (confirmatory for A5's prediction)")
    ap.add_argument("--codes", action="store_true", help="write analysis/out/a14_codes.json (before registration)")
    ap.add_argument("--strips", help="copy the coded strips into this folder for the blind review")
    ap.add_argument("--fixtures", help="a synthetic tree outside the repository; skips the registration check")
    a = ap.parse_args(argv)
    if a.codes:
        rec = build_codes()
        print(f"{CODES_JSON}: {len(rec['codes'])} codes")
        return 0
    if a.fixtures:
        root = check_fixtures(a.fixtures)
    else:
        root = ROOT
        require_public("A14", "read A14's draws", hint="Tests use --fixtures.")
    if a.strips:
        took, skipped = make_strips(root, a.strips)
        print(f"{len(took)} coded strips in {a.strips}; {len(skipped)} draw{'' if len(skipped) == 1 else 's'} "
              "skipped (refused, or no clip)")
        return 0
    res = analyse(root)
    out = root / "analysis" / "out"
    (out / "a14_seedance.json").write_text(json.dumps(res, indent=1, allow_nan=False) + "\n")
    (out / "a14_seedance.md").write_text(markdown(res))
    print(markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
