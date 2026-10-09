#!/usr/bin/env python3
"""Build the tidy per-cell results table from runs/metrics/*.json.

One row per benchmark cell (170 = 32 gen4_turbo + 33 h3-fal standard + 6 FLINT
+ 33 wan22 + 33 ltx23 + 33 gen4.5). Pilot-validation JSONs (pilot-*) are
excluded — they are metric-validation substrate, not benchmark data
(docs/PREREGISTRATION.md, preamble).

Headline scalars are exactly the frozen §3 definitions:
  line_drift      -> metrics.line_drift.vs_frame0.chamfer_px.mean   (px)
  tone_spectral   -> metrics.tone_spectral_drift.variance           (may be null)
  edge_decay      -> metrics.edge_decay.abs_slope_norm
  style_drift     -> metrics.style_drift.terminal
  closure_proxy   -> |metrics.closure_proxy.drift_terminal|

Extra (non-headline, clearly labelled) columns carried for the taxonomy and
sensitivity analyses: signed edge slope, edge/tone terminal ratios, style
mean/max, chamfer per 1000px of clip diagonal (grid-size sensitivity), source
panel covariates from dataset/panel-metadata.json (paper_white_p90, black_frac).

Output: analysis/out/results_table.csv (+ .json with the same rows).
"""
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
METRICS_DIR = ROOT / "runs" / "metrics"
OUT_DIR = Path(__file__).resolve().parent / "out"

ENGINE_SUFFIX = {
    "gen4t": "gen4_turbo",
    "h3": "h3-fal",
    "gen45": "gen4.5",
    "wan22": "wan22",
    "ltx23": "ltx23",
}

MOTIONS = {"idle": "IDLE", "burst": "BURST", "campush": "CAMPUSH"}


def content_class(panel_id: str) -> str:
    # cu-* / act-* / est-* core; cip-act-* -> act; chain-est-* -> est
    if panel_id.startswith("cip-act-"):
        return "act"
    if panel_id.startswith("chain-est-"):
        return "est"
    return panel_id.split("-")[0]


def treatment(panel_id: str) -> str:
    # Core panels: <class>-<treatment>-<n>. A1 panels get their own labels —
    # they sit outside the 3x3 treatment design (datasheet register notes).
    if panel_id.startswith("cip-act-tank"):
        return "ip-line+tone"      # fine-line + tone, no true blacks (datasheet)
    if panel_id.startswith("chain-est-cosmic"):
        return "chain-black"       # heavy-black/spot-white, no screentone (A1)
    parts = panel_id.split("-")
    return parts[1] if len(parts) >= 2 else "?"


def parse_cell(fname: str):
    """-> (cell_id, panel_id, motion, engine, flint_pair | None)"""
    stem = fname[:-len(".json")]
    tail = stem.rsplit("_", 1)[1]
    engine = ENGINE_SUFFIX[tail]
    body = stem.rsplit("_", 1)[0]
    if stem.startswith("flint-"):
        pair = body[len("flint-"):]
        first, last = pair.split("--")
        return stem, first, "FLINT", engine, (first, last)
    panel, motion = body.rsplit("_", 1)
    return stem, panel, MOTIONS[motion], engine, None


def main():
    OUT_DIR.mkdir(exist_ok=True)
    panel_meta = json.loads((ROOT / "dataset" / "panel-metadata.json").read_text())

    rows = []
    for f in sorted(METRICS_DIR.glob("*.json")):
        if f.name.startswith("pilot"):
            continue
        cell_id, panel_id, motion, engine, flint_pair = parse_cell(f.name)
        d = json.loads(f.read_text())
        m = d["metrics"]

        h, w = d["resolution"]
        diag = math.hypot(w, h)
        chamfer = m["line_drift"]["vs_frame0"]["chamfer_px"]["mean"]
        tone_var = m["tone_spectral_drift"].get("variance")
        style = m["style_drift"]
        if "error" in style:
            # a metric-level failure is carried as nulls, never imputed
            print(f"WARNING {cell_id}: style_drift error: {style['error']}")
            style = {}

        pm = panel_meta.get(panel_id, {})
        row = {
            "cell_id": cell_id,
            "engine": engine,
            "panel_id": panel_id,
            "content_class": content_class(panel_id),
            "treatment": treatment(panel_id),
            "motion": motion,
            "flint_pair": "--".join(flint_pair) if flint_pair else "",
            "n_frames": d["n_frames"],
            "width": w,
            "height": h,
            # frozen §3 headline scalars
            "line_chamfer_mean_px": chamfer,
            "tone_variance": tone_var,
            "edge_abs_slope": m["edge_decay"]["abs_slope_norm"],
            "style_terminal": style.get("terminal"),
            "closure_abs_terminal": abs(m["closure_proxy"]["drift_terminal"]),
            # non-headline diagnostics (taxonomy / sensitivity)
            "edge_slope_signed": m["edge_decay"]["slope_norm"],
            "edge_terminal_ratio": m["edge_decay"]["terminal_ratio"],
            "tone_terminal_ratio": m["tone_spectral_drift"].get("terminal_ratio"),
            "tone_n_tiles": m["tone_spectral_drift"].get("n_tiles"),
            "style_mean": style.get("mean"),
            "style_max": style.get("max"),
            "chamfer_terminal_px": m["line_drift"]["vs_frame0"]["chamfer_px"]["terminal"],
            "iou_terminal": m["line_drift"]["vs_frame0"]["tol_iou"]["terminal"],
            "chamfer_vs_source_mean_px": m["line_drift"]["vs_source"]["chamfer_px"]["mean"],
            "chamfer_per_kpx_diag": chamfer / (diag / 1000.0),
            # source-panel covariates
            "paper_white_p90": pm.get("paper_white_p90"),
            "black_frac": pm.get("black_frac"),
            "panel_engine": pm.get("engine"),
        }
        rows.append(row)

    rows.sort(key=lambda r: (r["engine"], r["motion"], r["panel_id"]))

    cols = list(rows[0].keys())
    with (OUT_DIR / "results_table.csv").open("w", newline="") as fh:
        wtr = csv.DictWriter(fh, fieldnames=cols)
        wtr.writeheader()
        wtr.writerows(rows)
    (OUT_DIR / "results_table.json").write_text(json.dumps(rows, indent=1))

    # integrity summary
    from collections import Counter
    eng = Counter(r["engine"] for r in rows)
    mot = Counter((r["engine"], r["motion"]) for r in rows)
    print(f"{len(rows)} cells -> {OUT_DIR / 'results_table.csv'}")
    print("per engine:", dict(sorted(eng.items())))
    print("tone_variance null:", sum(1 for r in rows if r["tone_variance"] is None))
    for e in sorted(eng):
        ms = {k[1]: v for k, v in sorted(mot.items()) if k[0] == e}
        print(f"  {e}: {ms}")


if __name__ == "__main__":
    main()
