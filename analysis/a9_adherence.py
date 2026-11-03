#!/usr/bin/env python3
"""A9 Test 1: on burst and camera-push cells, do the steadiest engines most often
fail to do the requested motion?

*** EXPLORATORY AND POST-HOC (amendment A9). Every number here is labelled so. ***

    python analysis/a9_adherence.py                  # the registered analysis
    python analysis/a9_adherence.py slim --rater AARON --study burst [--exported-on YYYY-MM-DD]
                                                     # record one rater's blindpanel session

Inputs: `analysis/out/results_table.json` (released line drift), `runs/metrics-motion/`
(released motion), and in `analysis/adherence/`: the slim ratings files
`ratings-<burst|push>-<AARON|R7>.json` (written only by `slim`, from `blindpanel export`
output and the stored session row, never from `report`, which drops flagged sessions;
flags never exclude a session), `<study>/study.lock.json`, `a9-config.json`
and, once R7's deadline has passed without both exports, `r7-status.json`.

Slim file (schema stilldrawn-a9-ratings/1): schema, rater, study (burst|push), instrument,
question, text_sha256 (the study's lock hash), received_day (the day blindpanel stored,
read from the stored row), registered_day and deadline (from a9-config.json; the deadline
only for R7, else null), within_deadline (received_day <= deadline, inclusive; null without
a deadline), flags, delivery, export_sha256, n (55) and ratings: [{position, clip, score}],
listed in the order the rater saw the clips (position 1..55), clip = public cell id.

`slim` reads two blindpanel files: the export (`ratings-V0001.json`, no day, no delivery) and
the stored session row (`.data/<RATER>/a9-<study>.jsonl`, which holds the day, the delivery and
the order as opaque codes). The codes are mapped to cell ids through `prepare.py` (the study
seed), and the export's clip order must equal the stored order. `--force` keeps the old file
as `<name>.prev` and refuses if a `.prev` already exists: nothing is ever discarded.

Set-aside sessions. The sha256 of every session that is not analysed (a rater's extra sessions)
and of every rating file replaced after it was first written is published in
`analysis/adherence/sessions.sha256`, one `<sha256>  <description>` line each. `slim --force`
appends the replaced file's hash. `set-aside --study S --rater R --store <store dir>` keeps the
first complete session in the store, moves every other row, byte for byte, to
`raw/<study>-<RATER>/extra-sessions.jsonl` (append; `raw/` never ships) and appends one hash line
per moved row (`extra session <study>-<RATER> row <k>`), so `slim` then sees one session. Stored rows
carry no rater, so the store folder's name must equal `--rater` (default layout `.data/<RATER>`); a
row for another study is refused, not moved; and the command refuses a store file modified in the
last 120 seconds. Stop the blindpanel server before running it.

Arithmetic. Spearman's rho is computed on exact midranks (twice the centred midrank is an
integer, so sums and products are exact integers: the same values as fractions.Fraction would
give); the exact test compares the integer cross-sums, so "rho_pi <= rho_obs" has no tolerance
and no platform dependence. The within-row check is the one place a tolerance (1e-12) remains,
on a mean of square roots. Every float written out is rounded to 12 significant digits.
Outputs are written atomically, as UTF-8 with LF line endings, and the figure is drawn without
pyplot under bundled matplotlib defaults; the JSON records the python, numpy, matplotlib and
Pillow versions it ran under and the sha256 of every input (the results table and the motion
files as canonical JSON of the values used, keyed by public id, so the release rename cannot move them).
"""
import argparse
import datetime
import hashlib
import importlib.util
import io
import itertools
import json
import math
import os
import platform
import re
import statistics
import sys
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261030
N_WITHIN = 10_000
Z95 = 1.959963984540054
ALPHA = 0.05
MISS_MAX, SENS_MISS_MAX = 2, 3
LEAGUE_ORDER = ("wan22", "gen4_turbo", "ltx23", "gen4.5", "h3-fal")      # frozen league order, never a rank
ENGINE_NAMES = {"wan22": "Wan 2.2", "gen4_turbo": "Gen-4 Turbo", "ltx23": "LTX-2.3",
                "gen4.5": "Gen-4.5", "h3-fal": "MiniMax H3"}
STUDIES = {"burst": "BURST", "push": "CAMPUSH"}        # study -> results-table motion class
RATERS = ("AARON", "R7")
N_PER_STUDY, N_PER_ENGINE_STUDY = 55, 11
DEADLINE_DAYS = 14
SLIM_SCHEMA = "stilldrawn-a9-ratings/1"
SESSIONS_SHA256 = "sessions.sha256"
CONFIG_SCHEMA = "stilldrawn-a9-config/1"
INSTRUMENT = "A9"
LABEL_TWO = "two raters"
LABEL_PENDING = "author-rated; second rater pending"
LABEL_AUTHOR = "author-rated"
VERDICT_PENDING = "no verdict (second rater pending)"
VERDICT_STATUS = {LABEL_PENDING: VERDICT_PENDING, LABEL_TWO: "final",
                  LABEL_AUTHOR: "no verdict (author-rated fallback)"}
VERDICT_NOT_TESTED = "not tested by two raters"
PROVISIONAL = "provisional (AARON only)"        # labels AARON's rho and p while R7 is pending (A9.3)
DECLARATION = {
    True: "R7 is declared blind to engine styles: R7, a new rater who has never rated for StillDrawn, had not "
          "seen its explorer, release, clips or results as of 3 Nov 2026 (Gate A, revised).",
    False: "R7 is declared NOT blind to engine styles: R7, a new rater who has never rated for StillDrawn, had "
           "seen its explorer, release, clips or results as of 3 Nov 2026 (Gate A, revised).",
    None: "R7's exposure to engine styles has not been declared.",
}
PERMS = list(itertools.permutations(range(5)))


def public_id(cell_id):
    """Public form of a cell or panel id (the creator-IP panel's private id differs
    from cip-act-tank-1 only in its three-letter prefix)."""
    return re.sub(r"^[a-z]{3}-act-tank-1", "cip-act-tank-1", cell_id)


# --------------------------------------------------------- files, json, dates
def _typename(types):
    names = {str: "a string", int: "an integer", float: "a number", bool: "true or false", dict: "an object",
             list: "a list", type(None): "null"}
    return " or ".join(names.get(t, t.__name__) for t in (types if isinstance(types, tuple) else (types,)))


def _is(v, types):
    for t in (types if isinstance(types, tuple) else (types,)):
        if t is type(None):
            ok = v is None
        elif t is bool:
            ok = isinstance(v, bool)
        elif t is int:
            ok = type(v) is int
        elif t is float:
            ok = isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        else:
            ok = isinstance(v, t)
        if ok:
            return True
    return False


def _need(obj, fields, where):
    """SystemExit naming `where` and the field unless obj has every field with the right type."""
    for name, types in fields.items():
        if name not in obj or not _is(obj[name], types):
            raise SystemExit(f"{where}: field {name!r} missing or not {_typename(types)}")
    return obj


def _refuse_constant(token):
    raise ValueError(f"non-finite number {token}")


def _parse(text, what, name):
    try:
        return json.loads(text, parse_constant=_refuse_constant)
    except ValueError as e:
        raise SystemExit(f"{what}: {name} is not valid JSON ({e})")


def _read(path, what):
    path = Path(path)
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"{what}: {path.name} not found ({path})")
    except (OSError, UnicodeDecodeError) as e:
        raise SystemExit(f"{what}: cannot read {path.name} ({e})")


def _load_json(path, what, fields=None, top=dict):
    """Read and parse one JSON file; SystemExit names the file (and the field) on any problem."""
    d = _parse(_read(path, what), what, Path(path).name)
    if not isinstance(d, top):
        raise SystemExit(f"{what}: {Path(path).name} must be a JSON {'object' if top is dict else 'list'}")
    if fields:
        _need(d, fields, f"{what} ({Path(path).name})")
    return d


def _load_jsonl(path, what):
    name = Path(path).name
    return [_parse(line, what, f"{name} line {k}")
            for k, line in enumerate(_read(path, what).splitlines(), 1) if line.strip()]


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _atomic_write(path, data):
    """Write `data` (UTF-8 text with LF line ends, or bytes) to a temporary file, then rename it into place."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        if isinstance(data, str):
            tmp.write_text(data, encoding="utf-8", newline="\n")
        else:
            tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _day(v):
    """True for a real calendar date written YYYY-MM-DD in ASCII digits."""
    if not isinstance(v, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", v):
        return False
    try:
        datetime.date.fromisoformat(v)
    except ValueError:
        return False
    return True


def _r12(x):
    """A float to 12 significant digits (None passes through)."""
    return None if x is None else float(f"{x:.12g}")


def _round_floats(o):
    if isinstance(o, float):
        return _r12(o)
    if isinstance(o, dict):
        return {k: _round_floats(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round_floats(v) for v in o]
    return o


# --------------------------------------------------------------------- stats
def midranks(a):
    """Exact midranks (Fractions); ties are values that compare equal."""
    a = list(a)
    order = sorted(range(len(a)), key=lambda i: a[i])
    ranks, i = [None] * len(a), 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and a[order[j + 1]] == a[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = Fraction(i + j + 2, 2)
        i = j + 1
    return ranks


def _centred2(ranks):
    """Twice the centred midranks: integers (the mean midrank is (n + 1) / 2)."""
    n = len(ranks)
    return [int(2 * r - (n + 1)) for r in ranks]


def _rho_parts(x, y):
    ux, uy = _centred2(midranks(x)), _centred2(midranks(y))
    return ux, uy, sum(a * a for a in ux), sum(b * b for b in uy)


def spearman(x, y):
    """Spearman rho on exact midranks; None when either side is constant."""
    if len(x) < 2:
        return None
    ux, uy, sxx, syy = _rho_parts(x, y)
    if sxx == 0 or syy == 0:
        return None
    return sum(a * b for a, b in zip(ux, uy)) / math.sqrt(sxx * syy)


def exact_one_sided_p(S, m):
    """(rho, p): p = #{permutations pi of m: rho(S, m_pi) <= rho_obs} / 120 (prediction rho < 0).
    S and every permuted m share their sums of squares, so rho_pi <= rho_obs is exactly
    cross-sum_pi <= cross-sum_obs, compared as integers."""
    ux, uy, sxx, syy = _rho_parts(S, m)
    if sxx == 0 or syy == 0:
        return None, None
    obs = sum(a * b for a, b in zip(ux, uy))
    hits = sum(sum(ux[i] * uy[p[i]] for i in range(5)) <= obs for p in PERMS)
    return obs / math.sqrt(sxx * syy), hits / len(PERMS)


def attainable_p_no_ties():
    """[rho, p] for every attainable rho with five untied engines (what A9 prints)."""
    ux = _centred2(midranks(range(1, 6)))
    sxx = sum(a * a for a in ux)
    cross = [sum(ux[i] * ux[p[i]] for i in range(5)) for p in PERMS]
    return [[c / sxx, sum(d <= c for d in cross) / len(cross)] for c in sorted(set(cross))]


def wilson(x, n, z=Z95):
    if n == 0:
        return None
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [c - h, c + h]


def weighted_kappa(x, y, k=5):
    """Quadratic-weighted Cohen's kappa for two raters on a 1..k scale (exact integer arithmetic)."""
    O = [[0] * k for _ in range(k)]
    for a, b in zip(x, y):
        O[a - 1][b - 1] += 1
    n = sum(map(sum, O))
    rows, cols = [sum(r) for r in O], [sum(O[i][j] for i in range(k)) for j in range(k)]
    num = sum((i - j) ** 2 * O[i][j] for i in range(k) for j in range(k))
    den = sum((i - j) ** 2 * rows[i] * cols[j] for i in range(k) for j in range(k))
    return None if den == 0 else float(1 - Fraction(num * n, den))


def auc(nonmiss, miss):
    """P(motion of a non-miss clip > motion of a miss clip), ties 1/2."""
    if not nonmiss or not miss:
        return None
    tot = sum(1.0 if a > b else 0.5 if a == b else 0.0 for a in nonmiss for b in miss)
    return tot / (len(nonmiss) * len(miss))


def auc_reading(a):
    if a is None:
        return "undefined (no misses or no non-misses in this class)"
    if a >= 0.70:
        return "corroborates: the misses are under-animated"
    if a <= 0.60:
        return "the misses are not under-animation"
    return "inconclusive (between 0.60 and 0.70)"


# --------------------------------------------------------------------- inputs
def load_cells(root):
    """The primary burst and camera-push cells: public id -> engine, panel, study, drift.
    Refuses public-id collisions and any design other than 55 cells per study, 11 per engine
    per study, and the five engines once in each of the 22 (panel, study) rows."""
    rows = _load_json(Path(root) / "analysis" / "out" / "results_table.json", "results table", top=list)
    by_motion = {v: k for k, v in STUDIES.items()}
    cells = {}
    for k, r in enumerate(rows):
        where = f"results_table.json row {k}"
        if not isinstance(r, dict):
            raise SystemExit(f"{where}: not an object")
        _need(r, {"cell_id": str, "motion": str}, where)
        if r.get("flint_pair") or r["motion"] not in by_motion:
            continue
        _need(r, {"engine": str, "panel_id": str, "line_chamfer_mean_px": float}, where)
        pid = public_id(r["cell_id"])
        if pid in cells:
            raise SystemExit(f"{where}: public id {pid} appears twice (a private/public id collision)")
        if r["engine"] not in LEAGUE_ORDER:
            raise SystemExit(f"{where}: unknown engine {r['engine']!r} for {pid}")
        cells[pid] = {"engine": r["engine"], "panel": public_id(r["panel_id"]), "study": by_motion[r["motion"]],
                      "drift": float(r["line_chamfer_mean_px"])}
    for study in STUDIES:
        mine = [c for c in cells.values() if c["study"] == study]
        if len(mine) != N_PER_STUDY:
            raise SystemExit(f"expected {N_PER_STUDY} {study} cells (primary); found {len(mine)}")
        counts = Counter(c["engine"] for c in mine)
        if any(counts[e] != N_PER_ENGINE_STUDY for e in LEAGUE_ORDER):
            raise SystemExit(f"expected {N_PER_ENGINE_STUDY} per engine in the {study} cells; found {dict(counts)}")
    by_row = {}
    for c in cells.values():
        by_row.setdefault((c["panel"], c["study"]), []).append(c["engine"])
    bad = {k: sorted(v) for k, v in by_row.items() if sorted(v) != sorted(LEAGUE_ORDER)}
    if len(by_row) != 2 * N_PER_ENGINE_STUDY or bad:
        raise SystemExit(f"expected {2 * N_PER_ENGINE_STUDY} (panel, study) rows with the five engines once each; "
                         f"found {len(by_row)} rows, odd rows {dict(list(bad.items())[:3])}")
    return cells


def load_motion(root, ids):
    out, seen = {}, {}
    for p in sorted((Path(root) / "runs" / "metrics-motion").glob("*.json")):
        pid = public_id(p.stem)
        if pid not in ids:
            continue
        if pid in seen:
            raise SystemExit(f"two motion files map to public id {pid}: {seen[pid]} and {p.name}")
        seen[pid] = p.name
        d = _load_json(p, "motion file", {"motion": dict})
        out[pid] = float(_need(d["motion"], {"headline_median_norm": float}, f"{p.name} motion")["headline_median_norm"])
    missing = sorted(set(ids) - set(out))
    if missing:
        raise SystemExit(f"no motion record for {len(missing)} cells, e.g. {missing[:3]}")
    return out


def load_config(adh):
    c = _load_json(Path(adh) / "a9-config.json", "config", {"schema": str})
    if c["schema"] != CONFIG_SCHEMA:
        raise SystemExit(f"a9-config.json: schema must be {CONFIG_SCHEMA}")
    for key in ("registered_on", "r7_deadline"):
        v = c.get(key)
        if v is not None and not _day(v):
            raise SystemExit(f"a9-config.json: {key} {v!r} is not a valid YYYY-MM-DD date")
    if not _is(c.get("r7_blind_to_engine_styles"), (bool, type(None))):
        raise SystemExit("a9-config.json: field 'r7_blind_to_engine_styles' must be true, false or null")
    if c.get("r7_deadline") is not None:
        if c.get("registered_on") is None:
            raise SystemExit("a9-config.json: r7_deadline is set but registered_on is null")
        want = (datetime.date.fromisoformat(c["registered_on"]) + datetime.timedelta(days=DEADLINE_DAYS)).isoformat()
        if c["r7_deadline"] != want:
            raise SystemExit(f"a9-config.json: r7_deadline {c['r7_deadline']} must be registered_on + "
                             f"{DEADLINE_DAYS} days ({want})")
    status_file = Path(adh) / "r7-status.json"
    c["r7_status"] = None
    c["r7_deadline_passed"] = False
    if status_file.exists():
        s = _load_json(status_file, "r7 status", {"deadline_passed": bool, "recorded_on": str})
        if not _day(s["recorded_on"]):
            raise SystemExit(f"r7-status.json: recorded_on {s['recorded_on']!r} is not a valid YYYY-MM-DD date")
        if s["deadline_passed"]:
            if c.get("r7_deadline") is None:
                raise SystemExit("r7-status.json says deadline_passed but a9-config.json has no r7_deadline")
            if s["recorded_on"] <= c["r7_deadline"]:
                raise SystemExit(f"r7-status.json: recorded_on {s['recorded_on']} must be after r7_deadline "
                                 f"{c['r7_deadline']} when deadline_passed is true")
        c["r7_status"], c["r7_deadline_passed"] = s, s["deadline_passed"]
    return c


def present_studies(adh, rater):
    return [s for s in STUDIES if (Path(adh) / f"ratings-{s}-{rater}.json").exists()]


SLIM_FIELDS = {"schema": str, "rater": str, "study": str, "instrument": str, "question": str, "text_sha256": str,
               "received_day": str, "registered_day": str, "deadline": (str, type(None)),
               "within_deadline": (bool, type(None)), "flags": list, "delivery": dict, "export_sha256": str,
               "n": int, "ratings": list}


def load_ratings(adh, rater, cells, config):
    """({public id: score} over both studies, {study: file metadata}), or None when neither of the
    rater's files exists. Exactly one of the two files is an error. Validates every file: schema,
    rater, instrument, no duplicate clips, exactly the study's clips, integer scores 1-5, positions
    1..n in the order listed, the wording hash against study.lock.json, and the registration and
    deadline fields against a9-config.json."""
    present = present_studies(adh, rater)
    if not present:
        return None
    if len(present) < len(STUDIES):
        missing = [s for s in STUDIES if s not in present]
        raise SystemExit(f"{rater}'s ratings are partial: {', '.join(missing)} missing "
                         "(both studies' files are needed)")
    scores, meta = {}, {}
    for study in STUDIES:
        f = Path(adh) / f"ratings-{study}-{rater}.json"
        d = _load_json(f, f"{rater} {study} ratings", SLIM_FIELDS)
        if d["schema"] != SLIM_SCHEMA or d["study"] != study:
            raise SystemExit(f"{f.name}: not a {SLIM_SCHEMA} file for the {study} study")
        if d["rater"] != rater:
            raise SystemExit(f"{f.name}: its rater is {d['rater']!r}, expected {rater!r}")
        if d["instrument"] != INSTRUMENT:
            raise SystemExit(f"{f.name}: its instrument is {d['instrument']!r}, expected {INSTRUMENT!r}")
        for k, r in enumerate(d["ratings"]):
            if not isinstance(r, dict):
                raise SystemExit(f"{f.name}: ratings[{k}] is not an object")
            _need(r, {"clip": str, "position": int}, f"{f.name} ratings[{k}]")
            if "score" not in r:
                raise SystemExit(f"{f.name} ratings[{k}]: field 'score' missing or not an integer 1-5")
        clips = [r["clip"] for r in d["ratings"]]
        dup = sorted(c for c, n in Counter(clips).items() if n > 1)
        if dup:
            raise SystemExit(f"{f.name}: duplicate clip(s) {dup}")
        want = sorted(p for p, c in cells.items() if c["study"] == study)
        if sorted(clips) != want:
            raise SystemExit(f"{f.name}: its clips are not the {len(want)} {study} cells")
        for r in d["ratings"]:
            s = r["score"]
            if type(s) is not int or not 1 <= s <= 5:
                raise SystemExit(f"{f.name}: clip {r['clip']} has score {s!r}, not an integer 1-5")
        if [r["position"] for r in d["ratings"]] != list(range(1, len(want) + 1)):
            raise SystemExit(f"{f.name}: positions are not 1..{len(want)} in the order listed (the order seen)")
        if d["n"] != len(want):
            raise SystemExit(f"{f.name}: n is {d['n']!r}, expected {len(want)}")
        lock = _load_json(Path(adh) / study / "study.lock.json", "study lock", {"text_sha256": str})
        if d["text_sha256"] != lock["text_sha256"]:
            raise SystemExit(f"{f.name}: text_sha256 differs from {study}/study.lock.json")
        registered = config.get("registered_on")
        if not _day(registered):
            raise SystemExit(f"{f.name}: ratings exist but a9-config.json has no registered_on")
        if d["registered_day"] != registered:
            raise SystemExit(f"{f.name}: registered_day {d['registered_day']!r} differs from a9-config.json ({registered})")
        day = d["received_day"]
        if not _day(day):
            raise SystemExit(f"{f.name}: received_day {day!r} is not YYYY-MM-DD")
        if day <= registered:
            raise SystemExit(f"{f.name}: received_day {day} is not after registration ({registered})")
        deadline = None
        if rater == "R7":
            deadline = config.get("r7_deadline")
            if not _day(deadline):
                raise SystemExit(f"{f.name}: R7's ratings are present but a9-config.json has no valid r7_deadline")
        if d["deadline"] != deadline:
            raise SystemExit(f"{f.name}: deadline {d['deadline']!r} differs from a9-config.json ({deadline!r})")
        if d["within_deadline"] != ((day <= deadline) if deadline else None):
            raise SystemExit(f"{f.name}: within_deadline {d['within_deadline']!r} does not match "
                             f"received_day {day} and deadline {deadline!r}")
        scores.update({r["clip"]: r["score"] for r in d["ratings"]})
        meta[study] = {k: d[k] for k in ("instrument", "question", "text_sha256", "received_day", "within_deadline",
                                         "export_sha256", "flags", "delivery", "n")}
    return scores, meta


def _canonical_sha256(values):
    """sha256 of canonical JSON ({public id: float}, sorted keys, no spaces)."""
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False)
                          .encode("utf-8")).hexdigest()


def input_hashes(root, cells, motion):
    """sha256 of every input. The already-public files (config, status, locks, ratings) are
    hashed byte for byte. The results table and the motion files are not: the release build renames
    the private panel prefix in their text and in the motion file names, so their raw bytes differ
    between the private tree and the release. They are hashed as canonical JSON of the values the
    analysis uses, keyed by public cell id."""
    root = Path(root)
    rels = ["analysis/adherence/a9-config.json", "analysis/adherence/r7-status.json",
            *(f"analysis/adherence/{s}/study.lock.json" for s in STUDIES),
            *(f"analysis/adherence/ratings-{s}-{r}.json" for r in RATERS for s in STUDIES)]
    files = {rel: _sha256(root / rel) for rel in sorted(rels) if (root / rel).exists()}
    drift = {p: c["drift"] for p, c in cells.items()}
    return {"files": files,
            "extracted": {"results_table.line_chamfer_mean_px": {"n": len(drift), "sha256": _canonical_sha256(drift)},
                          "motion.headline_median_norm": {"n": len(motion), "sha256": _canonical_sha256(motion)}}}


def environment():
    import matplotlib
    import PIL
    return {"python": platform.python_version(), "numpy": np.__version__,
            "matplotlib": matplotlib.__version__, "pillow": PIL.__version__}


# ------------------------------------------------------------------ analysis
def steadiness(cells):
    """S_e: the engine's median released line_chamfer_mean_px over its 22 cells."""
    return {e: float(statistics.median(c["drift"] for c in cells.values() if c["engine"] == e))
            for e in LEAGUE_ORDER}


def miss_rate_test(cells, S, scores, miss_max):
    """Miss rates per engine and the registered exact test of rho(S, m) < 0."""
    ids = sorted(cells)
    per_engine = {}
    for e in LEAGUE_ORDER:
        mine = [p for p in ids if cells[p]["engine"] == e]
        k = sum(scores[p] <= miss_max for p in mine)
        per_engine[e] = {"n": len(mine), "misses": k, "miss_rate": k / len(mine), "wilson95": wilson(k, len(mine))}
    rho, p = exact_one_sided_p([S[e] for e in LEAGUE_ORDER], [per_engine[e]["miss_rate"] for e in LEAGUE_ORDER])
    return {"miss": f"score <= {miss_max}", "per_engine": per_engine, "rho": rho, "p_one_sided": p,
            "p_le_0_05": p is not None and p <= ALPHA}


def by_class(cells, scores):
    out = {}
    for e in LEAGUE_ORDER:
        out[e] = {}
        for study in STUDIES:
            mine = [p for p in sorted(cells) if cells[p]["engine"] == e and cells[p]["study"] == study]
            k = sum(scores[p] <= MISS_MAX for p in mine)
            out[e][study] = {"n": len(mine), "misses": k, "miss_rate": k / len(mine), "wilson95": wilson(k, len(mine))}
    return out


def within_row(cells, scores, draws=N_WITHIN, seed=SEED):
    """Mean over the panel-class rows of Spearman(drift, score) across the five engines;
    null: scores permuted within rows. One-sided p for a positive mean, (k + 1) / (draws + 1).
    Rows where rho is undefined (constant drift or constant scores) drop out of the observed and
    every null mean; constancy is permutation-invariant, so the same rows drop out every time.
    Only rows with a defined rho draw: each draw takes one rng.permutation(n) per defined row, in
    sorted row order; an undefined row consumes nothing from the stream."""
    rows = {}
    for p in sorted(cells):
        c = cells[p]
        rows.setdefault((c["panel"], c["study"]), []).append((LEAGUE_ORDER.index(c["engine"]), c["drift"], scores[p]))
    keys = sorted(rows)
    prepared = []                                     # per row: (n, ux, uy, denominator) or None when undefined
    for k in keys:
        ordered = sorted(rows[k])
        ux, uy, sxx, syy = _rho_parts([d for _, d, _ in ordered], [s for _, _, s in ordered])
        prepared.append((len(ordered), ux, uy, math.sqrt(sxx * syy)) if sxx and syy else None)
    defined = [r for r in prepared if r is not None]
    obs = (math.fsum(sum(a * b for a, b in zip(ux, uy)) / den for _, ux, uy, den in defined) / len(defined)
           if defined else None)
    res = {"n_rows": len(keys), "n_rows_defined": len(defined), "mean_rho": obs, "draws": draws, "seed": seed,
           "p_one_sided": None}
    if obs is None:
        return res
    rng = np.random.default_rng(seed)
    k = 0
    for _ in range(draws):
        rhos = []
        for row in prepared:
            if row is None:
                continue
            n, ux, uy, den = row
            idx = rng.permutation(n).tolist()
            rhos.append(sum(ux[i] * uy[idx[i]] for i in range(n)) / den)
        k += math.fsum(rhos) / len(rhos) >= obs - 1e-12
    res["p_one_sided"] = (k + 1) / (draws + 1)
    return res


def motion_check(cells, scores, motion):
    out = {}
    for study in STUDIES:
        ids = [p for p in sorted(cells) if cells[p]["study"] == study]
        miss = [motion[p] for p in ids if scores[p] <= MISS_MAX]
        nonmiss = [motion[p] for p in ids if scores[p] > MISS_MAX]
        a = auc(nonmiss, miss)
        out[study] = {"n_miss": len(miss), "n_nonmiss": len(nonmiss), "auc": a, "reading": auc_reading(a)}
    return out


def analyse_rater(cells, S, scores, motion, draws):
    primary = miss_rate_test(cells, S, scores, MISS_MAX)
    eng_motion = {e: float(statistics.median(motion[p] for p in cells if cells[p]["engine"] == e))
                  for e in LEAGUE_ORDER}
    return {
        "primary": primary,
        "sensitivity_miss_le_3": miss_rate_test(cells, S, scores, SENS_MISS_MAX),
        "by_engine_and_class": by_class(cells, scores),
        "within_row": within_row(cells, scores, draws),
        "motion_auc": motion_check(cells, scores, motion),
        "engine_level_motion_vs_miss_rate": {
            "rho": spearman([eng_motion[e] for e in LEAGUE_ORDER],
                            [primary["per_engine"][e]["miss_rate"] for e in LEAGUE_ORDER]),
            "note": "non-evidential: the engine ordering of motion was seen before registration"},
    }


def reporting_status(r7, config, r7_note=None, r7_late=None):
    """(label, basis) for Test 1 under the registered reporting rule. `r7_note` (one of R7's two
    files present) keeps the state it would have had without R7 and says so; `r7_late` names the
    study of that one file when its received_day is after the deadline, which is the fallback
    even without r7-status.json (A9.3)."""
    if r7 is not None:
        deadline = config.get("r7_deadline")
        if not deadline:
            raise SystemExit("R7's ratings are present but a9-config.json has no r7_deadline")
        late = [s for s, m in r7[1].items() if m["received_day"] > deadline]
        if not late:
            return LABEL_TWO, "both raters exported both studies by the deadline"
        return LABEL_AUTHOR, f"registered fallback: R7's {', '.join(late)} export was received after the deadline ({deadline})"
    extra = f"; {r7_note}" if r7_note else ""
    if r7_late:
        return LABEL_AUTHOR, (f"registered fallback: R7's {r7_late} export was received after the deadline "
                              f"({config.get('r7_deadline')})" + extra)
    if config.get("r7_deadline_passed"):
        return LABEL_AUTHOR, "registered fallback: R7 did not export both studies by the deadline" + extra
    return LABEL_PENDING, "R7's export has not landed; AARON's statistic only" + extra


def lone_r7_late_study(adh, study, config):
    """The study name if R7's only file (for `study`) was received after r7_deadline, else None.
    Only received_day is read here; the file is not analysed (a partial pair never is)."""
    f = Path(adh) / f"ratings-{study}-R7.json"
    d = _load_json(f, f"R7 {study} ratings", {"received_day": str})
    if not _day(d["received_day"]):
        raise SystemExit(f"{f.name}: received_day {d['received_day']!r} is not YYYY-MM-DD")
    deadline = config.get("r7_deadline")
    if not _day(deadline):
        raise SystemExit(f"{f.name}: R7's ratings are present but a9-config.json has no valid r7_deadline")
    return study if d["received_day"] > deadline else None


def verdict(label, raters):
    """Registered rule: "Supported iff p <= 0.05 for both raters". The two-rater verdict exists only when
    both R7 study files are present and within the deadline. Without it (the author-rated fallback, or
    while R7 is pending) there is no verdict at all: AARON's rho and p are still reported, labelled
    "author-rated" or "provisional (AARON only)", and never as "supported"."""
    if label == LABEL_AUTHOR:
        return VERDICT_NOT_TESTED
    if label == LABEL_PENDING:
        return VERDICT_PENDING
    return "supported" if all(raters[r]["primary"]["p_le_0_05"] for r in RATERS) else "not supported"


# -------------------------------------------------------------------- output
def _fmt(v, nd=3):
    return "n/a" if v is None else f"{v:.{nd}f}"


def markdown(res):
    out = [f"# A9 Test 1: adherence ({res['label']})", "",
           f"Post-hoc (A9), exploratory. Status: **{res['label']}** ({res['basis']}).", "",
           f"**Verdict: {res['verdict']}.** Rule: {res['verdict_rule']}", "",
           f"Declaration: {res['r7_declaration']}", "",
           "Rows are in frozen-league order; there is no rank column. Miss = score <= 2 of 5.", ""]
    for rater, r in res["raters"].items():
        if r is None:
            continue
        pr = r["primary"]
        files = res["ratings_files"][rater]
        if rater == "R7":
            when = f"deadline {res['r7_deadline']}: " + (
                "in time" if all(files[s]["within_deadline"] for s in STUDIES) else "late")
        else:
            when = "deadline: none"
        out += [f"## {rater}", "",
                "Ratings received: " + ", ".join(f"{s} {files[s]['received_day']}" for s in STUDIES) + f" ({when}).", "",
                "| engine | steadiness S (median drift, px) | misses / clips | miss rate (Wilson 95%) |",
                "|---|---|---|---|"]
        for e in LEAGUE_ORDER:
            pe = pr["per_engine"][e]
            lo, hi = pe["wilson95"]
            out.append(f"| {ENGINE_NAMES[e]} | {_fmt(res['steadiness_px'][e])} | {pe['misses']} / {pe['n']} | "
                       f"{_fmt(pe['miss_rate'], 2)} ({_fmt(lo, 2)} to {_fmt(hi, 2)}) |")
        out += ["", "| engine | burst misses / n (Wilson 95%) | push misses / n (Wilson 95%) |", "|---|---|---|"]
        for e in LEAGUE_ORDER:
            cols = []
            for study in STUDIES:
                c = r["by_engine_and_class"][e][study]
                lo, hi = c["wilson95"]
                cols.append(f"{c['misses']} / {c['n']} ({_fmt(lo, 2)} to {_fmt(hi, 2)})")
            out.append(f"| {ENGINE_NAMES[e]} | {cols[0]} | {cols[1]} |")
        sens = r["sensitivity_miss_le_3"]
        wr = r["within_row"]
        tag = f"{r['provisional']}: " if r.get("provisional") else ""      # AARON's rho and p while R7 is pending
        out += ["", f"- {tag}Spearman rho(S, m) = {_fmt(pr['rho'])}; exact one-sided p = {_fmt(pr['p_one_sided'], 4)} "
                    f"(120 permutations).",
                f"- {tag}Sensitivity, miss = score <= 3: rho = {_fmt(sens['rho'])}, p = {_fmt(sens['p_one_sided'], 4)} "
                "(no verdict).",
                f"- {tag}Within-row check: mean rho(drift, score) over {wr['n_rows_defined']} of {wr['n_rows']} rows = "
                f"{_fmt(wr['mean_rho'])}; one-sided p = {_fmt(wr['p_one_sided'], 4)} ({wr['draws']} draws, seed "
                f"{wr['seed']}; no verdict)."]
        for study, m in r["motion_auc"].items():
            line = f"- Motion cross-check, {study}: AUC = {_fmt(m['auc'])} ({m['n_nonmiss']} non-misses, " \
                   f"{m['n_miss']} misses): {m['reading']}."
            out.append(f"- **{line[2:]}**" if m["auc"] is not None and m["auc"] <= 0.60 else line)
        em = r["engine_level_motion_vs_miss_rate"]
        out += [f"- Engine-level rho(motion, miss rate) = {_fmt(em['rho'])} ({em['note']}).", ""]
    if res["agreement_quadratic_kappa"] is not None:
        k = res["agreement_quadratic_kappa"]
        out += ["## Agreement", "", f"Quadratic-weighted kappa: burst {_fmt(k['burst'])}, push {_fmt(k['push'])}.", ""]
    out += ["## Attainable p-values (five engines, no ties)", "",
            ", ".join(f"rho {r:+.1f}: p {p:.4f}" for r, p in res["attainable_p_no_ties"] if r <= -0.5), ""]
    return "\n".join(out)


def figure_png(res):
    """The figure as PNG bytes: no pyplot, bundled matplotlib defaults (no user rc file), DejaVu Sans,
    no metadata, a fixed PNG compression level."""
    import matplotlib
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    rc = {k: v for k, v in matplotlib.rcParamsDefault.items() if k != "backend"}
    rc["font.family"] = ["DejaVu Sans"]
    with matplotlib.rc_context(rc):
        fig = Figure(figsize=(7, 3.6))
        FigureCanvasAgg(fig)
        ax = fig.subplots()
        present = [r for r in RATERS if res["raters"].get(r) is not None]
        for i, rater in enumerate(present):
            pe = res["raters"][rater]["primary"]["per_engine"]
            xs = np.arange(len(LEAGUE_ORDER)) + (i - (len(present) - 1) / 2) * 0.18
            ys = [pe[e]["miss_rate"] for e in LEAGUE_ORDER]
            err = [[y - pe[e]["wilson95"][0] for e, y in zip(LEAGUE_ORDER, ys)],
                   [pe[e]["wilson95"][1] - y for e, y in zip(LEAGUE_ORDER, ys)]]
            ax.errorbar(xs, ys, yerr=err, fmt="o" if i == 0 else "s", color="black" if i == 0 else "0.45",
                        capsize=3, label=rater)
        ax.set_xticks(range(len(LEAGUE_ORDER)), [ENGINE_NAMES[e] for e in LEAGUE_ORDER])
        ax.set_ylim(0, 1)
        ax.set_ylabel("miss rate (score <= 2)")
        ax.set_title(f"A9 Test 1, post-hoc ({res['label']})", fontsize=10)
        ax.legend(frameon=False)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, metadata={"Software": None}, pil_kwargs={"compress_level": 6})
    return buf.getvalue()


def run(root=ROOT, out_dir=None, draws=N_WITHIN):
    root = Path(root)
    adh = root / "analysis" / "adherence"
    out_dir = Path(out_dir) if out_dir else root / "analysis" / "out"
    cells = load_cells(root)
    config = load_config(adh)
    aaron = load_ratings(adh, "AARON", cells, config)   # checked first: no statistic exists without ratings
    if aaron is None:
        raise SystemExit("AARON's two ratings files are not both in analysis/adherence/: nothing to analyse")
    r7_present = present_studies(adh, "R7")
    r7_note, r7_late = None, None
    if len(r7_present) == 1:                            # one of R7's two files: pending (or fallback if late), says so
        r7_note = f"R7 partial: {next(s for s in STUDIES if s not in r7_present)} missing"
        r7_late = lone_r7_late_study(adh, r7_present[0], config)
        r7 = None
    else:
        r7 = load_ratings(adh, "R7", cells, config)
    motion = load_motion(root, cells)
    S = steadiness(cells)
    label, basis = reporting_status(r7, config, r7_note, r7_late)
    raters = {"AARON": analyse_rater(cells, S, aaron[0], motion, draws),
              "R7": analyse_rater(cells, S, r7[0], motion, draws) if r7 else None}
    # while R7 is pending AARON's numbers are provisional; the label travels with them
    raters["AARON"]["provisional"] = PROVISIONAL if label == LABEL_PENDING else None
    kappa = None
    if r7:
        kappa = {}
        for study in STUDIES:
            ids = sorted(p for p in cells if cells[p]["study"] == study)
            kappa[study] = weighted_kappa([aaron[0][p] for p in ids], [r7[0][p] for p in ids])
    blind = config.get("r7_blind_to_engine_styles")
    res = {
        "amendment": "A9", "test": "Test 1: adherence", "status": "exploratory, post-hoc",
        "label": label, "basis": basis, "verdict": verdict(label, raters), "verdict_status": VERDICT_STATUS[label],
        "verdict_rule": {
            LABEL_TWO: "supported iff the exact one-sided p <= 0.05 for both raters",
            LABEL_PENDING: "no verdict until R7's export lands by the deadline, when the two-rater rule applies; "
                           "AARON's rho and p below are provisional (AARON only)",
            LABEL_AUTHOR: "supported iff the exact one-sided p <= 0.05 for both raters; that verdict exists only "
                          "when both R7 study files are present and within the deadline, so there is none here "
                          "(the numbers below are author-rated, not a test)",
        }[label],
        "r7_blind_to_engine_styles": blind, "r7_declaration": DECLARATION[blind],
        "registered_on": config.get("registered_on"), "r7_deadline": config.get("r7_deadline"),
        "r7_status_file": config["r7_status"], "r7_partial_note": r7_note,
        "engine_order": list(LEAGUE_ORDER), "steadiness_px": S,
        "attainable_p_no_ties": attainable_p_no_ties(),
        "raters": raters,
        "agreement_quadratic_kappa": kappa,
        "ratings_files": {"AARON": aaron[1], "R7": r7[1] if r7 else None},
        "environment": environment(),
        "inputs": input_hashes(root, cells, motion),
    }
    res = _round_floats(res)
    texts = (json.dumps(res, indent=1, allow_nan=False) + "\n", markdown(res), figure_png(res))
    _atomic_write(out_dir / "a9_adherence.json", texts[0])
    _atomic_write(out_dir / "a9_adherence.md", texts[1])
    _atomic_write(out_dir / "figures" / "a9_adherence.png", texts[2])
    return res


# ---------------------------------------------------------------------- slim
def slim(export_path, store_path, rater, study, cells, config, lock, question=None, exported_on=None, code_map=None):
    """One rater's session for one study -> the slim record that ships.

    Reads two blindpanel files. `export_path`: the `blindpanel export` file ratings-V0001.json,
    {rater, instrument, ratings: [{clip, <question id>: n}, ...in the order seen], baseline, flags}
    (no day, no delivery). `store_path`: the file store's .jsonl, one stored row with order (opaque
    codes), answers, delivery, flags and received_day. The row supplies the day and delivery and is
    cross-checked against the export: same clips in the same order (`code_map` turns the stored
    codes into public cell ids; a stored order that already holds cell ids needs none), same scores,
    same flags, same study and instrument, and the same rater if the row records one. Registration
    day and deadline come from `config`, the wording hash from `lock`. `exported_on`, if given, is
    only a cross-check against the stored day."""
    if rater not in RATERS or study not in STUDIES:
        raise SystemExit(f"rater must be one of {RATERS} and study one of {tuple(STUDIES)}")
    if exported_on is not None and not _day(exported_on):
        raise SystemExit("--exported-on must be YYYY-MM-DD")
    question = question or study                      # blindpanel question ids are "burst" and "push"
    name = Path(export_path).name
    d = _load_json(export_path, "blindpanel export", {"instrument": str, "ratings": list})
    if d["instrument"] != INSTRUMENT or lock.get("instrument") != INSTRUMENT:
        raise SystemExit(f"{name}: instrument {d['instrument']!r} (lock {lock.get('instrument')!r}), "
                         f"expected {INSTRUMENT!r}")
    ratings = []
    for k, x in enumerate(d["ratings"]):
        if not isinstance(x, dict):
            raise SystemExit(f"{name}: ratings[{k}] is not an object")
        _need(x, {"clip": str}, f"{name} ratings[{k}]")
        s = x.get(question)
        if type(s) is not int or not 1 <= s <= 5:
            raise SystemExit(f"clip {x['clip']}: answer to {question!r} is {s!r}, not 1-5")
        ratings.append({"position": k + 1, "clip": x["clip"], "score": s})
    clips = [r["clip"] for r in ratings]
    dup = sorted(c for c, n in Counter(clips).items() if n > 1)
    if dup:
        raise SystemExit(f"{name}: duplicate clip(s) {dup}")
    want = sorted(p for p, c in cells.items() if c["study"] == study)
    if sorted(clips) != want:
        raise SystemExit(f"{name}: its clips are not the {len(want)} {study} cells (by public id)")
    rows = _load_jsonl(store_path, "stored session")
    if len(rows) != 1:
        raise SystemExit(f"{Path(store_path).name}: expected one stored session, found {len(rows)}: stop and ask "
                         "Aaron (flags never exclude a session; a second session needs a decision)")
    row = rows[0]
    where = f"stored session ({Path(store_path).name})"
    _need(row, {"study": str, "instrument": str, "order": dict, "answers": dict, "delivery": dict, "flags": list,
                "received_day": str}, where)
    _need(row["order"], {"clips": list}, f"{where} order")
    _need(row["answers"], {"clips": dict}, f"{where} answers")
    if row["study"] != f"a9-{study}" or row["instrument"] != INSTRUMENT:
        raise SystemExit(f"the stored row is for study {row['study']!r}, instrument {row['instrument']!r}; "
                         f"expected a9-{study}, {INSTRUMENT}")
    if "rater" in row and row["rater"] != rater:
        raise SystemExit(f"the stored row's rater is {row['rater']!r}, not {rater!r}")
    if list(row["flags"]) != list(d.get("flags", [])):
        raise SystemExit("the export and the stored row disagree on flags")
    codes = code_map or {}
    stored_clips = [public_id(codes.get(c, c)) for c in row["order"]["clips"]]
    if stored_clips != clips:
        raise SystemExit("the export's clip order differs from the stored row's order (the stored order holds "
                         "opaque codes: they are mapped to cell ids through prepare.py)")
    stored = []
    for c in row["order"]["clips"]:
        ans = row["answers"]["clips"].get(c)
        if not isinstance(ans, dict):
            raise SystemExit(f"{where}: no answers for clip code {c!r}")
        stored.append(ans.get(question))
    if stored != [r["score"] for r in ratings]:
        raise SystemExit("the export and the stored row differ in the scores")
    day = row["received_day"]
    if not _day(day):
        raise SystemExit(f"the stored row's received_day {day!r} is not YYYY-MM-DD")
    if exported_on is not None and exported_on != day:
        raise SystemExit(f"--exported-on {exported_on} differs from the stored day {day}")
    registered = config.get("registered_on")
    if not _day(registered):
        raise SystemExit("a9-config.json has no registered_on: fill it at registration before recording ratings")
    if day <= registered:
        raise SystemExit(f"rated on {day}, not after registration ({registered}): stop and tell Aaron")
    deadline = config.get("r7_deadline") if rater == "R7" else None
    if rater == "R7" and not _day(deadline):
        raise SystemExit("a9-config.json has no r7_deadline: fill it at registration before recording R7's ratings")
    _need(lock, {"text_sha256": str}, "study lock")
    return {"schema": SLIM_SCHEMA, "rater": rater, "study": study, "instrument": INSTRUMENT,
            "question": question, "text_sha256": lock["text_sha256"], "received_day": day,
            "registered_day": registered, "deadline": deadline,
            "within_deadline": (day <= deadline) if deadline else None,
            "flags": list(row["flags"]), "delivery": row["delivery"],
            "export_sha256": _sha256(export_path), "n": len(ratings), "ratings": ratings}


def replace_keeping_prev(out, prev, text):
    """Write `text` to a temporary name first, then move out -> prev and the temporary file -> out.
    A failed write leaves `out` untouched; a failed final rename puts the old file back."""
    out, prev = Path(out), Path(prev)
    new = out.with_name(f".{out.name}.new")
    try:
        new.write_text(text, encoding="utf-8", newline="\n")
        had_old = out.exists()
        if had_old:
            os.replace(out, prev)
        try:
            os.replace(new, out)
        except BaseException:
            if had_old:
                os.replace(prev, out)
            raise
    finally:
        if new.exists():
            new.unlink()


def _utc_day():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def append_sessions_lines(adh, entries):
    """Append `<sha256>  <description>` lines, one per (digest, description) pair, to
    analysis/adherence/sessions.sha256 in a single atomic write (UTF-8, LF)."""
    f = Path(adh) / SESSIONS_SHA256
    old = f.read_bytes().decode("utf-8") if f.exists() else ""
    if old and not old.endswith("\n"):
        old += "\n"
    _atomic_write(f, old + "".join(f"{digest}  {description}\n" for digest, description in entries))


def append_sessions_sha256(adh, digest, description):
    """Append one `<sha256>  <description>` line to analysis/adherence/sessions.sha256."""
    append_sessions_lines(adh, [(digest, description)])


def _session_complete(row, study):
    """A stored row is a complete session when it is for this study and holds an answer object for
    each of the study's 55 clips (blindpanel stores a row only when the rater submits)."""
    if not isinstance(row, dict) or row.get("study") != f"a9-{study}" or row.get("instrument") != INSTRUMENT:
        return False
    order, answers = row.get("order"), row.get("answers")
    if not isinstance(order, dict) or not isinstance(answers, dict) or not isinstance(order.get("clips"), list):
        return False
    given = answers.get("clips")
    return (len(order["clips"]) == N_PER_STUDY and isinstance(given, dict)
            and all(isinstance(given.get(c), dict) for c in order["clips"]))


STORE_QUIET_S = 120                 # set-aside refuses a store file written in the last two minutes


def set_aside(store_dir, study, rater, adh, today=None):
    """Keep the first complete session in `<store_dir>/a9-<study>.jsonl`; move every other row,
    byte for byte, to `<adh>/raw/<study>-<RATER>/extra-sessions.jsonl` (appended), drop them from the
    store, and record one line per moved row in sessions.sha256:
    `<sha256 of the row's bytes as stored>  extra session <study>-<RATER> row <k> (<day> UTC)`, where k
    counts the rows of extra-sessions.jsonl (1 is its first). The hashed bytes are the row exactly as
    the store held it, including its own line terminator if it had one; a final row stored without a
    terminator is hashed without one (the extra file then gets a separating LF after it). Returns the
    number of rows moved (0 changes nothing).

    blindpanel's stored rows carry no rater, so the folder is the rater: the store folder's name must
    equal `rater` (the default layout is `.data/<RATER>`). Refuses, changing nothing, when the folder
    name differs, when any row's `study` is not `a9-<study>`, when a row names another rater, when no
    session is complete, or when the store file was modified in the last 120 seconds (a blindpanel
    server may still be writing it: stop the server and retry). Every non-empty line that is not a
    complete session for this study (including one that parses to JSON null) is moved, never kept.
    Order of writes: the extra file, the hash lines, then the store, so a failure part-way never loses
    a row (a repeat shows as a duplicate)."""
    if rater not in RATERS or study not in STUDIES:
        raise SystemExit(f"rater must be one of {RATERS} and study one of {tuple(STUDIES)}")
    if Path(store_dir).resolve().name != rater:
        raise SystemExit(f"set-aside: the store folder is named {Path(store_dir).resolve().name!r}, not {rater!r}: "
                         "blindpanel's rows carry no rater, so the folder name is the rater "
                         f"(default layout .data/{rater}); check --rater and --store")
    store = Path(store_dir) / f"a9-{study}.jsonl"
    try:
        raw = store.read_bytes()
        age = time.time() - store.stat().st_mtime
    except FileNotFoundError:
        raise SystemExit(f"stored session: {store.name} not found in the store folder")
    if age < STORE_QUIET_S:
        raise SystemExit(f"set-aside: {store.name} was modified {max(age, 0):.0f} s ago (less than {STORE_QUIET_S} s): "
                         "a blindpanel server may still be writing it. Stop the blindpanel server and retry.")
    lines = raw.splitlines(keepends=True)
    blank = object()
    kept = None
    parsed = []
    for k, line in enumerate(lines, 1):
        if not line.strip():                            # only a truly empty / whitespace line is blank
            parsed.append(blank)
            continue
        try:
            row = _parse(line.decode("utf-8"), "stored session", f"{store.name} line {k}")
        except UnicodeDecodeError as e:
            raise SystemExit(f"stored session: {store.name} line {k} is not UTF-8 ({e})")
        parsed.append(row)
        if isinstance(row, dict):
            if row.get("study") != f"a9-{study}":
                raise SystemExit(f"{store.name} line {k}: the stored row is for study {row.get('study')!r}, not "
                                 f"a9-{study}: wrong store or wrong --study; nothing is moved")
            if "rater" in row and row["rater"] != rater:
                raise SystemExit(f"{store.name} line {k}: the stored row's rater is {row['rater']!r}, not {rater!r}")
        if kept is None and _session_complete(row, study):
            kept = k - 1
    if kept is None:
        raise SystemExit(f"{store.name}: no complete session for a9-{study} (55 clips answered): nothing is "
                         "kept, nothing is moved")
    stay = [l for k, l in enumerate(lines) if k == kept or parsed[k] is blank]
    move = [l for k, l in enumerate(lines) if k != kept and parsed[k] is not blank]
    if not move:
        return 0
    extra = Path(adh) / "raw" / f"{study}-{rater}" / "extra-sessions.jsonl"
    extra.parent.mkdir(parents=True, exist_ok=True)
    before = extra.read_bytes() if extra.exists() else b""
    first = sum(1 for l in before.splitlines() if l.strip()) + 1
    _atomic_write(extra, before + b"".join(l if l.endswith((b"\n", b"\r")) else l + b"\n" for l in move))
    day = today or _utc_day()
    append_sessions_lines(adh, [(hashlib.sha256(l).hexdigest(), f"extra session {study}-{rater} row {first + i} ({day} UTC)")
                                for i, l in enumerate(move)])
    _atomic_write(store, b"".join(stay))
    return len(move)


def codes_from_prepare(adh, study, cells):
    """{opaque code: public cell id} as the blindpanel build for `study` derives it (prepare.py)."""
    f = Path(adh) / "prepare.py"
    if not f.exists():
        raise SystemExit("prepare.py not found in analysis/adherence/: slim needs it to map blindpanel's opaque "
                         "clip codes to cell ids")
    spec = importlib.util.spec_from_file_location("a9_prepare", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        seed, opaque_code = mod.STUDIES[study]["seed"], mod.opaque_code
    except (AttributeError, KeyError) as e:
        raise SystemExit(f"prepare.py has no STUDIES[{study!r}]['seed'] or opaque_code ({e!r})")
    return {opaque_code(seed, "clip", p): p for p in sorted(p for p, c in cells.items() if c["study"] == study)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("slim", help="record one rater's blindpanel session for one study")
    s.add_argument("--rater", required=True, choices=RATERS)
    s.add_argument("--study", required=True, choices=tuple(STUDIES))
    s.add_argument("--export", help="ratings-V0001.json (default raw/<study>-<RATER>/ratings-V0001.json)")
    s.add_argument("--store", help="the stored session .jsonl (default .data/<RATER>/a9-<study>.jsonl)")
    s.add_argument("--question", help="the study's clip question id (default: the study name)")
    s.add_argument("--exported-on", help="optional cross-check only: must equal the stored day")
    s.add_argument("--force", action="store_true",
                   help="replace an existing ratings file, keeping the old one as <name>.prev")
    z = sub.add_parser("set-aside", help="keep a store's first complete session, move the others aside")
    z.add_argument("--study", required=True, choices=tuple(STUDIES))
    z.add_argument("--rater", required=True, choices=RATERS)
    z.add_argument("--store", required=True,
                   help="blindpanel's file-store folder for this rater (holds a9-<study>.jsonl); its name must equal "
                        "--rater (default layout .data/<RATER>). STOP THE BLINDPANEL SERVER FIRST: the command "
                        "refuses a store file modified in the last 120 seconds")
    a = ap.parse_args(argv)
    if a.cmd == "set-aside":
        adh = ROOT / "analysis" / "adherence"
        n = set_aside(a.store, a.study, a.rater, adh)
        print(f"set aside {n} extra session row(s) for {a.study}-{a.rater}" +
              (f"; hash recorded in analysis/adherence/{SESSIONS_SHA256}" if n else ""))
        return 0
    if a.cmd == "slim":
        adh = ROOT / "analysis" / "adherence"
        out = adh / f"ratings-{a.study}-{a.rater}.json"
        prev = out.with_name(out.name + ".prev")
        if out.exists() and not a.force:
            raise SystemExit(f"{out.name} exists; ratings are recorded once (pass --force to replace it; "
                             "the old file is kept as .prev)")
        if out.exists() and prev.exists():
            raise SystemExit(f"{prev.name} exists already: move it away first (nothing is ever discarded)")
        export = a.export or adh / "raw" / f"{a.study}-{a.rater}" / "ratings-V0001.json"
        store = a.store or adh / ".data" / a.rater / f"a9-{a.study}.jsonl"
        cells = load_cells(ROOT)
        lock = _load_json(adh / a.study / "study.lock.json", "study lock", {"instrument": str, "text_sha256": str})
        rec = slim(export, store, a.rater, a.study, cells, load_config(adh), lock, a.question, a.exported_on,
                   codes_from_prepare(adh, a.study, cells))
        replaced = _sha256(out) if out.exists() else None
        replace_keeping_prev(out, prev, json.dumps(rec, indent=1) + "\n")
        if replaced:
            append_sessions_sha256(adh, replaced, f"replaced analysis/adherence/{out.name} ({_utc_day()} UTC)")
        print(f"wrote {out.relative_to(ROOT)} ({rec['n']} clips, received {rec['received_day']}, "
              f"flags {rec['flags']!a}, export sha256 {rec['export_sha256']})")
        return 0
    res = run()
    print(f"A9 Test 1 ({res['label']}): {res['verdict']} -> analysis/out/a9_adherence.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
