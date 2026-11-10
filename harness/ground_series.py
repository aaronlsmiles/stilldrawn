#!/usr/bin/env python3
"""Ground-value causal series (amendment A3) — variant builder + run driver; A12's draws.

`build`: derive the five ground-value variants of the base panel by global
linear luminance scale k ∈ {1.00, 0.90, 0.80, 0.65, 0.52}; write derived
recipe JSONs (source, transform verbatim, measured p90/black_frac) and copy
the source lineart layer per variant (a global value scale moves no geometry).

`run --engine E`: execute the 5 IDLE cells for one engine via gen_video.py
(frozen prompt path), metrics NOT run here (backfill with `metrics --engine E`
which writes to runs/metrics-ground/).

`--draw D` (amendment A12): a draw of the same five cells in a same-hardware
series. On the local engines (Wan 2.2, LTX-2.3) draws 1, 2 and 3 are all fresh,
at seed 20260812 + (D - 1), and A3's existing cell (no suffix) is not a draw of
the series, because A3's local cells ran on other hardware (ruled 4 Nov 2026). On
Gen-4 Turbo, A3's existing cell is draw 1 (hosted, same hardware; it was sent no
seed) and `--draw` takes 2 or 3 only, sent seeds 20260813 and 20260814 (the same
rule, 7 Nov 2026; gen_video.py sends them through harness/runway_task.py). Runway's
word for a seed is "similar results": it fixes the request, not the bytes, so each
submission is still a fresh draw.
Cell ids, clips and metric files carry `-d1` / `-d2` / `-d3`. Any draw refuses
to run until amendment A12 is in the PUBLIC pre-registration
(harness/registration.py), and a local draw refuses unless STILLDRAWN_HW names the
machine, so the same-hardware claim reaches every manifest line (gen_video.py's
model_version). `draw_stem` is the one source of a draw's file stem. Without
`--draw`, A3's behaviour is unchanged.

A draw's cells follow harness/ladder.py's rule (decided 4 Nov 2026). A cell is skipped only when
its clip exists AND the manifest has its (non-refused) line, or when its refusal is already
in the manifest; a clip with no manifest line (an orphan, or a half-written download) and a
clip line whose file is missing each stop the run and name the cell. gen_video's stderr is
captured and echoed. A cell that fails is resubmitted once, identically (prereg §5), unless
the failed attempt left a clip behind, which stops the run. On Gen-4 Turbo a cell is written
to the manifest as refused only when BOTH attempts ended in a FAILED task outcome from
Runway (runway_gen.py's `task <id> FAILED: ...` line; the last one is recorded verbatim as
the refusal, in the shape of the manifest's existing refused lines); any other double
failure stops the run without a manifest line, so a re-run tries the cell again. A local
draw that fails twice stops the run: a harness fault, not a refusal.

`abandon --engine E [--pod-manifest FILE]` (A12.3.1, ruled 10 Nov 2026): the machine of a local
engine's series was lost, and the fifteen draws with their lines cannot be retrieved. The
series is written to runs/manifest.jsonl as abandoned, one line per cell (`"abandoned":
"machine lost"`, `"out": null`, the draw's seed, the lost machine's model_version where its line
came back, and whether its clip came back); every clip that came back is moved to
runs/abandoned/<engine>/, which is never measured, analysed or released. FILE is the lost
machine's manifest as retrieved: the series' lines leave it (the file as it was is kept beside it
as `<name>-lost-<engine>-<date>.jsonl`), so the rest merges as usual; it is required whenever
runs/pod-a10-manifest.jsonl exists. An abandoned line makes its cell neither made nor refused, so
the series is re-run whole, once, on one fresh machine, at the same cell ids and seeds. A second
`abandon` of the same engine is refused: a second loss is not re-run, and what can be retrieved
enters the series as it stands. It also refuses a series that came back whole (all fifteen lines
in FILE and all fifteen clips in runs/<engine>/: merge it), a series whose lines are already in
the manifest, and any draw already measured. Its steps run in an order a crash cannot spoil (lost
copy, trimmed pod manifest, moved clips, then the manifest lines as the commit point): run the same
command again and it says what it found and finishes.
"""
import argparse
import datetime as _dt
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
VENV_PY = pathlib.Path(__import__("os").environ.get("STILLDRAWN_PY", __import__("sys").executable))
if not VENV_PY.exists():   # pod execution (A2/A3): system python has the deps
    VENV_PY = pathlib.Path(sys.executable)
sys.path.insert(0, str(HERE))   # registration.py is imported only when a draw is asked for

BASE = "cu-line-1"
KS = [1.00, 0.90, 0.80, 0.65, 0.52]
ENGINE_TAG = {"gen4_turbo": "gen4t", "gen4.5": "gen45", "h3-fal": "h3",
              "wan22": "wan22", "ltx23": "ltx23"}
RATIO = "1280:720"
LOCAL = {"wan22", "ltx23"}
# A12: the draws each engine is given. Local engines: three fresh draws on one machine.
# Gen-4 Turbo: A3's cell is draw 1, so two further draws.
DRAWS = {"wan22": (1, 2, 3), "ltx23": (1, 2, 3), "gen4_turbo": (2, 3)}
BASE_SEED = 20260812                              # prereg §5; draw d is sent BASE_SEED + (d - 1)
ABANDONED = "machine lost"                  # A12.3.1: the manifest's mark on a lost machine's series
ABANDONED_DIR = pathlib.Path("runs") / "abandoned"   # kept privately; never measured, analysed or released
POD_MANIFEST = pathlib.Path("runs") / "pod-a10-manifest.jsonl"   # a pod's manifest as retrieved to the Mac
# runway_gen.py's task-level outcome with status FAILED, as harness/ladder.py: the only failure
# that may be recorded as a refusal. CANCELLED, its timeout and its API-error lines do not match.
TASK_OUTCOME = re.compile(r"^task \S+ FAILED: .*$", re.M)


def vid(k):
    return f"ground-{BASE}-v{int(round(k * 100)):03d}"


def cell_id(k, engine, draw=None):
    """A3's cell id without a draw; `-d1` / `-d2` / `-d3` for A12's draws."""
    cell = f"{vid(k)}_idle_{ENGINE_TAG[engine]}"
    return cell if draw is None else f"{cell}-d{draw}"


def draw_stem(k, engine, draw):
    """The file stem of an A12 draw (clip and metric file): local draws 1-3 carry
    `-d1` / `-d2` / `-d3`; Gen-4 Turbo's draw 1 is A3's unsuffixed cell, its draws
    2-3 carry `-d2` / `-d3`. No draw: A3's stem."""
    return cell_id(k, engine, None if (engine not in LOCAL and draw == 1) else draw)


def draw_seed(engine, draw):
    """The seed A12's draw `draw` is sent: BASE_SEED + (draw - 1), on the local engines and on
    Gen-4 Turbo alike (ruled 7 Nov 2026); None without a draw (A3's cells)."""
    return None if draw is None else BASE_SEED + (draw - 1)


def check_draw(engine, draw):
    """Refuse a draw A12 does not register. No draw (A3's cells) passes on every engine."""
    if draw is None:
        return
    if draw not in (1, 2, 3):
        raise SystemExit(f"--draw {draw}: A12 registers draws 1-3 on wan22 and ltx23, "
                         "2-3 on gen4_turbo")
    if engine not in DRAWS:
        raise SystemExit(f"--draw on {engine}: A12 extends {', '.join(DRAWS)} only")
    if draw not in DRAWS[engine]:
        raise SystemExit(f"--draw {draw} on {engine}: A3's existing cell is draw 1 on this "
                         f"hosted engine; A12 adds draws {' and '.join(map(str, DRAWS[engine]))} only")


def gen_cmd(k, engine, draw=None):
    cmd = [str(VENV_PY), str(HERE / "gen_video.py"), "--engine", engine,
           "--panel", str(ROOT / "dataset/panels" / f"{vid(k)}.png"),
           "--motion", "IDLE", "--cell-id", draw_stem(k, engine, draw), "--ratio", RATIO]
    if draw is not None:
        cmd += ["--seed", str(draw_seed(engine, draw))]
    return cmd


def series_cells(engine):
    """The cell ids of a local engine's A12 series: draws 1-3 at the five levels, in run order."""
    return [draw_stem(k, engine, d) for d in DRAWS[engine] for k in KS]


def manifest_cells(root):
    """(made, refused): cell ids with a clip line in runs/manifest.jsonl, and with a refused line.
    An abandoned line (A12.3.1) takes its cell out of both: the series is re-run whole."""
    m = pathlib.Path(root) / "runs" / "manifest.jsonl"
    made, refused = set(), set()
    if not m.exists():
        return made, refused
    for line in m.read_text().splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec.get("abandoned"):
                made.discard(rec["cell_id"])
                refused.discard(rec["cell_id"])
                continue
            (refused if rec.get("refused") else made).add(rec["cell_id"])
    return made, refused


def _write_lost_copy(pm, lost_copy):
    """Step 1 of abandon: keep the lost machine's manifest as it came back."""
    shutil.copy2(pm, lost_copy)


def _write_rest(pm, rest):
    """Step 2: the pod manifest copy without the series' lines, through a temporary file."""
    tmp = pm.with_name(pm.name + ".tmp")
    tmp.write_text("".join(x + "\n" for x in rest))
    os.replace(tmp, pm)


def _keep_clip(clip, kept):
    """Step 3, per clip: move a retrieved clip of the lost series to the private folder."""
    kept.parent.mkdir(parents=True, exist_ok=True)
    os.replace(clip, kept)


def _append_lines(m, new):
    """Step 4, the commit point: the abandoned lines, appended to runs/manifest.jsonl in one write."""
    m.parent.mkdir(parents=True, exist_ok=True)
    with m.open("a") as f:
        f.write("".join(json.dumps(r) + "\n" for r in new))


def abandon(engine, pod_manifest=None, out=print):
    """A12.3.1: record a local engine's series as abandoned after its machine was lost, once.

    Order, so that a crash at any step is finished by running the same command again: (1) keep the
    lost machine's manifest as `<name>-lost-<engine>-<date>.jsonl`; (2) rewrite the pod manifest copy
    without the series' lines (a temporary file, then os.replace); (3) move the retrieved clips to
    runs/abandoned/<engine>/; (4) append the abandoned lines to runs/manifest.jsonl, the commit point.
    Before (4) the manifest holds nothing of the abandon, so a retry finds the earlier steps' work
    (the lost copy, the moved clips), says so and finishes; anything it cannot account for, it refuses."""
    if engine not in LOCAL:
        raise SystemExit(f"abandon --engine {engine}: A12's lost-machine rule covers the local engines "
                         f"({', '.join(sorted(LOCAL))}) only")
    from registration import require_public
    require_public("A12", f"record {engine}'s ground series as abandoned")
    cells = series_cells(engine)
    m = ROOT / "runs" / "manifest.jsonl"
    recs = [json.loads(x) for x in m.read_text().splitlines() if x.strip()] if m.exists() else []
    if any(r.get("abandoned") and r.get("cell_id") in cells for r in recs):
        live_after = {r["cell_id"] for r in recs if r.get("cell_id") in cells and not r.get("abandoned")}
        raise SystemExit(f"{engine}: runs/manifest.jsonl already writes its ground series as abandoned (an "
                         f"earlier abandon finished; {len(live_after)} of its cells have lines from a merge "
                         "since). If the machine just lost ran the re-run, this is a second loss, and there "
                         "is no second re-run (A12.3.1): merge the draws of that machine whose clips and lines "
                         "both came back, as they stand; the series reads \"incomplete: N points missing\" "
                         "unless all fifteen came back. Nothing was changed.")
    made, refused = manifest_cells(ROOT)
    merged = [c for c in cells if c in made | refused]
    if merged:
        raise SystemExit(f"{engine}: the manifest already holds lines for {', '.join(merged)}; a series "
                         "merged into the manifest is not abandoned. Nothing was changed.")
    measured = [c for c in cells if (ROOT / "runs" / "metrics-ground" / f"{c}.json").exists()]
    if measured:
        raise SystemExit(f"{engine}: {', '.join(measured)} already measured; an abandoned draw is never "
                         "measured (A12.3.1). Stop and tell Aaron. Nothing was changed.")
    kept_dir = ROOT / ABANDONED_DIR / engine
    src = {c: ROOT / "runs" / engine / f"{c}.mp4" for c in cells}
    dst = {c: kept_dir / f"{c}.mp4" for c in cells}
    both = [str(dst[c]) for c in cells if src[c].exists() and dst[c].exists()]
    if both:
        raise SystemExit(f"{', '.join(both)}: a clip is in both runs/{engine}/ and {ABANDONED_DIR / engine}/; "
                         "inspect them by hand. Nothing was changed.")
    already_kept = [c for c in cells if dst[c].exists()]
    today = _dt.date.today().isoformat()
    pod_lines, rest, pm, lost_copy, resumed = {}, [], None, None, []
    if pod_manifest is None and (ROOT / POD_MANIFEST).exists():
        raise SystemExit(f"{ROOT / POD_MANIFEST} exists: pass it as --pod-manifest, so the series' lines "
                         "leave it before the rest is merged. Nothing was changed.")
    if pod_manifest is not None:
        pm = pathlib.Path(pod_manifest)
        if not pm.is_file():
            raise SystemExit(f"{pm}: no such file (omit --pod-manifest when nothing came back)")
        earlier = sorted(pm.parent.glob(f"{pm.stem}-lost-{engine}-*.jsonl"))
        if len(earlier) > 1:
            raise SystemExit(f"{', '.join(map(str, earlier))}: more than one lost copy for {engine}; inspect "
                             "them by hand. Nothing was changed.")
        lost_copy = earlier[0] if earlier else pm.with_name(f"{pm.stem}-lost-{engine}-{today}.jsonl")
        source = lost_copy if earlier else pm            # the lost machine's manifest as it came back
        # A line of another engine's series that its own lost copy holds left this pod manifest when that
        # engine was abandoned, so it is not part of what remains to merge. Only those lines: a line for one
        # of its cells that the copy does not hold (a later session's) stays.
        other = {c for e in sorted(LOCAL - {engine}) for c in series_cells(e)}
        other_lines = {x.strip() for e in sorted(LOCAL - {engine})
                       for q in pm.parent.glob(f"{pm.stem}-lost-{e}-*.jsonl")
                       for x in q.read_text().splitlines() if x.strip()}
        before_this = []                                  # the pod manifest as this abandon found it
        for x in source.read_text().splitlines():
            if x.strip():
                r = json.loads(x)
                if r.get("cell_id") in other and x.strip() in other_lines:
                    continue
                before_this.append(x)
                if r.get("cell_id") in cells:
                    pod_lines[r["cell_id"]] = r
                else:
                    rest.append(x)
        rest_text = "".join(x + "\n" for x in rest)
        if earlier:
            now = pm.read_text()
            untouched = (lost_copy.read_text(), "".join(x + "\n" for x in before_this))
            if now not in (*untouched, rest_text):
                raise SystemExit(f"{lost_copy} is kept from an earlier abandon of {engine}, and {pm} matches "
                                 "neither it nor it without the series' lines (a re-fetched or edited pod "
                                 "manifest?). Inspect both by hand. Nothing was changed.")
            resumed.append(f"the lost copy {lost_copy.name}" + ("" if now in untouched
                                                                 else ", the pod manifest already trimmed"))
        present = [c for c in cells if src[c].exists() or dst[c].exists()]
        if set(pod_lines) == set(cells) and len(present) == len(cells):
            raise SystemExit(f"{engine}: all fifteen draws and their lines came back whole, so the machine is "
                             "not lost for this series (A12.3.1): merge it as it stands. Nothing was changed.")
    if already_kept:
        resumed.append(f"{len(already_kept)} clips already in {ABANDONED_DIR / engine}/")
    if resumed:
        out(f"{engine}: resuming an abandon that stopped part-way; found {'; '.join(resumed)}.")
    draw_of = {draw_stem(k, engine, d): d for d in DRAWS[engine] for k in KS}
    new = [{"cell_id": c, "engine": engine, "draw": draw_of[c], "seed": draw_seed(engine, draw_of[c]),
            "model_version": (pod_lines.get(c) or {}).get("model_version"), "date": today, "out": None,
            "clip_kept_privately": src[c].exists() or dst[c].exists(), "abandoned": ABANDONED} for c in cells]
    if pm is not None:
        if not lost_copy.exists():
            _write_lost_copy(pm, lost_copy)                                    # (1)
        if pm.read_text() != rest_text:
            _write_rest(pm, rest)                                              # (2)
    for c in cells:
        if src[c].exists():
            _keep_clip(src[c], dst[c])                                         # (3)
    _append_lines(m, new)                                                      # (4) the commit point
    n_kept = sum(r["clip_kept_privately"] for r in new)
    out(f"{engine}: {len(new)} cells written to the manifest as abandoned (machine lost); {n_kept} clips "
        f"kept privately in {ABANDONED_DIR / engine}. Re-run the series whole, once, on one fresh machine.")
    if pm is not None:
        out(f"{pm}: {len(pod_lines)} lines of the series removed, {len(rest)} left to merge (the lost "
            f"machine's file is kept as {lost_copy.name})")


def task_outcome(stderr):
    """runway_gen.py's last task-level FAILED outcome line in `stderr`, or None."""
    hits = TASK_OUTCOME.findall(stderr or "")
    return hits[-1] if hits else None


def refusal_line(k, engine, cell, reason, seed=None):
    """A refused hosted draw, in the shape of the manifest's existing refused lines (the frozen
    pack, so no prompt_pack key), with the seed both attempts were sent."""
    from gen_video import RUNWAY_API_VERSION, resolve_prompt
    return {"cell_id": cell, "panel": f"dataset/panels/{vid(k)}.png", "motion_class": "IDLE",
            "prompt": resolve_prompt("IDLE"), "engine": engine,
            "model_version": f"{engine} (Runway dev API, X-Runway-Version {RUNWAY_API_VERSION})",
            "seed": seed, "duration_s": 5, "ratio": RATIO, "cost_usd": 0.0,
            "date": _dt.date.today().isoformat(), "out": None, "refused": True, "refusal": reason}


def run_draw(engine, draw, runner=subprocess.run, out=print, err=sys.stderr.write):
    """A12's draw of the five cells, under harness/ladder.py's skip and refusal rule."""
    made, refused = manifest_cells(ROOT)
    for k in KS:
        cell = draw_stem(k, engine, draw)
        clip = ROOT / "runs" / engine / f"{cell}.mp4"
        if cell in refused or (clip.exists() and cell in made):
            out(f"skip {cell} ({'refused' if cell in refused else 'exists'})")
            continue
        if clip.exists():
            raise SystemExit(f"{clip}: the clip exists but the manifest has no line for {cell} (an "
                             "orphan or a half-written download). Inspect it and move it aside by "
                             "hand; nothing was submitted for it.")
        if cell in made:
            raise SystemExit(f"{clip}: the manifest has a clip line for {cell} but the file is missing "
                             "(an incomplete rsync, or moved aside?). Restore it; not regenerating.")
        out(f"[A12] {cell}")
        errors, outcomes = [], []
        for attempt in (1, 2):
            try:
                res = runner(gen_cmd(k, engine, draw), check=True, stderr=subprocess.PIPE, text=True)
                if getattr(res, "stderr", None):
                    err(res.stderr)
                break
            except subprocess.CalledProcessError as e:
                if e.stderr:
                    err(e.stderr)
                outcomes.append(task_outcome(e.stderr))
                errors.append(f"attempt {attempt}: exit {e.returncode}")
                if clip.exists():
                    raise SystemExit(f"{clip}: attempt {attempt} failed ({errors[-1]}) but left a clip "
                                     "behind (a partial download?). Not resubmitting and not "
                                     "recording a refusal: inspect it, move it aside, re-run.")
                out(f"  failed ({errors[-1]})" + ("; resubmitting once (prereg §5)" if attempt == 1 else ""))
        else:
            if engine in LOCAL:
                raise SystemExit(f"{cell}: the local engine failed twice ({'; '.join(errors)}). That "
                                 "is a harness fault, not a refusal: fix it and re-run (it resumes).")
            if not all(outcomes):
                raise SystemExit(f"{cell}: failed twice ({'; '.join(errors)}) without a task-level "
                                 "FAILED outcome from Runway on both attempts (op sign-in, API error, "
                                 "network, a CANCELLED task?). Not recorded as refused: fix it and "
                                 "re-run (it resumes).")
            m = ROOT / "runs" / "manifest.jsonl"
            m.parent.mkdir(parents=True, exist_ok=True)
            with m.open("a") as f:
                f.write(json.dumps(refusal_line(k, engine, cell, outcomes[-1],
                                                seed=draw_seed(engine, draw))) + "\n")
            out("  refused (both attempts FAILED at Runway); recorded in the manifest")


def p90_black(img):
    g = np.asarray(img.convert("L"), dtype=float) / 255.0
    return float(np.percentile(g, 90)), float((g < 0.1).mean())


def build():
    src = Image.open(ROOT / "dataset/panels" / f"{BASE}.png").convert("RGB")
    for k in KS:
        arr = np.asarray(src, dtype=float) * k
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        pid = vid(k)
        im.save(ROOT / "dataset/panels" / f"{pid}.png")
        shutil.copy(ROOT / "dataset/lineart" / f"{BASE}-lines.png",
                    ROOT / "dataset/lineart" / f"{pid}-lines.png")
        p90, bf = p90_black(im)
        (ROOT / "dataset/recipes" / f"{pid}.json").write_text(json.dumps({
            "derived_from": BASE,
            "transform": f"global linear luminance scale: pixel' = clip(pixel * {k})",
            "amendment": "A3 (2026-08-13, ground-value causal series)",
            "engine": "derived", "date": "2026-08-13",
            "paper_white_p90": round(p90, 3), "black_frac": round(bf, 3),
            "lineart": f"copied from {BASE} (global value scale moves no geometry)",
        }, indent=1))
        print(f"{pid}: p90={p90:.3f} black_frac={bf:.3f}")


def run(engine, draw=None, runner=subprocess.run):
    check_draw(engine, draw)
    if draw is not None:
        from registration import require_public
        require_public("A12", f"generate ground draw {draw} on {engine}")
        if engine in LOCAL and not os.environ.get("STILLDRAWN_HW"):
            raise SystemExit(f"REFUSING to generate ground draw {draw} on {engine}: set "
                             "STILLDRAWN_HW to the machine's name, so every manifest line of "
                             "the same-hardware series records it (gen_video.py model_version)")
        return run_draw(engine, draw, runner)
    for k in KS:
        cell = draw_stem(k, engine, draw)
        out = ROOT / "runs" / engine / f"{cell}.mp4"
        if out.exists():
            print(f"skip {cell} (exists)")
            continue
        print(f"[{'A3' if draw is None else 'A12'}] {cell}")
        runner(gen_cmd(k, engine, draw), check=True)


def metrics(engine, draw=None, runner=subprocess.run):
    check_draw(engine, draw)
    mdir = ROOT / "runs/metrics-ground"
    mdir.mkdir(exist_ok=True)
    for k in KS:
        pid = vid(k)
        cell = draw_stem(k, engine, draw)
        clip = ROOT / "runs" / engine / f"{cell}.mp4"
        mjson = mdir / f"{cell}.json"
        if not clip.exists() or mjson.exists():
            continue
        runner([str(VENV_PY), str(ROOT / "metrics/inkstab.py"), str(clip),
                "--panel", str(ROOT / "dataset/panels" / f"{pid}.png"),
                "--lineart", str(ROOT / "dataset/lineart" / f"{pid}-lines.png"),
                "--out", str(mjson)], check=True, timeout=1800)
        print(f"metrics -> {mjson.name}")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["build", "run", "metrics", "abandon"])
    p.add_argument("--engine", choices=sorted(ENGINE_TAG))
    seeds = "/".join(str(BASE_SEED + d - 1) for d in DRAWS["wan22"])
    p.add_argument("--draw", type=int, choices=[1, 2, 3], default=None,
                   help=f"A12: a draw of the same-hardware series; 1-3 on wan22/ltx23 (seed "
                        f"{seeds}, STILLDRAWN_HW set), 2-3 on gen4_turbo (seeds sent to Runway); "
                        "files carry -d1/-d2/-d3. Omit for A3's cells")
    p.add_argument("--pod-manifest", default=None,
                   help="abandon: the lost machine's manifest as retrieved, if it came back")
    a = p.parse_args(argv)
    if a.mode == "abandon":
        if a.draw is not None:
            raise SystemExit("abandon takes no --draw: a lost machine's whole series is abandoned (A12.3.1)")
        abandon(a.engine, a.pod_manifest)
    elif a.mode == "build":
        build()
    elif a.mode == "run":
        run(a.engine, a.draw)
    else:
        metrics(a.engine, a.draw)


if __name__ == "__main__":
    main()
