#!/usr/bin/env python3
"""masked: line drift measured only where the prompt does not allow motion.

*** NOT ONE OF THE FIVE FROZEN METRICS. EXPLORATORY AND POST-HOC (amendment A9). ***

`inkstab.py` holds the five metrics whose definitions were frozen before any
generation. This tool sits beside `motion.py` (A6). It imports inkstab's frozen
line extractor and chamfer and never changes a byte of inkstab's DEFS.

    python metrics/masked.py gate [--first N] [--expect-device mps] [--redo]
    python metrics/masked.py score CLIP --masks FILE --row ROW --out OUT.json
    python metrics/masked.py a9-run --public-repo PATH

gate    Re-extracts the line maps of the 109 primary idle and burst clips and
        checks each clip's whole-frame line drift against its released value,
        then measures frame 0 against the panel's line-art layer under two
        panel-to-clip mappings. Line maps live in memory for one clip at a time
        and are never saved. Resumable: one small JSON part per clip.
score   Whole-frame and masked line drift for any clip, masks file and row.
        An A9 clip (recognised by path, name or identical bytes; a re-encoded
        copy is not caught) is refused until the amendment is public.
a9-run  The registered A9 pass over the 109 clips. Refuses to run until the
        amendment is public (see registration_guard).

Run with the ComfyUI venv python (torch, scikit-image, scipy and PyAV live
there). In the public release, set STILLDRAWN_CONTROLNET_AUX_SRC to the
custom_controlnet_aux source folder, as for inkstab.py.

Sections (in file order):
  cells, mapping      the 109 primary idle and burst cells; panel-to-clip geometry
  gate                reproduction gate: parts, resume, finalise (frozen with A9)
  masked drift        rasterise, region, masked chamfer, mask files, per-clip scoring
  registration guard  the git checks that A9 is public before any masked value
  a9 run              the registered pass: gate inputs, records, resume
  CLI                 gate, score, a9-run
"""
import argparse
import csv
import datetime
import gc
import hashlib
import io
import json
import os
import platform
import re
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inkstab  # noqa: E402  (frozen: imported, never edited)

ROOT = Path(__file__).resolve().parents[1]

MASKED_DEFS = {
    "version": "masked 1.0 (A9): POST-HOC, exploratory, NOT part of the frozen five",
    "line_maps": "inkstab._line_maps under inkstab's frozen DEFS (AnimeLineArt, detect_resolution 1024, per-map Otsu, nearest resize)",
    "whole_frame": "inkstab._chamfer(frame t, frame 0) for t = 1..N-1; clip value = mean of the non-None frames (the released line_chamfer_mean_px)",
    "gate_reference": "frame-0 line map vs the dataset line-art layer, binarised as inkstab's --lineart branch (invert, anti-aliased resize onto the clip grid under the mapping, Otsu)",
    "mapping": "stretch: the panel scales to the clip grid (scaled size = grid, offsets 0); centre-crop: the panel scales by max(H/ph, W/pw) to cover the clip grid, the scaled size rounded to whole pixels (at least the grid), and the grid is the centred window (offsets floor((scaled - grid) / 2)). The gate's line-art reference is resampled to the scaled size with skimage resize (anti-aliased) and cropped to that window",
    "mask": "M = union of the row's allowed polygons (x, y in panel fractions, origin top-left), each filled with skimage.draw.polygon(r = y*scaled_h - top, c = x*scaled_w - left, shape = (H, W)) on the clip grid, boundary pixels included (stretch: r = y*H, c = x*W, sub-plan B's contract); status nothing-allowed gives an empty M",
    "region": "R = ~scipy.ndimage.binary_dilation(M, structure=skimage.morphology.disk(m)), computed exactly as scipy.ndimage.distance_transform_edt(~M) > m (unit-tested equal); R is all-true when M is empty",
    "margins_px": [16, 32, 64],
    "masked_chamfer": "a = frame t, b = frame 0, full-frame EDTs. None if a or b is empty. If a&R and b&R are both non-empty: 0.5*(EDT(~b)[a&R].mean() + EDT(~a)[b&R].mean()). If only b&R is non-empty (lines vanished from R): EDT(~a)[b&R].mean(). If only a&R is non-empty (lines appeared in R): EDT(~b)[a&R].mean(). If both are empty: None",
    "clip_value": "mean of the scorable frames; +inf when no frame is scorable (stored as chamfer_px null with no_scorable_frame true)",
    "min_f0_line_px_in_R": 500,
    "gate_pass": "|recomputed - released| <= max(0.01 px, 0.5 % of released), same frame count, grid and device",
}

ENGINES = {"gen4t": "gen4_turbo", "gen45": "gen4.5", "h3": "h3-fal", "wan22": "wan22", "ltx23": "ltx23"}
LEAGUE_ORDER = ("wan22", "gen4_turbo", "ltx23", "gen4.5", "h3-fal")   # frozen league order, never a rank
CELL_RE = re.compile(r"^(?P<panel>.+)_(?P<motion>idle|burst|campush)_(?P<suffix>gen4t|gen45|h3|wan22|ltx23)$")
A9_MOTIONS = ("idle", "burst")
A9_N_CLIPS = 109
MAPPINGS = ("stretch", "centre-crop")
GATE_ABS_TOL, GATE_REL_TOL = 0.01, 0.005
ENV_NOT_COMPARED = ("masked_sha256", "git_commit", "git_dirty")
PARTS = "analysis/out/a9_gate_parts"
GATE_CSV = "analysis/out/a9_repro_gate.csv"
GATE_MD = "analysis/out/a9_repro_gate.md"
GEOM_CSV = "analysis/out/a9_geometry.csv"
GATE_FIELDS = ["cell_id", "engine", "motion", "n_frames", "n_frames_released", "grid", "grid_released",
               "device", "chamfer_px", "chamfer_px_released", "abs_diff_px", "tolerance_px", "pass"]
GEOM_FIELDS = ["cell_id", "engine", "motion", "grid", "panel_px", "chamfer_stretch_px", "chamfer_centre_crop_px"]


def public_id(cell_id):
    """Public form of a cell or panel id. The creator-IP panel's private working id
    differs from its public one (cip-act-tank-1) only in its three-letter prefix;
    every other id is already public."""
    return re.sub(r"^[a-z]{3}-act-tank-1", "cip-act-tank-1", cell_id)


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_atomic(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _grid(hw):
    return f"{int(hw[0])}x{int(hw[1])}"


# ------------------------------------------------------------------ cells
def a9_cells(root=ROOT, motions=A9_MOTIONS):
    """Primary cells of the given motion classes, sorted by public id.

    A cell is primary when it has a released runs/metrics/<cell_id>.json, its id
    names one of the five engines with no replicate suffix, and it is not a FLINT,
    pilot or ground-series cell. Its clip is the `out` of the last manifest line
    for that cell_id (the last line wins)."""
    root = Path(root)
    last = {}
    for line in (root / "runs" / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            last[rec["cell_id"]] = rec
    cells = []
    for cell_id, rec in last.items():
        m = CELL_RE.match(cell_id)
        if not m or m["motion"] not in motions or rec.get("refused"):
            continue
        if cell_id.startswith(("flint-", "pilot", "ground-")):
            continue
        mj = root / "runs" / "metrics" / f"{cell_id}.json"
        if not mj.exists():
            continue
        try:
            rel = json.loads(mj.read_text(encoding="utf-8"))
            cells.append({
                "cell_id": cell_id, "public_id": public_id(cell_id),
                "panel": m["panel"], "public_panel": public_id(m["panel"]),
                "motion": m["motion"], "engine": ENGINES[m["suffix"]],
                "clip": rec["out"],
                "released_px": rel["metrics"]["line_drift"]["vs_frame0"]["chamfer_px"]["mean"],
                "released_n_frames": int(rel["n_frames"]),
                "released_grid": [int(x) for x in rel["resolution"]],
            })
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"cell {cell_id}: missing or malformed field {e!r} "
                             f"(manifest line or runs/metrics/{cell_id}.json)") from e
    return sorted(cells, key=lambda c: c["public_id"])


# ---------------------------------------------------------------- mapping
def crop_geometry(panel_wh, clip_hw, mapping):
    """(scaled_h, scaled_w, top, left): the panel is scaled to scaled_h x scaled_w
    and the clip grid is the window that starts at (top, left)."""
    pw, ph = panel_wh
    H, W = clip_hw
    if mapping == "stretch":
        return H, W, 0, 0
    if mapping != "centre-crop":
        raise ValueError(f"unknown mapping: {mapping}")
    s = max(H / ph, W / pw)
    sh, sw = max(H, int(round(ph * s))), max(W, int(round(pw * s)))
    return sh, sw, (sh - H) // 2, (sw - W) // 2


def map_to_grid(img, clip_hw, mapping):
    """Resample a float panel-space image onto the clip grid, anti-aliased, as
    inkstab resizes the line-art layer."""
    from skimage.transform import resize
    H, W = clip_hw
    sh, sw, top, left = crop_geometry((img.shape[1], img.shape[0]), clip_hw, mapping)
    return resize(img, (sh, sw), anti_aliasing=True)[top:top + H, left:left + W]


def lineart_reference(root, panel, clip_hw, mapping):
    """The panel's line-art layer as a binary line map on the clip grid, binarised as
    inkstab's --lineart branch (invert, resize, Otsu), under `mapping`."""
    import imageio.v3 as iio
    from skimage.filters import threshold_otsu
    lg = 1.0 - inkstab._grey(iio.imread(Path(root) / "dataset" / "lineart" / f"{panel}-lines.png"))
    lg = map_to_grid(lg, clip_hw, mapping)
    return lg > (threshold_otsu(lg) if lg.max() > lg.min() else 0.5)


def panel_size(root, panel):
    """[width, height] of dataset/panels/<panel>.png."""
    import imageio.v3 as iio
    shape = iio.improps(Path(root) / "dataset" / "panels" / f"{panel}.png").shape
    return [int(shape[1]), int(shape[0])]


# ------------------------------------------------------------------- gate
def whole_frame_series(masks):
    """The frozen vs-frame-0 series: inkstab._chamfer(frame t, frame 0), t = 1..N-1."""
    return [inkstab._chamfer(m, masks[0]) for m in masks[1:]]


def gate_tolerance(released):
    """Pass tolerance in px: max(0.01 px, 0.5 % of the released value)."""
    return max(GATE_ABS_TOL, GATE_REL_TOL * abs(released))


def within_tolerance(value, released):
    """|value - released| <= gate_tolerance(released), bounds inclusive. False if either is missing."""
    if value is None or released is None:
        return False
    return abs(value - released) <= gate_tolerance(released)


def gate_clip(cell, root, device, expect_device, load=None, extract=None):
    """Gate record for one clip. Line maps never leave this function."""
    load = load or inkstab._load_frames
    extract = extract or inkstab._line_maps
    frames, _fps = load(str(Path(root) / cell["clip"]))
    n = int(len(frames))
    grid = [int(frames.shape[1]), int(frames.shape[2])]
    masks = extract(frames, device)
    del frames
    value = inkstab._stats(whole_frame_series(masks))["mean"]
    geometry = {mp: inkstab._chamfer(masks[0], lineart_reference(root, cell["panel"], grid, mp))
                for mp in MAPPINGS}
    del masks
    released = cell.get("released_px")
    tol = None if released is None else gate_tolerance(released)
    diff = None if value is None or released is None else abs(value - released)
    reasons = []
    if released is None:
        reasons.append("no released value")
    if value is None:
        reasons.append("no recomputed value")
    elif released is not None and not within_tolerance(value, released):
        reasons.append("value outside tolerance")
    if n != cell["released_n_frames"]:
        reasons.append("frame count differs")
    if grid != cell["released_grid"]:
        reasons.append("grid differs")
    if device != expect_device:
        reasons.append("device differs")
    ok = not reasons
    return {
        "cell_id": cell["public_id"], "engine": cell["engine"], "motion": cell["motion"],
        "n_frames": n, "n_frames_released": cell["released_n_frames"],
        "grid": grid, "grid_released": cell["released_grid"], "device": device,
        "chamfer_px": value, "chamfer_px_released": released,
        "abs_diff_px": diff, "tolerance_px": tol, "pass": ok, "reason": "; ".join(reasons),
        "panel_px": panel_size(root, cell["panel"]), "geometry": geometry,
    }


def code_identity(root=ROOT):
    """Which code produced a part: the bytes of inkstab.py and masked.py, and the git commit."""
    here = Path(__file__).resolve().parent
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8",
                              timeout=60, check=True).stdout
    try:
        commit = git("rev-parse", "HEAD").strip() or "unknown"
        dirty = bool(git("status", "--porcelain").strip())
    except Exception:
        commit, dirty = "unknown", "unknown"
    return {"inkstab_sha256": sha256_file(here / "inkstab.py"),
            "masked_sha256": sha256_file(here / "masked.py"), "git_commit": commit, "git_dirty": dirty}


def environment(device, expect_device="mps"):
    """Versions and weights the extraction ran under (echoed into every output)."""
    import scipy
    import skimage
    import torch
    from custom_controlnet_aux.util import HF_MODEL_NAME, custom_hf_download
    return {
        "netG_sha256": sha256_file(custom_hf_download(HF_MODEL_NAME, "netG.pth")),
        "torch": torch.__version__, "device": device, "python": platform.python_version(),
        "numpy": np.__version__, "scipy": scipy.__version__, "scikit_image": skimage.__version__,
        **code_identity(), "expect_device": expect_device,
    }


PART_KEYS = tuple(GATE_FIELDS) + ("panel_px", "geometry", "env")


def _env_core(env):
    return {k: v for k, v in env.items() if k not in ENV_NOT_COMPARED}


def part_is_current(path, cell, env):
    """True when `path` holds a complete part for this cell under this environment."""
    try:
        rec = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (isinstance(rec, dict) and all(k in rec for k in PART_KEYS)
            and isinstance(rec["env"], dict)
            and rec["cell_id"] == cell["public_id"]
            and rec["chamfer_px_released"] == cell.get("released_px")
            and _env_core(rec["env"]) == _env_core(env))


def max_rss_mb():
    """Peak resident set size of this process, MB (ru_maxrss is bytes on macOS, KB on Linux)."""
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / (1 << 20) if sys.platform == "darwin" else rss / 1024


def _release_memory(device):
    gc.collect()
    if device == "mps":
        try:
            import torch
            torch.mps.empty_cache()
        except Exception:
            pass


def _hms(seconds):
    s = int(round(seconds))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def run_gate(root, cells, device, env, expect_device="mps", parts_dir=None, redo=False,
             gate_one=gate_clip, log=None):
    """Score each clip that has no current part and write its part atomically.

    A clip that raises is logged and skipped (no part is written); the run goes on.
    Returns the list of (public id, error) for the clips that failed."""
    log = log or (lambda s: print(s, file=sys.stderr, flush=True))
    parts = Path(parts_dir) if parts_dir else Path(root) / PARTS
    parts.mkdir(parents=True, exist_ok=True)
    (parts / ".gitignore").write_text("*\n", encoding="utf-8", newline="\n")
    todo = []
    for i, cell in enumerate(cells, 1):
        out = parts / f"{cell['public_id']}.json"
        if redo or not out.exists():
            todo.append((i, cell))
        elif not part_is_current(out, cell, env):
            log(f"[gate {i}/{len(cells)}] {cell['public_id']}: stale part, re-running")
            todo.append((i, cell))
    log(f"[gate] resuming: {len(cells) - len(todo)} of {len(cells)} done")
    failed, spent = [], []
    for k, (i, cell) in enumerate(todo):
        out = parts / f"{cell['public_id']}.json"
        log(f"[gate {i}/{len(cells)}] start {cell['public_id']}")
        out.unlink(missing_ok=True)                  # a stale part must not survive a failed re-run
        t0 = time.time()
        try:
            rec = gate_one(cell, root, device, expect_device)
            rec["env"] = env
            rec["seconds"] = round(time.time() - t0, 1)
            write_atomic(out, json.dumps(rec, indent=1) + "\n")
        except Exception as e:
            failed.append((cell["public_id"], f"{type(e).__name__}: {e}"))
            log(f"[gate {i}/{len(cells)}] ERROR {cell['public_id']}: {type(e).__name__}: {e}")
            rec = None
        spent.append(time.time() - t0)
        _release_memory(device)
        if rec is not None:
            eta = _hms(sum(spent) / len(spent) * (len(todo) - k - 1))
            log(f"[gate {i}/{len(cells)}] {cell['public_id']}: {rec['chamfer_px']} vs released "
                f"{rec['chamfer_px_released']} -> {'PASS' if rec['pass'] else 'FAIL'} ({rec['seconds']} s, "
                f"max rss {max_rss_mb():.0f} MB, eta {eta})")
    if failed:
        log(f"[gate] {len(failed)} clip(s) failed and have no part: "
            + ", ".join(f"{pid} ({msg})" for pid, msg in failed))
    return failed


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)
    return str(v)


def _median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def choose_mappings(geometry_rows):
    """Per engine, the mapping with the lower median frame-0-vs-panel chamfer
    (stretch on a tie: it is what inkstab itself does)."""
    by = {}
    for r in geometry_rows:
        d = by.setdefault(r["engine"], {"stretch": [], "centre-crop": []})
        for mp, key in (("stretch", "chamfer_stretch_px"), ("centre-crop", "chamfer_centre_crop_px")):
            v = r[key]
            if v not in ("", None):
                d[mp].append(float(v))
    out = {}
    for e, d in by.items():
        s, c = _median(d["stretch"]), _median(d["centre-crop"])
        out[e] = "centre-crop" if (s is not None and c is not None and c < s) else "stretch"
    return out


def finalise_gate(root, cells, parts_dir=None):
    """Write the gate CSVs and summary once every clip has a part. Returns the
    number of passing clips, or None while parts are missing."""
    root = Path(root)
    parts = Path(parts_dir) if parts_dir else root / PARTS
    missing = [c["public_id"] for c in cells if not (parts / f"{c['public_id']}.json").exists()]
    if missing:
        print(f"[gate] {len(missing)} of {len(cells)} clips still to run; not finalised", file=sys.stderr)
        return None
    recs = [json.loads((parts / f"{c['public_id']}.json").read_text(encoding="utf-8")) for c in cells]
    for c, r in zip(cells, recs):
        if r.get("cell_id") != c["public_id"]:
            raise SystemExit(f"part {c['public_id']}.json holds cell {r.get('cell_id')!r}; re-run it with --redo")
    # masked.py and the commit may move during a resumed run (Task 3 edits masked.py while the
    # gate runs; the gate code is unchanged), so they are listed but not compared.
    envs = {json.dumps({k: v for k, v in r["env"].items() if k not in ENV_NOT_COMPARED}, sort_keys=True)
            for r in recs}
    if len(envs) != 1:
        raise SystemExit(f"gate parts were computed under {len(envs)} different environments; "
                         "re-run the odd ones with --redo")
    env = dict(recs[0]["env"])
    for r in recs:
        again = (within_tolerance(r["chamfer_px"], r["chamfer_px_released"])
                 and r["n_frames"] == r["n_frames_released"] and r["grid"] == r["grid_released"]
                 and r["device"] == r["env"].get("expect_device", r["device"]))
        if again != bool(r["pass"]):
            raise SystemExit(f"{r['cell_id']}: stored pass flag ({r['pass']}) disagrees with its numbers "
                             f"({again}); re-run it with --redo")
    for k in ENV_NOT_COMPARED:
        env[k] = ", ".join(sorted({str(r["env"].get(k, "unknown")) for r in recs}))

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(GATE_FIELDS)
    for r in recs:
        w.writerow([_cell(r["cell_id"]), r["engine"], r["motion"], r["n_frames"], r["n_frames_released"],
                    _grid(r["grid"]), _grid(r["grid_released"]), r["device"], _cell(r["chamfer_px"]),
                    _cell(r["chamfer_px_released"]), _cell(r["abs_diff_px"]), _cell(r["tolerance_px"]),
                    _cell(r["pass"])])
    write_atomic(root / GATE_CSV, buf.getvalue())

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(GEOM_FIELDS)
    geo_rows = []
    for r in recs:
        row = {"cell_id": r["cell_id"], "engine": r["engine"], "motion": r["motion"],
               "grid": _grid(r["grid"]), "panel_px": f"{r['panel_px'][0]}x{r['panel_px'][1]}",
               "chamfer_stretch_px": _cell(r["geometry"]["stretch"]),
               "chamfer_centre_crop_px": _cell(r["geometry"]["centre-crop"])}
        geo_rows.append(row)
        w.writerow([row[k] for k in GEOM_FIELDS])
    write_atomic(root / GEOM_CSV, buf.getvalue())

    n_pass = sum(r["pass"] for r in recs)
    chosen = choose_mappings(geo_rows)
    lines = [
        "# A9 reproduction gate", "",
        "Post-hoc (A9). The line maps of the 109 primary idle and burst clips were re-extracted",
        "before any mask existed. They were held in memory one clip at a time and never saved.", "",
        "Pass rule: every clip within max(0.01 px, 0.5 %) of its released `line_chamfer_mean_px`,",
        "with the same frame count, grid and device. A failure blocks everything; no clip is dropped.", "",
        f"**Result: {'PASS' if n_pass == len(recs) else 'FAIL'} ({n_pass} of {len(recs)} clips pass).**", "",
        "## Environment", "",
    ]
    lines += [f"- {k}: `{v}`" for k, v in env.items()]
    fails = [r for r in recs if not r["pass"]]
    if fails:
        lines += ["", "## Failing clips", "",
                  "| clip | frames (released) | grid (released) | device | recomputed px | released px | diff px | tolerance px | reason |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in fails:
            lines.append(f"| `{r['cell_id']}` | {r['n_frames']} ({r['n_frames_released']}) | "
                         f"{_grid(r['grid'])} ({_grid(r['grid_released'])}) | {r['device']} | "
                         f"{_cell(r['chamfer_px'])} | {_cell(r['chamfer_px_released'])} | "
                         f"{_cell(r['abs_diff_px'])} | {_cell(r['tolerance_px'])} | {r.get('reason', '')} |")
    lines += ["", "## Panel-to-clip mapping (frame 0 vs the panel's line-art layer)", "",
              "Median chamfer per engine, rows in frozen-league order. Each engine's mapping is the one",
              "with the lower median (stretch on a tie).", "",
              "| engine | clips | stretch, median px | centre-crop, median px | mapping |", "|---|---|---|---|---|"]
    for e in [x for x in LEAGUE_ORDER if x in chosen]:
        rows = [g for g in geo_rows if g["engine"] == e]
        ms = _median([float(g["chamfer_stretch_px"]) for g in rows if g["chamfer_stretch_px"]])
        mc = _median([float(g["chamfer_centre_crop_px"]) for g in rows if g["chamfer_centre_crop_px"]])
        lines.append(f"| {e} | {len(rows)} | {_cell(ms)} | {_cell(mc)} | {chosen[e]} |")
    lines += ["", "## Definitions echoed", "", "inkstab DEFS (frozen) and masked DEFS:", "", "```json",
              json.dumps({"inkstab": inkstab.DEFS, "masked": MASKED_DEFS}, indent=1), "```", ""]
    write_atomic(root / GATE_MD, "\n".join(lines))
    return n_pass


# ---------------------------------------------------------- masked drift
MARGINS = (16, 32, 64)
SET_NAMES = ("aaron", "agent")
MASK_FILES = {"aaron": "dataset/masks/allowed-aaron.json", "agent": "dataset/masks/allowed-agent.json"}
MASK_SCHEMA = "stilldrawn-allowed-regions/1"
MASK_TOP_KEYS = ("schema", "set", "drawn_by", "rule", "notes", "rows")
MASK_ROW_KEYS = ("panel", "motion", "panel_px", "allowed", "status")
MASK_STATUSES = ("drawn", "nothing-allowed")
MASKS_OUT = "runs/metrics-masked"
GATE_MATCH_PX = 1e-6
A9_HEADING = re.compile(r"^### A9 \u2014 ", re.M)        # "### A9 \u2014 " at the start of a line
MANIFEST = "docs/A9-MANIFEST.sha256"
A9_CONFIG = "analysis/adherence/a9-config.json"     # registered_on: read only once the manifest verifies it
GUARDED_INPUTS = ("metrics/masked.py", "metrics/inkstab.py", MASK_FILES["aaron"], MASK_FILES["agent"],
                  GATE_CSV, GEOM_CSV, A9_CONFIG)
A9_TAG = "a9-registered"
# The public StillDrawn repo on GitHub, over https or ssh; nothing else counts as "public".
PUBLIC_ORIGIN = re.compile(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
                           r"aaronlsmiles/stilldrawn(?:\.git)?")
EXTRACTION_KEYS = ("netG_sha256", "torch", "device")
# The release build rewrites these two lines of any .py file (tools/build_release.py, rewrite_text).
# The search strings are assembled from two pieces so that the rewrite leaves this file unchanged.
# The build's rewrite is a plain text replace over the whole file, so a literal copy of a search
# string (or of the working name in _OLD) here would itself be rewritten and change this file's
# registered hash; split across a `+`, no literal copy exists for it to find.
_HOME = "pathlib.Path.home() / "
RELEASE_LINES = (
    (_HOME + '"tools/ComfyUI/.venv/bin/python"',
     'pathlib.Path(__import__("os").environ.get("STILLDRAWN_PY", __import__("sys").executable))'),
    (_HOME + '"tools/ComfyUI/custom_nodes/comfyui_controlnet_aux/src"',
     'pathlib.Path(__import__("os").environ.get(   # AnimeLineArt extractor source\n'
     '    "STILLDRAWN_CONTROLNET_AUX_SRC", "comfyui_controlnet_aux/src"))'),
)
_OLD = ("Ink" + "Bench", "ink" + "bench", "INK" + "BENCH")   # the benchmark's working name, renamed in the release
RELEASE_NAMES = tuple(zip(_OLD, ("StillDrawn", "stilldrawn", "STILLDRAWN")))
# The build also renames the creator-IP panel's private id in every text file it ships. It is matched by
# its shape, so that no file that ships spells it: three lower-case letters other than the public `cip`,
# then `-act-tank-1` (no word boundary, as the build's own plain replace has none).
RELEASE_PANEL_ID = (re.compile(r"(?!cip-)[a-z]{3}-act-tank-1"), "cip-act-tank-1")
AARON_RATINGS = ("analysis/adherence/ratings-burst-AARON.json", "analysis/adherence/ratings-push-AARON.json")
RATINGS_SCHEMA = "stilldrawn-a9-ratings/1"


def rasterise(polygons, panel_wh, clip_hw, mapping):
    """Fill the allowed polygons (panel fractions) on the clip grid: M = may move.
    A point (x, y) lands at row y*scaled_h - top, column x*scaled_w - left; under stretch
    that is (y*H, x*W), sub-plan B's contract. skimage.draw.polygon includes boundary pixels."""
    from skimage.draw import polygon as fill
    H, W = clip_hw
    sh, sw, top, left = crop_geometry(panel_wh, clip_hw, mapping)
    M = np.zeros((H, W), dtype=bool)
    for poly in polygons:
        pts = np.asarray(poly, dtype=float)
        rr, cc = fill(pts[:, 1] * sh - top, pts[:, 0] * sw - left, shape=(H, W))
        M[rr, cc] = True
    return M


def region(M, margin):
    """R = ~binary_dilation(M, disk(margin)), computed as distance_transform_edt(~M) > margin
    (identical, unit-tested; and fast at margin 64). An empty M allows nothing to move: R is all-true."""
    from scipy.ndimage import distance_transform_edt
    if not M.any():
        return np.ones(M.shape, dtype=bool)
    return distance_transform_edt(~M) > margin


def regions(M, margins):
    """{margin: region(M, margin)} from one distance transform of ~M (tested identical)."""
    from scipy.ndimage import distance_transform_edt
    if not M.any():
        return {m: np.ones(M.shape, dtype=bool) for m in margins}
    d = distance_transform_edt(~M)
    return {m: d > m for m in margins}


def masked_frame(a, b, R, da=None, db=None):
    """The one per-frame implementation of MASKED_DEFS["masked_chamfer"]. a = frame t line map,
    b = frame 0 line map, R = measured region (bool, same shape). Full-frame distance transforms:
    da = EDT(~b), db = EDT(~a), as in inkstab._chamfer. None if a or b has no line at all; both
    a&R and b&R non-empty: 0.5*(da[a&R].mean() + db[b&R].mean()); only b&R (lines vanished from R):
    db[b&R].mean(); only a&R (lines appeared in R): da[a&R].mean(); neither: None. Returns a Python
    float or None. With R all-true it equals inkstab._chamfer(a, b) bit for bit.
    `da` and `db` are optional precomputed transforms (masked_series shares them across regions
    and frames); they are the same scipy call on the same input, so the result is bit-identical
    to computing them here."""
    if not a.any() or not b.any():
        return None
    if da is None or db is None:
        from scipy.ndimage import distance_transform_edt
        da = distance_transform_edt(~b) if da is None else da
        db = distance_transform_edt(~a) if db is None else db
    aR, bR = a & R, b & R
    has_a, has_b = bool(aR.any()), bool(bR.any())
    if has_a and has_b:
        return float(0.5 * (da[aR].mean() + db[bR].mean()))
    if has_b:                      # frame-0 lines vanished from R: they count as drift
        return float(db[bR].mean())
    if has_a:                      # lines appeared where frame 0 had none in R (the mirror term)
        return float(da[aR].mean())
    return None


masked_chamfer = masked_frame      # the earlier name, kept for callers and tests


def masked_series(masks, regions):
    """{key: series over frames 1..N-1} for every region in `regions`, each value from
    masked_frame, sharing the distance transforms across regions and frames."""
    from scipy.ndimage import distance_transform_edt
    b = masks[0]
    if not b.any():
        return {k: [None] * (len(masks) - 1) for k in regions}
    out = {k: [] for k in regions}
    da = distance_transform_edt(~b)        # distance to frame-0 lines: the same for every frame
    for a in masks[1:]:
        if not a.any():
            for k in regions:
                out[k].append(None)
            continue
        db = distance_transform_edt(~a)
        for k, R in regions.items():
            out[k].append(masked_frame(a, b, R, da=da, db=db))
    return out


def clip_value(series):
    """(mean of the scorable frames, no_scorable_frame). The value is None (read as +inf)
    when no frame is scorable."""
    s = [x for x in series if x is not None]
    if not s:
        return None, True
    return float(np.mean(s)), False


def _reject_constant(name):
    raise ValueError(f"{name} is not a number JSON allows")


def _no_duplicate_keys(pairs):
    keys = [k for k, _v in pairs]
    dup = sorted({k for k in keys if keys.count(k) > 1})
    if dup:
        raise ValueError(f"duplicate key(s) {dup}")
    return dict(pairs)


def _fraction(v):
    return (not isinstance(v, bool) and isinstance(v, (int, float)) and np.isfinite(v)
            and 0.0 <= v <= 1.0)


def _mask_problems(d):
    if not isinstance(d, dict):
        return ["not a JSON object"]
    if sorted(d) != sorted(MASK_TOP_KEYS):
        return [f"top-level keys must be exactly {list(MASK_TOP_KEYS)}, found {sorted(d)}"]
    errs = []
    if d["schema"] != MASK_SCHEMA:
        errs.append(f"schema must be {MASK_SCHEMA!r}")
    for k in ("set", "drawn_by", "rule"):
        if not isinstance(d[k], str) or not d[k]:
            errs.append(f"{k} must be a non-empty string")
    if not isinstance(d["notes"], str):
        errs.append("notes must be a string")
    if not isinstance(d["rows"], dict) or not d["rows"]:
        return errs + ["rows must be a non-empty object"]
    for key, row in d["rows"].items():
        if not isinstance(row, dict) or sorted(row) != sorted(MASK_ROW_KEYS):
            errs.append(f"{key}: a row has exactly the keys {list(MASK_ROW_KEYS)}")
            continue
        panel, motion = row["panel"], row["motion"]
        if not (isinstance(panel, str) and panel and isinstance(motion, str) and motion) \
                or key != f"{panel}_{motion}":
            errs.append(f"{key}: the row id must be <panel>_<motion> of its own panel and motion")
        px = row["panel_px"]
        if not (isinstance(px, list) and len(px) == 2
                and all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in px)):
            errs.append(f"{key}: panel_px must be [width, height] in whole pixels")
        status, polys = row["status"], row["allowed"]
        if status not in MASK_STATUSES:
            errs.append(f"{key}: status must be drawn or nothing-allowed, got {status!r}")
            continue
        if not isinstance(polys, list):
            errs.append(f"{key}: allowed must be a list of polygons")
            continue
        if (status == "drawn") != bool(polys):
            errs.append(f"{key}: drawn rows need polygons; nothing-allowed rows have none")
        for i, poly in enumerate(polys):
            if not isinstance(poly, list) or len(poly) < 3:
                errs.append(f"{key}, polygon {i}: a polygon needs at least 3 points")
                continue
            for pt in poly:
                if not (isinstance(pt, list) and len(pt) == 2 and all(_fraction(v) for v in pt)):
                    errs.append(f"{key}, polygon {i}: point {pt!r} is not [x, y] with both in [0, 1]")
                    break
    return errs


def read_masks(path):
    """(document, sha256 of the bytes parsed): one read, so the hash recorded is of the exact
    bytes checked. A stilldrawn-allowed-regions/1 file (sub-plan B's schema): top-level keys
    exactly schema, set, drawn_by, rule, notes, rows; row id <panel>_<motion>; row keys exactly
    panel, motion, panel_px, allowed, status; no duplicate key, NaN or infinity. Raises
    ValueError on any problem."""
    raw = Path(path).read_bytes()
    try:
        d = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant, object_pairs_hook=_no_duplicate_keys)
    except ValueError as e:
        raise ValueError(f"{path}: not a valid {MASK_SCHEMA} file: {e}") from None
    errs = _mask_problems(d)
    if errs:
        raise ValueError(f"{path}: not a valid {MASK_SCHEMA} file:\n  " + "\n  ".join(errs))
    return d, sha256_bytes(raw)


def load_masks(path):
    """The checked document of a mask file (see read_masks)."""
    return read_masks(path)[0]


def score_line_maps(masks, rows, mapping, margins=MARGINS):
    """Whole-frame and masked drift for one clip's line maps. `rows` maps a mask-set
    name to that set's row for this clip's panel and class."""
    clip_hw = masks[0].shape
    by_cond, m_empty = {}, {}
    for name, row in rows.items():
        M = rasterise(row["allowed"], tuple(row["panel_px"]), clip_hw, mapping)
        # a drawn row whose polygons cover no pixel centre on this grid: M is empty, R is everything
        m_empty[name] = bool(row["status"] == "drawn" and not M.any())
        for m, R in regions(M, margins).items():
            by_cond[(name, m)] = R
    series = masked_series(masks, by_cond)
    whole = whole_frame_series(masks)
    out = {"whole_frame": {"chamfer_px": clip_value(whole)[0], "chamfer_series": whole}, "masked": {},
           "m_empty": m_empty}
    for (name, m), R in by_cond.items():
        v, none = clip_value(series[(name, m)])
        out["masked"].setdefault(name, {})[f"m{m}"] = {
            "region_frac": float(R.mean()), "f0_line_px_in_R": int((masks[0] & R).sum()),
            "chamfer_px": v, "no_scorable_frame": none, "chamfer_series": series[(name, m)],
        }
    return out


def release_form(relpath, text):
    """The text of a .py file as the release build ships it: the private home-folder paths
    of the venv python and the line extractor become environment variables, and the
    benchmark's working name becomes StillDrawn; in any text file the creator-IP panel's private id
    becomes its public one (as the build does). Identity on a
    file already in release form (the public tree). Unit-tested against the build on the
    real inkstab.py and masked.py."""
    if relpath.endswith(".py"):
        for old, new in RELEASE_LINES + RELEASE_NAMES:
            text = text.replace(old, new)
    return RELEASE_PANEL_ID[0].sub(RELEASE_PANEL_ID[1], text)


def _registered_sha256(root, relpath):
    """sha256 of the local file in its release form (the manifest hashes release-tree bytes)."""
    p = Path(root) / relpath
    if relpath.endswith(".py"):
        return sha256_bytes(release_form(relpath, p.read_text(encoding="utf-8")).encode("utf-8"))
    return sha256_file(p)


def record_text(rec):
    """A record as JSON text: indent 1, LF, ASCII, and no NaN or infinity (ValueError)."""
    return json.dumps(rec, indent=1, allow_nan=False) + "\n"


# ------------------------------------------------------- registration guard
class GuardError(Exception):
    pass


_run = subprocess.run                    # every guard git call goes through _git_run (tests swap this)
GIT_NETWORK = ("fetch", "ls-remote")
GIT_NETWORK_TIMEOUT_S, GIT_LOCAL_TIMEOUT_S = 120, 60
ORIGIN_MAIN = "refs/remotes/origin/main"  # always the full ref: a local branch named origin/main shadows the short form


def _git_run(repo, *args, ok=(0,)):
    """Run one git command in `repo`: no terminal prompt, a timeout (120 s for fetch and ls-remote,
    60 s otherwise). A timeout, a git that cannot start, or an exit code outside `ok` is a GuardError
    naming the command."""
    what = f"git {' '.join(args)}"
    timeout = GIT_NETWORK_TIMEOUT_S if args[0] in GIT_NETWORK else GIT_LOCAL_TIMEOUT_S
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        r = _run(["git", "-C", str(repo), *args], capture_output=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise GuardError(f"{what} timed out after {timeout} s in {repo}") from None
    except OSError as e:
        raise GuardError(f"{what} could not run in {repo}: {e}") from None
    if r.returncode not in ok:
        raise GuardError(f"{what} failed (exit {r.returncode}) in {repo}: "
                         f"{r.stderr.decode('utf-8', errors='replace').strip()[-300:]}")
    return r


def _git(repo, *args):
    return _git_run(repo, *args).stdout


def _utf8(raw, what):
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise GuardError(f"{what} is not UTF-8 ({e})") from None


def _git_text(repo, *args):
    """git output as UTF-8 text; undecodable bytes are a GuardError."""
    return _utf8(_git(repo, *args), f"the output of git {' '.join(args)}")


def parse_manifest(text):
    """{path: sha256} from `sha256sum` output lines. Malformed or repeated lines are refused."""
    out = {}
    for line in text.split("\n"):
        if not line:
            continue
        m = re.fullmatch(r"([0-9a-f]{64}) [ *](\S.*)", line)
        if not m:
            raise GuardError(f"malformed manifest line: {line!r}")
        if m[2] in out:
            raise GuardError(f"manifest lists {m[2]} twice")
        out[m[2]] = m[1]
    return out


def _day(v):
    """A YYYY-MM-DD string as a date, else None."""
    if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return None
    try:
        return datetime.date.fromisoformat(v)
    except ValueError:
        return None


def _registered_on(root):
    """(date, problem): a9-config.json's registered_on."""
    try:
        c = json.loads((Path(root) / A9_CONFIG).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        c = None
    day = _day(c.get("registered_on")) if isinstance(c, dict) else None
    if day is None:
        return None, f"{A9_CONFIG}: registered_on must be the registration day (YYYY-MM-DD)"
    return day, None


def _check_ratings(root, path, study, registered):
    """Problem with one of AARON's slim ratings files, or None."""
    p = root / path
    if not p.exists():
        return f"{path}: AARON's ratings must be exported and committed before any masked value"
    if _git_run(root, "cat-file", "-e", f"HEAD:{path}", ok=(0, 1, 128)).returncode:
        return f"{path}: not committed"
    if _git_run(root, "diff", "--quiet", "HEAD", "--", path, ok=(0, 1)).returncode == 1:
        return f"{path}: has uncommitted changes"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = None
    if not (isinstance(d, dict) and d.get("schema") == RATINGS_SCHEMA and d.get("rater") == "AARON"
            and d.get("study") == study):
        return f"{path}: not AARON's slim {study} ratings ({RATINGS_SCHEMA})"
    received = _day(d.get("received_day"))
    if received is None or registered is None or not received > registered:
        return (f"{path}: received_day {d.get('received_day')!r} is not after registration "
                f"({registered}); A9.5 has AARON rate on a later calendar day")
    return None


def _check_public_ratings(public_repo, root, path, registered):
    """Problem with one of AARON's slim ratings files as published, or None. The file must exist at
    origin/main of the public repo, byte-identical to the private file in its release form, with a
    received_day strictly after registered_on."""
    try:
        blob = _git(public_repo, "cat-file", "blob", f"{ORIGIN_MAIN}:{path}")     # raw blob bytes, no textconv
    except GuardError:
        return (f"{path}: not on origin/main of the public repo; AARON's ratings must be published "
                "there before any masked value")
    local = Path(root) / path
    try:
        # raw bytes both sides: read_text would fold CRLF into LF and hide a line-ending difference
        want = release_form(path, local.read_bytes().decode("utf-8")).encode("utf-8")
    except (OSError, UnicodeDecodeError):
        return f"{path}: the private file cannot be read, so the public copy cannot be compared"
    if blob != want:
        return (f"{path}: the public copy at origin/main differs from the private file's release form; "
                "publish the file as it is")
    try:
        d = json.loads(blob.decode("utf-8"))
    except ValueError:
        d = None
    received = _day(d.get("received_day")) if isinstance(d, dict) else None
    if received is None or registered is None or not received > registered:
        return (f"{path}: the public copy's received_day "
                f"{d.get('received_day') if isinstance(d, dict) else None!r} is not after registration "
                f"({registered}); A9.5 has AARON rate on a later calendar day")
    return None


def _redact(url):
    return re.sub(r"(://)[^/@]+@", r"\1***@", url)


def _has_credentials(url):
    return bool(re.match(r"^[a-z][a-z0-9+.-]*://[^/@]*:[^/@]*@", url, re.I) or re.match(r"^https?://[^/]*@", url, re.I))


def _origin_url(public_repo):
    """The effective origin URL: `git remote get-url origin` applies insteadOf rewrites from any
    config level (and GIT_CONFIG_* variables), so this is where a fetch really goes."""
    return _git_text(public_repo, "remote", "get-url", "origin").strip()


def _check_public_repo(public_repo, root):
    """The public checkout is not the private repo, and its origin is the pinned GitHub repo
    with no credentials in the URL (the effective URL, after any insteadOf rewrite)."""
    try:
        top = Path(_git_text(public_repo, "rev-parse", "--show-toplevel").strip()).resolve()
    except GuardError as e:
        raise GuardError(f"--public-repo {public_repo} is not a git checkout ({e})") from None
    mine = {Path(root).resolve()}
    try:
        mine.add(Path(_git_text(root, "rev-parse", "--show-toplevel").strip()).resolve())
    except GuardError:
        pass
    if top in mine:
        raise GuardError(f"--public-repo {public_repo} is the private repo; give the public StillDrawn checkout")
    try:
        url = _origin_url(public_repo)
    except GuardError:
        # get-url can fail on its own when the URL carries credentials (transfer.credentialsInUrl=die);
        # the configured URL is read only to say why, never trusted as the effective one.
        try:
            url = _git_text(public_repo, "config", "--get", "remote.origin.url").strip()
        except GuardError:
            raise GuardError("the public checkout has no origin remote") from None
        if not _has_credentials(url):
            raise GuardError("git remote get-url origin failed in the public checkout") from None
    if _has_credentials(url):
        raise GuardError("the public checkout's origin URL carries credentials; use a plain URL "
                         "(credentials belong in the keychain)")
    if not PUBLIC_ORIGIN.fullmatch(url):
        raise GuardError(f"origin {_redact(url)!r} is not the public StillDrawn repo "
                         "(pinned: github.com/aaronlsmiles/stilldrawn over https or ssh)")


def _tag_commit(public_repo, fetch):
    """The commit tag a9-registered names on origin (peeled), fetched if needed."""
    if fetch:
        out = _git_text(public_repo, "ls-remote", "--tags", "origin", f"refs/tags/{A9_TAG}")
        refs = dict(reversed(line.split("\t", 1)) for line in out.splitlines() if "\t" in line)
        sha = refs.get(f"refs/tags/{A9_TAG}^{{}}") or refs.get(f"refs/tags/{A9_TAG}")
        if not sha:
            raise GuardError(f"tag {A9_TAG} is not on origin: A9 is not registered")
        if _git_run(public_repo, "cat-file", "-e", f"{sha}^{{commit}}", ok=(0, 1, 128)).returncode:
            _git(public_repo, "fetch", "--quiet", "origin", f"refs/tags/{A9_TAG}")
        return _git_text(public_repo, "rev-parse", "--verify", f"{sha}^{{commit}}").strip()
    try:
        return _git_text(public_repo, "rev-parse", "--verify", f"refs/tags/{A9_TAG}^{{commit}}").strip()
    except GuardError:
        raise GuardError(f"tag {A9_TAG} is not in the public checkout: A9 is not registered") from None


def _registered_at(public_repo, ref, label):
    """(manifest bytes) at `ref`, after checking its A9 heading."""
    try:
        raw = _git(public_repo, "show", f"{ref}:docs/PREREGISTRATION.md")
    except GuardError as e:
        raise GuardError(f"{label} has no docs/PREREGISTRATION.md: A9 is not registered ({e})") from None
    prereg = _utf8(raw, f"{label}'s docs/PREREGISTRATION.md")
    if not A9_HEADING.search(prereg):
        raise GuardError(f"{label}'s docs/PREREGISTRATION.md has no '### A9 \u2014 ' heading: A9 is not registered")
    try:
        return _git(public_repo, "show", f"{ref}:{MANIFEST}")
    except GuardError as e:
        raise GuardError(f"{label} has no {MANIFEST}: A9 is not registered ({e})") from None


def registration_guard(public_repo, root=ROOT, fetch=True):
    """Refuse unless A9 is public. All of these must hold:
    - `public_repo` is not the private repo, and its origin is the pinned public StillDrawn repo
      on GitHub (https or ssh), with no credentials in the URL;
    - after a fetch, origin/main and the tag a9-registered (on origin, an ancestor of
      origin/main) both carry a `### A9 \u2014 ` heading in docs/PREREGISTRATION.md and the same
      docs/A9-MANIFEST.sha256, identical to the local one;
    - every manifest hash matches the file at both the tag and origin/main;
    - the local copies of the inputs this tool reads (masked.py, inkstab.py, both mask files,
      both gate CSVs, a9-config.json) are the registered bytes, .py files compared in their
      release form and every other file byte for byte;
    - AARON's two slim ratings files are committed (private HEAD) and were received after
      a9-config.json's registered_on (A9.5: ratings on a later day, before any masked value), and
      both are also at origin/main of the public repo, byte-identical to the private files in
      their release form.
    Returns the manifest entries; raises GuardError otherwise."""
    if not public_repo:
        raise GuardError("--public-repo is required: A9 must be public before any masked value exists")
    root = Path(root)
    _check_public_repo(public_repo, root)
    if fetch:
        _git(public_repo, "fetch", "--quiet", "origin")
        heads = _git_text(public_repo, "ls-remote", "origin", "refs/heads/main").split()
        if not heads:
            raise GuardError("origin has no main branch")
        try:
            tracked = _git_text(public_repo, "rev-parse", "--verify", f"{ORIGIN_MAIN}^{{commit}}").strip()
        except GuardError:
            tracked = None
        if heads[0] != tracked:
            raise GuardError(f"{ORIGIN_MAIN} is stale: it is {tracked}, but origin's main is {heads[0]} "
                             "after the fetch (check the checkout's fetch refspec)")
    main_manifest = _registered_at(public_repo, ORIGIN_MAIN, "origin/main")
    tag = _tag_commit(public_repo, fetch)
    if _git_run(public_repo, "merge-base", "--is-ancestor", tag, ORIGIN_MAIN, ok=(0, 1)).returncode == 1:
        raise GuardError(f"tag {A9_TAG} is not an ancestor of origin/main: the registered commit is not on main")
    if _registered_at(public_repo, tag, A9_TAG) != main_manifest:
        raise GuardError(f"{MANIFEST} at {A9_TAG} differs from origin/main's: the manifest moved after registration")
    local = root / MANIFEST
    if not local.exists() or local.read_bytes() != main_manifest:
        raise GuardError(f"local {MANIFEST} is missing or differs from origin/main's")
    entries = parse_manifest(_utf8(main_manifest, MANIFEST))
    problems = []
    for ref, label in ((tag, A9_TAG), (ORIGIN_MAIN, "origin/main")):
        for path, digest in entries.items():
            try:
                blob = _git(public_repo, "show", f"{ref}:{path}")
            except GuardError:
                problems.append(f"{path}: listed in the manifest but absent at {label}")
                continue
            if sha256_bytes(blob) != digest:
                problems.append(f"{path}: {label}'s bytes do not match the manifest")
    for path in GUARDED_INPUTS:
        if path not in entries:
            problems.append(f"{path}: not in the manifest")
        elif not (root / path).is_file() or _registered_sha256(root, path) != entries[path]:
            problems.append(f"{path}: the local file is not the registered one")
    registered, problem = _registered_on(root)
    if problem:
        problems.append(problem)
    for path, study in zip(AARON_RATINGS, ("burst", "push")):
        problem = _check_ratings(root, path, study, registered)
        if problem:
            problems.append(problem)
        problem = _check_public_ratings(public_repo, root, path, registered)
        if problem:
            problems.append(problem)
    if problems:
        raise GuardError("registration guard refused:\n  " + "\n  ".join(problems))
    return entries


def is_a9_clip(clip, cells, root=ROOT):
    """True if `clip` is one of the A9 clips: by path (the same file), by name (a file named
    after an A9 cell or its clip) or by identical bytes (a copy). A re-encoded or otherwise
    altered copy under a new name is not caught: this is a tripwire, not a proof."""
    root, p = Path(root), Path(clip)
    paths = {(root / c["clip"]).resolve() for c in cells}
    if p.resolve() in paths or (root / p).resolve() in paths:
        return True
    names = {c["public_id"] for c in cells} | {public_id(Path(c["clip"]).stem) for c in cells}
    if public_id(p.stem) in names:
        return True
    if p.is_file():
        size, digest = p.stat().st_size, None
        for q in paths:
            if q.is_file() and q.stat().st_size == size:
                digest = digest or sha256_file(p)
                if sha256_file(q) == digest:
                    return True
    return False


# ------------------------------------------------------------------ a9 run
def read_gate(root):
    """({public cell id: recomputed whole-frame px}, device) from an all-pass gate CSV."""
    with open(Path(root) / GATE_CSV, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for i, r in enumerate(rows, 1):
        for k in ("cell_id", "device", "chamfer_px", "pass"):
            if not (r.get(k) or "").strip():
                raise SystemExit(f"{GATE_CSV} row {i}: {k} is blank")
        try:
            v = float(r["chamfer_px"])
        except ValueError:
            v = float("nan")
        if not np.isfinite(v) or v < 0:
            raise SystemExit(f"{GATE_CSV} row {i}: chamfer_px {r['chamfer_px']!r} is not a finite number >= 0")
    ids = {r["cell_id"] for r in rows}
    if len(rows) != A9_N_CLIPS or len(ids) != len(rows) or any(r["pass"] != "true" for r in rows):
        raise SystemExit(f"{GATE_CSV} must hold {A9_N_CLIPS} passing clips, one row each, before a9-run")
    devices = {r["device"] for r in rows}
    if len(devices) != 1:
        raise SystemExit(f"{GATE_CSV}: the gate must have been computed on one device, found {sorted(devices)}")
    return {r["cell_id"]: float(r["chamfer_px"]) for r in rows}, devices.pop()


def read_geometry(root):
    with open(Path(root) / GEOM_CSV, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


_PANEL_SIZES = {}


def _panel_size_cached(root, panel):
    key = (str(Path(root).resolve()), panel)
    if key not in _PANEL_SIZES:
        _PANEL_SIZES[key] = panel_size(root, panel)
    return _PANEL_SIZES[key]


def check_mask_sets(cells, sets, root):
    """Before any extraction: both sets present under their own names, and every A9 row in
    each, drawn on a panel of the right size."""
    if sorted(sets) != sorted(SET_NAMES):
        raise SystemExit(f"a9-run needs exactly the mask sets {list(SET_NAMES)}, got {sorted(sets)}")
    sizes = {}
    for name, s in sets.items():
        if s["set"] != name:
            raise SystemExit(f"the {name} mask file says set {s['set']!r}")
        for cell in cells:
            key = f"{cell['public_panel']}_{cell['motion']}"
            if key not in s["rows"]:
                raise SystemExit(f"mask set {name} has no row {key}")
            if cell["panel"] not in sizes:
                sizes[cell["panel"]] = _panel_size_cached(root, cell["panel"])
            if s["rows"][key]["panel_px"] != sizes[cell["panel"]]:
                raise SystemExit(f"mask set {name} row {key}: panel_px {s['rows'][key]['panel_px']} "
                                 f"is not the panel's size {sizes[cell['panel']]}")


def a9_clip(cell, root, device, env, sets, shas, mapping, gate_px, load=None, extract=None):
    """The registered record for one clip: whole frame plus 2 mask sets x 3 margins, from
    one extraction. Stops if the clip or its whole-frame value is not the gate's."""
    load = load or inkstab._load_frames
    extract = extract or inkstab._line_maps
    check_mask_sets([cell], sets, root)
    key = f"{cell['public_panel']}_{cell['motion']}"
    rows = {name: s["rows"][key] for name, s in sets.items()}
    frames, _fps = load(str(Path(root) / cell["clip"]))
    n, grid = int(len(frames)), [int(frames.shape[1]), int(frames.shape[2])]
    if n != cell["released_n_frames"] or grid != cell["released_grid"]:
        raise SystemExit(f"{cell['public_id']}: {n} frames on {grid}, but the gate saw "
                         f"{cell['released_n_frames']} on {cell['released_grid']}. Stop and investigate; "
                         "nothing was written for this clip.")
    masks = extract(frames, device)
    del frames
    res = score_line_maps(masks, rows, mapping)
    del masks
    w = res["whole_frame"]["chamfer_px"]
    if w is None or gate_px is None or abs(w - gate_px) > GATE_MATCH_PX:
        raise SystemExit(f"{cell['public_id']}: whole-frame {w} differs from the gate's {gate_px} by more than "
                         f"{GATE_MATCH_PX} px. Stop and investigate; nothing was written for this clip.")
    clip = re.sub(r"(^|/)[a-z]{3}-act-tank-1", r"\1cip-act-tank-1", cell["clip"])   # public path
    return {
        "cell_id": cell["public_id"], "clip": clip, "panel": cell["public_panel"],
        "motion": cell["motion"], "engine": cell["engine"], "n_frames": n, "resolution": grid,
        "defs": {"inkstab": inkstab.DEFS, "masked": MASKED_DEFS},
        "extraction": {k: env[k] for k in EXTRACTION_KEYS},
        "mapping": mapping,
        "whole_frame": {**res["whole_frame"], "gate_chamfer_px": gate_px},
        "masked": res["masked"], "m_empty": res["m_empty"], "masks_sha256": shas,
    }


def record_expectations(cell, env, shas, mapping, gate_px):
    """What an existing record must hold to count as this run's: the cell, both mask
    hashes, the mapping, the extraction fields and the gate's whole-frame value."""
    return {"cell_id": cell["public_id"], "masks_sha256": shas, "mapping": mapping,
            "extraction": {k: env[k] for k in EXTRACTION_KEYS}, "gate_chamfer_px": gate_px}


RECORD_BLOCK_KEYS = ("region_frac", "f0_line_px_in_R", "chamfer_px", "no_scorable_frame", "chamfer_series")


def _record_complete(rec):
    """Every block a9_clip writes is there: n_frames, whole_frame with its chamfer_px and a
    series of n_frames - 1 values, the six masked.<set>.m<margin> blocks with all fields and
    series of the same length, and m_empty for both sets."""
    n = rec.get("n_frames")
    if isinstance(n, bool) or not isinstance(n, int) or n < 2:
        return False

    def series_ok(s):
        return isinstance(s, list) and len(s) == n - 1

    whole, masked, m_empty = rec.get("whole_frame"), rec.get("masked"), rec.get("m_empty")
    if not (isinstance(whole, dict) and "chamfer_px" in whole and series_ok(whole.get("chamfer_series"))):
        return False
    if not (isinstance(m_empty, dict) and all(isinstance(m_empty.get(s), bool) for s in SET_NAMES)):
        return False
    if not isinstance(masked, dict):
        return False
    for s in SET_NAMES:
        for m in MARGINS:
            block = masked.get(s, {}).get(f"m{m}") if isinstance(masked.get(s), dict) else None
            if not (isinstance(block, dict) and all(k in block for k in RECORD_BLOCK_KEYS)
                    and series_ok(block["chamfer_series"])):
                return False
    return True


def record_state(path, expect):
    """'missing', 'damaged' (unreadable or incomplete), 'stale' (another run's masks, mapping,
    extraction or gate value) or 'done'. A readable record for another cell is refused."""
    path = Path(path)
    if not path.exists():
        return "missing"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "damaged"
    if not isinstance(rec, dict):
        return "damaged"
    if rec.get("cell_id") != expect["cell_id"]:
        raise SystemExit(f"{path} holds cell {rec.get('cell_id')!r}, not {expect['cell_id']!r}. "
                         "Stop and investigate; remove it by hand if it does not belong there.")
    if not _record_complete(rec):
        return "damaged"
    whole = rec.get("whole_frame")
    same = (rec.get("masks_sha256") == expect["masks_sha256"] and rec.get("mapping") == expect["mapping"]
            and rec.get("extraction") == expect["extraction"] and isinstance(whole, dict)
            and whole.get("gate_chamfer_px") == expect["gate_chamfer_px"])
    return "done" if same else "stale"


def run_a9(root, cells, device, env, gate, mappings, sets, shas, out_dir=None, clip_fn=a9_clip, log=None):
    """Write one record per clip, atomically. A record that already holds this run's masks,
    mapping, extraction and gate value is kept (resumable); a damaged or stale one is re-run and
    stays in place until write_atomic replaces it. The file name is the repo's cell id; the
    release build renames it."""
    log = log or (lambda s: print(s, file=sys.stderr, flush=True))
    out_dir = Path(out_dir) if out_dir else Path(root) / MASKS_OUT
    for i, cell in enumerate(cells, 1):
        out = out_dir / f"{cell['cell_id']}.json"
        mapping, gate_px = mappings[cell["engine"]], gate[cell["public_id"]]
        state = record_state(out, record_expectations(cell, env, shas, mapping, gate_px))
        if state == "done":
            continue
        if state != "missing":
            log(f"[a9-run {i}/{len(cells)}] {cell['public_id']}: {state} record, re-running")
        t0 = time.time()
        rec = clip_fn(cell, root, device, env, sets, shas, mapping, gate_px)
        write_atomic(out, record_text(rec))
        log(f"[a9-run {i}/{len(cells)}] {cell['public_id']} done ({time.time() - t0:.0f} s, "
            f"max rss {max_rss_mb():.0f} MB)")
        _release_memory(device)


# -------------------------------------------------------------------- CLI
def refuse_if_masks_exist(root):
    """Gate before masks (D3): the gate must run before any mask file exists."""
    found = sorted(Path(root).glob("dataset/masks/allowed-*.json"))
    if found:
        raise SystemExit("refusing to run the gate: mask file(s) already exist "
                         f"({', '.join(p.name for p in found)}). The reproduction gate runs before any mask.")


def cmd_gate(a):
    refuse_if_masks_exist(ROOT)
    device = inkstab._device()
    if device != a.expect_device:
        raise SystemExit(f"device is {device!r} but --expect-device is {a.expect_device!r}: the released "
                         "values were computed on the expected device, so the gate cannot pass here")
    cells = a9_cells(ROOT)
    if len(cells) != A9_N_CLIPS:
        raise SystemExit(f"expected {A9_N_CLIPS} primary idle and burst clips, found {len(cells)}")
    todo = cells[: a.first] if a.first else cells
    env = environment(device, a.expect_device)
    print(json.dumps({"inkstab_defs": inkstab.DEFS, "masked_defs": MASKED_DEFS, "env": env}, indent=1),
          file=sys.stderr, flush=True)
    failed = run_gate(ROOT, todo, device, env, expect_device=a.expect_device, redo=a.redo)
    if failed:
        print(f"[gate] {len(failed)} clip(s) errored; not finalised. Re-run to resume.", file=sys.stderr)
        return 1
    if a.first:
        print(f"[gate] --first {a.first}: parts written; finalise skipped", file=sys.stderr)
        return 0
    n_pass = finalise_gate(ROOT, cells)
    if n_pass is None:
        return 1
    print(f"[gate] {n_pass} of {len(cells)} clips pass -> {GATE_CSV}, {GEOM_CSV}, {GATE_MD}", file=sys.stderr)
    return 0 if n_pass == len(cells) else 1


def cmd_score(a):
    """Any clip, masks file and row (P47 reuses this). An A9 clip is refused until A9 is public.
    The A9 check is by path, name or identical bytes (is_a9_clip); it does not catch a
    re-encoded copy. A masks file byte-identical to either registered A9 mask set also needs the
    guard. The output records the clip's file name only, never its path."""
    if not (ROOT / "runs" / "manifest.jsonl").is_file():
        raise SystemExit(f"score needs runs/manifest.jsonl under {ROOT} to recognise the A9 clips; "
                         "run it from a StillDrawn checkout")
    if is_a9_clip(a.clip, a9_cells(ROOT), ROOT):
        try:
            registration_guard(a.public_repo, ROOT)
        except GuardError as e:
            raise SystemExit(f"{Path(a.clip).name} is an A9 clip: {e}")
    try:
        s, masks_sha = read_masks(a.masks)
    except (OSError, ValueError) as e:
        raise SystemExit(str(e))
    a9_masks = {sha256_file(ROOT / f): name for name, f in MASK_FILES.items() if (ROOT / f).is_file()}
    if masks_sha in a9_masks:
        try:
            registration_guard(a.public_repo, ROOT)
        except GuardError as e:
            raise SystemExit(f"{Path(a.masks).name} is the registered A9 mask set {a9_masks[masks_sha]}: {e}")
    if a.row not in s["rows"]:
        raise SystemExit(f"{a.masks} has no row {a.row}")
    device = inkstab._device()
    env = environment(device, device)
    frames, _fps = inkstab._load_frames(str(a.clip))
    n, grid = int(len(frames)), [int(frames.shape[1]), int(frames.shape[2])]
    masks = inkstab._line_maps(frames, device)
    del frames
    res = score_line_maps(masks, {s["set"]: s["rows"][a.row]}, a.mapping, tuple(a.margins))
    del masks
    out = {"clip": Path(a.clip).name, "row": a.row, "n_frames": n, "resolution": grid,
           "defs": {"inkstab": inkstab.DEFS, "masked": MASKED_DEFS},
           "extraction": {k: env[k] for k in EXTRACTION_KEYS},
           "mapping": a.mapping, **res, "masks_sha256": {s["set"]: masks_sha}}
    write_atomic(a.out, record_text(out))
    print(f"[score] -> {a.out}", file=sys.stderr)
    return 0


def cmd_a9_run(a):
    """The registered A9 pass (A9.5 step 6). Every check runs before the first extraction."""
    try:
        registration_guard(a.public_repo, ROOT)
    except GuardError as e:
        raise SystemExit(str(e))
    cells = a9_cells(ROOT)
    if len(cells) != A9_N_CLIPS:
        raise SystemExit(f"expected {A9_N_CLIPS} primary idle and burst clips, found {len(cells)}")
    ids = {c["public_id"] for c in cells}
    gate, gate_device = read_gate(ROOT)
    if set(gate) != ids:
        raise SystemExit(f"{GATE_CSV}: its cell ids are not the {len(ids)} A9 cells")
    geometry = read_geometry(ROOT)
    if len(geometry) != len(ids) or {r["cell_id"] for r in geometry} != ids:
        raise SystemExit(f"{GEOM_CSV}: its cell ids are not the gate's {len(ids)} A9 cells")
    mappings = choose_mappings(geometry)
    missing = sorted({c["engine"] for c in cells} - set(mappings))
    if missing:
        raise SystemExit(f"{GEOM_CSV}: no mapping for engine(s) {missing}")
    try:
        loaded = {name: read_masks(ROOT / path) for name, path in MASK_FILES.items()}
    except (OSError, ValueError) as e:
        raise SystemExit(str(e))
    sets = {name: doc for name, (doc, _sha) in loaded.items()}
    shas = {name: sha for name, (_doc, sha) in loaded.items()}
    check_mask_sets(cells, sets, ROOT)
    device = inkstab._device()
    if device != gate_device:
        raise SystemExit(f"device is {device!r} but the gate ran on {gate_device!r}: the whole-frame values "
                         "cannot match the gate's here")
    env = environment(device, gate_device)
    print(json.dumps({"mappings": mappings, "masks_sha256": shas, "env": env}, indent=1),
          file=sys.stderr, flush=True)
    run_a9(ROOT, cells, device, env, gate, mappings, sets, shas)
    done = sum(record_state(ROOT / MASKS_OUT / f"{c['cell_id']}.json",
                            record_expectations(c, env, shas, mappings[c["engine"]], gate[c["public_id"]]))
               == "done" for c in cells)
    print(f"[a9-run] {done} of {len(cells)} clips written to {MASKS_OUT}/", file=sys.stderr)
    return 0 if done == len(cells) else 1


def _positive_int(text):
    try:
        v = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number of pixels") from None
    if v <= 0:
        raise argparse.ArgumentTypeError(f"margin {v} must be a positive number of pixels")
    return v


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate", help="reproduction gate, before any mask exists")
    g.add_argument("--first", type=int, help="only the first N clips in public-id order (timing run)")
    g.add_argument("--expect-device", default="mps",
                   help="device the released values were computed on (default mps, per the run logs)")
    g.add_argument("--redo", action="store_true", help="re-score clips that already have a part")
    s = sub.add_parser("score", help="whole-frame and masked drift for any clip, masks file and row")
    s.add_argument("clip")
    s.add_argument("--masks", required=True, help="a stilldrawn-allowed-regions/1 file")
    s.add_argument("--row", required=True, help="row id, <panel>_<motion>")
    s.add_argument("--mapping", choices=MAPPINGS, default="stretch")
    s.add_argument("--margins", type=_positive_int, nargs="+", default=list(MARGINS))
    s.add_argument("--out", required=True)
    s.add_argument("--public-repo", help="checkout of the public repo (needed only for an A9 clip)")
    r = sub.add_parser("a9-run", help="the registered A9 pass (refuses until A9 is public)")
    r.add_argument("--public-repo", required=True, help="checkout of the public repo whose origin/main is checked")
    return ap


def main(argv=None):
    a = build_parser().parse_args(argv)
    return {"gate": cmd_gate, "score": cmd_score, "a9-run": cmd_a9_run}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
