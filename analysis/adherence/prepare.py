#!/usr/bin/env python3
"""Rating copies and the two blind adherence studies of amendment A9 (Test 1).

    python3 analysis/adherence/prepare.py cells [--study burst|push|pilot]
    python3 analysis/adherence/prepare.py media [--study burst|push|pilot]
    python3 analysis/adherence/prepare.py write [--study burst|push|pilot]
    python3 analysis/adherence/prepare.py check [--study burst|push|pilot] [--partial]
    python3 analysis/adherence/prepare.py check-build --study burst|push|pilot --dist .build/a9-burst
                                              [--record [--replace-recorded] | --expect-recorded | --expect-tree HEX]

--root DIR (default: this checkout) is the repository root; cells, media, check and check-build use it
(manifest, sources, release rules), write does not. check and check-build take --tree-kind
private|public (default private). Exit status 0 means clean.

Standard library only, plus ffmpeg and ffprobe on PATH (in the private tree it also loads
tools/build_release.py for the release rules, which needs numpy and Pillow). It never shows a clip: it
reads stream metadata, bytes and hashes of decoded frames, and writes re-encoded copies.

Cells. The 110 primary burst and camera-push clips: 11 panels per class, five engines, the
last manifest line per cell_id. Re-rolls (-r2), hazard draws (-hN), the ground series and
every other suffix fall outside the cell pattern and are rejected by `validate_cells`.

Rating copies (A9.3). Each clip is scaled to cover and centre-cropped to 1280x704 (portrait
704x1280); its first 121 frames are kept at 24 fps constant. A source at another rate is
retimed with the fps filter (by frame timing), never relabelled; the filter and a constant-rate
output apply to every clip, so irregular timestamps at a nominal 24/1 are made constant too.
libx264 CRF 16, yuv420p, no audio, container and stream metadata stripped, the encoder's SEI
message removed. Each panel shown beside its clips is a PNG copy with the same pixels and only
the chunks the pixels need (ffmpeg alone would carry over EXIF and the pixel-density chunk).

Studies. One blindpanel study per class (`burst/`, `push/`), instrument A9, every clip
labelled "clip" with empty meta; each clip shows its own panel as the "Original image"; there are no
reference metrics and no reveal links. Each question quotes only the motion clause of the prompt the
clips were made with, inside a fixed frame.

Release rules. In the private working tree, tools/build_release.py supplies the public id
for each private one and the leak scan; prepare.py applies the renames to everything it
writes and `check` holds every shipping file to the scan. The public tree has no such file
and needs neither.

Banned terms. The shipped banned-terms.txt holds what can be published: engine and model names, cell
and panel id patterns and the old working name. The names and ids that must not be published in any
form are in private-terms.txt (same line format), which the private repo tracks and the release never
ships. `check` and `check-build` scan with both lists when that file is present (shipping files are also
scanned with split strings and character classes joined) and say so when it is absent, as in the public
tree, where they run with the public list only. A report names a private term by its line number.

Builds. `blindpanel build` (or `dev`) writes a study's site; `check-build` then reads every file
in it, and every file's path, against the banned terms, the literal public cell, panel and engine
ids and the private id, holds study.json and reveal.json to their exact shapes (reveal.json is
the one file blindpanel's own `verify` does not scan), checks the media against media-sources.json
and hashes the whole tree. `--record` writes a clean build's tree hash to build-trees.json (it will not
replace a different recorded hash without --replace-recorded); every later sitting runs
`--expect-recorded`, so a rater only ever sits at the registered build. The scan guards against accidental
leaks, not an adversary: JSON escapes are decoded, but HTML entities, JavaScript string escapes,
zero-width characters and strings split across expressions are not.

Sections of this file, in order (each starts with a banner comment; key functions in brackets):
    the instrument (A9.3)       the registered wording, the three study specs, BANNED_TERMS
    small helpers               [run, write_text, write_text_atomic, write_json, release_rules]
    cells                       [load_manifest, select_cells, validate_cells]
    media                       [encode_clip, copy_panel, build_media]
    checks                      [check_copy, positive_control, parse_banned, check_study, check_shipping]
    the study files             [opaque_code, question_text, study_config, to_yaml, write_study]
    the build and its record    [dist_files, tree_hash, check_build, record_tree, recorded_tree]
    command line                [main]
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import stat
import struct
import subprocess
import sys
import unicodedata
import zlib
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

INSTRUMENT = "A9"
FRAMES, FPS, CRF = 121, 24, 16
LANDSCAPE, PORTRAIT = (1280, 704), (704, 1280)
ENGINES = {"gen4.5": "gen45", "gen4_turbo": "gen4t", "h3-fal": "h3", "ltx23": "ltx23", "wan22": "wan22"}
CLASS_TOKEN = {"BURST": "burst", "CAMPUSH": "campush"}
A6_SEEDS = {"20260813", "stilldrawn-a6-blindpanel-1"}   # the A6 kit's and blindpanel's example

# ---------------------------------------------------------------- the instrument (A9.3)
BURST_CLAUSE = "The action implied by the drawing continues in one fast, committed burst of motion, then settles."
PUSH_CLAUSE = "Slow, steady camera push-in toward the focal point of the drawing."
INTRO = [
    "Each screen shows an **original image** (left) and a **5-second clip** made from it "
    "(right, plays on loop). You answer **one question** about each clip.",
    "Every clip was asked for the same motion, quoted in the question. Rate how fully the clip carries it out.",
    "Go with your eye. There are no right answers. You can change an answer with Back before finishing.",
]
WATCH_NOTE = "Watch the whole five seconds before answering."
BURST = {
    "key": "burst", "id": "a9-burst", "dir": "burst", "motion_class": "BURST",
    "title": "Motion check: set 1", "seed": "a9-burst-2026-10-31",
    "clause": BURST_CLAUSE, "n_clips": 55, "n_panels": 11,
    "question": {
        "id": "burst", "short": "The burst happens",
        "direction": "5 = yes, fully · 1 = no, not at all",
        "note": "Rate only this motion. How the clip looks, and anything else that changes, is not being asked about.",
    },
    "labels": [
        "No: the implied action doesn't happen (still, idle movement only, or something else)",
        "Barely: small or hesitant, not a burst",
        "Partly",
        "Mostly: a burst, a little weak or incomplete",
        "Yes: one fast, committed burst",
    ],
}
PUSH = {
    "key": "push", "id": "a9-push", "dir": "push", "motion_class": "CAMPUSH",
    "title": "Motion check: set 2", "seed": "a9-push-2026-10-31",
    "clause": PUSH_CLAUSE, "n_clips": 55, "n_panels": 11,
    "question": {
        "id": "push", "short": "The push-in happens",
        "direction": "5 = yes, fully · 1 = no, not at all",
        "note": "Rate only the camera's move. What the subject does, and how the clip looks, is not being asked about.",
    },
    "labels": [
        "No push-in (holds, pulls back, pans or cuts)",
        "Barely: a slight or hesitant move in, not a clear push-in",           # drafted; Gate C
        "Partly",                                                               # drafted; Gate C
        "Mostly: a push-in, a little uneven, quick or off the main subject",   # drafted; Gate C
        "A slow, steady push-in toward the main subject",
    ],
}
# The pilot: burst wording on A3 (ground series) and A4 (hazard draws) clips only; discarded.
PILOT = dict(BURST, key="pilot", id="a9-pilot", dir="pilot", motion_class=None,
             title="Motion check: pilot", seed="a9-pilot-2026-10-31", n_clips=6, n_panels=6,
             cells=["act-black-3_burst_h3-h1", "act-line-2_burst_h3-h1", "cu-black-3_burst_h3-h1",
                    "cu-line-1_burst_h3-h1", "ground-cu-line-1-v052_idle_ltx23",
                    "ground-cu-line-1-v100_idle_gen45"])
STUDIES = {"burst": BURST, "push": PUSH, "pilot": PILOT}

# Files under analysis/adherence/ that the release ships (paths relative to it).
SHIPPING = [
    "prepare.py", "test_prepare.py", "README.md", "rating-copies.sha256", "build-trees.json",
    "a9-config.json",                                        # written by sub-plan A
    *[f"{d}/{f}" for d in ("burst", "push")
      for f in ("study.yaml", "study.lock.json", "banned-terms.txt", "media-sources.json")],
    *[f"ratings-{s}-{r}.json" for s in ("burst", "push") for r in ("AARON", "R7")],
]
# Shipped only when present: r7-status.json exists only after R7's deadline (sub-plan A);
# sessions.sha256 (hashes of set-aside sessions and replaced rating files) exists only once there is one.
OPTIONAL_SHIPPING = ["r7-status.json", "sessions.sha256"]

# `turbo` and `/gen[ -]?4/i` over-ban on purpose: they also match ordinary words, and a false alarm
# costs a look at one hit while a miss shows a rater which engine made the clip.
BANNED_TERMS = """\
# Names that must not reach the rating page, its URLs, its requests or reveal.json.
# Plain lines match as case-insensitive substrings; /.../flags lines are regular
# expressions (no i flag: case-sensitive). Written by prepare.py; never edit by hand.
# This is the public list. The terms that may not be published at all (a private name, the private
# id prefix, uncleared names) live in private-terms.txt, which only the private repo holds; prepare.py
# scans with both lists when that file is present. The working-name line is a character class so that the
# release build's own rename leaves this file byte-identical.
runway
/gen[ -]?4/i
gen45
gen4t
turbo
/\\bwan\\b/i
/wan ?2/i
ltx
lightricks
/\\bH3\\b/
h3-fal
_h3
hailuo
minimax
/\\bfal\\b/i
fal.ai
seedance
bytedance
comfyui
/stable ?diffusion/i
kling
/\\bsora\\b/i
/\\bveo\\b/i
/\\bluma\\b/i
/\\bpika\\b/i
gemini
/i[n]kbench/i
# cell and panel ids
/_(idle|burst|campush)_/i
/\\b(cu|act|est)-(line|tone|black)-\\d/i
/\\bcip-/i
/chain-est/i
/act-tank/i
/ground-cu/i
"""


# The private terms: names that must not appear in any file that ships, in any form. They live in
# private-terms.txt next to this file (same line format as banned-terms.txt), tracked in the private
# repo and never shipped (tools/build_release.py's ADHERENCE_PRIVATE). The public tree does not have it;
# checks there run with the public list only and say so. Nothing in this file spells them.
PRIVATE_TERMS_NAME = "private-terms.txt"
PRIVATE_TERMS = HERE / PRIVATE_TERMS_NAME


# ---------------------------------------------------------------- small helpers
RUN_TIMEOUT = 600      # seconds; one clip encodes in about a second, so this only ever catches a hang


def run(cmd, timeout=RUN_TIMEOUT):
    """Run a program and return its stdout as text. Any failure is a RuntimeError that keeps the
    end of stderr (where ffmpeg puts the cause)."""
    name = str(cmd[0])
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
    except FileNotFoundError:
        raise RuntimeError(f"{name} not found on PATH (ffmpeg and ffprobe are needed)") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{name} timed out after {timeout} s") from None
    if r.returncode != 0:
        raise RuntimeError(f"{name} failed ({r.returncode}): {r.stderr.strip()[-400:]}")
    return r.stdout


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(p):
    """Every text file in this folder is UTF-8."""
    with open(p, encoding="utf-8") as f:
        return f.read()


def write_text(p, text):
    """UTF-8 with Unix newlines on every platform, so shipped bytes (and hashes) never vary."""
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_text_atomic(p, text):
    """write_text, but the file is never half-written: the text goes to a temporary file in the same folder
    (a dot-name, which the release never ships), is flushed and fsynced, then replaces `p` in one step
    (os.replace). On any failure the temporary file is removed and `p` is as it was."""
    p = Path(p)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    try:                                              # best effort: make the rename itself durable
        fd = os.open(p.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def write_json(p, obj):
    write_text(p, json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def release_rules(root):
    """The private release build's rules (OLD_ID, NEW_ID, LEAK_RE, rewrite_text), or None
    in the public tree, which has already been through them."""
    path = Path(root) / "tools" / "build_release.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("_release_rules", path)
    mod = importlib.util.module_from_spec(spec)
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True     # leave no __pycache__ behind
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = keep
    return mod


def renames_of(rules):
    return {rules.OLD_ID: rules.NEW_ID} if rules else {}


def public(text, renames):
    for old, new in renames.items():
        text = text.replace(old, new)
    return text


# ---------------------------------------------------------------- cells
def load_manifest(root):
    """Last manifest line per cell_id. A bad line stops the run and is named by line number."""
    last = {}
    for n, line in enumerate(read_text(Path(root) / "runs" / "manifest.jsonl").splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError as e:
            raise SystemExit(f"manifest.jsonl:{n}: not valid JSON ({e})")
        if not isinstance(r, dict) or not isinstance(r.get("cell_id"), str) or not r["cell_id"]:
            raise SystemExit(f"manifest.jsonl:{n}: not an object with a cell_id")
        last[r["cell_id"]] = r          # the last line per cell_id wins
    return last


# What may be written to a shipping file. Everything else on a cell is private: the manifest
# cell id and output path (they carry the private id), the prompt, and panel_src (an absolute path).
PUBLIC_KEYS = ("id", "engine", "motion_class", "panel", "panel_source", "source")


def public_view(cell):
    return {k: cell[k] for k in PUBLIC_KEYS}


def _cell(cid, r, root, renames):
    for key in ("engine", "panel", "out"):
        if not r.get(key):
            raise SystemExit(f"manifest row {cid}: no '{key}'")
    panel_path = Path(r["panel"])
    # Never trust an absolute manifest path: rented-GPU rows carry the pod's checkout path.
    panel_src = Path(root) / "dataset" / "panels" / panel_path.name
    panel = public(panel_path.stem, renames)
    return {
        "id": public(cid, renames), "cell_id": cid, "engine": r["engine"],
        "motion_class": r.get("motion_class"), "prompt": r.get("prompt", ""),
        "panel": panel, "panel_src": str(panel_src), "panel_source": f"dataset/panels/{panel}.png",
        "out": r["out"], "source": public(r["out"], renames),
    }


def select_cells(manifest, spec, root, renames):
    """The study's cells, sorted by public id."""
    if spec.get("cells"):
        missing = [c for c in spec["cells"] if c not in manifest]
        if missing:
            raise SystemExit(f"pilot cells missing from the manifest: {missing}")
        return sorted((_cell(c, manifest[c], root, renames) for c in spec["cells"]), key=lambda c: c["id"])
    token = CLASS_TOKEN[spec["motion_class"]]
    out = []
    for cid, r in manifest.items():
        suffix = ENGINES.get(r.get("engine"))
        if suffix and not cid.startswith("ground-") and r.get("motion_class") == spec["motion_class"] \
                and re.fullmatch(rf"(.+)_{token}_{re.escape(suffix)}", cid):
            out.append(_cell(cid, r, root, renames))
    return sorted(out, key=lambda c: c["id"])


PRIMARY_RE = re.compile(r"(.+)_(burst|campush|idle)_(%s)" % "|".join(re.escape(s) for s in ENGINES.values()))


def is_primary(cid):
    """A primary-arm cell: one of the 29 panels (not a ground variant), one engine suffix."""
    return not cid.startswith("ground-") and PRIMARY_RE.fullmatch(cid) is not None


def validate_cells(cells, spec):
    """Problems with a study's cell list (empty when it is the registered set)."""
    p = []
    if len(cells) != spec["n_clips"]:
        p.append(f"{spec['id']}: {len(cells)} cells, expected {spec['n_clips']}")
    if any("-r2" in c["id"] for c in cells):
        p.append(f"{spec['id']}: a re-roll (-r2) cell is selected")
    if len({c["id"] for c in cells}) != len(cells):
        p.append(f"{spec['id']}: duplicate ids")
    panels = sorted({c["panel"] for c in cells})
    if len(panels) != spec["n_panels"]:
        p.append(f"{spec['id']}: {len(panels)} panels, expected {spec['n_panels']}")
    if spec.get("cells"):
        for c in cells:
            if is_primary(c["cell_id"]):
                p.append(f"pilot cell {c['id']} is a primary cell")
            if not (c["cell_id"].startswith("ground-") or re.search(r"_h3-h\d+$", c["cell_id"])):
                p.append(f"pilot cell {c['id']} is not an A3 or A4 cell")
        return p
    by_engine = {}
    for c in cells:
        by_engine.setdefault(c["engine"], set()).add(c["panel"])
    if set(by_engine) != set(ENGINES) or any(v != set(panels) for v in by_engine.values()):
        p.append(f"{spec['id']}: engines do not each cover the same {spec['n_panels']} panels")
    for c in cells:
        if not c["prompt"].startswith(spec["clause"] + " "):
            p.append(f"{c['id']}: prompt does not open with the quoted clause")
    return p


# ---------------------------------------------------------------- media
def probe(path):
    data = json.loads(run(["ffprobe", "-v", "error", "-show_entries",
                           "stream=index,codec_type,codec_name,pix_fmt,width,height,r_frame_rate,"
                           "avg_frame_rate,nb_frames:stream_tags:format_tags",
                           "-of", "json", path]))
    streams = data.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    if not video:
        raise RuntimeError(f"no video stream in {path}")
    v = video[0]
    n = str(v.get("nb_frames", ""))
    return {
        "stream_types": [s.get("codec_type") for s in streams], "codec": v.get("codec_name"),
        "pix_fmt": v.get("pix_fmt"), "width": int(v["width"]), "height": int(v["height"]),
        "r_frame_rate": v.get("r_frame_rate"), "avg_frame_rate": v.get("avg_frame_rate"),
        "nb_frames": int(n) if n.isdigit() else None,
        "stream_tags": [s.get("tags", {}) for s in streams],
        "format_tags": data.get("format", {}).get("tags", {}),
    }


def needs_retime(info):
    return not (info["r_frame_rate"] == f"{FPS}/1" and info["avg_frame_rate"] == f"{FPS}/1")


def encode_args(src, dst, size):
    """fps comes first, always: a source at 24/1 can still carry irregular timestamps, and the
    filter (a no-op on true 24 fps constant) retimes by frame timing, never by relabelling."""
    w, h = size
    vf = [f"fps={FPS}", f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos",
          f"crop={w}:{h}", "setsar=1"]
    return ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
            "-map", "0:v:0", "-an", "-sn", "-dn",
            "-map_metadata", "-1", "-map_metadata:s:v", "-1", "-map_chapters", "-1",
            "-metadata:s:v:0", "encoder=",
            "-vf", ",".join(vf), "-fps_mode", "cfr", "-frames:v", str(FRAMES),
            "-c:v", "libx264", "-preset", "medium", "-crf", str(CRF), "-pix_fmt", "yuv420p",
            "-threads", "4", "-bsf:v", "filter_units=remove_types=6",
            "-flags:v", "+bitexact", "-fflags", "+bitexact", "-movflags", "+faststart",
            "-f", "mp4", str(dst)]


def panel_args(src, dst):
    return ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
            "-map_metadata", "-1", "-flags:v", "+bitexact", "-fflags", "+bitexact",
            "-frames:v", "1", "-update", "1", "-c:v", "png", "-f", "image2", str(dst)]


def frames_sha256(path):
    """SHA-256 of the decoded frames: unchanged by metadata rewrites of the file."""
    out = run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", path,
               "-map", "0:v:0", "-f", "hash", "-hash", "sha256", "-"])
    return out.strip().split("=", 1)[1].lower()


def target_size(info):
    return PORTRAIT if info["height"] > info["width"] else LANDSCAPE


def encode_clip(src, dst, size):
    dst = Path(dst)
    tmp = dst.with_name(dst.stem + ".tmp.mp4")
    try:
        run(encode_args(src, tmp, size))
        tmp.replace(dst)
    finally:
        tmp.unlink(missing_ok=True)


PNG_SIG = b"\x89PNG\r\n\x1a\n"
PNG_KEEP = {"IHDR", "PLTE", "tRNS", "IDAT", "IEND"}         # everything else is ancillary (text, EXIF, time, density)
# Chunks that change how the pixels look. ffmpeg writes none of them, so a copy would show other
# colours than the panel it was made from; such a panel is refused, not silently changed.
COLOUR_CHUNKS = {"gAMA", "cHRM", "iCCP", "sRGB", "cICP", "sBIT"}


def png_chunks(data, strict=False):
    """[(type, chunk)] for every chunk up to IEND; chunk is the whole slice (length, type, data,
    CRC), so b"".join(chunk) after the signature rebuilds the file. ValueError names the problem:
    bad signature, truncation, a bad CRC, a first chunk that is not IHDR, no IEND. Bytes after
    IEND are ignored (a source panel may carry some); strict=True refuses them. ffmpeg's PNG
    encoder never writes any, and copy_panel checks its own output strictly."""
    if not data.startswith(PNG_SIG):
        raise ValueError("not a PNG (bad signature)")
    out, off = [], len(PNG_SIG)
    while True:
        if off + 8 > len(data):
            raise ValueError(f"truncated PNG: no chunk header at byte {off} (no IEND)")
        n, raw = struct.unpack(">I4s", data[off:off + 8])
        name = raw.decode("latin-1")
        if not re.fullmatch(r"[A-Za-z]{4}", name):
            raise ValueError(f"bad chunk type {raw!r} at byte {off}")
        end = off + 12 + n
        if end > len(data):
            raise ValueError(f"truncated PNG: chunk {name} at byte {off} needs {n} data bytes")
        if zlib.crc32(data[off + 4:end - 4]) & 0xFFFFFFFF != struct.unpack(">I", data[end - 4:end])[0]:
            raise ValueError(f"bad CRC in chunk {name} at byte {off}")
        if not out and name != "IHDR":
            raise ValueError(f"first chunk is {name}, not IHDR")
        out.append((name, data[off:end]))
        off = end
        if name == "IEND":
            break
    if strict and off != len(data):
        raise ValueError(f"{len(data) - off} bytes after IEND")
    return out


def png_size(path):
    """(width, height) from the IHDR chunk (data bytes 0-7 of the first chunk)."""
    return struct.unpack(">II", png_chunks(Path(path).read_bytes())[0][1][8:16])


def copy_panel(src, dst):
    """A PNG with the same pixels and only the chunks the pixels need (PNG_KEEP). Refuses, before
    ffmpeg runs, a panel it cannot read or one that carries a colour chunk."""
    src, dst = Path(src), Path(dst)
    colour = sorted({t for t, _ in png_chunks(src.read_bytes())} & COLOUR_CHUNKS)
    if colour:
        raise ValueError(f"the panel carries colour chunks {colour}; the copy would not look the same")
    tmp = dst.with_name(dst.stem + ".tmp.png")
    try:
        run(panel_args(src, tmp))
        keep = b"".join(c for t, c in png_chunks(tmp.read_bytes()) if t in PNG_KEEP)
        tmp.write_bytes(PNG_SIG + keep)
        png_chunks(tmp.read_bytes(), strict=True)               # what is written is well formed, nothing after IEND
        tmp.replace(dst)
    finally:
        tmp.unlink(missing_ok=True)


def ffmpeg_version():
    return run(["ffmpeg", "-version"]).splitlines()[0].split(" Copyright")[0]


def x264_version():
    """libx264's own version, read from the SEI string of a one-frame encode (the rating copies
    have that string removed, so this is the only record of it)."""
    out = run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
               "color=c=black:s=64x64:r=24", "-frames:v", "1", "-c:v", "libx264", "-f", "h264", "-"])
    m = re.search(r"x264 - core (\d+)(?: (r\d+ [0-9a-f]+))?", out)
    if not m:
        raise RuntimeError("could not read the libx264 version from a test encode")
    return f"core {m.group(1)}" + (f" {m.group(2)}" if m.group(2) else "")


def _step(label, fn, *args):
    """Run one cell's or panel's step; a failure is re-raised naming it by its public id."""
    try:
        return fn(*args)
    except (RuntimeError, ValueError, OSError) as e:
        raise RuntimeError(f"{label}: {e}") from e


def _build_clip(c, pub, root, mdir):
    src = Path(root) / c["out"]
    info = probe(src)
    size, retime = target_size(info), needs_retime(info)       # retime is only recorded, never decides
    dst = mdir / f"{pub['id']}.mp4"
    encode_clip(src, dst, size)
    made = probe(dst)             # a wrong copy must stop the build, not wait for `check`
    got = (made["nb_frames"], made["width"], made["height"], made["stream_types"], made["codec"], made["pix_fmt"],
           made["r_frame_rate"], made["avg_frame_rate"])
    want = (FRAMES, *size, ["video"], "h264", "yuv420p", f"{FPS}/1", f"{FPS}/1")
    if got != want:
        raise RuntimeError(f"the copy is (frames, w, h, streams, codec, pix_fmt, r, avg) = {got}; "
                           f"expected {want} (source {info['width']}x{info['height']}, {info['nb_frames']} frames)")
    print(f"  {pub['id']}  {info['width']}x{info['height']} {info['avg_frame_rate']} -> {size[0]}x{size[1]}")
    return {
        "engine": pub["engine"], "panel": pub["panel"], "source": pub["source"],
        "source_frames_sha256": frames_sha256(src),
        "source_video": {k: info[k] for k in ("width", "height", "r_frame_rate", "avg_frame_rate", "nb_frames")},
        "source_streams": info["stream_types"], "retimed": retime,
        "copy": f"media/{pub['id']}.mp4", "copy_sha256": sha256_file(dst),
    }


def _build_panel(c, pub, mdir):
    pdst = mdir / f"{pub['panel']}.png"
    copy_panel(c["panel_src"], pdst)
    src_px, copy_px = frames_sha256(c["panel_src"]), frames_sha256(pdst)
    if src_px != copy_px:
        raise RuntimeError("the copy changed the pixels")
    width, height = png_size(pdst)
    return {"source": pub["panel_source"], "source_pixels_sha256": src_px, "width": width, "height": height,
            "copy": f"media/{pub['panel']}.png", "copy_sha256": sha256_file(pdst)}


def build_media(spec, cells, root, here):
    sdir = Path(here) / spec["dir"]
    mdir = sdir / "media"
    mdir.mkdir(parents=True, exist_ok=True)
    for stale in mdir.glob("*.tmp.*"):          # left by an interrupted run; nothing else is touched
        stale.unlink()
    panels, clips = {}, {}
    for c in cells:
        pub = public_view(c)          # only this view of a cell is ever written or printed
        clips[pub["id"]] = _step(pub["id"], _build_clip, c, pub, root, mdir)
        if pub["panel"] not in panels:
            panels[pub["panel"]] = _step(f"panel {pub['panel']}", _build_panel, c, pub, mdir)
    doc = {
        "format": "stilldrawn-a9-media/1",
        "note": ("Rating copies for the blind adherence study; the copies themselves are not released. "
                 "source_frames_sha256 and source_pixels_sha256 hash the decoded frames, which the "
                 "release's metadata rewrites leave unchanged. source_frames_sha256 covers the whole source; "
                 f"the copy is its first {FRAMES} frames."),
        "study": spec["id"], "motion_class": spec["motion_class"], "prompt_clause": spec["clause"],
        "ffmpeg": ffmpeg_version(),
        "encode": {
            "libx264": x264_version(),
            "frames": FRAMES, "fps": FPS, "crf": CRF, "landscape": list(LANDSCAPE), "portrait": list(PORTRAIT),
            "command": " ".join(encode_args("{source}", "{copy}", ("{w}", "{h}"))),
            "retime": f"fps={FPS} is the first filter on every clip and the output is constant frame rate, so a "
                      f"source with other or irregular timing is retimed by frame timing; `retimed` marks "
                      f"sources that did not report {FPS}/1",
        },
        "panels": dict(sorted(panels.items())),
        "clips": dict(sorted(clips.items())),
    }
    write_json(sdir / "media-sources.json", doc)
    return doc


# ---------------------------------------------------------------- checks
C2PA_BMFF_UUID = bytes.fromhex("d8fec3d61b0e483c92975828877ec481")   # the C2PA uuid box in MP4
C2PA_JUMBF_TYPE = bytes.fromhex("6332706100110010800000aa00389b71")  # JUMBF type of a C2PA manifest store
SHORT_TOKENS = (b"c2pa", b"jumb", b"jumd")
ENCODER_TOKENS = (b"x264", b"core ", b"lavc", b"lavf")       # the encoder's tags and the start of its SEI text
X264_SEI_TAIL = b"- H.264/MPEG-4 AVC codec"                    # long enough to be searched in the payload too
TANK_PANEL = "cip-act-tank-1"                                  # the one portrait row; its public id
MP4_CONTAINERS = {"moov", "trak", "mdia", "minf", "stbl", "udta", "edts", "dinf"}
MP4_ALLOWED = {"ftyp", "free", "moov", "mdat", "mvhd", "trak", "tkhd", "edts", "elst", "mdia", "mdhd",
               "hdlr", "minf", "vmhd", "dinf", "dref", "stbl", "stsd", "stts", "stss", "ctts", "stsc",
               "stsz", "stco", "co64", "sdtp", "udta", "meta", "ilst"}
# A copy's PNG carries exactly the chunks copy_panel keeps (PNG_KEEP): no pHYs, no text, no time, no EXIF.
FORMAT_TAGS = {"major_brand", "minor_version", "compatible_brands"}   # ffprobe reads these from ftyp
STREAM_TAGS = {"language": "und", "handler_name": "VideoHandler"}
# Hosted sources known to carry C2PA credentials (two Runway engines, one MiniMax): the detector's positive control.
REAL_C2PA_SOURCES = ("runs/gen4.5/cu-line-2_burst_gen45.mp4", "runs/gen4_turbo/cu-line-2_burst_gen4t.mp4",
                     "runs/h3-fal/cu-line-2_burst_h3.mp4")
CONTROL_FINDS = ("box /uuid not allowed", "provenance bytes: C2PA uuid", "provenance bytes: C2PA JUMBF type")


def mp4_boxes(data):
    """[(path, start, payload_start, end)] for every box, descending into containers."""
    boxes = []

    def walk(off, end, path):
        while off < end:
            if end - off < 8:
                raise ValueError(f"truncated box at {off}")
            size, typ = struct.unpack(">I4s", data[off:off + 8])
            hdr = 8
            if size == 1:
                if end - off < 16:
                    raise ValueError(f"truncated box at {off}")
                size, hdr = struct.unpack(">Q", data[off + 8:off + 16])[0], 16
            elif size == 0:
                size = end - off
            if size < hdr or off + size > end:
                raise ValueError(f"bad box size at {off}")
            t = typ.decode("latin-1")
            boxes.append((f"{path}/{t}", off, off + hdr, off + size))
            if t in MP4_CONTAINERS:
                walk(off + hdr, off + size, f"{path}/{t}")
            elif t == "meta":
                if size < hdr + 4:
                    raise ValueError(f"bad box size at {off}")        # no room for the version and flags
                walk(off + hdr + 4, off + size, f"{path}/{t}")   # a full box: version and flags first
            off += size

    walk(0, len(data), "")
    return boxes


def provenance_hits(data, payload, low=None):
    """C2PA/JUMBF traces. The long signatures are searched everywhere; the four-byte tokens
    only outside the compressed payload, where a chance match is impossible to tell apart.
    `low` is _outside(data, payload) when the caller has it already."""
    hits = [name for name, sig in (("C2PA uuid", C2PA_BMFF_UUID), ("C2PA JUMBF type", C2PA_JUMBF_TYPE))
            if sig in data]
    low = _outside(data, payload) if low is None else low
    return hits + [t.decode() for t in SHORT_TOKENS if t in low]


def _outside(data, payload):
    """The bytes lower-cased, with the compressed payload ranges blanked."""
    masked = bytearray(data)
    for a, b in payload:
        masked[a:b] = bytes(b - a)
    return bytes(masked).lower()


def encoder_hits(data, payload, low=None):
    """Traces of the encoder: its long SEI string anywhere, its short tags outside the payload."""
    low = _outside(data, payload) if low is None else low
    return (["H.264/MPEG-4 AVC codec string"] if X264_SEI_TAIL in data else []) \
        + [t.decode() for t in ENCODER_TOKENS if t in low]


def check_mp4_bytes(path):
    data = Path(path).read_bytes()
    try:
        boxes = mp4_boxes(data)
    except ValueError as e:
        return [f"unreadable box structure: {e}"]
    names = {b[0] for b in boxes}
    p = [f"box {top} is missing" for top in ("/ftyp", "/moov") if top not in names]
    p += [f"box {b[0]} not allowed" for b in boxes if b[0].rsplit("/", 1)[1] not in MP4_ALLOWED]
    p += [f"metadata list {b[0]} is not empty" for b in boxes if b[0].endswith("/ilst") and b[3] - b[1] != 8]
    p += [f"box {b[0]} at byte {b[1]} carries data" for b in boxes
          if b[0].rsplit("/", 1)[1] == "free" and any(data[b[2]:b[3]])]          # padding is empty or all zero
    payload = [(b[2], b[3]) for b in boxes if b[0] == "/mdat"]
    low = _outside(data, payload)                                               # blanked and lower-cased once
    p += [f"provenance bytes: {h}" for h in provenance_hits(data, payload, low)]
    return p + [f"encoder text: {h}" for h in encoder_hits(data, payload, low)]


def check_png_bytes(path):
    data = Path(path).read_bytes()
    try:
        chunks = png_chunks(data, strict=True)
    except ValueError as e:
        return [f"unreadable PNG: {e}"]
    p = [f"chunk {t} not allowed" for t, _ in chunks if t not in PNG_KEEP]
    payload, off = [], len(PNG_SIG)
    for t, c in chunks:                       # chunk = length, type, data, CRC: the compressed data is c[8:-4]
        if t == "IDAT":
            payload.append((off + 8, off + len(c) - 4))
        off += len(c)
    return p + [f"provenance bytes: {h}" for h in provenance_hits(data, payload)]


def count_frames(path):
    return int(run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                    "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", path]).strip())


def frame_gaps(path):
    """The set of distances between consecutive frame timestamps, in the stream's own time base
    (integers, so no rounding). A constant-rate clip has exactly one."""
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts",
               "-of", "csv=p=0", path])
    try:
        pts = sorted(int(line.strip().rstrip(",")) for line in out.splitlines() if line.strip())
    except ValueError:
        raise RuntimeError("a video packet has no timestamp") from None
    return {b - a for a, b in zip(pts, pts[1:])}


def _check_copy_streams(path, size):
    try:
        info = probe(path)
    except (RuntimeError, ValueError) as e:        # ValueError: ffprobe printed something that is not a number or JSON
        return [f"unreadable: {e}"]
    p = []
    if info["stream_types"] != ["video"]:
        p.append(f"streams {info['stream_types']}, expected one video stream")
    if (info["codec"], info["pix_fmt"]) != ("h264", "yuv420p"):
        p.append(f"{info['codec']} {info['pix_fmt']}, expected h264 yuv420p")
    if (info["width"], info["height"]) != tuple(size):
        p.append(f"size {info['width']}x{info['height']}, expected {size[0]}x{size[1]}")
    if info["r_frame_rate"] != f"{FPS}/1" or info["avg_frame_rate"] != f"{FPS}/1":
        p.append(f"rate {info['r_frame_rate']} / {info['avg_frame_rate']}, expected {FPS}/1")
    if info["nb_frames"] != FRAMES:
        p.append(f"{info['nb_frames']} frames in the container, expected {FRAMES}")
    try:                                           # each ffprobe read stands alone: one failing keeps the others' findings
        decoded = count_frames(path)
        if decoded != FRAMES:
            p.append(f"{decoded} decoded frames, expected {FRAMES}")
    except (RuntimeError, ValueError) as e:
        p.append(f"unreadable: {e}")
    try:
        gaps = frame_gaps(path)
        if len(gaps) != 1:
            p.append(f"{len(gaps)} distinct frame intervals (expected 1)")
    except (RuntimeError, ValueError) as e:
        p.append(f"unreadable: {e}")
    extra = set(info["format_tags"]) - FORMAT_TAGS
    if extra:
        p.append(f"container tags {sorted(extra)}")
    for tags in info["stream_tags"]:
        bad = {k: v for k, v in tags.items() if STREAM_TAGS.get(k) != v}
        if bad:
            p.append(f"stream tags {bad}")
    return p


def check_copy(path, size):
    """Problems with one rating copy (empty when it is clean). A file ffprobe cannot read is a
    problem, not a crash; the byte checks run regardless."""
    return _check_copy_streams(path, size) + check_mp4_bytes(path)


TREE_FILES = ("runs/manifest.jsonl", "tools/build_release.py")      # present in the private tree only


def tree_problems(root, tree):
    """The caller says which tree this is; the files that tell them apart must agree. The private
    tree has the run manifest and the release script, the public one has neither."""
    if tree not in ("private", "public"):
        raise ValueError(f"tree must be 'private' or 'public', not {tree!r}")
    present = {rel: (Path(root) / rel).is_file() for rel in TREE_FILES}
    if tree == "private":
        return [f"private tree: {rel} is missing" for rel, ok in present.items() if not ok]
    return [f"public tree: {rel} exists (this is the private tree)" for rel, ok in present.items() if ok]


def positive_control(root, tree):
    """(problems, sources checked). The detector must find what hosted sources really carry. Reads
    bytes only. `tree` is "private" or "public" (see tree_problems). In the private tree every
    source must be there to be checked, so a control that checks nothing cannot pass; the public
    tree may have none of them."""
    p, checked = tree_problems(root, tree), 0
    for rel in REAL_C2PA_SOURCES:
        f = Path(root) / rel
        if f.is_file():
            checked += 1
            found = check_mp4_bytes(f)
            p += [f"{rel}: detector missed {need!r} (the box may have moved: the source was changed, "
                  "or CONTROL_FINDS needs updating)" for need in CONTROL_FINDS if need not in found]
    need = len(REAL_C2PA_SOURCES)
    if tree == "private" and checked < need:
        p.append(f"positive control: {checked} of {need} hosted sources checked, {need} needed")
    return p, checked


class PrivateTerm:
    """A term from private-terms.txt. A hit is reported by its line number in that file, never by the
    term or the text it matched, so no report spells it."""
    def __init__(self, n, term):
        self.n, self.term = n, term


def parse_banned(text, private=False):
    """(terms, problems). A plain line is a case-insensitive substring; /pattern/ or /pattern/i is a
    regular expression. A line that cannot be loaded is a problem naming it, never a crash, and a
    list that loads no term at all is a problem (it would let everything through). With `private`
    each term is a PrivateTerm (see there)."""
    terms, problems = [], []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.fullmatch(r"/(.+)/([a-z]*)", s)
        if not m:
            term = s
        elif m.group(2) not in ("", "i"):
            problems.append(f"banned-terms line {n}: flags {m.group(2)!r} not supported (only 'i')")
            continue
        else:
            try:
                term = re.compile(m.group(1), re.I if m.group(2) else 0)
            except re.error as e:
                problems.append(f"banned-terms line {n}: bad regular expression ({e})")
                continue
        terms.append(PrivateTerm(n, term) if private else term)
    if not terms:
        problems.append("no banned terms loaded")
    return terms, problems


def load_private_terms(path=None):
    """(terms, problems) from private-terms.txt: terms is None when the file is absent (the public
    tree has none, and the checks then run with the public list only), else a list of PrivateTerm.
    A file that is present but unreadable or empty is a problem, never a silent pass."""
    path = Path(PRIVATE_TERMS if path is None else path)
    if not path.is_file():
        return None, []
    try:
        text = read_text(path)
    except (OSError, ValueError) as e:
        return [], [f"{PRIVATE_TERMS_NAME}: unreadable ({getattr(e, 'strerror', None) or e})"]
    terms, bad = parse_banned(text, private=True)
    return terms, [f"{PRIVATE_TERMS_NAME}: {x}" for x in bad]


def private_terms_note(here=None):
    """One line saying which banned list the checks ran with."""
    terms, _ = load_private_terms(None if here is None else Path(here) / PRIVATE_TERMS_NAME)
    if terms is None:
        return (f"private terms: {PRIVATE_TERMS_NAME} is absent (the public tree has none): "
                "checks ran with the public list only")
    return f"private terms: {len(terms)} loaded from {PRIVATE_TERMS_NAME}"


_ZERO_WIDTH = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff"))


def deobfuscate(text):
    """`text` with the usual ways of splitting a word undone, for scanning only: adjacent string
    literals joined ("a" "b", "a" + "b", 'a' + 'b'), single-character classes opened (a[b]c),
    \\xHH and \\uHHHH escapes decoded, zero-width characters and soft hyphens dropped."""
    text = text.translate(_ZERO_WIDTH)
    text = re.sub(r"""(["'])\s*\+?\s*(["'])""", "", text)
    text = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    return re.sub(r"\[(.)\]", r"\1", text)


def find_banned(text, banned):
    low, hits = text.lower(), []
    for b in banned:
        priv = isinstance(b, PrivateTerm)
        t = b.term if priv else b
        if isinstance(t, str):
            if t.lower() in low:
                hits.append(f"private term {b.n}" if priv else t)
        else:
            m = t.search(text)
            if m:
                hits.append(f"private term {b.n}" if priv else f"/{t.pattern}/ -> {m.group(0)}")
    return hits


SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _is_int(v):
    """An integer size: bool is an int subclass in Python, and True is not a width."""
    return isinstance(v, int) and not isinstance(v, bool)


def _record_problems(name, rec, fields):
    """Problems with one media-sources record: not an object, a missing field, a copy path that
    leaves media/, a hash that is not a SHA-256 digest."""
    if not isinstance(rec, dict):
        return [f"{name}: not an object"]
    p = [f"{name}: missing field {f!r}" for f in fields if f not in rec]
    copy = rec.get("copy")
    if "copy" in rec and not (isinstance(copy, str) and copy.startswith("media/") and len(copy) > len("media/")
                              and "\\" not in copy and ".." not in copy.split("/")):
        p.append(f"{name}: copy path {copy!r} must be a file inside media/")
    if "copy_sha256" in rec and not (isinstance(rec["copy_sha256"], str) and SHA256_RE.fullmatch(rec["copy_sha256"])):
        p.append(f"{name}: copy_sha256 is not a SHA-256 hex digest")
    return p


def check_study(spec, here):
    """(problems, hashes). Problems with one study's media-sources.json and the copies it lists
    (empty when clean); hashes maps each clip copy's path under `here` ("burst/media/<id>.mp4")
    to its SHA-256, for rating-copies.sha256. A record with a missing or bad field is reported by
    name and left out of the later checks; a media-sources.json without clips or panels objects
    returns just that problem and {}."""
    sdir = Path(here) / spec["dir"]
    try:
        src = json.loads(read_text(sdir / "media-sources.json"))
    except ValueError as e:                      # bad JSON or bad UTF-8 (JSONDecodeError and UnicodeDecodeError)
        return [f"media-sources.json: not valid JSON ({e})"], {}
    if not isinstance(src, dict):
        return ["media-sources.json: not a JSON object"], {}
    clips, panels = src.get("clips"), src.get("panels")
    for key, val in (("clips", clips), ("panels", panels)):
        if not isinstance(val, dict):
            return [f"media-sources.json: no '{key}' object"], {}
    p = []
    if len(clips) != spec["n_clips"]:
        p.append(f"{spec['id']}: {len(clips)} items, expected {spec['n_clips']}")
    if any("-r2" in cid for cid in clips):
        p.append(f"{spec['id']}: a re-roll (-r2) item")
    if len(panels) != spec["n_panels"]:
        p.append(f"{spec['id']}: {len(panels)} panels, expected {spec['n_panels']}")
    good_panels, good_clips = {}, {}
    for pid, rec in panels.items():
        bad = _record_problems(pid, rec, ("copy", "copy_sha256", "width", "height"))
        if not bad:
            bad = [f"{pid}: {k} is not an integer" for k in ("width", "height") if not _is_int(rec[k])]
        p += bad
        if not bad:
            good_panels[pid] = rec
    for cid, rec in clips.items():
        bad = _record_problems(cid, rec, ("panel", "engine", "copy", "copy_sha256", "source_video"))
        if not bad:
            sv = rec["source_video"]
            for k in ("width", "height"):
                if not isinstance(sv, dict) or k not in sv:
                    bad.append(f"{cid}: source_video has no {k}")
                elif not _is_int(sv[k]):
                    bad.append(f"{cid}: source_video {k} is not an integer")
        p += bad
        if not bad:
            good_clips[cid] = rec
    listed = {rec["copy"] for rec in (*good_panels.values(), *good_clips.values())}
    if (sdir / "media").is_dir():                # a stray file in media/ could be served; nothing unlisted may sit there
        p += [f"{f.relative_to(sdir).as_posix()}: a file that media-sources.json does not list"
              for f in sorted((sdir / "media").rglob("*")) if f.is_file() and f.relative_to(sdir).as_posix() not in listed]
    hashes, panel_hashes = {}, {}
    for pid, rec in good_panels.items():
        f = sdir / rec["copy"]
        if not f.is_file():
            p.append(f"{pid}: panel copy missing")
            continue
        h = sha256_file(f)
        if h != rec["copy_sha256"]:
            p.append(f"{pid}: panel copy hash differs from media-sources.json")
        panel_hashes[f"{spec['dir']}/{rec['copy']}"] = h
        bad = check_png_bytes(f)
        p += [f"{pid}: {x}" for x in bad]
        if not any(x.startswith("unreadable PNG") for x in bad):
            w, h_ = png_size(f)
            if (w, h_) != (rec["width"], rec["height"]):
                p.append(f"{pid}: panel copy is {w}x{h_}, media-sources.json records {rec['width']}x{rec['height']}")
            elif (h_ > w) != (pid == TANK_PANEL):
                p.append(f"{pid}: a {'portrait' if h_ > w else 'landscape'} panel, "
                         f"expected {'portrait' if pid == TANK_PANEL else 'landscape'}")
    for cid, rec in good_clips.items():
        f = sdir / rec["copy"]
        if not f.is_file():
            p.append(f"{cid}: copy missing")
            continue
        h = sha256_file(f)
        if h != rec["copy_sha256"]:
            p.append(f"{cid}: copy hash differs from media-sources.json")
        hashes[f"{spec['dir']}/{rec['copy']}"] = h
        sv = rec["source_video"]
        size = PORTRAIT if sv["height"] > sv["width"] else LANDSCAPE
        p += [f"{cid}: {x}" for x in check_copy(f, size)]
    by_hash = {}
    for name, h in {**panel_hashes, **hashes}.items():
        by_hash.setdefault(h, []).append(name)
    p += [f"{' and '.join(names)} are identical files" for names in by_hash.values() if len(names) > 1]
    return p + orientation_problems(spec, good_clips, good_panels), hashes


def orientation_problems(spec, clips, panels):
    """Every clip names a panel in `panels` and one of the five engines. Exactly the tank row is
    portrait, on every engine; every other row is landscape. A full study also has exactly one
    clip per panel and engine (a pilot or a small test tree has fewer)."""
    rows, counts, p = {}, Counter(), []
    for cid, rec in clips.items():
        if rec["panel"] not in panels:
            p.append(f"{cid}: panel {rec['panel']!r} is not in panels")
        if rec["engine"] not in ENGINES:
            p.append(f"{cid}: engine {rec['engine']!r} is not one of the five")
        counts[(rec["panel"], rec["engine"])] += 1
        sv = rec["source_video"]
        rows.setdefault(rec["panel"], set()).add(sv["height"] > sv["width"])
    for pid, tall in sorted(rows.items()):
        if len(tall) != 1:
            p.append(f"{pid}: engines disagree on orientation")
            continue
        (tall,) = tall
        if tall != (pid == TANK_PANEL):
            p.append(f"{pid}: a {'portrait' if tall else 'landscape'} row, expected {'portrait' if pid == TANK_PANEL else 'landscape'}")
    if not spec.get("cells") and spec["n_clips"] == spec["n_panels"] * len(ENGINES):
        p += [f"{pid}: {counts[(pid, e)]} clips from {e}, expected 1"
              for pid in sorted(panels) for e in ENGINES if counts[(pid, e)] != 1]
    return p


def shipping_files(here, rules):
    """(listed, unlisted): the SHIPPING files (and any OPTIONAL_SHIPPING one) that exist, and
    the files the release would ship that SHIPPING does not list. The release's own rule is
    required: without it the unlisted files cannot be found, and that is not passed over."""
    here = Path(here)
    listed = [r for r in (*SHIPPING, *OPTIONAL_SHIPPING) if (here / r).is_file()]
    found = {f.relative_to(here).as_posix() for f in here.rglob("*")
             if rules.a9_shippable(f, here, rules.ADHERENCE_SUFFIXES)}
    return listed, sorted(found - set(listed))


def check_shipping(here, root, tree, require_all=True):
    """(problems, files scanned). Every shipping file passes the release build's rewrite unchanged
    and its leak scan, judged on the bytes the release would read and write. `tree` is "private" or
    "public" (see tree_problems). The public tree has been through the release rules and nothing is
    scanned there: ([], 0), or the mismatch if it turns out to be the private tree. In the private
    tree a SHIPPING file that is absent is a problem (the ratings files exist only after Gates E and
    E2, and OPTIONAL_SHIPPING ones only sometimes, so those are exempt; require_all=False skips the
    rest while the folder is still being built), and so is scanning nothing. A file the release would
    ship that SHIPPING does not list is a problem and is scanned too. When private-terms.txt is present
    each of these files is also scanned for the private terms, as written and with split strings and
    character classes joined; the file itself is never listed or shipped."""
    p = tree_problems(root, tree)
    rules = release_rules(root) if tree == "private" else None
    if rules is None:
        return p, 0
    here = Path(here)
    if require_all:
        p += [f"{rel}: a shipping file that is absent" for rel in SHIPPING
              if not rel.startswith("ratings-") and not (here / rel).is_file()]
    if hasattr(rules, "a9_shippable") and hasattr(rules, "ADHERENCE_SUFFIXES"):
        listed, unlisted = shipping_files(here, rules)
    else:
        p.append("the release rules define no a9_shippable or ADHERENCE_SUFFIXES: "
                 "files the release would ship cannot be listed")
        listed, unlisted = [r for r in (*SHIPPING, *OPTIONAL_SHIPPING) if (here / r).is_file()], []
    p += [f"{rel}: the release would ship this file but SHIPPING does not list it" for rel in unlisted]
    for rel in (*listed, *unlisted):
        raw = (here / rel).read_bytes()
        try:
            text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")      # what read_text gives the release
        except UnicodeDecodeError:
            p.append(f"{rel}: not UTF-8")
            continue
        hit = rules.LEAK_RE.search(text)
        if hit:
            p.append(f"{rel}: release leak scan hit {hit.group(0)!r}")
        try:
            written = rules.rewrite_text(f"analysis/adherence/{rel}", text, [])
        except SystemExit as e:
            p.append(f"{rel}: the release rewrite stops on this file ({e})")
            continue
        if written.encode("utf-8") != raw:
            p.append(f"{rel}: the release build would rewrite this file (its hash would change)")
    private, bad = load_private_terms(here / PRIVATE_TERMS_NAME)
    p += bad
    if private:
        for rel in (*listed, *unlisted):
            try:
                text = (here / rel).read_bytes().decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue                                  # reported above
            hits = dict.fromkeys(find_banned(text, private) + find_banned(deobfuscate(text), private))
            p += [f"{rel}: {h}, in the file or once its split strings and character classes are joined" for h in hits]
    scanned = len(listed) + len(unlisted)
    if scanned == 0:
        p.append("private tree: 0 shipping files scanned")
    return p, scanned


# ---------------------------------------------------------------- the study files
def opaque_code(seed, kind, item_id):
    """blindpanel's seeded code (src/core/codes.ts): "c" or "p" plus five base32 characters from the
    first 25 bits of sha256("<seed>:code:<kind>:<id>"). `analysis/a9_adherence.py slim` calls this to
    map the codes in an export back to cells, so the name and signature are fixed; a test pins literal
    codes produced by blindpanel itself and, with BLINDPANEL set, compares every real id."""
    if kind not in ("clip", "panel"):
        raise ValueError(f"kind must be 'clip' or 'panel', not {kind!r}")
    alphabet = "0123456789abcdefghjkmnpqrstvwxyz"
    bits = int.from_bytes(hashlib.sha256(f"{seed}:code:{kind}:{item_id}".encode("utf-8")).digest()[:4], "big")
    out = ""
    for _ in range(5):
        out += alphabet[(bits >> 27) & 31]
        bits = (bits << 5) & 0xFFFFFFFF
    return ("c" if kind == "clip" else "p") + out


def question_text(spec):
    """The question text as registered (amendment A9.3): the study's quoted motion clause inside a fixed
    frame. It is locked into study.lock.json's wording hash and registered, so never reword it: change the
    constants and re-lock at Gate C instead."""
    return f'The clip was asked for this motion: **"{spec["clause"]}"** Does the clip do it?'


def study_config(spec, sources):
    """The blindpanel config for one study, from its media-sources.json. Every clip is labelled "clip"
    with no meta and no link, and there is no `reference` block: reveal.json (fetchable on the dev
    server) then holds nothing about engine, panel or motion class."""
    q = spec["question"]
    return {
        "blindpanel": 1,
        "id": spec["id"],
        "title": spec["title"],
        "instrument": INSTRUMENT,
        "media": {"base": "./media/", "origins": []},
        "blinding": {"seed": spec["seed"], "banned_terms_file": "banned-terms.txt", "embedded_provenance": "allow"},
        "scales": {q["id"]: {"labels": list(spec["labels"])}},
        "questions": [{"id": q["id"], "short": q["short"], "part": "clips", "text": question_text(spec),
                       "direction": q["direction"], "notes": [q["note"]], "scale": q["id"]}],
        "parts": {"clips": {"intro": list(INTRO), "watch_note": WATCH_NOTE, "clip_seconds": 5,
                            "session_size": len(sources["clips"]), "extend": False,
                            "video": {"loop": True, "autoplay": "unless_reduced_motion"}}},
        "items": {
            "panels": [{"id": pid, "file": Path(r["copy"]).name, "sha256": r["copy_sha256"]}
                       for pid, r in sorted(sources["panels"].items())],
            "clips": [{"id": cid, "reference": r["panel"], "file": Path(r["copy"]).name,
                       "sha256": r["copy_sha256"], "label": "clip", "meta": {}}
                      for cid, r in sorted(sources["clips"].items())],
        },
        "modes": {"public": {"submit": True, "tally": False}},
    }


YAML_KEY = re.compile(r"[a-z_][a-z0-9_]*")
YAML_WORDS = {"yes", "no", "on", "off", "true", "false", "null"}      # YAML 1.1 reads these keys as non-strings
YAML_SPACE = "\t\n"       # the only controls allowed in a string: json.dumps writes them as the escapes \t and \n


def _text(s):
    """A string that can go into a YAML double-quoted scalar: any C0 or C1 control (U+007F and U+0085
    among them) other than tab and newline, a lone surrogate, a line or paragraph separator, a byte-order
    mark or U+FFFE/U+FFFF is refused. (json.dumps escapes the first block and leaves the rest raw.)"""
    for ch in s:
        if ch not in YAML_SPACE and (unicodedata.category(ch) in ("Cc", "Cs", "Zl", "Zp") or ch in "\ufeff\ufffe\uffff"):
            raise ValueError(f"string {s[:30]!r} has the non-printable character U+{ord(ch):04X}")
    return json.dumps(s, ensure_ascii=False)       # a JSON string is a YAML double-quoted scalar


def _scalar(v):
    """One scalar as YAML. A shape this writer does not support (a non-empty list or mapping where a scalar
    belongs, a tuple, a set, bytes, a number that is not finite) is an error, never written as something else."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, int):
        return repr(v)
    if isinstance(v, float):
        if not math.isfinite(v):
            raise TypeError(f"cannot write {v!r} as YAML here: not a finite number")
        text = repr(v)
        return text.replace("e", ".0e") if re.fullmatch(r"-?\d+e[-+]\d+", text) else text    # YAML wants 1.0e+22, not 1e+22
    if isinstance(v, str):
        return _text(v)
    if isinstance(v, dict) and not v:
        return "{}"
    if isinstance(v, list) and not v:
        return "[]"
    raise TypeError(f"cannot write a {type(v).__name__} as a YAML scalar here: {str(v)[:40]!r}")


def _key(k):
    if not isinstance(k, str):
        raise TypeError(f"YAML key {k!r} is not a string")
    if not YAML_KEY.fullmatch(k) or k in YAML_WORDS:
        raise ValueError(f"YAML key {k!r} is not a plain lower-case name (letters, digits, underscores)")
    return k


def to_yaml(v, indent=0):
    """The small YAML subset study_config uses: mappings, sequences, every string a double-quoted
    scalar. (An empty mapping or sequence is written inline.) Anything outside that subset is a TypeError
    or ValueError (see _scalar, _text, _key), never written as something else. The top level is a mapping
    or a sequence."""
    pad = "  " * indent
    lines = []
    if isinstance(v, dict):
        for k, x in v.items():
            if isinstance(x, (dict, list)) and x:
                lines += [f"{pad}{_key(k)}:", to_yaml(x, indent + 1)]
            else:
                lines.append(f"{pad}{_key(k)}: {_scalar(x)}")
    elif isinstance(v, list):
        for x in v:
            if isinstance(x, dict) and x:
                body = to_yaml(x, indent + 1).split("\n")
                lines += [f"{pad}- {body[0].lstrip()}", *body[1:]]
            else:
                lines.append(f"{pad}- {_scalar(x)}")
    else:
        raise TypeError(f"to_yaml writes a mapping or a sequence, not a {type(v).__name__}")
    return "\n".join(lines)


def write_study(spec, here):
    """Write the study's study.yaml and banned-terms.txt next to its media-sources.json (UTF-8, Unix
    newlines, the same bytes every run). A media-sources.json of the wrong size is a ValueError and
    nothing is written."""
    sdir = Path(here) / spec["dir"]
    sources = json.loads(read_text(sdir / "media-sources.json"))
    n_clips, n_panels = len(sources["clips"]), len(sources["panels"])
    if (n_clips, n_panels) != (spec["n_clips"], spec["n_panels"]):       # nothing is written for a wrong-size study
        raise ValueError(f"{spec['id']}: media-sources.json has {n_clips} clips and {n_panels} panels, "
                         f"expected {spec['n_clips']} clips and {spec['n_panels']} panels")
    head = ("# Generated by prepare.py for amendment A9. Do not edit by hand: change prepare.py,\n"
            "# rerun `prepare.py write`, then `blindpanel lock` (see the A9 plan).\n")
    write_text(sdir / "study.yaml", head + to_yaml(study_config(spec, sources)) + "\n")
    write_text(sdir / "banned-terms.txt", BANNED_TERMS)


# ---------------------------------------------------------------- the build and its record
CLIP_REVEAL = {"label": "clip", "meta": {}}        # what reveal.json may say about a clip, exactly
REVEAL_KEYS = {"study", "items", "reference"}
MEDIA_SUFFIXES = {".mp4", ".png"}
BINARY_CONTROLS = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]")      # controls other than tab, newline, carriage return
MIN_LITERAL = 4                                    # shorter ids ("h3") would match ordinary text; the banned list covers them

# The keys study.json may hold, exactly as blindpanel 0.1.0 writes them (checked against a real build by
# the BLINDPANEL-gated test). LEAF: a scalar, or a list of scalars. A dict is an object with those keys only
# ("*": any key, one shape); a one-element list is a list of objects of that shape. `meta` must be {} if present.
LEAF = None
STUDY_SHAPE = {
    "blindpanel": LEAF, "id": LEAF, "instrument": LEAF, "text_sha256": LEAF, "seed": LEAF, "title": LEAF,
    "privacy": LEAF,
    "scales": {"*": {"min": LEAF, "max": LEAF, "labels": LEAF}},
    "questions": [{"id": LEAF, "short": LEAF, "part": LEAF, "text": LEAF, "direction": LEAF, "notes": LEAF,
                   "intro_notes": LEAF, "scale": LEAF}],
    "panels": [{"code": LEAF, "image": LEAF, "meta": {}}],
    "parts": {"baseline": LEAF,
              "clips": {"intro": LEAF, "watch_note": LEAF, "clip_seconds": LEAF, "session_size": LEAF, "extend": LEAF,
                        "video": {"loop": LEAF, "muted": LEAF, "autoplay": LEAF},
                        "items": [{"code": LEAF, "video": LEAF, "reference": LEAF, "meta": {}}]}},
    "modes": {"public": {"submit": LEAF, "tally": LEAF, "min_crowd_n": LEAF}},
    "endpoints": {"submit": LEAF, "tally": LEAF, "reveal": LEAF},
}


def shape_problems(value, shape, path=""):
    """Where `value` leaves `shape` (see STUDY_SHAPE): an extra key, or the wrong kind of value. Paths use []
    for list elements, never an index, and a message never quotes a value."""
    where = path or "the file"
    if shape is LEAF:
        scalar = lambda v: not isinstance(v, (dict, list))
        if scalar(value) or (isinstance(value, list) and all(scalar(x) for x in value)):
            return []
        return [f"{where} should be a plain value or a list of them"]
    if isinstance(shape, list):
        if not isinstance(value, list):
            return [f"{where} should be a list"]
        return [x for item in value for x in shape_problems(item, shape[0], path + "[]")]
    if not isinstance(value, dict):
        return [f"{where} should be an object"]
    out = []
    for key, sub in value.items():
        here = f"{path}.{key}" if path else key
        if key in shape:
            out += shape_problems(sub, shape[key], here)
        elif "*" in shape:
            out += shape_problems(sub, shape["*"], here)
        else:
            out.append(f"{here} is not an allowed key")
    return out


def dist_files(dist):
    """(files, problems) under `dist`: every regular file as a path relative to it, in path order, and a
    problem for anything else: a symlink (never followed), a FIFO, socket or device (never opened, which
    could hang), an unreadable folder, or a name that is not valid UTF-8 (hashing and reporting it would
    fail). Decided with lstat and S_ISREG."""
    dist, files, odd = Path(dist), [], []
    walk = os.walk(dist, onerror=lambda e: odd.append(f"{ascii(str(e.filename))}: cannot be read ({e.strerror})"))
    for base, dirs, names in walk:
        for name in dirs + names:
            path = Path(base) / name
            rel = path.relative_to(dist)
            try:
                rel.as_posix().encode("utf-8")
            except UnicodeEncodeError:
                odd.append(f"{ascii(rel.as_posix())}: file name is not valid UTF-8")
                continue
            try:
                mode = os.lstat(path).st_mode
            except OSError as e:
                odd.append(f"{rel.as_posix()}: cannot be read ({e.strerror})")
                continue
            if stat.S_ISLNK(mode):
                odd.append(f"{rel.as_posix()}: a symlink (not followed)")
            elif stat.S_ISREG(mode):
                files.append(rel)
            elif not stat.S_ISDIR(mode):
                odd.append(f"{rel.as_posix()}: not a regular file (a FIFO, socket or device)")
    return sorted(files, key=lambda f: f.parts), sorted(odd)


def tree_hash(dist):
    """SHA-256 over the regular files of a build: each one's relative path and content hash, in path order.
    Any added, removed, renamed or changed file changes it. Names are hashed exactly as the file system
    reports them, with no Unicode normalisation (NFC or NFD): blindpanel names its files with ASCII codes,
    so the two cannot differ in a real build. Entries dist_files reports as problems are left out; the hash
    means something only beside a clean check_build."""
    dist, h = Path(dist), hashlib.sha256()
    for rel in dist_files(dist)[0]:
        h.update(f"{rel.as_posix()}\0{sha256_file(dist / rel)}\n".encode("utf-8"))
    return h.hexdigest()


def _load_object(path, label):
    """(object, problem): a JSON object from a file, or None and a problem naming `label`."""
    try:
        doc = json.loads(read_text(path))
    except FileNotFoundError:
        return None, f"{label}: missing"
    except (OSError, ValueError) as e:                  # ValueError: bad JSON or bad UTF-8
        return None, f"{label}: not valid JSON ({e})"
    if not isinstance(doc, dict):
        return None, f"{label}: not a JSON object"
    return doc, None


def _dig(doc, *keys):
    for k in keys:
        doc = doc.get(k) if isinstance(doc, dict) else None
    return doc


def _str(value):
    """The value if it is a string, else None: a code or path in a built file may be any JSON type."""
    return value if isinstance(value, str) else None


def is_text(data):
    """Bytes that are UTF-8 text: they decode, and hold no control character but tab, newline and carriage return."""
    try:
        return BINARY_CONTROLS.search(data.decode("utf-8")) is None
    except UnicodeDecodeError:
        return False


def _objects(value):
    return isinstance(value, list) and all(isinstance(x, dict) for x in value)


def _media_path(rel):
    """A path from study.json that stays inside the build, or None."""
    if not isinstance(rel, str) or not rel or "\\" in rel or rel.startswith("/"):
        return None
    parts = rel.split("/")
    return rel if all(x not in ("", ".", "..") for x in parts) else None


def _hits(text, terms, literals, where=""):
    """What `text` must not contain: a banned term, or one of the literal ids (case-insensitive)."""
    low = text.lower()
    return [f"{where}banned term {h}" for h in find_banned(text, terms)] + \
           [f"{where}{label}" for lit, label in literals if lit in low]


def _load_build(spec, sdir, dist):
    """The inputs a build is checked against, with a problem for each one that is missing or wrong:
    a namespace with problems, terms, sources/lock/study/reveal (None when unusable) and the seeded
    code tables clips, panels, clip_code ({code: cell id}) and panel_code ({panel id: code})."""
    b = SimpleNamespace(problems=[], sources=None, lock=None, study=None, reveal=None)
    b.terms, bad = parse_banned(BANNED_TERMS)
    b.problems += bad
    private, bad = load_private_terms(Path(sdir).parent / PRIVATE_TERMS_NAME)
    b.problems += bad
    b.terms += private or []          # absent in the public tree: the public list alone
    try:
        if (sdir / "banned-terms.txt").read_bytes() != BANNED_TERMS.encode("utf-8"):
            b.problems.append("banned-terms.txt: differs from BANNED_TERMS in prepare.py (rerun `write`)")
    except OSError as e:
        b.problems.append(f"banned-terms.txt: unreadable ({e.strerror or e})")
    for name, path, label in (("sources", sdir / "media-sources.json", "media-sources.json"),
                              ("lock", sdir / "study.lock.json", "study.lock.json"),
                              ("study", dist / "study.json", "study.json"),
                              ("reveal", dist / "reveal.json", "reveal.json")):
        setattr(b, name, None)
        doc, bad = _load_object(path, label)
        if bad:
            b.problems.append(bad)
        setattr(b, name, doc)
    if b.sources is not None and not (isinstance(b.sources.get("clips"), dict) and isinstance(b.sources.get("panels"), dict)):
        b.problems.append("media-sources.json: no 'clips' and 'panels' objects")
        b.sources = None
    b.clips, b.panels = (b.sources["clips"], b.sources["panels"]) if b.sources else ({}, {})
    b.clip_code = {opaque_code(spec["seed"], "clip", c): c for c in b.clips}
    b.panel_code = {x: opaque_code(spec["seed"], "panel", x) for x in b.panels}
    if b.sources:
        if (len(b.clips), len(b.panels)) != (spec["n_clips"], spec["n_panels"]):
            b.problems.append(f"media-sources.json: {len(b.clips)} clips and {len(b.panels)} panels, "
                              f"expected {spec['n_clips']} clips and {spec['n_panels']} panels")
        if any("-r2" in c for c in b.clips):
            b.problems.append("media-sources.json: a re-roll (-r2) clip")
    if spec["seed"] in A6_SEEDS:
        b.problems.append("seed reuses an A6 seed")
    b.problems += [f"seed: {h}" for h in _hits(spec["seed"], b.terms, [])]
    return b


def _check_study_json(spec, b):
    """(problems, media): study.json against the spec, the lock, the seeded codes and STUDY_SHAPE, and the
    (path, hash) of every clip and panel file it lists."""
    p, media, study = [], [], b.study
    if study is None:
        return p, media
    p += [f"study.json: {x}" for x in shape_problems(study, STUDY_SHAPE)]
    if study.get("id") != spec["id"]:
        p.append(f"study.json: study id {study.get('id')!r}, expected {spec['id']!r}")
    if study.get("seed") != spec["seed"]:
        p.append("study.json: seed differs from the spec")
    if b.lock is not None:
        if study.get("instrument") != b.lock.get("instrument"):
            p.append("study.json: instrument differs from study.lock.json")
        if study.get("text_sha256") != b.lock.get("text_sha256"):
            p.append("study.json: wording hash differs from study.lock.json")
    if _dig(study, "modes", "public", "tally") is not False:
        p.append("study.json: the tally is not off (raters would see each other's answers)")
    items, plist = _dig(study, "parts", "clips", "items"), study.get("panels")
    if not _objects(items):
        p.append("study.json: no parts.clips.items list of objects")
    if not _objects(plist):
        p.append("study.json: no panels list of objects")
    if b.sources and _objects(items):
        codes = [i.get("code") for i in items]
        if not (all(isinstance(c, str) for c in codes) and sorted(codes) == sorted(b.clip_code)):
            p.append("study.json: clip codes differ from the seeded codes of media-sources.json")
        for i in items:
            rec = b.clips.get(b.clip_code.get(_str(i.get("code"))))
            if not isinstance(rec, dict):
                continue
            own = b.panel_code.get(_str(rec.get("panel")))
            if own is None or i.get("reference") != own:
                p.append(f"study.json: clip {i.get('code')} is not beside its own panel (reference)")
            if isinstance(i.get("video"), str):
                media.append((i["video"], rec.get("copy_sha256")))
    if b.sources and _objects(plist):
        codes = [x.get("code") for x in plist]
        if not (all(isinstance(c, str) for c in codes) and sorted(codes) == sorted(b.panel_code.values())):
            p.append("study.json: panel codes differ from the seeded codes of media-sources.json")
        by_code = {c: x for x, c in b.panel_code.items()}
        for x in plist:
            rec = b.panels.get(by_code.get(_str(x.get("code"))))
            if isinstance(rec, dict) and isinstance(x.get("image"), str):
                media.append((x["image"], rec.get("copy_sha256")))
    return p, media


def _check_media(dist, media):
    """(problems, listed): the files study.json lists must be inside media/, listed once, present and
    hash to what media-sources.json records. `listed` holds the paths that are fine (not scanned as text)."""
    p, listed = [], set()
    for path, n in Counter(path for path, _ in media).items():
        if n > 1:
            p.append(f"{path}: listed {n} times in study.json")
    for path, want in media:
        if _media_path(path) is None:
            p.append("study.json: a media path leaves the build")
        elif not path.startswith("media/"):
            p.append(f"{path}: media path outside media/")
        elif not (Path(dist) / path).is_file():
            p.append(f"{path}: media file missing")
        elif sha256_file(Path(dist) / path) != want:
            p.append(f"{path}: media differs from the copy media-sources.json records")
        else:
            listed.add(path)
    return p, listed


def _check_reveal(spec, b):
    """reveal.json is the one file the page fetches only after the last answer, and nothing may be in it."""
    p, reveal = [], b.reveal
    if reveal is None:
        return p
    if set(reveal) != REVEAL_KEYS:
        p.append(f"reveal.json: top-level keys {sorted(reveal)}, expected {sorted(REVEAL_KEYS)}")
    if reveal.get("study") != spec["id"]:
        p.append(f"reveal.json: study is {reveal.get('study')!r}, expected {spec['id']!r}")
    if reveal.get("reference") is not None:
        p.append("reveal.json: reference is not null (a reference block would name raters or metrics)")
    if "-r2" in json.dumps(reveal).lower():
        p.append("reveal.json: a re-roll (-r2) marker")
    rows = reveal.get("items")
    if not isinstance(rows, dict):
        p.append("reveal.json: items is not an object")
        return p
    if len(rows) != spec["n_clips"]:
        p.append(f"reveal.json: {len(rows)} items, expected {spec['n_clips']}")
    if b.sources and set(rows) != set(b.clip_code):
        p.append("reveal.json: codes differ from the seeded codes of media-sources.json")
    return p + [f"reveal.json: item {code} reveals something (it is not exactly {json.dumps(CLIP_REVEAL)})"
                for code, item in rows.items() if item != CLIP_REVEAL]


def _scan_files(dist, files, listed, terms, ids):
    """Every file's path, and every file's content unless it is media, against the banned terms and
    the literal ids; a file that is not text and not listed media is a problem."""
    p = []
    for rel in files:
        name = rel.as_posix()
        p += [f"{name}: {h}" for h in _hits(name, terms, ids, "path ")]
        if name in listed:
            continue
        if rel.parts[0] == "media" or rel.suffix in MEDIA_SUFFIXES:   # media are never read as text: a chance match in video bytes means nothing
            p.append(f"{name}: not listed in study.json")
            continue
        try:
            data = (Path(dist) / rel).read_bytes()
        except OSError as e:
            p.append(f"{name}: cannot be read ({e.strerror})")
            continue
        text = data.decode("utf-8", errors="replace")
        seen = [text]
        if rel.suffix in (".json", ".map"):
            try:
                seen.append(json.dumps(json.loads(text), ensure_ascii=False))     # as parsed: escapes undone
            except ValueError:
                pass
        p += [f"{name}: {h}" for h in dict.fromkeys(h for t in seen for h in _hits(t, terms, ids))]
        if not is_text(data):
            p.append(f"{name}: not a text file and not listed media")
    return p


def check_build(spec, here, dist, root, tree, expect_tree=None):
    """(problems, tree hash, files scanned) for a built study; empty problems mean clean. `tree` is
    "private" or "public" (see tree_problems); the private id is searched for in the private tree only.

    Every file of the build is read, and every file's path checked, against the banned terms and the
    literal ids: the study's public cell and panel ids, the five engines' ids and (private tree) the
    private panel id. That includes reveal.json, which blindpanel's own `verify` leaves unscanned, and
    every script of blindpanel's bundle (it names StillDrawn in a comment; that word is not banned). JSON
    is also scanned as parsed, so an escape such as \\u0057 cannot hide a term. Media are not read as text:
    each must be listed once in study.json, inside media/, and hash to media-sources.json's copy_sha256, and
    nothing else may stand in as media. Any other file must be text (is_text); a compressed, archived or
    unknown binary file, a symlink, a FIFO or socket or device, and a name that is not UTF-8 are problems.
    reveal.json must be exactly {study, items, reference} with reference null and one
    {"label": "clip", "meta": {}} per clip. study.json must hold only the keys of STUDY_SHAPE and agree with
    the spec, the lock and the seeded codes, with the tally off. A value of the wrong type in a built file
    is a problem, never a crash. What a report echoes from the build is limited to: the banned term, regular
    expression match or literal id that hit, file paths, key names, the study id, reveal.json's top-level key
    names, counts and the opaque codes of reveal items; none of which maps a code to an engine.
    `expect_tree` is the recorded tree hash, if the caller has one."""
    p = tree_problems(root, tree)
    dist = Path(dist)
    if not dist.is_dir():
        return p + [f"{dist}: is not a directory"], None, 0
    files, odd = dist_files(dist)
    p += odd
    if not files:
        p.append("the build is empty")
    b = _load_build(spec, Path(here) / spec["dir"], dist)
    rules = release_rules(root) if tree == "private" else None
    ids = [(i.lower(), f"cell, panel or engine id {i!r}") for i in [*b.clips, *b.panels, *ENGINES, *ENGINES.values()]
           if len(i) >= MIN_LITERAL]
    if rules:
        ids.append((rules.OLD_ID.lower(), "the private panel id"))
    sp, media = _check_study_json(spec, b)
    mp, listed = _check_media(dist, media)
    p += b.problems + sp + mp + _check_reveal(spec, b) + _scan_files(dist, files, listed, b.terms, ids)
    tree_sha = tree_hash(dist)
    if expect_tree and tree_sha != expect_tree:
        p.append(f"build tree {tree_sha[:12]}… differs from the recorded {expect_tree[:12]}…")
    return p, tree_sha, len(files)


def record_tree(spec, here, dist, tree, replace=False):
    """Record a clean build's tree hash (and the blindpanel version its scripts name) in build-trees.json,
    written atomically; every rater's sitting is checked against it. The pilot is never recorded. A different
    hash already recorded for the study is not replaced unless `replace` is true (SystemExit naming both).
    Returns the hash that was there, or None."""
    if spec["key"] == "pilot":
        raise SystemExit("the pilot build is never recorded")
    versions = sorted({m.decode() for js in Path(dist).rglob("*.js")
                       for m in re.findall(rb"blindpanel@\d+\.\d+\.\d+", js.read_bytes())})
    if not versions:
        raise SystemExit("no blindpanel version (blindpanel@x.y.z) found in the build's scripts: not recording")
    f = Path(here) / "build-trees.json"
    try:
        doc = json.loads(read_text(f)) if f.exists() else {}
    except (OSError, ValueError) as e:
        raise SystemExit(f"build-trees.json: not valid JSON ({e}): not recording over it") from None
    if not isinstance(doc, dict):
        raise SystemExit("build-trees.json: not a JSON object: not recording over it")
    old = doc.get(spec["id"])
    old = old.get("tree_sha256") if isinstance(old, dict) else None
    old = old if isinstance(old, str) else None
    if old and old != tree and not replace:
        raise SystemExit(f"{spec['id']}: build-trees.json records tree {old} but this build is {tree}. "
                         "A recorded build is the one raters sit at: pass --replace-recorded only to re-record "
                         "deliberately (Gate C, before any rating)")
    doc[spec["id"]] = {"tree_sha256": tree, "blindpanel": versions}
    write_text_atomic(f, json.dumps(dict(sorted(doc.items())), indent=1, ensure_ascii=False) + "\n")
    return old


def recorded_tree(spec, here):
    """The tree hash recorded for this study; SystemExit says what is missing."""
    if spec["key"] == "pilot":
        raise SystemExit("the pilot build is never recorded, so --expect-recorded does not apply to it")
    f = Path(here) / "build-trees.json"
    try:
        doc = json.loads(read_text(f))
    except FileNotFoundError:
        raise SystemExit("build-trees.json: not found (record a clean build with check-build --record)") from None
    except (OSError, ValueError) as e:
        raise SystemExit(f"build-trees.json: not valid JSON ({e})") from None
    rec = doc.get(spec["id"]) if isinstance(doc, dict) else None
    tree = rec.get("tree_sha256") if isinstance(rec, dict) else None
    if tree is None:
        raise SystemExit(f"build-trees.json: no recorded tree for {spec['id']} (record a clean build with check-build --record)")
    if not (isinstance(tree, str) and SHA256_RE.fullmatch(tree)):
        raise SystemExit(f"build-trees.json: the tree recorded for {spec['id']} is not a SHA-256 digest")
    return tree


# ---------------------------------------------------------------- command line
def _fail(problems):
    for x in problems:
        print("  ✗", x)
    return 1 if problems else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    ap.add_argument("command", choices=["cells", "media", "write", "check", "check-build"])
    ap.add_argument("--study", choices=sorted(STUDIES), action="append",
                    help="repeatable; default burst and push (check-build needs exactly one)")
    ap.add_argument("--root", default=str(ROOT),
                    help="cells, media, check, check-build: the repository root (manifest, sources, release rules); "
                         "write does not use it")
    ap.add_argument("--tree-kind", choices=["private", "public"],
                    help="check, check-build: which tree this is (default private; the public one has been through "
                         "the release rules and has no run manifest)")
    ap.add_argument("--partial", action="store_true",
                    help="check: shipping files still to be written (lock, build record, README) may be absent")
    ap.add_argument("--dist", help="check-build: the built site (blindpanel build --out)")
    once = ap.add_mutually_exclusive_group()
    once.add_argument("--record", action="store_true", help="check-build: record a clean build's tree in build-trees.json")
    once.add_argument("--expect-recorded", action="store_true", help="check-build: the tree must be the one in build-trees.json")
    once.add_argument("--expect-tree", metavar="HEX", help="check-build: the tree must be this SHA-256")
    ap.add_argument("--replace-recorded", action="store_true",
                    help="check-build --record: replace a different recorded tree (re-recording, Gate C only)")
    a = ap.parse_args(argv)
    if a.command != "check-build" and (a.dist or a.record or a.expect_recorded or a.expect_tree or a.replace_recorded):
        ap.error("--dist, --record, --replace-recorded, --expect-recorded and --expect-tree belong to check-build")
    if a.replace_recorded and not a.record:
        ap.error("--replace-recorded belongs with --record")
    if a.partial and a.command != "check":
        ap.error("--partial belongs to check")
    if a.tree_kind and a.command not in ("check", "check-build"):
        ap.error("--tree-kind belongs to check and check-build")
    if a.expect_tree and not SHA256_RE.fullmatch(a.expect_tree):
        ap.error("--expect-tree wants a lower-case SHA-256 hex digest")
    root, kind = Path(a.root), a.tree_kind or "private"
    keys = list(dict.fromkeys(a.study or ["burst", "push"]))
    specs = [STUDIES[k] for k in keys]

    if a.command in ("cells", "media"):
        if not (root / "runs" / "manifest.jsonl").is_file():
            raise SystemExit(f"{root / 'runs' / 'manifest.jsonl'} not found: the cells come from the private tree's run manifest")
        rules, manifest, problems = release_rules(root), load_manifest(root), []
        for spec in specs:
            cells = select_cells(manifest, spec, root, renames_of(rules))
            problems += validate_cells(cells, spec)
            if rules:
                problems += [f"{c['id']}: private id survives" for c in cells
                             if rules.LEAK_RE.search(c["id"] + c["panel"] + c["source"])]
            print(f"{spec['id']}: {len(cells)} cells on {len({c['panel'] for c in cells})} panels")
            if a.command == "media" and not problems:
                try:
                    build_media(spec, cells, root, HERE)
                except (RuntimeError, ValueError, OSError) as e:
                    problems.append(str(e))
        return _fail(problems)

    if a.command == "write":
        for spec in specs:
            write_study(spec, HERE)
            print(f"wrote {spec['dir']}/study.yaml and {spec['dir']}/banned-terms.txt")
        return 0

    if a.command == "check":
        problems, hashes = [], {}
        for spec in specs:
            try:
                p, h = check_study(spec, HERE)
            except OSError as e:                      # a missing media-sources.json is a finding, not a crash
                p, h = [f"{spec['dir']}/media-sources.json: {e.strerror or e}"], {}
            problems += p
            hashes.update(h)
            print(f"{spec['id']}: {len(h)} copies checked, {len(p)} problem(s)")
        p, checked = positive_control(root, kind)
        problems += p
        print(f"positive control: {checked} hosted sources checked")
        if any(k != "pilot" for k in keys):           # the pilot ships nothing
            p, scanned = check_shipping(HERE, root, kind, require_all=not a.partial)
            problems += p
            print(f"shipping files: {scanned} scanned")
        print(private_terms_note(HERE))
        if set(keys) == {"burst", "push"} and not problems:
            sizes = set()
            for spec in specs:
                for rec in json.loads(read_text(HERE / spec["dir"] / "media-sources.json"))["clips"].values():
                    sv = rec["source_video"]
                    sizes.add(PORTRAIT if sv["height"] > sv["width"] else LANDSCAPE)
            lines = [f"{h}  {path}" for path, h in sorted(hashes.items())]
            write_text_atomic(HERE / "rating-copies.sha256", "\n".join(lines) + "\n")
            print(f"wrote rating-copies.sha256 ({len(lines)} copies; sizes {sorted(sizes)})")
        return _fail(problems)

    if len(keys) != 1 or not a.study or not a.dist:      # check-build
        ap.error("check-build needs exactly one --study and a --dist")
    spec = specs[0]
    expect = recorded_tree(spec, HERE) if a.expect_recorded else a.expect_tree
    p, tree_sha, scanned = check_build(spec, HERE, a.dist, root, kind, expect)
    print(f"{spec['id']}: {scanned} files scanned")
    print(private_terms_note(HERE))
    if tree_sha:
        print(f"{spec['id']}: build tree {tree_sha}")
    _fail(p)
    print("clean" if not p else f"{len(p)} problem(s)")
    if a.record and not p:
        old = record_tree(spec, HERE, a.dist, tree_sha, replace=a.replace_recorded)
        if old is None:
            print("recorded in build-trees.json")
        elif old == tree_sha:
            print("recorded in build-trees.json (unchanged)")
        else:
            print(f"recorded in build-trees.json: replaced the recorded tree {old} with {tree_sha}")
    return 1 if p else 0


if __name__ == "__main__":
    sys.exit(main())
