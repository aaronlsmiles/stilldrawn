"""Tests for prepare.py: the A9 rating copies, the two blind studies and the slim ratings.

    python3 -m pytest analysis/adherence/test_prepare.py

The media tests make tiny synthetic sources with ffmpeg; no test reads a real clip. Strings
that the release build would rename or reject are built from parts, so this file ships
byte-identical.
"""
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time
import urllib.request
import zipfile
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare as pp  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                                  reason="ffmpeg and ffprobe are needed")
PRIVATE_NAME = "private-terms.txt"
PRIVATE_TANK = "zzz-act-tank-1"          # stands in for the private panel id
RENAMES = {PRIVATE_TANK: "cip-act-tank-1"}


def private_terms_or_skip():
    """The private terms (PrivateTerm objects), or a skip in the public tree, which does not have the file.
    No test spells a private term: it reads them from private-terms.txt."""
    terms, problems = pp.load_private_terms()
    if terms is None:
        pytest.skip("private-terms.txt exists only in the private repo; the public tree checks with the public list")
    assert problems == [] and terms
    return terms


def sample_of(term):
    """A string the private term matches, made from the term itself (word boundaries dropped, a [-_] class
    made a hyphen), so that no test has to spell it."""
    t = term.term
    return t if isinstance(t, str) else t.pattern.replace("\\b", "").replace("[-_]", "-")


BURST_PANELS = ["act-black-3", "act-line-2", "act-tone-1", "chain-est-cosmic-1", "cu-black-3", "cu-line-2",
                "cu-tone-1", "est-black-3", "est-line-2", "est-tone-1", PRIVATE_TANK]
PUSH_PANELS = ["act-black-1", "act-line-3", "act-tone-2", "chain-est-cosmic-1", "cu-black-1", "cu-line-3",
               "cu-tone-2", "est-black-1", "est-line-3", "est-tone-2", PRIVATE_TANK]
CLAUSES = {"BURST": pp.BURST_CLAUSE, "CAMPUSH": pp.PUSH_CLAUSE, "IDLE": "Subtle idle motion only."}


# ---------------------------------------------------------------- fixtures
def row(cid, engine, cls, panel, prompt=None):
    return {"cell_id": cid, "engine": engine, "motion_class": cls, "panel": f"dataset/panels/{panel}.png",
            "prompt": prompt or CLAUSES[cls] + " Camera locked off. The image is an inked drawing.",
            "out": f"runs/{engine}/{cid}.mp4"}


def full_manifest():
    rows = []
    for engine, suffix in pp.ENGINES.items():
        for cls, token, panels in (("BURST", "burst", BURST_PANELS), ("CAMPUSH", "campush", PUSH_PANELS)):
            for p in panels:
                rows.append(row(f"{p}_{token}_{suffix}", engine, cls, p))
                rows.append(row(f"{p}_{token}_{suffix}-r2", engine, cls, p))       # re-roll
        rows.append(row(f"cu-line-1_idle_{suffix}", engine, "IDLE", "cu-line-1"))
    for cid in pp.PILOT["cells"]:
        engine = {"h3": "h3-fal", "gen45": "gen4.5", "ltx23": "ltx23"}[re.search(r"_(h3|gen45|ltx23)", cid).group(1)]
        rows.append(row(cid, engine, "IDLE" if "_idle_" in cid else "BURST", cid.split("_")[0]))
    rows.append(row("cu-line-1_burst_sd2-h1", "seedance", "BURST", "cu-line-1"))
    return rows


def write_manifest(root, rows):
    (root / "runs").mkdir(parents=True, exist_ok=True)
    pp.write_text(root / "runs" / "manifest.jsonl", "".join(json.dumps(r) + "\n" for r in rows))


def make_clip(path, size, rate, frames, audio=False, source=None, lossless=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
           "-i", source or f"testsrc2=s={size[0]}x{size[1]}:r={rate}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=32000"]
    cmd += ["-frames:v", str(frames), "-c:v", "libx264", "-preset", "ultrafast",
            *(["-qp", "0"] if lossless else ["-crf", "12"]), "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac", "-shortest"]
    subprocess.run(cmd + [str(path)], check=True)
    return path


def chunk(t, d):
    return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)


ALLOWED_PNG_CHUNKS = {"IHDR", "PLTE", "tRNS", "IDAT", "IEND"}       # the pixels, nothing else


def write_png(path, w, h, text=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = b"".join(b"\x00" + bytes((x * 7 + y * 3) % 256 for x in range(w * 3)) for y in range(h))

    data = pp.PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    for k, v in (text or {}).items():
        data += chunk(b"tEXt", k.encode() + b"\0" + v.encode())
    path.write_bytes(data + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return path


SOURCES = {
    "panels": {"cu-line-2": {"copy": "media/cu-line-2.png", "copy_sha256": "a" * 64}},
    "clips": {f"cu-line-2_burst_{s}": {"panel": "cu-line-2", "copy": f"media/cu-line-2_burst_{s}.mp4",
                                       "copy_sha256": "b" * 64} for s in ("gen45", "ltx23", "wan22")},
}
LOCK = {"instrument": "A9", "text_sha256": "c" * 64}


# ---------------------------------------------------------------- cells
def test_load_manifest_last_line_wins(tmp_path):
    rows = full_manifest()
    write_manifest(tmp_path, [dict(rows[0], out="runs/old.mp4")] + rows)
    assert pp.load_manifest(tmp_path)[rows[0]["cell_id"]]["out"] == rows[0]["out"]


def test_select_cells_takes_the_primary_arm_only(tmp_path):
    m = {r["cell_id"]: r for r in full_manifest()}
    for spec in (pp.BURST, pp.PUSH):
        cells = pp.select_cells(m, spec, tmp_path, RENAMES)
        assert len(cells) == 55
        assert not any("-r2" in c["id"] or "-h" in c["id"] or "sd2" in c["id"] for c in cells)
        assert pp.validate_cells(cells, spec) == []


def test_select_cells_applies_public_ids(tmp_path):
    m = {r["cell_id"]: r for r in full_manifest()}
    tank = [c for c in pp.select_cells(m, pp.BURST, tmp_path, RENAMES) if "tank" in c["id"]]
    assert len(tank) == 5
    for c in tank:
        assert c["id"].startswith("cip-act-tank-1_burst_") and c["panel"] == "cip-act-tank-1"
        assert c["cell_id"].startswith(PRIVATE_TANK) and c["out"].startswith(f"runs/{c['engine']}/{PRIVATE_TANK}")
        assert PRIVATE_TANK not in c["source"] + c["panel_source"]
        assert c["panel_source"] == "dataset/panels/cip-act-tank-1.png"


def test_panel_source_never_uses_an_absolute_manifest_path(tmp_path):
    rows = {r["cell_id"]: r for r in full_manifest()}
    cid = "cu-line-2_burst_wan22"
    pod = "/work" + "space/somewhere/dataset/panels/cu-line-2.png"          # a rented pod's path
    m = {cid: dict(rows[cid], panel=pod)}
    spec = dict(pp.BURST, cells=[cid])
    (c,) = pp.select_cells(m, spec, tmp_path, RENAMES)
    assert c["panel_src"] == str(tmp_path / "dataset" / "panels" / "cu-line-2.png")
    assert c["panel"] == "cu-line-2" and c["panel_source"] == "dataset/panels/cu-line-2.png"


def test_validate_cells_catches_a_wrong_set(tmp_path):
    m = {r["cell_id"]: r for r in full_manifest()}
    cells = pp.select_cells(m, pp.BURST, tmp_path, RENAMES)
    assert any("expected 55" in x for x in pp.validate_cells(cells[:-1], pp.BURST))
    reroll = [dict(cells[0], id=cells[0]["id"] + "-r2")] + cells[1:]
    assert any("re-roll" in x for x in pp.validate_cells(reroll, pp.BURST))
    other = [dict(cells[0], prompt="Something else. " + pp.BURST_CLAUSE)] + cells[1:]
    assert any("quoted clause" in x for x in pp.validate_cells(other, pp.BURST))


def test_pilot_cells_are_a3_and_a4_only(tmp_path):
    m = {r["cell_id"]: r for r in full_manifest()}
    cells = pp.select_cells(m, pp.PILOT, tmp_path, RENAMES)
    assert [c["id"] for c in cells] == sorted(pp.PILOT["cells"])
    assert pp.validate_cells(cells, pp.PILOT) == []
    primary = pp.select_cells(m, pp.BURST, tmp_path, RENAMES)[0]
    assert any("primary" in x for x in pp.validate_cells(cells[:-1] + [primary], pp.PILOT))


def test_every_real_panel_source_is_a_local_panel():
    if not (pp.ROOT / "runs" / "manifest.jsonl").exists():
        pytest.skip("no run manifest in this tree")
    renames = pp.renames_of(pp.release_rules(pp.ROOT))
    m = pp.load_manifest(pp.ROOT)
    panels = (pp.ROOT / "dataset" / "panels").resolve()
    cells = [c for spec in (pp.BURST, pp.PUSH) for c in pp.select_cells(m, spec, pp.ROOT, renames)]
    assert len(cells) == 110
    for c in cells:
        src = Path(c["panel_src"])
        assert src.is_file() and src.resolve().parent == panels, c["id"]


def test_text_files_are_utf8_with_unix_newlines(tmp_path):
    pp.write_text(tmp_path / "t.txt", "caf\u00e9\nline\n")
    assert (tmp_path / "t.txt").read_bytes() == "caf\u00e9\nline\n".encode("utf-8")
    pp.write_json(tmp_path / "j.json", {"k": "caf\u00e9", "n": [1, 2]})
    raw = (tmp_path / "j.json").read_bytes()
    assert "caf\u00e9".encode("utf-8") in raw and b"\r" not in raw and raw.endswith(b"}\n")
    assert pp.read_text(tmp_path / "j.json") == raw.decode("utf-8")
    assert pp.write_json(tmp_path / "j2.json", {"k": "caf\u00e9", "n": [1, 2]}) is None
    assert (tmp_path / "j2.json").read_bytes() == raw          # deterministic


def test_load_manifest_skips_blank_lines_and_reads_utf8(tmp_path):
    (tmp_path / "runs").mkdir()
    lines = [json.dumps({"cell_id": "a", "note": "caf\u00e9"}, ensure_ascii=False), "", "   ",
             json.dumps({"cell_id": "b"})]
    (tmp_path / "runs" / "manifest.jsonl").write_bytes("\n".join(lines).encode("utf-8"))
    m = pp.load_manifest(tmp_path)
    assert sorted(m) == ["a", "b"] and m["a"]["note"] == "caf\u00e9"


@pytest.mark.parametrize("body, lineno", [
    ('{"cell_id": "a"}\n{not json}\n', 2),
    ('\n\n{"engine": "x"}\n', 3),                      # no cell_id; blank lines still count
    ('{"cell_id": "a"}\n[1, 2]\n', 2),                  # not an object
    ('{"cell_id": ""}\n', 1),
])
def test_load_manifest_names_the_bad_line(tmp_path, body, lineno):
    (tmp_path / "runs").mkdir()
    pp.write_text(tmp_path / "runs" / "manifest.jsonl", body)
    with pytest.raises(SystemExit) as e:
        pp.load_manifest(tmp_path)
    assert f"manifest.jsonl:{lineno}" in str(e.value)


def test_cell_names_the_cell_on_a_missing_key(tmp_path):
    rows = {r["cell_id"]: r for r in full_manifest()}
    cid = "cu-line-2_burst_wan22"
    for key in ("engine", "panel", "out"):
        bad = {cid: {k: v for k, v in rows[cid].items() if k != key}}
        with pytest.raises(SystemExit) as e:
            pp.select_cells(bad, dict(pp.BURST, cells=[cid]), tmp_path, RENAMES)
        assert cid in str(e.value) and key in str(e.value)


def test_select_cells_ignores_ground_ids_and_engine_suffix_mismatches(tmp_path):
    m = {r["cell_id"]: r for r in full_manifest()}
    m["ground-cu-line-2_burst_wan22"] = row("ground-cu-line-2_burst_wan22", "wan22", "BURST", "cu-line-2")
    m["cu-line-2_burst_gen4t"] = row("cu-line-2_burst_gen4t", "gen4.5", "BURST", "cu-line-2")     # suffix and engine disagree
    m["cu-line-2_burst_wan22"] = row("cu-line-2_burst_wan22", "unknown-engine", "BURST", "cu-line-2")
    ids = [c["id"] for c in pp.select_cells(m, pp.BURST, tmp_path, RENAMES)]
    assert not any(i.startswith("ground-") for i in ids)
    assert "cu-line-2_burst_gen4t" not in ids and "cu-line-2_burst_wan22" not in ids
    assert len(ids) == 53 and ids == sorted(ids)
    assert any("expected 55" in x for x in pp.validate_cells(pp.select_cells(m, pp.BURST, tmp_path, RENAMES), pp.BURST))


def test_validate_cells_catches_duplicates_panel_count_and_engine_coverage(tmp_path):
    m = {r["cell_id"]: r for r in full_manifest()}
    cells = pp.select_cells(m, pp.BURST, tmp_path, RENAMES)
    dup = cells[:-1] + [dict(cells[0])]
    assert any("duplicate ids" in x for x in pp.validate_cells(dup, pp.BURST))
    onepanel = [dict(c, panel="cu-line-2") if c["panel"] == "cu-tone-1" else c for c in cells]
    assert any("10 panels, expected 11" in x for x in pp.validate_cells(onepanel, pp.BURST))
    wrong = [dict(cells[0], engine="gen4_turbo" if cells[0]["engine"] != "gen4_turbo" else "wan22")] + cells[1:]
    assert any("do not each cover" in x for x in pp.validate_cells(wrong, pp.BURST))


def test_public_view_has_only_public_keys_and_no_private_text(tmp_path):
    m = {r["cell_id"]: r for r in full_manifest()}
    pod = "/work" + "space/x/dataset/panels/" + PRIVATE_TANK + ".png"
    m[PRIVATE_TANK + "_burst_wan22"] = dict(m[PRIVATE_TANK + "_burst_wan22"], panel=pod)
    cells = pp.select_cells(m, pp.BURST, tmp_path, RENAMES)
    assert any(PRIVATE_TANK in c["cell_id"] for c in cells)
    for c in cells:
        v = pp.public_view(c)
        assert tuple(v) == pp.PUBLIC_KEYS
        text = json.dumps(v)
        assert PRIVATE_TANK not in text and str(tmp_path) not in text and ("/Us" + "ers") not in text
        assert not any(str(x).startswith("/") for x in v.values())
        assert "prompt" not in v and "out" not in v and "cell_id" not in v and "panel_src" not in v


def test_public_view_of_the_real_cells_never_names_the_private_id():
    if not (pp.ROOT / "runs" / "manifest.jsonl").exists():
        pytest.skip("no run manifest in this tree")
    rules = pp.release_rules(pp.ROOT)
    m = pp.load_manifest(pp.ROOT)
    for spec in (pp.BURST, pp.PUSH, pp.PILOT):
        for c in pp.select_cells(m, spec, pp.ROOT, pp.renames_of(rules)):
            text = json.dumps(pp.public_view(c))
            assert (rules is None or rules.OLD_ID not in text) and str(pp.ROOT) not in text
            assert ("/Us" + "ers") not in text and "~/" not in text


def test_the_quoted_clauses_open_every_real_prompt():
    if not (pp.ROOT / "runs" / "manifest.jsonl").exists():
        pytest.skip("no run manifest in this tree")
    renames = pp.renames_of(pp.release_rules(pp.ROOT))
    m = pp.load_manifest(pp.ROOT)
    for spec in (pp.BURST, pp.PUSH, pp.PILOT):
        assert pp.validate_cells(pp.select_cells(m, spec, pp.ROOT, renames), spec) == []



# ---------------------------------------------------------------- rating copies
@needs_ffmpeg
def test_a_720_source_is_cropped_to_the_grid(tmp_path):
    src = make_clip(tmp_path / "a.mp4", (1280, 720), 24, 126)
    info = pp.probe(src)
    assert pp.target_size(info) == pp.LANDSCAPE and not pp.needs_retime(info)
    dst = tmp_path / "a-copy.mp4"
    pp.encode_clip(src, dst, pp.LANDSCAPE)
    out = pp.probe(dst)
    assert (out["width"], out["height"], out["nb_frames"], out["stream_types"]) == (1280, 704, 121, ["video"])


@needs_ffmpeg
def test_audio_is_dropped_and_the_first_121_of_124_frames_kept(tmp_path):
    src = make_clip(tmp_path / "h.mp4", (1344, 768), 24, 124, audio=True)
    assert pp.probe(src)["stream_types"] == ["video", "audio"]
    dst = tmp_path / "h-copy.mp4"
    pp.encode_clip(src, dst, pp.LANDSCAPE)
    out = pp.probe(dst)
    assert (out["width"], out["height"], out["nb_frames"], out["stream_types"]) == (1280, 704, 121, ["video"])


@needs_ffmpeg
def test_a_portrait_source_gets_the_portrait_grid(tmp_path):
    src = make_clip(tmp_path / "t.mp4", (720, 1280), 24, 121)
    assert pp.target_size(pp.probe(src)) == pp.PORTRAIT
    dst = tmp_path / "t-copy.mp4"
    pp.encode_clip(src, dst, pp.PORTRAIT)
    assert (pp.probe(dst)["width"], pp.probe(dst)["height"]) == (704, 1280)


@needs_ffmpeg
def test_a_30fps_source_is_retimed_not_relabelled(tmp_path):
    # luma = source frame number, so each copied frame says which source frame it came from
    src = make_clip(tmp_path / "r.mp4", (64, 64), 30, 180, lossless=True,
                    source="color=c=black:s=64x64:r=30,format=yuv420p,geq=lum='N':cb=128:cr=128")
    info = pp.probe(src)
    assert pp.needs_retime(info)
    dst = tmp_path / "r-copy.mp4"
    pp.encode_clip(src, dst, pp.LANDSCAPE)
    out = pp.probe(dst)
    assert (out["nb_frames"], out["avg_frame_rate"]) == (121, "24/1")
    raw = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(dst), "-vf", "scale=32:18",
                          "-pix_fmt", "yuv420p", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    frame = 32 * 18 * 3 // 2
    assert len(raw) == 121 * frame
    y = raw[96 * frame: 96 * frame + 32 * 18]
    # 4.0 s in: source frame 120 at 30 fps; relabelling 30 fps as 24 would show frame 96
    assert abs(sum(y) / len(y) - 120) <= 4


@needs_ffmpeg
def test_encoding_is_deterministic(tmp_path):
    # Same machine, same ffmpeg and libx264, same threads: this does not prove that another
    # machine or build gives the same bytes. The copies' hashes are therefore recorded, and the
    # build records the ffmpeg and libx264 versions beside them.
    src = make_clip(tmp_path / "d.mp4", (1280, 720), 24, 121)
    pp.encode_clip(src, tmp_path / "1.mp4", pp.LANDSCAPE)
    pp.encode_clip(src, tmp_path / "2.mp4", pp.LANDSCAPE)
    assert pp.sha256_file(tmp_path / "1.mp4") == pp.sha256_file(tmp_path / "2.mp4")


@needs_ffmpeg
def test_a_panel_copy_drops_text_and_keeps_pixels(tmp_path):
    src = write_png(tmp_path / "p.png", 40, 30, {"prompt": "a workflow naming a model"})
    # plant more ancillary chunks than text: a timestamp, EXIF, a compressed and an international text chunk
    data = src.read_bytes()
    extra = b"".join(chunk(t, d) for t, d in ((b"tIME", b"\x07\xea\x0a\x1e\x0c\x00\x00"), (b"eXIf", b"MM\x00*\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00SECRET"),
                                              (b"zTXt", b"k\x00\x00" + zlib.compress(b"SECRET")),
                                              (b"iTXt", b"k\x00\x00\x00\x00\x00SECRET"), (b"pHYs", b"\x00\x00\x0e\xc4\x00\x00\x0e\xc4\x01")))
    at = data.index(b"IDAT") - 4
    src.write_bytes(data[:at] + extra + data[at:])
    kinds = [c[0] for c in pp.png_chunks(src.read_bytes())]
    assert {"tEXt", "tIME", "eXIf", "zTXt", "iTXt"} <= set(kinds)
    dst = tmp_path / "copy.png"
    pp.copy_panel(src, dst)
    kinds = [c[0] for c in pp.png_chunks(dst.read_bytes())]
    assert set(kinds) <= ALLOWED_PNG_CHUNKS, kinds
    assert b"SECRET" not in dst.read_bytes() and b"workflow" not in dst.read_bytes()
    assert pp.frames_sha256(src) == pp.frames_sha256(dst)


def small_tree(tmp_path):
    root, here = tmp_path / "root", tmp_path / "here"
    make_clip(root / "runs/gen4.5" / f"{PRIVATE_TANK}_burst_gen45.mp4", (720, 1280), 24, 121)
    make_clip(root / "runs/wan22/cu-line-2_burst_wan22.mp4", (1280, 704), 24, 121)
    write_png(root / "dataset/panels" / f"{PRIVATE_TANK}.png", 36, 64, {"prompt": "x"})
    write_png(root / "dataset/panels/cu-line-2.png", 64, 36)
    rows = [row(f"{PRIVATE_TANK}_burst_gen45", "gen4.5", "BURST", PRIVATE_TANK),
            row("cu-line-2_burst_wan22", "wan22", "BURST", "cu-line-2")]
    spec = dict(pp.BURST, n_clips=2, n_panels=2)
    cells = pp.select_cells({r["cell_id"]: r for r in rows}, spec, root, RENAMES)
    return root, here, spec, cells


@needs_ffmpeg
def test_build_media_records_sources_and_copies(tmp_path):
    root, here, spec, cells = small_tree(tmp_path)
    doc = pp.build_media(spec, cells, root, here)
    assert set(doc["clips"]) == {"cip-act-tank-1_burst_gen45", "cu-line-2_burst_wan22"}
    tank = doc["clips"]["cip-act-tank-1_burst_gen45"]
    assert tank["source"] == "runs/gen4.5/cip-act-tank-1_burst_gen45.mp4" and tank["retimed"] is False
    assert pp.sha256_file(here / "burst" / tank["copy"]) == tank["copy_sha256"]
    assert set(doc["panels"]) == {"cip-act-tank-1", "cu-line-2"}
    assert PRIVATE_TANK not in pp.read_text(here / "burst" / "media-sources.json")
    assert doc["prompt_clause"] == pp.BURST_CLAUSE and doc["encode"]["crf"] == 16


def pts_times(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout
    return sorted(float(x) for x in out.split())


def irregular_clip(path, kind):
    """A 24 fps source whose timestamps are not constant: 'jitter' nudges every tenth frame late,
    'gap' drops frames and keeps the others' timestamps."""
    base = make_clip(path.with_name("base-" + path.name), (320, 180), 24, 140)
    if kind == "jitter":
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(base), "-c", "copy", "-bsf:v",
                        "setts=ts=TS+if(eq(mod(N\\,10)\\,5)\\,0.1/24/TB\\,0)", str(path)], check=True)
    else:
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(base), "-vf",
                        "select='not(between(n\\,40\\,42))*not(eq(n\\,90))'", "-fps_mode", "passthrough",
                        "-c:v", "libx264", "-preset", "ultrafast", str(path)], check=True)
    return path


@needs_ffmpeg
@pytest.mark.parametrize("kind", ["jitter", "gap"])
def test_irregular_timestamps_give_a_constant_24fps_copy(tmp_path, kind):
    src = irregular_clip(tmp_path / f"{kind}.mp4", kind)
    deltas = [round(b - a, 5) for a, b in zip(pts_times(src), pts_times(src)[1:])]
    assert len(set(deltas)) > 1                                  # the fixture really is irregular
    dst = tmp_path / "copy.mp4"
    pp.encode_clip(src, dst, pp.LANDSCAPE)
    out = pp.probe(dst)
    assert (out["r_frame_rate"], out["avg_frame_rate"], out["nb_frames"]) == ("24/1", "24/1", 121)
    copy_deltas = {round(b - a, 4) for a, b in zip(pts_times(dst), pts_times(dst)[1:])}
    assert copy_deltas == {round(1 / 24, 4)}


@needs_ffmpeg
def test_build_media_refuses_a_non_cfr_copy(tmp_path, monkeypatch):
    root, here, spec, cells = small_tree(tmp_path)
    real = pp.probe
    def lying(path):
        info = real(path)
        return dict(info, avg_frame_rate="726/31") if "/media/" in str(path) and str(path).endswith(".mp4") else info
    monkeypatch.setattr(pp, "probe", lying)
    with pytest.raises(RuntimeError, match="24/1"):
        pp.build_media(spec, cells, root, here)


# ---- hardening beyond the plan's tests: what a leak or a drifting copy would look like
ALLOWED_FORMAT_TAGS = {"major_brand", "minor_version", "compatible_brands"}
ALLOWED_STREAM_TAGS = {"language", "handler_name"}


@needs_ffmpeg
def test_copy_carries_no_source_metadata_or_encoder_text(tmp_path):
    base = make_clip(tmp_path / "base.mp4", (1280, 720), 24, 126)
    src = tmp_path / "tagged.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(base), "-c", "copy",
                    "-metadata", "title=SECRETTITLE", "-metadata", "comment=SECRETCOMMENT",
                    "-metadata:s:v:0", "handler_name=SECRETHANDLER", "-metadata:s:v:0", "encoder=SECRETENC",
                    str(src)], check=True)
    assert b"SECRETTITLE" in src.read_bytes()                 # the fixture really is tagged
    dst = tmp_path / "copy.mp4"
    pp.encode_clip(src, dst, pp.LANDSCAPE)
    data = dst.read_bytes()
    for needle in (b"SECRET", b"x264", b"Lavc", b"Lavf", b"libx264", b"encoder"):
        assert needle not in data, needle
    out = pp.probe(dst)
    assert set(out["format_tags"]) <= ALLOWED_FORMAT_TAGS
    assert all(set(t) <= ALLOWED_STREAM_TAGS for t in out["stream_tags"])
    assert out["stream_tags"][0].get("handler_name", "VideoHandler") == "VideoHandler"


@needs_ffmpeg
def test_copy_is_the_registered_format(tmp_path):
    src = make_clip(tmp_path / "f.mp4", (1344, 768), 24, 124, audio=True)
    dst = tmp_path / "f-copy.mp4"
    pp.encode_clip(src, dst, pp.LANDSCAPE)
    out = pp.probe(dst)
    assert (out["codec"], out["pix_fmt"], out["r_frame_rate"], out["avg_frame_rate"]) == ("h264", "yuv420p", "24/1", "24/1")
    assert out["stream_types"] == ["video"]


@needs_ffmpeg
def test_a_source_with_too_few_frames_is_refused(tmp_path):
    root, here, spec, cells = small_tree(tmp_path)
    make_clip(root / "runs/wan22/cu-line-2_burst_wan22.mp4", (1280, 704), 24, 100)
    with pytest.raises(RuntimeError, match="cu-line-2_burst_wan22"):
        pp.build_media(spec, cells, root, here)


@needs_ffmpeg
def test_media_sources_json_describes_cells_by_public_view_only(tmp_path):
    root, here, spec, cells = small_tree(tmp_path)
    doc = pp.build_media(spec, cells, root, here)
    text = pp.read_text(here / "burst" / "media-sources.json")
    assert json.loads(text) == doc
    for private in (PRIVATE_TANK, str(tmp_path), "/Us" + "ers", "Camera locked off", "workflow"):
        assert private not in text, private
    # per-clip and per-panel records carry only what public_view lets out, plus the media facts
    for c in cells:
        v = pp.public_view(c)
        rec = doc["clips"][v["id"]]
        assert (rec["engine"], rec["panel"], rec["source"]) == (v["engine"], v["panel"], v["source"])
        assert doc["panels"][v["panel"]]["source"] == v["panel_source"]
        assert (here / "burst" / rec["copy"]).is_file() and (here / "burst" / doc["panels"][v["panel"]]["copy"]).is_file()
    assert (here / "burst" / "media-sources.json").read_bytes() == text.encode("utf-8")


@needs_ffmpeg
def test_media_sources_json_passes_the_release_rules_unchanged(tmp_path):
    rules = pp.release_rules(pp.ROOT)
    if rules is None:
        pytest.skip("no release build rules in this tree")
    root, here, spec, cells = small_tree(tmp_path)
    pp.build_media(spec, cells, root, here)
    text = pp.read_text(here / "burst" / "media-sources.json")
    rel = "analysis/adherence/burst/media-sources.json"
    assert rules.rewrite_text(rel, text, []) == text
    assert not rules.LEAK_RE.search(text)
    assert rules.OLD_ID not in text


@needs_ffmpeg
def test_encoding_the_same_source_twice_gives_the_same_media_sources(tmp_path):
    root, here, spec, cells = small_tree(tmp_path)
    pp.build_media(spec, cells, root, here)
    first = (here / "burst" / "media-sources.json").read_bytes()
    pp.build_media(spec, cells, root, here)
    assert (here / "burst" / "media-sources.json").read_bytes() == first


# ---------------------------------------------------------------- run(), PNG parsing, failure handling
def test_run_reports_a_missing_program():
    with pytest.raises(RuntimeError, match="not found on PATH"):
        pp.run(["no-such-program-" + "x" * 8, "-version"])


def test_run_times_out_with_a_runtime_error():
    with pytest.raises(RuntimeError, match="timed out after 0.5 s"):
        pp.run([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.5)


def test_run_keeps_the_tail_of_stderr_and_survives_undecodable_bytes():
    code = ("import sys; sys.stderr.buffer.write(b'HEAD-MARK ' + b'x' * 3000 + b' \\xff\\xfe bad bytes TAIL-MARK'); "
            "sys.exit(3)")
    with pytest.raises(RuntimeError) as e:
        pp.run([sys.executable, "-c", code])
    msg = str(e.value)
    assert "TAIL-MARK" in msg and "HEAD-MARK" not in msg and "(3)" in msg and len(msg) < 900


def test_run_decodes_stdout_as_utf8():
    assert pp.run([sys.executable, "-c", "import sys; sys.stdout.buffer.write('caf\\u00e9'.encode('utf-8'))"]) == "caf\u00e9"


def png_bytes(w=8, h=6, extra=()):
    """A valid RGB PNG with the (type, data) chunks in `extra` placed before IDAT."""
    raw = b"".join(b"\x00" + bytes((x * 7 + y * 3) % 256 for x in range(w * 3)) for y in range(h))
    out = pp.PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    for t, d in extra:
        out += chunk(t, d)
    return out + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def test_png_chunks_returns_full_chunk_slices():
    data = png_bytes(extra=[(b"tEXt", b"k\x00v")])
    chunks = pp.png_chunks(data)
    assert [c[0] for c in chunks] == ["IHDR", "tEXt", "IDAT", "IEND"]
    assert pp.PNG_SIG + b"".join(c[1] for c in chunks) == data
    assert chunks[1][1][4:8] == b"tEXt" and chunks[1][1][8:-4] == b"k\x00v"


@pytest.mark.parametrize("cut, problem", [
    (4, "signature"), (12, "truncated"), (20, "truncated"), (-1, "truncated"), (-9, "truncated"),
])
def test_png_chunks_names_a_truncated_file(cut, problem):
    data = png_bytes()
    with pytest.raises(ValueError, match=problem):
        pp.png_chunks(data[:cut])


def test_png_chunks_names_a_bad_crc_with_its_chunk():
    data = bytearray(png_bytes())
    at = bytes(data).index(b"IDAT") + 6
    data[at] ^= 0xFF
    with pytest.raises(ValueError, match="bad CRC.*IDAT"):
        pp.png_chunks(bytes(data))


def test_png_chunks_requires_ihdr_first_and_a_real_type():
    first_text = pp.PNG_SIG + chunk(b"tEXt", b"k\x00v") + chunk(b"IEND", b"")
    with pytest.raises(ValueError, match="IHDR"):
        pp.png_chunks(first_text)
    odd = pp.PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"\x00\x01zz", b"")
    with pytest.raises(ValueError, match="chunk type"):
        pp.png_chunks(odd)
    with pytest.raises(ValueError, match="no IEND"):
        pp.png_chunks(pp.PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)))


def test_png_chunks_stops_at_iend_and_strict_refuses_trailing_bytes():
    data = png_bytes() + b"TRAILING-GARBAGE"
    assert [c[0] for c in pp.png_chunks(data)][-1] == "IEND"                  # a source panel may carry a tail
    with pytest.raises(ValueError, match="after IEND"):
        pp.png_chunks(data, strict=True)
    assert pp.png_chunks(png_bytes(), strict=True)


@needs_ffmpeg
@pytest.mark.parametrize("name", sorted(pp.COLOUR_CHUNKS))
def test_copy_panel_refuses_a_colour_chunk_before_running_ffmpeg(tmp_path, monkeypatch, name):
    src = tmp_path / "c.png"
    src.write_bytes(png_bytes(extra=[(b"tEXt", b"k\x00v"), (name.encode(), b"\x00" * 4)]))
    monkeypatch.setattr(pp, "run", lambda *a, **k: pytest.fail("ffmpeg must not run"))
    with pytest.raises(ValueError, match=name):
        pp.copy_panel(src, tmp_path / "out.png")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c.png"]


def test_copy_panel_refuses_a_damaged_source_before_running_ffmpeg(tmp_path, monkeypatch):
    src = tmp_path / "bad.png"
    src.write_bytes(png_bytes()[:-20])
    monkeypatch.setattr(pp, "run", lambda *a, **k: pytest.fail("ffmpeg must not run"))
    with pytest.raises(ValueError, match="truncated"):
        pp.copy_panel(src, tmp_path / "out.png")


def write_palette_png(path, w=16, h=16):
    plte = bytes(v for i in range(4) for v in (i * 60, 255 - i * 60, i * 30))
    trns = bytes([255, 128, 64, 0])
    raw = b"".join(b"\x00" + bytes((x + y) % 4 for x in range(w)) for y in range(h))
    path.write_bytes(pp.PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0)) + chunk(b"PLTE", plte)
                     + chunk(b"tRNS", trns) + chunk(b"tEXt", b"prompt\x00SECRET") + chunk(b"IDAT", zlib.compress(raw))
                     + chunk(b"IEND", b""))
    return path


@needs_ffmpeg
def test_a_palette_panel_keeps_plte_trns_and_pixels(tmp_path):
    src = write_palette_png(tmp_path / "pal.png")
    dst = tmp_path / "copy.png"
    pp.copy_panel(src, dst)
    kinds = [c[0] for c in pp.png_chunks(dst.read_bytes(), strict=True)]
    assert kinds == ["IHDR", "PLTE", "tRNS", "IDAT", "IEND"]
    assert b"SECRET" not in dst.read_bytes()
    rgba = lambda f: subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(f), "-pix_fmt", "rgba",
                                     "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    assert rgba(src) == rgba(dst) and pp.frames_sha256(src) == pp.frames_sha256(dst)


@needs_ffmpeg
def test_a_failed_encode_leaves_no_temp_file_and_keeps_an_earlier_copy(tmp_path, monkeypatch):
    src = make_clip(tmp_path / "s.mp4", (1280, 720), 24, 121)
    dst = tmp_path / "out" / "c.mp4"
    dst.parent.mkdir()
    dst.write_bytes(b"EARLIER")

    def fail_after_writing(cmd, **kw):
        Path(cmd[-1]).write_bytes(b"partial")
        raise RuntimeError("ffmpeg failed (1): boom")
    monkeypatch.setattr(pp, "run", fail_after_writing)
    with pytest.raises(RuntimeError, match="boom"):
        pp.encode_clip(src, dst, pp.LANDSCAPE)
    assert sorted(p.name for p in dst.parent.iterdir()) == ["c.mp4"] and dst.read_bytes() == b"EARLIER"
    png = write_png(tmp_path / "p.png", 8, 8)
    with pytest.raises(RuntimeError, match="boom"):
        pp.copy_panel(png, tmp_path / "out" / "p-copy.png")
    assert sorted(p.name for p in dst.parent.iterdir()) == ["c.mp4"]


@needs_ffmpeg
def test_build_media_errors_name_the_public_cell_and_panel(tmp_path):
    root, here, spec, cells = small_tree(tmp_path)
    make_clip(root / "runs/wan22/cu-line-2_burst_wan22.mp4", (1280, 704), 24, 100)        # short source
    with pytest.raises(RuntimeError) as e:
        pp.build_media(spec, cells, root, here)
    assert "cu-line-2_burst_wan22" in str(e.value) and PRIVATE_TANK not in str(e.value)
    assert not list((here / "burst" / "media").glob("*.tmp.*"))
    root, here, spec, cells = small_tree(tmp_path / "second")
    panel = root / "dataset/panels" / f"{PRIVATE_TANK}.png"
    panel.write_bytes(panel.read_bytes()[:-30])
    with pytest.raises(RuntimeError) as e:
        pp.build_media(spec, cells, root, here)
    assert "panel cip-act-tank-1" in str(e.value) and "truncated" in str(e.value) and PRIVATE_TANK not in str(e.value)
    assert not list((here / "burst" / "media").glob("*.tmp.*"))


@needs_ffmpeg
def test_build_media_removes_stale_temp_files_and_nothing_else(tmp_path):
    root, here, spec, cells = small_tree(tmp_path)
    mdir = here / "burst" / "media"
    mdir.mkdir(parents=True)
    for name in ("old.tmp.mp4", "old.tmp.png", "note.txt", "tmp.mp4"):
        (mdir / name).write_bytes(b"x")
    pp.build_media(spec, cells, root, here)
    assert not list(mdir.glob("*.tmp.*"))
    assert (mdir / "note.txt").exists() and (mdir / "tmp.mp4").exists()


@needs_ffmpeg
def test_media_sources_records_the_encoder_and_what_the_source_hash_covers(tmp_path):
    root, here, spec, cells = small_tree(tmp_path)
    doc = pp.build_media(spec, cells, root, here)
    assert re.fullmatch(r"core \d+( r\d+ [0-9a-f]+)?", doc["encode"]["libx264"]), doc["encode"]["libx264"]
    assert doc["ffmpeg"].startswith("ffmpeg version")
    assert "whole source" in doc["note"] and "first 121 frames" in doc["note"]


# ---------------------------------------------------------------- checks
def box(t, payload=b""):
    return struct.pack(">I4s", 8 + len(payload), t) + payload


def png_file(path, data):
    path.write_bytes(data)
    return path


@pytest.fixture(scope="module")
def clean_copy(tmp_path_factory):
    d = tmp_path_factory.mktemp("copy")
    src = make_clip(d / "s.mp4", (1280, 720), 24, 121)
    pp.encode_clip(src, d / "c.mp4", pp.LANDSCAPE)
    return d / "c.mp4"


@needs_ffmpeg
def test_a_clean_copy_passes(clean_copy):
    boxes = pp.mp4_boxes(clean_copy.read_bytes())
    assert {b[0].rsplit("/", 1)[1] for b in boxes} <= pp.MP4_ALLOWED
    assert pp.check_copy(clean_copy, pp.LANDSCAPE) == []


@needs_ffmpeg
def test_a_planted_c2pa_box_is_caught(clean_copy, tmp_path):
    payload = b"jumb" + pp.C2PA_JUMBF_TYPE + b"c2pa manifest"
    planted = struct.pack(">I4s", 8 + 16 + len(payload), b"uuid") + pp.C2PA_BMFF_UUID + payload
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(clean_copy.read_bytes() + planted)
    p = pp.check_mp4_bytes(bad)
    assert "box /uuid not allowed" in p
    assert {"provenance bytes: C2PA uuid", "provenance bytes: C2PA JUMBF type", "provenance bytes: jumb"} <= set(p)


def test_mp4_boxes_walks_containers_the_meta_full_box_and_64_bit_sizes():
    meta = box(b"meta", bytes(4) + box(b"hdlr", bytes(8)) + box(b"ilst"))
    big = struct.pack(">I4sQ", 1, b"free", 16)
    data = box(b"ftyp", bytes(8)) + box(b"moov", box(b"udta", meta)) + big
    assert [b[0] for b in pp.mp4_boxes(data)] == [
        "/ftyp", "/moov", "/moov/udta", "/moov/udta/meta", "/moov/udta/meta/hdlr", "/moov/udta/meta/ilst", "/free"]
    last = pp.mp4_boxes(data)[-1]
    assert last[3] - last[1] == 16 and last[2] - last[1] == 16          # a 64-bit header is 16 bytes, no payload
    assert pp.mp4_boxes(box(b"free") + struct.pack(">I4s", 0, b"mdat") + b"abc")[-1][3] == 8 + 8 + 3   # size 0: to the end


@pytest.mark.parametrize("data, problem", [
    (box(b"free") + b"abc", "truncated"),
    (struct.pack(">I4s", 99, b"free"), "bad box size"),
    (struct.pack(">I4s", 4, b"free"), "bad box size"),
])
def test_a_damaged_box_structure_is_reported_not_raised(tmp_path, data, problem):
    with pytest.raises(ValueError, match=problem):
        pp.mp4_boxes(data)
    f = tmp_path / "x.mp4"
    f.write_bytes(data)
    (only,) = pp.check_mp4_bytes(f)
    assert only.startswith("unreadable box structure") and problem in only


def test_check_mp4_bytes_on_a_minimal_file(tmp_path):
    def mp4(ilst):
        return box(b"ftyp", bytes(8)) + box(b"moov", box(b"udta", box(b"meta", bytes(4) + box(b"ilst", ilst))))
    f = tmp_path / "m.mp4"
    f.write_bytes(mp4(b""))
    assert pp.check_mp4_bytes(f) == []                                       # an empty metadata list is allowed
    f.write_bytes(mp4(b"xxxx"))
    assert pp.check_mp4_bytes(f) == ["metadata list /moov/udta/meta/ilst is not empty"]
    f.write_bytes(box(b"ftyp", bytes(8)) + box(b"moov", box(b"udta", box(b"XMP_", b"x"))))
    assert pp.check_mp4_bytes(f) == ["box /moov/udta/XMP_ not allowed"]


def test_short_tokens_count_only_outside_the_payload():
    inside = box(b"free", bytes(4)) + box(b"mdat", b"xxjumbxx")
    boxes = pp.mp4_boxes(inside)
    assert pp.provenance_hits(inside, [(b[2], b[3]) for b in boxes if b[0] == "/mdat"]) == []
    outside = box(b"free", b"xxJUMBxx")
    assert pp.provenance_hits(outside, []) == ["jumb"]
    assert pp.provenance_hits(box(b"free", b"C2PA jumd"), []) == ["c2pa", "jumd"]
    # the long signatures are searched over every byte, payload included
    hidden = box(b"mdat", pp.C2PA_BMFF_UUID + pp.C2PA_JUMBF_TYPE)
    assert pp.provenance_hits(hidden, [(8, len(hidden))]) == ["C2PA uuid", "C2PA JUMBF type"]


@needs_ffmpeg
def test_audio_tags_and_size_are_caught(clean_copy, tmp_path):
    src = make_clip(tmp_path / "h.mp4", (1280, 704), 24, 121, audio=True)
    bad = tmp_path / "bad.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(src), "-frames:v", "121",
                    "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    "-metadata", "title=made by an engine", str(bad)], check=True)
    p = pp.check_copy(bad, pp.LANDSCAPE)
    assert any(x.startswith("streams") for x in p) and any(x.startswith("container tags") for x in p)
    assert any(x.startswith("size") for x in pp.check_copy(clean_copy, pp.PORTRAIT))


@needs_ffmpeg
def test_wrong_stream_tags_frame_count_and_codec_are_caught(clean_copy, tmp_path):
    bad = tmp_path / "bad.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(clean_copy), "-c", "copy",
                    "-metadata:s:v:0", "handler_name=Engine v1", "-metadata:s:v:0", "language=eng", str(bad)], check=True)
    assert any(x.startswith("stream tags") and "Engine v1" in x for x in pp.check_copy(bad, pp.LANDSCAPE))
    short = make_clip(tmp_path / "short.mp4", (1280, 704), 24, 100)
    p = pp.check_copy(short, pp.LANDSCAPE)
    assert any("100 frames in the container" in x for x in p) and any("100 decoded frames" in x for x in p)
    slow = make_clip(tmp_path / "slow.mp4", (1280, 704), 25, 121)
    assert any(x.startswith("rate 25/1") for x in pp.check_copy(slow, pp.LANDSCAPE))


@needs_ffmpeg
@pytest.mark.parametrize("kind", ["jitter", "gap"])
def test_irregular_frame_timing_is_caught(tmp_path, kind):
    src = irregular_clip(tmp_path / f"{kind}.mp4", kind)
    assert len(pp.frame_gaps(src)) > 1
    assert any("distinct frame intervals (expected 1)" in x for x in pp.check_copy(src, (320, 180)))
    dst = tmp_path / "copy.mp4"
    pp.encode_clip(src, dst, pp.LANDSCAPE)
    assert len(pp.frame_gaps(dst)) == 1


@needs_ffmpeg
def test_an_unreadable_copy_is_a_problem_not_a_crash(tmp_path):
    f = tmp_path / "junk.mp4"
    f.write_bytes(b"not a video at all" * 10)
    p = pp.check_copy(f, pp.LANDSCAPE)
    assert any(x.startswith("unreadable") for x in p) and any(x.startswith("unreadable box structure") for x in p)


def test_a_png_text_chunk_is_caught(tmp_path):
    assert pp.check_png_bytes(write_png(tmp_path / "p.png", 8, 8, {"prompt": "x"})) == ["chunk tEXt not allowed"]
    assert pp.check_png_bytes(write_png(tmp_path / "q.png", 8, 8)) == []


def test_png_allowlist_is_what_copy_panel_keeps_nothing_more(tmp_path):
    assert pp.PNG_KEEP == {"IHDR", "PLTE", "tRNS", "IDAT", "IEND"}
    for name in (b"pHYs", b"eXIf", b"tIME", b"caBX", b"gAMA"):
        f = png_file(tmp_path / "x.png", png_bytes(extra=[(name, b"\x00" * 9)]))
        assert pp.check_png_bytes(f) == [f"chunk {name.decode()} not allowed"], name


def test_png_damage_and_trailing_bytes_are_reported(tmp_path):
    f = png_file(tmp_path / "t.png", png_bytes() + b"TRAILING-BYTES")
    (only,) = pp.check_png_bytes(f)
    assert only.startswith("unreadable PNG") and "after IEND" in only
    (only,) = pp.check_png_bytes(png_file(tmp_path / "u.png", png_bytes()[:-20]))
    assert only.startswith("unreadable PNG") and "truncated" in only
    (only,) = pp.check_png_bytes(png_file(tmp_path / "v.png", b"GIF89a" + bytes(40)))
    assert only.startswith("unreadable PNG") and "signature" in only


def test_png_provenance_search_masks_idat_payload_only(tmp_path):
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))

    def png(idat, extra=b""):
        return png_file(tmp_path / "p.png", pp.PNG_SIG + ihdr + extra + chunk(b"IDAT", idat) + chunk(b"IEND", b""))
    assert pp.check_png_bytes(png(b"xxJUMBxx c2pa jumd")) == []                          # chance matches in compressed data
    assert pp.check_png_bytes(png(b"zz" + pp.C2PA_BMFF_UUID)) == ["provenance bytes: C2PA uuid"]
    assert pp.check_png_bytes(png(b"zz" + pp.C2PA_JUMBF_TYPE)) == ["provenance bytes: C2PA JUMBF type"]
    assert pp.check_png_bytes(png(b"zz", chunk(b"tEXt", b"k\x00C2PA"))) == ["chunk tEXt not allowed", "provenance bytes: c2pa"]


@needs_ffmpeg
def test_a_panel_copy_passes_the_png_check_where_its_source_does_not(tmp_path):
    src = write_png(tmp_path / "p.png", 40, 30, {"prompt": "a workflow naming a model"})
    assert pp.check_png_bytes(src) == ["chunk tEXt not allowed"]
    pp.copy_panel(src, tmp_path / "copy.png")
    assert pp.check_png_bytes(tmp_path / "copy.png") == []


def test_banned_terms_catch_engines_ids_and_the_working_name():
    banned, problems = pp.parse_banned(pp.BANNED_TERMS)
    assert problems == [] and len(banned) > 30
    for leak in ("Gen-4.5", "gen4_turbo", "Wan 2.2", "wan22", "LTX-2.3", "H3", "MiniMax", "runway.com",
                 "x_burst_y", "cu-line-2", "cip-act-tank-1", "chain-est-cosmic-1",
                 "i" + "nkbench"):
        assert pp.find_banned(leak, banned), leak
    for clean in ("clip", "Motion check: set 1", "a9-burst-2026-10-31", "h3", "c3tf9a", "media/cq4zgy.mp4"):
        assert not pp.find_banned(clean, banned), clean


def test_banned_terms_are_case_insensitive_substrings_or_regexes():
    banned, problems = pp.parse_banned("# comment\n\nRunWay\n/\\bH3\\b/\n/gen-?4/i\n")
    assert problems == [] and len(banned) == 3
    assert pp.find_banned("made by RUNWAY", banned) == ["RunWay"]
    assert pp.find_banned("h3 and H3", banned) == ["/\\bH3\\b/ -> H3"]            # no i flag: case-sensitive
    assert pp.find_banned("Gen4", banned) == ["/gen-?4/ -> Gen4"]
    assert pp.find_banned("nothing here", banned) == []


@needs_ffmpeg
def test_check_study_passes_a_clean_set_and_catches_tampering(tmp_path):
    root, here, spec, cells = small_tree(tmp_path)
    pp.build_media(spec, cells, root, here)
    p, hashes = pp.check_study(spec, here)
    assert p == [] and len(hashes) == 2 and set(hashes) == {
        "burst/media/cip-act-tank-1_burst_gen45.mp4", "burst/media/cu-line-2_burst_wan22.mp4"}
    assert any("expected 3" in x for x in pp.check_study(dict(spec, n_clips=3), here)[0])
    copy = here / "burst/media/cu-line-2_burst_wan22.mp4"
    copy.write_bytes(copy.read_bytes() + struct.pack(">I4s", 8, b"free"))
    assert any("hash differs" in x for x in pp.check_study(spec, here)[0])
    src = json.loads(pp.read_text(here / "burst/media-sources.json"))
    src["clips"]["cu-line-2_burst_wan22-r2"] = src["clips"].pop("cu-line-2_burst_wan22")
    pp.write_json(here / "burst/media-sources.json", src)
    assert any("re-roll" in x for x in pp.check_study(spec, here)[0])


@needs_ffmpeg
def test_check_study_catches_stray_missing_and_duplicate_media(tmp_path):
    root, here, spec, cells = small_tree(tmp_path)
    pp.build_media(spec, cells, root, here)
    media = here / "burst/media"
    (media / "stray-source.mp4").write_bytes(b"x")
    assert pp.check_study(spec, here)[0] == ["media/stray-source.mp4: a file that media-sources.json does not list"]
    (media / "stray-source.mp4").unlink()
    (media / "cu-line-2.png").write_bytes(write_png(tmp_path / "t.png", 64, 36, {"prompt": "x"}).read_bytes())
    p = pp.check_study(spec, here)[0]
    assert any("cu-line-2" in x and "hash differs" in x for x in p) and any("chunk tEXt not allowed" in x for x in p)
    (media / "cu-line-2.png").unlink()
    assert any("panel copy missing" in x for x in pp.check_study(spec, here)[0])
    wan = media / "cu-line-2_burst_wan22.mp4"
    shutil.copy(media / "cip-act-tank-1_burst_gen45.mp4", wan)
    assert any("identical" in x for x in pp.check_study(spec, here)[0])
    wan.unlink()
    assert "cu-line-2_burst_wan22: copy missing" in pp.check_study(spec, here)[0]


@needs_ffmpeg
def test_check_study_names_a_wrong_size_and_mixed_orientation(tmp_path):
    root, here, spec, cells = small_tree(tmp_path)
    pp.build_media(spec, cells, root, here)
    src = json.loads(pp.read_text(here / "burst/media-sources.json"))
    src["clips"]["cu-line-2_burst_wan22"]["source_video"].update(width=720, height=1280)    # claims a portrait source
    pp.write_json(here / "burst/media-sources.json", src)
    assert any(x.startswith("cu-line-2_burst_wan22: size 1280x704, expected 704x1280") for x in pp.check_study(spec, here)[0])
    src["clips"]["cu-line-2_burst_wan22"]["source_video"].update(width=1280, height=704)
    src["clips"]["cu-line-2_burst_wan22"]["panel"] = "cip-act-tank-1"      # one panel, a portrait and a landscape clip
    pp.write_json(here / "burst/media-sources.json", src)
    assert any("engines disagree on orientation" in x for x in pp.check_study(spec, here)[0])


def fake_rules_root(tmp_path, shippable=True):
    root = tmp_path / "root"
    (root / "tools").mkdir(parents=True)
    (root / "runs").mkdir()
    pp.write_text(root / "runs/manifest.jsonl", "")
    pp.write_text(root / "tools/build_release.py",
                  "import re\n"
                  f"OLD_ID, NEW_ID = {PRIVATE_TANK!r}, 'cip-act-tank-1'\n"
                  "LEAK_RE = re.compile('zzz-|secretword')\n"
                  "def rewrite_text(relpath, text, log):\n"
                  "    return text.replace('Workname', 'Publicname')\n"
                  + ("ADHERENCE_SUFFIXES = {'.md', '.json'}\n"
                     "def a9_shippable(p, root, suffixes):\n"
                     "    return p.is_file() and p.suffix in suffixes and 'media' not in p.relative_to(root).parts\n"
                     if shippable else ""))
    return root


def test_check_shipping_holds_files_to_the_release_rules(tmp_path):
    root, here = fake_rules_root(tmp_path), tmp_path / "here"
    (here / "burst").mkdir(parents=True)
    pp.write_text(here / "prepare.py", "clean\n")
    assert pp.check_shipping(here, root, "private", require_all=False) == ([], 1)
    pp.write_text(here / "burst/study.yaml", f"id: {PRIVATE_TANK}_burst_wan22\n")
    pp.write_text(here / "README.md", "Workname notes\n")
    p, n = pp.check_shipping(here, root, "private", require_all=False)
    assert n == 3
    assert any(x.startswith("burst/study.yaml: release leak scan") for x in p)
    assert any(x.startswith("README.md: the release build would rewrite") for x in p)
    assert pp.renames_of(pp.release_rules(root)) == RENAMES
    assert pp.release_rules(tmp_path / "nowhere") is None
    assert pp.check_shipping(here, tmp_path / "nowhere", "public") == ([], 0)  # the public tree: nothing to hold them to


def test_check_shipping_covers_the_optional_files_when_present(tmp_path):
    root, here = fake_rules_root(tmp_path), tmp_path / "here"
    here.mkdir()
    assert pp.OPTIONAL_SHIPPING == ["r7-status.json", "sessions.sha256"]
    pp.write_text(here / "prepare.py", "clean\n")
    assert pp.check_shipping(here, root, "private", require_all=False) == ([], 1)          # the optional file is absent: fine
    pp.write_text(here / "r7-status.json", '{"note": "secretword"}\n')
    pp.write_text(here / "a9-config.json", '{"note": "Workname"}\n')            # a required file written by sub-plan A
    p, n = pp.check_shipping(here, root, "private", require_all=False)
    assert n == 3
    assert any(x.startswith("r7-status.json: release leak scan") for x in p)
    assert any(x.startswith("a9-config.json: the release build would rewrite") for x in p)


def test_check_shipping_lists_sessions_sha256_when_present_and_scans_it(tmp_path):
    root, here = fake_rules_root(tmp_path), tmp_path / "here"
    here.mkdir()
    pp.write_text(here / "prepare.py", "clean\n")
    pp.write_text(here / "sessions.sha256", "0" * 64 + "  extra sessions burst-R7 (1 rows, 2026-11-05 UTC)\n")
    assert pp.check_shipping(here, root, "private", require_all=False) == ([], 2)       # listed: not "unlisted"
    pp.write_text(here / "sessions.sha256", "0" * 64 + "  secretword\n")
    p, _ = pp.check_shipping(here, root, "private", require_all=False)
    assert any(x.startswith("sessions.sha256: release leak scan") for x in p)


def test_check_shipping_judges_bytes_the_way_the_release_reads_them(tmp_path):
    root, here = fake_rules_root(tmp_path), tmp_path / "here"
    here.mkdir()
    (here / "README.md").write_bytes(b"line one\r\nline two\r\n")              # read_text would make these \n
    (here / "a9-config.json").write_bytes(b'{"k": "\xff"}\n')
    p, _ = pp.check_shipping(here, root, "private", require_all=False)
    assert any(x.startswith("README.md: the release build would rewrite") for x in p)
    assert any(x.startswith("a9-config.json: not UTF-8") for x in p)


def test_check_shipping_flags_a_file_the_release_would_ship_unlisted(tmp_path):
    root, here = fake_rules_root(tmp_path), tmp_path / "here"
    (here / "burst/media").mkdir(parents=True)
    pp.write_text(here / "README.md", "fine\n")
    pp.write_text(here / "burst/media/x.md", "never ships\n")                  # under a never-ship folder
    assert pp.check_shipping(here, root, "private", require_all=False) == ([], 1)
    pp.write_text(here / "notes.md", "secretword\n")                            # ships, is not listed, is not clean
    p, n = pp.check_shipping(here, root, "private", require_all=False)
    assert n == 2
    assert "notes.md: the release would ship this file but SHIPPING does not list it" in p
    assert any(x.startswith("notes.md: release leak scan") for x in p)


def test_check_shipping_requires_every_shipping_file_in_the_private_tree(tmp_path):
    root, here = fake_rules_root(tmp_path), tmp_path / "here"
    here.mkdir()
    pp.write_text(here / "prepare.py", "clean\n")
    p, n = pp.check_shipping(here, root, "private")                             # require_all is the default
    assert n == 1
    required = [r for r in pp.SHIPPING if not r.startswith("ratings-") and r != "prepare.py"]
    assert required and set(p) == {f"{r}: a shipping file that is absent" for r in required}
    assert not any("r7-status.json" in x or "ratings-" in x for x in p)         # optional; and the ratings only exist after Gates E/E2
    for r in required:
        (here / r).parent.mkdir(parents=True, exist_ok=True)
        pp.write_text(here / r, "clean\n")
    assert pp.check_shipping(here, root, "private") == ([], len(required) + 1)


def test_the_tree_kind_is_explicit_and_checked(tmp_path):
    here = tmp_path / "here"
    here.mkdir()
    pp.write_text(here / "prepare.py", "clean\n")
    with pytest.raises(ValueError, match="tree"):
        pp.check_shipping(here, tmp_path, "both")
    with pytest.raises(TypeError):
        pp.check_shipping(here, tmp_path)                                       # no default
    # a private run needs the manifest and the release script; a bare folder has neither, and scans nothing
    p, n = pp.check_shipping(here, tmp_path / "bare", "private", require_all=False)
    assert n == 0 and p == ["private tree: runs/manifest.jsonl is missing", "private tree: tools/build_release.py is missing"]
    # a public run finding the private tree's files has been pointed at the wrong tree
    root = fake_rules_root(tmp_path)
    p, n = pp.check_shipping(here, root, "public")
    assert n == 0 and p == ["public tree: runs/manifest.jsonl exists (this is the private tree)",
                            "public tree: tools/build_release.py exists (this is the private tree)"]


def test_a_private_run_that_scans_nothing_is_a_problem(tmp_path):
    root, here = fake_rules_root(tmp_path), tmp_path / "here"
    here.mkdir()
    assert pp.check_shipping(here, root, "private", require_all=False) == (["private tree: 0 shipping files scanned"], 0)


def test_check_shipping_cannot_silently_lose_the_release_helpers(tmp_path):
    root, here = fake_rules_root(tmp_path, shippable=False), tmp_path / "here"
    here.mkdir()
    pp.write_text(here / "prepare.py", "clean\n")
    p, n = pp.check_shipping(here, root, "private", require_all=False)
    assert n == 1 and p == ["the release rules define no a9_shippable or ADHERENCE_SUFFIXES: "
                            "files the release would ship cannot be listed"]


def test_shipping_files_pass_the_real_release_rules():
    if pp.release_rules(pp.ROOT) is None:
        pytest.skip("public tree: the release rules have already been applied")
    # every shipping file is in place (Tasks 7 and 8 wrote the study files, lock, build record and README)
    p, n = pp.check_shipping(pp.HERE, pp.ROOT, "private", require_all=True)
    assert p == [] and n >= 4                                                   # prepare.py, test_prepare.py, a9-config.json


# ---- positive control: the detector must find what the hosted sources really carry
REAL_SOURCES = [pytest.param(rel, id=Path(rel).stem) for rel in pp.REAL_C2PA_SOURCES]
MUST_FIND = ["box /uuid not allowed", "provenance bytes: C2PA uuid", "provenance bytes: C2PA JUMBF type"]


@pytest.mark.parametrize("rel", REAL_SOURCES)
def test_the_detector_finds_the_credentials_real_hosted_sources_carry(rel):
    f = pp.ROOT / rel
    if not f.is_file():
        pytest.skip("source not in this tree")
    found = pp.check_mp4_bytes(f)                                               # bytes only; the clip is never opened
    for need in MUST_FIND:
        assert need in found, (rel, need)


@pytest.mark.parametrize("rel", ["runs/wan22/cu-line-2_burst_wan22.mp4", "runs/ltx23/cu-line-2_burst_ltx23.mp4"])
def test_local_engine_sources_carry_no_credential_bytes(rel):
    f = pp.ROOT / rel
    if not f.is_file():
        pytest.skip("source not in this tree")
    found = pp.check_mp4_bytes(f)
    assert not any(x.startswith("provenance bytes: C2PA") or x == "box /uuid not allowed" for x in found), found


@needs_ffmpeg
@pytest.mark.parametrize("rel", REAL_SOURCES)
def test_a_real_credentialed_source_encodes_to_a_clean_copy(tmp_path, rel):
    f = pp.ROOT / rel
    if not f.is_file():
        pytest.skip("source not in this tree")
    size = pp.target_size(pp.probe(f))                                          # metadata only
    pp.encode_clip(f, tmp_path / "copy.mp4", size)                              # a scratch copy in the pytest folder
    assert pp.check_copy(tmp_path / "copy.mp4", size) == []
    data = (tmp_path / "copy.mp4").read_bytes()
    assert pp.C2PA_BMFF_UUID not in data and pp.C2PA_JUMBF_TYPE not in data


def private_root(tmp_path):
    (tmp_path / "runs").mkdir(exist_ok=True)
    (tmp_path / "tools").mkdir(exist_ok=True)
    pp.write_text(tmp_path / "runs/manifest.jsonl", "")
    pp.write_text(tmp_path / "tools/build_release.py", "")
    return tmp_path


@needs_ffmpeg
def test_positive_control_fails_when_the_detector_goes_deaf(tmp_path, clean_copy):
    for rel in pp.REAL_C2PA_SOURCES:                                            # sources that carry nothing: a deaf detector looks like this
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(clean_copy, tmp_path / rel)
    p, n = pp.positive_control(tmp_path, "public")
    assert n == len(pp.REAL_C2PA_SOURCES) and len(p) == 3 * n and all("detector missed" in x for x in p)
    assert all("box may have moved" in x for x in p)                            # the message says where else to look
    planted = box(b"uuid", pp.C2PA_BMFF_UUID + b"jumb" + pp.C2PA_JUMBF_TYPE)
    for rel in pp.REAL_C2PA_SOURCES:
        (tmp_path / rel).write_bytes(clean_copy.read_bytes() + planted)
    assert pp.positive_control(tmp_path, "public") == ([], len(pp.REAL_C2PA_SOURCES))
    assert pp.positive_control(tmp_path / "nowhere", "public") == ([], 0)       # the public tree may have no sources


@needs_ffmpeg
def test_positive_control_cannot_pass_vacuously_in_the_private_tree(tmp_path, clean_copy):
    root = private_root(tmp_path)
    planted = box(b"uuid", pp.C2PA_BMFF_UUID + b"jumb" + pp.C2PA_JUMBF_TYPE)
    assert pp.positive_control(root, "private") == (["positive control: 0 of 3 hosted sources checked, 3 needed"], 0)
    for rel in pp.REAL_C2PA_SOURCES[:2]:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(clean_copy.read_bytes() + planted)
    assert pp.positive_control(root, "private") == (["positive control: 2 of 3 hosted sources checked, 3 needed"], 2)
    rel = pp.REAL_C2PA_SOURCES[2]
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_bytes(clean_copy.read_bytes() + planted)
    assert pp.positive_control(root, "private") == ([], 3)


def test_positive_control_names_the_tree_it_was_run_on(tmp_path):
    with pytest.raises(ValueError, match="tree"):
        pp.positive_control(tmp_path, "either")
    with pytest.raises(TypeError):
        pp.positive_control(tmp_path)                                           # no default
    p, n = pp.positive_control(tmp_path, "private")                             # no manifest, no release script, no sources
    assert n == 0 and p == ["private tree: runs/manifest.jsonl is missing", "private tree: tools/build_release.py is missing",
                            "positive control: 0 of 3 hosted sources checked, 3 needed"]
    p, n = pp.positive_control(private_root(tmp_path), "public")
    assert n == 0 and p == ["public tree: runs/manifest.jsonl exists (this is the private tree)",
                            "public tree: tools/build_release.py exists (this is the private tree)"]


def test_positive_control_on_the_real_sources():
    if not (pp.ROOT / "runs" / "manifest.jsonl").is_file():
        pytest.skip("not the private tree")
    assert pp.positive_control(pp.ROOT, "private") == ([], len(pp.REAL_C2PA_SOURCES))


# ---- hardening (spec review): unreadable values, free boxes, the encoder SEI, orientation counts
@needs_ffmpeg
def test_a_value_error_inside_a_check_is_a_problem_not_a_crash(clean_copy, monkeypatch):
    monkeypatch.setattr(pp, "count_frames", lambda path: int("N/A"))          # ffprobe printed N/A
    p = pp.check_copy(clean_copy, pp.LANDSCAPE)
    assert len(p) == 1 and p[0].startswith("unreadable: ") and "N/A" in p[0]


def test_a_free_box_must_be_empty_or_all_zero(tmp_path):
    def check(*free_payloads):
        f = tmp_path / "f.mp4"
        f.write_bytes(box(b"ftyp", bytes(8)) + box(b"moov") + b"".join(box(b"free", x) for x in free_payloads))
        return pp.check_mp4_bytes(f)
    assert check(b"") == [] and check(bytes(40)) == [] and check(b"", bytes(1000), b"") == []
    (only,) = check(bytes(3) + b"\x01" + bytes(3))
    assert only == "box /free at byte 24 carries data"
    (only,) = check(b"", b"hidden payload")
    assert only == "box /free at byte 32 carries data"


@needs_ffmpeg
def test_the_encoder_sei_and_tags_are_caught_in_a_copy(clean_copy, tmp_path):
    assert pp.check_mp4_bytes(clean_copy) == []
    raw = make_clip(tmp_path / "raw.mp4", (1280, 704), 24, 121)             # an ordinary libx264 encode keeps its SEI text
    data = raw.read_bytes()
    assert b"x264" in data and b"- H.264/MPEG-4 AVC codec" in data
    p = pp.check_mp4_bytes(raw)
    assert "encoder text: H.264/MPEG-4 AVC codec string" in p
    assert "encoder text: lavf" in p


def test_encoder_text_rules_by_location(tmp_path):
    def check(*boxes):
        f = tmp_path / "e.mp4"
        f.write_bytes(box(b"ftyp", bytes(8)) + box(b"moov") + b"".join(boxes))
        return pp.check_mp4_bytes(f)
    long_string = b"x264 - core 164 r3095 - H.264/MPEG-4 AVC codec - Copyleft"
    assert check(box(b"mdat", long_string)) == ["encoder text: H.264/MPEG-4 AVC codec string"]      # the long string, even in mdat
    assert check(box(b"mdat", b"..x264..core ..Lavc..")) == []                                      # short tokens are chance in mdat
    assert check(box(b"free", b"X264 core ")) == ["box /free at byte 24 carries data", "encoder text: x264", "encoder text: core "]
    assert check(box(b"free", b"Lavc61")) == ["box /free at byte 24 carries data", "encoder text: lavc"]


def clip_rows(panel_flags):
    """media-sources 'clips' for {panel: (portrait?, engines)}."""
    return {f"{pid}_burst_{i}_{e}": {"panel": pid, "engine": e,
                                     "source_video": {"width": 720 if tall else 1280, "height": 1280 if tall else 720}}
            for pid, (tall, engines) in panel_flags.items() for i, e in enumerate(engines)}


def panels_of(clips):
    return {rec["panel"]: {} for rec in clips.values()}


def test_orientation_is_the_tank_row_portrait_and_every_other_row_landscape():
    spec = dict(pp.BURST, n_clips=10, n_panels=2)                                # 2 panels x 5 engines
    engines = list(pp.ENGINES)
    ok = clip_rows({"cip-act-tank-1": (True, engines), "cu-line-2": (False, engines)})
    assert pp.orientation_problems(spec, ok, panels_of(ok)) == []
    swapped = clip_rows({"cip-act-tank-1": (False, engines), "cu-line-2": (True, engines)})
    assert pp.orientation_problems(spec, swapped, panels_of(swapped)) == [
        "cip-act-tank-1: a landscape row, expected portrait", "cu-line-2: a portrait row, expected landscape"]
    mixed = clip_rows({"cip-act-tank-1": (True, engines[:4]), "cu-line-2": (False, engines)})
    mixed["cip-act-tank-1_x"] = dict(mixed["cip-act-tank-1_burst_0_" + engines[0]], engine=engines[4],
                                     source_video={"width": 1280, "height": 720})
    assert pp.orientation_problems(spec, mixed, panels_of(mixed)) == ["cip-act-tank-1: engines disagree on orientation"]


def test_a_full_study_needs_exactly_one_clip_per_panel_and_engine():
    spec, engines = dict(pp.BURST, n_clips=10, n_panels=2), list(pp.ENGINES)
    base = clip_rows({"cip-act-tank-1": (True, engines), "cu-line-2": (False, engines)})
    panels = panels_of(base)
    short = {k: v for k, v in base.items() if not k.endswith(engines[4])}
    assert pp.orientation_problems(spec, short, panels) == [f"cip-act-tank-1: 0 clips from {engines[4]}, expected 1",
                                                            f"cu-line-2: 0 clips from {engines[4]}, expected 1"]
    twice = dict(base, extra=dict(base["cu-line-2_burst_0_" + engines[0]]))
    assert pp.orientation_problems(spec, twice, panels) == [f"cu-line-2: 2 clips from {engines[0]}, expected 1"]
    norow = {k: v for k, v in base.items() if v["panel"] != "cu-line-2"}
    assert pp.orientation_problems(spec, norow, panels) == [f"cu-line-2: 0 clips from {e}, expected 1" for e in engines]
    ghost = dict(base, ghost=dict(base["cu-line-2_burst_0_" + engines[0]], panel="ghost-row"))
    assert "ghost: panel 'ghost-row' is not in panels" in pp.orientation_problems(spec, ghost, panels)


def test_every_study_refuses_an_engine_outside_the_five_and_a_clip_without_a_panel():
    clips = clip_rows({"cu-line-2": (False, ["seedance", list(pp.ENGINES)[0]])})
    for spec in (dict(pp.PILOT, n_clips=2, n_panels=1), dict(pp.BURST, n_clips=2, n_panels=1)):
        assert pp.orientation_problems(spec, clips, panels_of(clips)) == [
            "cu-line-2_burst_0_seedance: engine 'seedance' is not one of the five"]
    first = list(pp.ENGINES)[0]
    assert pp.orientation_problems(dict(pp.PILOT, n_clips=2, n_panels=1), clips, {"other": {}}) == [
        "cu-line-2_burst_0_seedance: panel 'cu-line-2' is not in panels",
        "cu-line-2_burst_0_seedance: engine 'seedance' is not one of the five",
        f"cu-line-2_burst_1_{first}: panel 'cu-line-2' is not in panels"]


def test_orientation_engine_count_applies_only_to_a_full_study():
    engines = list(pp.ENGINES)
    two = clip_rows({"cip-act-tank-1": (True, engines[:1]), "cu-line-2": (False, engines[:1])})
    assert pp.orientation_problems(dict(pp.BURST, n_clips=2, n_panels=2), two, panels_of(two)) == []   # a tiny test tree
    pilot = clip_rows({"cu-line-2": (False, engines[:1])})
    assert pp.orientation_problems(dict(pp.PILOT, n_clips=1, n_panels=1), pilot, panels_of(pilot)) == []


# ---- hardening (quality review): banned-term loading, media-sources fields, and smaller false-pass paths
def test_banned_terms_that_do_not_load_are_problems_not_crashes():
    assert pp.parse_banned("") == ([], ["no banned terms loaded"])
    assert pp.parse_banned("# only a comment\n\n   \n") == ([], ["no banned terms loaded"])
    terms, problems = pp.parse_banned("ok\n/(unclosed/i\n/abc/g\n/abc/ig\n/fine/i\n")
    assert [t if isinstance(t, str) else t.pattern for t in terms] == ["ok", "fine"]
    assert len(problems) == 3
    assert problems[0].startswith("banned-terms line 2: bad regular expression")
    assert problems[1] == "banned-terms line 3: flags 'g' not supported (only 'i')"
    assert problems[2] == "banned-terms line 4: flags 'ig' not supported (only 'i')"
    terms, problems = pp.parse_banned("/(bad/\n")                               # nothing valid left: both are reported
    assert terms == [] and len(problems) == 2 and problems[-1] == "no banned terms loaded"


def edit_sources(here, fn):
    f = here / "burst/media-sources.json"
    doc = json.loads(pp.read_text(f))
    fn(doc)
    pp.write_json(f, doc)


@needs_ffmpeg
def test_check_study_names_missing_fields_instead_of_crashing(tmp_path):
    root, here, spec, cells = small_tree(tmp_path)
    pp.build_media(spec, cells, root, here)
    wan = "cu-line-2_burst_wan22"
    edit_sources(here, lambda d: d["clips"][wan].pop("copy_sha256"))
    assert f"{wan}: missing field 'copy_sha256'" in pp.check_study(spec, here)[0]
    edit_sources(here, lambda d: d["clips"][wan].update(copy_sha256="b" * 64) or d["clips"][wan]["source_video"].pop("width"))
    assert f"{wan}: source_video has no width" in pp.check_study(spec, here)[0]
    edit_sources(here, lambda d: d["clips"][wan].pop("panel") and None)
    assert f"{wan}: missing field 'panel'" in pp.check_study(spec, here)[0]
    edit_sources(here, lambda d: d["panels"]["cu-line-2"].pop("copy"))
    assert "cu-line-2: missing field 'copy'" in pp.check_study(spec, here)[0]
    edit_sources(here, lambda d: d.pop("clips"))
    assert pp.check_study(spec, here) == (["media-sources.json: no 'clips' object"], {})
    edit_sources(here, lambda d: d.update(clips=[], panels={}))
    assert pp.check_study(spec, here) == (["media-sources.json: no 'clips' object"], {})
    edit_sources(here, lambda d: d.update(clips={wan: "not an object"}))
    assert f"{wan}: not an object" in pp.check_study(spec, here)[0]


@needs_ffmpeg
@pytest.mark.parametrize("bad", ["media/../x.mp4", "elsewhere/x.mp4", "/abs/x.mp4", "media\\x.mp4", "media/a/../../x.mp4", ""])
def test_check_study_keeps_every_copy_path_inside_media(tmp_path, bad):
    root, here, spec, cells = small_tree(tmp_path)
    pp.build_media(spec, cells, root, here)
    wan = "cu-line-2_burst_wan22"
    edit_sources(here, lambda d: d["clips"][wan].update(copy=bad))
    p, hashes = pp.check_study(spec, here)
    assert f"{wan}: copy path {bad!r} must be a file inside media/" in p
    assert all(not k.endswith("x.mp4") for k in hashes)


@needs_ffmpeg
def test_check_study_checks_panel_dimensions_and_shape(tmp_path):
    root, here, spec, cells = small_tree(tmp_path)
    doc = pp.build_media(spec, cells, root, here)
    assert (doc["panels"]["cip-act-tank-1"]["width"], doc["panels"]["cip-act-tank-1"]["height"]) == (36, 64)
    assert pp.check_study(spec, here)[0] == []
    edit_sources(here, lambda d: d["panels"]["cu-line-2"].update(width=999))
    assert "cu-line-2: panel copy is 64x36, media-sources.json records 999x36" in pp.check_study(spec, here)[0]
    edit_sources(here, lambda d: d["panels"]["cu-line-2"].pop("height"))
    assert "cu-line-2: missing field 'height'" in pp.check_study(spec, here)[0]
    # a portrait picture on a landscape row (and its record agrees): the shape check still fires
    new = write_png(tmp_path / "t.png", 36, 64)
    shutil.copy(new, here / "burst/media/cu-line-2.png")
    edit_sources(here, lambda d: d["panels"]["cu-line-2"].update(width=36, height=64, copy_sha256=pp.sha256_file(new)))
    assert pp.check_study(spec, here)[0] == ["cu-line-2: a portrait panel, expected landscape"]


@needs_ffmpeg
def test_check_study_sees_identical_panel_copies(tmp_path):
    root, here, spec, cells = small_tree(tmp_path)
    pp.build_media(spec, cells, root, here)
    media = here / "burst/media"
    shutil.copy(media / "cu-line-2.png", media / "cip-act-tank-1.png")
    assert any("burst/media/cip-act-tank-1.png and burst/media/cu-line-2.png are identical files" in x
               for x in pp.check_study(spec, here)[0])


def test_a_meta_box_too_short_for_its_version_and_flags_is_a_bad_box():
    with pytest.raises(ValueError, match="bad box size"):
        pp.mp4_boxes(box(b"moov", box(b"udta", box(b"meta", bytes(2)))))
    assert pp.mp4_boxes(box(b"moov", box(b"udta", box(b"meta", bytes(4)))))[-1][0] == "/moov/udta/meta"


def test_a_copy_must_have_ftyp_and_moov(tmp_path):
    f = tmp_path / "x.mp4"
    f.write_bytes(box(b"free"))
    assert pp.check_mp4_bytes(f) == ["box /ftyp is missing", "box /moov is missing"]
    f.write_bytes(box(b"ftyp", bytes(8)) + box(b"mdat", b"xx"))
    assert pp.check_mp4_bytes(f) == ["box /moov is missing"]
    f.write_bytes(box(b"ftyp", bytes(8)) + box(b"moov") + box(b"mdat", b"xx"))
    assert pp.check_mp4_bytes(f) == []


@needs_ffmpeg
def test_one_unreadable_probe_does_not_hide_the_other_problems(clean_copy, monkeypatch):
    def broken(path):
        raise RuntimeError("a video packet has no timestamp")
    monkeypatch.setattr(pp, "frame_gaps", broken)
    p = pp.check_copy(clean_copy, pp.PORTRAIT)
    assert any(x.startswith("size 1280x704") for x in p)
    assert "unreadable: a video packet has no timestamp" in p


# ---------------------------------------------------------------- the study files (Task 4)
# Codes produced by blindpanel's own opaqueCode (dist/core/codes.js, node), not by prepare.py: the
# first three are the ones its synthetic example builds with; the rest are this plan's own seeds.
BLINDPANEL_CODES = [
    ("synthetic-demo-1", "clip", "box-still_engine-alpha", "c580jm"),
    ("synthetic-demo-1", "clip", "box-drift_engine-beta", "cjjptg"),
    ("synthetic-demo-1", "panel", "panel-box", "pw8bmg"),
    ("a9-burst-2026-10-31", "clip", "cu-line-2_burst_wan22", "cmj4rg"),
    ("a9-burst-2026-10-31", "clip", "cip-act-tank-1_burst_h3", "cqy114"),
    ("a9-burst-2026-10-31", "panel", "cip-act-tank-1", "phk040"),
    ("a9-burst-2026-10-31", "panel", "cu-line-2", "pbbggv"),
    ("a9-push-2026-10-31", "clip", "cu-line-2_burst_wan22", "ca9bng"),
    ("a9-push-2026-10-31", "clip", "est-tone-2_campush_gen45", "c148s5"),
    ("a9-push-2026-10-31", "panel", "chain-est-cosmic-1", "py4538"),
    ("a9-pilot-2026-10-31", "clip", "cu-line-1_burst_h3-h1", "cekr69"),
    ("a9-pilot-2026-10-31", "panel", "cu-line-1", "p1vwgf"),
    ("ünï-seed", "clip", "x", "cdyhee"),                      # a seed outside ASCII hashes as UTF-8
]
BLINDPANEL = os.environ.get("BLINDPANEL")
needs_blindpanel = pytest.mark.skipif(not (BLINDPANEL and shutil.which("node")),
                                      reason="set BLINDPANEL to blindpanel's bin/blindpanel.mjs (and have node)")


def public_ids(spec):
    """The 55 clip ids and 11 panel ids a real study has (the tank row under its public id)."""
    token = {"BURST": "burst", "CAMPUSH": "campush"}[spec["motion_class"]]
    panels = [p.replace(PRIVATE_TANK, "cip-act-tank-1") for p in (BURST_PANELS if token == "burst" else PUSH_PANELS)]
    return [f"{p}_{token}_{s}" for p in panels for s in pp.ENGINES.values()], panels


def full_sources(spec):
    """A media-sources.json of the registered size: 55 clips on 11 panels (placeholder hashes)."""
    cids, pids = public_ids(spec)
    return {"panels": {p: {"copy": f"media/{p}.png", "copy_sha256": hashlib.sha256(p.encode()).hexdigest()}
                       for p in pids},
            "clips": {c: {"panel": c.rsplit("_", 2)[0], "copy": f"media/{c}.mp4",
                          "copy_sha256": hashlib.sha256(c.encode()).hexdigest()} for c in cids}}


def test_opaque_code_matches_blindpanel():
    for seed, kind, item, code in BLINDPANEL_CODES:
        assert pp.opaque_code(seed, kind, item) == code, (seed, kind, item)


@needs_blindpanel
def test_opaque_code_agrees_with_blindpanels_own_code_for_every_real_id():
    clips, panels = {}, {}
    for key in ("burst", "push", "pilot"):
        spec = pp.STUDIES[key]
        cids, pids = public_ids(pp.BURST if key == "pilot" else spec)
        clips[spec["seed"]], panels[spec["seed"]] = cids, pids
    js = ("const { opaqueCode } = await import(process.argv[1]);"
          "const want = JSON.parse(process.argv[2]); const out = [];"
          "for (const [s, k, i] of want) out.push(await opaqueCode(s, k, i));"
          "console.log(JSON.stringify(out));")
    asks = [[s, "clip", i] for s, ids in clips.items() for i in ids] + \
           [[s, "panel", i] for s, ids in panels.items() for i in ids]
    codes_js = Path(BLINDPANEL).resolve().parent.parent / "dist" / "core" / "codes.js"
    r = subprocess.run(["node", "--input-type=module", "-e", js, codes_js.as_uri(), json.dumps(asks)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [pp.opaque_code(s, k, i) for s, k, i in asks] and len(asks) == 3 * 66


def test_codes_do_not_collide_inside_a_study():
    """blindpanel refuses a build whose codes collide (25 bits each): these exact id sets must not."""
    for key in ("burst", "push"):
        cids, pids = public_ids(pp.STUDIES[key])
        seed = pp.STUDIES[key]["seed"]
        assert len(cids) == 55 and len(pids) == 11
        assert len({pp.opaque_code(seed, "clip", i) for i in cids}) == 55
        assert len({pp.opaque_code(seed, "panel", i) for i in pids}) == 11


def test_study_table_has_what_the_slim_tool_reads():
    """analysis/a9_adherence.py slim reads STUDIES[study]["seed"] and calls opaque_code(seed, "clip", id)."""
    for key in ("burst", "push"):
        s = pp.STUDIES[key]
        assert isinstance(s["seed"], str) and s["seed"] and s["id"] == f"a9-{key}" and s["dir"] == key
    assert pp.opaque_code(pp.STUDIES["burst"]["seed"], "clip", "cu-line-2_burst_wan22") == "cmj4rg"


def test_the_registered_wording():
    assert pp.BURST_CLAUSE == ("The action implied by the drawing continues in one fast, committed burst "
                               "of motion, then settles.")
    assert pp.PUSH_CLAUSE == "Slow, steady camera push-in toward the focal point of the drawing."
    assert pp.BURST["labels"] == [
        "No: the implied action doesn't happen (still, idle movement only, or something else)",
        "Barely: small or hesitant, not a burst", "Partly",
        "Mostly: a burst, a little weak or incomplete", "Yes: one fast, committed burst"]
    assert pp.PUSH["labels"][0] == "No push-in (holds, pulls back, pans or cuts)"
    assert pp.PUSH["labels"][4] == "A slow, steady push-in toward the main subject"
    assert pp.PILOT["labels"] == pp.BURST["labels"] and pp.PILOT["clause"] == pp.BURST_CLAUSE


def test_study_config_blinds_and_quotes_only_the_clause():
    for spec in (pp.BURST, pp.PUSH):
        c = pp.study_config(spec, SOURCES)
        q = c["questions"][0]
        assert spec["clause"] in q["text"]
        for other in ("Camera locked off", "No subject motion", "inked drawing", "ambient drift"):
            assert other not in q["text"]
        assert c["instrument"] == "A9" and "reference" not in c and c["media"]["base"] == "./media/"
        assert all(x["label"] == "clip" and x["meta"] == {} and "link" not in x for x in c["items"]["clips"])
        assert c["parts"]["clips"]["session_size"] == 3 and c["parts"]["clips"]["extend"] is False
        assert c["modes"]["public"] == {"submit": True, "tally": False}
        assert len(c["scales"][q["scale"]]["labels"]) == 5
        assert c["blinding"] == {"seed": spec["seed"], "banned_terms_file": "banned-terms.txt",
                                 "embedded_provenance": "allow"}
        assert [p["id"] for p in c["items"]["panels"]] == ["cu-line-2"]
        assert {x["reference"] for x in c["items"]["clips"]} == {"cu-line-2"}


def test_the_question_texts_as_registered():
    assert pp.question_text(pp.BURST) == ('The clip was asked for this motion: **"The action implied by the '
                                          'drawing continues in one fast, committed burst of motion, then '
                                          'settles."** Does the clip do it?')
    assert pp.question_text(pp.PUSH) == ('The clip was asked for this motion: **"Slow, steady camera push-in '
                                         'toward the focal point of the drawing."** Does the clip do it?')


def page_text(config):
    """Everything blindpanel can put on the rating page or in reveal.json: the config without the item ids
    and file names (those are only hashed into opaque codes), plus each item's label, meta and link."""
    shown = {k: v for k, v in config.items() if k != "items"}
    items = [{k: x.get(k) for k in ("label", "meta", "link")} for x in config["items"]["clips"]]
    return json.dumps([shown, items], ensure_ascii=False)


def test_nothing_engine_revealing_reaches_the_page_or_reveal_json():
    banned, problems = pp.parse_banned(pp.BANNED_TERMS)
    assert problems == []
    for spec in (pp.BURST, pp.PUSH, pp.PILOT):
        text = page_text(pp.study_config(spec, SOURCES))
        assert pp.find_banned(text, banned) == [], spec["id"]
        for word in ("wan", "ltx", "gen4", "h3", "engine", "runway", "model"):
            assert word not in text.lower(), (spec["id"], word)
        if pp.load_private_terms()[0]:                      # private repo: the private terms too
            assert pp.find_banned(text, pp.load_private_terms()[0]) == [], spec["id"]
    assert "push" not in page_text(pp.study_config(pp.BURST, SOURCES)).lower().replace("push-in", "")
    assert "burst" not in page_text(pp.study_config(pp.PUSH, SOURCES)).lower()


def test_the_banned_terms_file_bans_what_the_studies_must_not_show():
    banned, problems = pp.parse_banned(pp.BANNED_TERMS)
    assert problems == []
    for leak in ("Wan 2.2", "wan22", "gen45", "Gen-4 Turbo", "LTX-2.3", "H3", "h3-fal", "Hailuo", "cu-line-2",
                 "cip-act-tank-1", "x_burst_y", "x_campush_y", "x_idle_y"):
        assert pp.find_banned(leak, banned), leak
    assert pp.BANNED_TERMS.endswith("\n") and "\r" not in pp.BANNED_TERMS


def test_seeds_are_fresh_and_clean():
    banned, problems = pp.parse_banned(pp.BANNED_TERMS)
    assert problems == []
    seeds = [s["seed"] for s in pp.STUDIES.values()]
    assert len(seeds) == 3 and len(set(seeds)) == 3 and not set(seeds) & pp.A6_SEEDS
    assert not any(pp.find_banned(s, banned) for s in seeds)
    ids = [f"cu-line-{i}_burst_wan22" for i in range(50)]
    a6 = {pp.opaque_code("stilldrawn-a6-blindpanel-1", "clip", i) for i in ids}
    for s in seeds:
        assert not {pp.opaque_code(s, "clip", i) for i in ids} & a6
    cids, _ = public_ids(pp.BURST)
    for a6_seed in pp.A6_SEEDS:                                  # no clip's code recurs from an A6 seed either
        old = {pp.opaque_code(a6_seed, "clip", i) for i in cids}
        assert not {pp.opaque_code(pp.BURST["seed"], "clip", i) for i in cids} & old


def test_to_yaml_round_trips():
    yaml = pytest.importorskip("yaml")
    for spec in (pp.BURST, pp.PUSH, pp.PILOT):
        c = pp.study_config(spec, SOURCES)
        assert yaml.safe_load(pp.to_yaml(c)) == c


def test_to_yaml_quotes_awkward_strings_and_keeps_types():
    yaml = pytest.importorskip("yaml")
    doc = {"s": ["yes", "null", "5", "a: b", '"q"', "back\\slash", "tab\there", "ünï · ✓", "- x", "#c", ""],
           "t": True, "f": False, "n": None, "i": 3, "x": 1.5, "e": {}, "l": [],
           "rows": [{"id": "a", "k": {}, "n": 1}, {"id": "b", "k": {}, "n": 2}], "nest": {"a": {"b": ["c", "d"]}}}
    assert yaml.safe_load(pp.to_yaml(doc)) == doc


def test_write_study_writes_both_files(tmp_path):
    (tmp_path / "burst").mkdir()
    pp.write_json(tmp_path / "burst/media-sources.json", full_sources(pp.BURST))
    pp.write_study(pp.BURST, tmp_path)
    text = pp.read_text(tmp_path / "burst/study.yaml")
    assert text.startswith("# Generated by prepare.py") and 'id: "a9-burst"' in text and text.endswith("\n")
    assert pp.read_text(tmp_path / "burst/banned-terms.txt") == pp.BANNED_TERMS
    assert b"\r" not in (tmp_path / "burst/study.yaml").read_bytes()
    before = (tmp_path / "burst/study.yaml").read_bytes()
    pp.write_study(pp.BURST, tmp_path)                                       # deterministic
    assert (tmp_path / "burst/study.yaml").read_bytes() == before


def test_write_study_is_utf8_whatever_the_locale(tmp_path, monkeypatch):
    monkeypatch.setattr("locale.getpreferredencoding", lambda *a, **k: "ascii")
    (tmp_path / "push").mkdir()
    pp.write_json(tmp_path / "push/media-sources.json", full_sources(pp.PUSH))
    pp.write_study(pp.PUSH, tmp_path)
    assert "·".encode("utf-8") in (tmp_path / "push/study.yaml").read_bytes()    # the direction line's middle dot


def test_study_files_pass_the_real_release_rules_unchanged(tmp_path):
    """study.yaml and banned-terms.txt ship, so the release build must neither reject nor rewrite them."""
    rules = pp.release_rules(pp.ROOT)
    if rules is None:
        pytest.skip("public tree: the release rules have already been applied")
    for spec in (pp.BURST, pp.PUSH):
        (tmp_path / spec["dir"]).mkdir()
        pp.write_json(tmp_path / spec["dir"] / "media-sources.json", full_sources(spec))
        pp.write_study(spec, tmp_path)
        for name in ("study.yaml", "banned-terms.txt"):
            raw = (tmp_path / spec["dir"] / name).read_bytes()
            text = raw.decode("utf-8")
            assert rules.LEAK_RE.search(text) is None, (spec["dir"], name)
            assert rules.rewrite_text(f"analysis/adherence/{spec['dir']}/{name}", text, []).encode("utf-8") == raw


def fill_media(sdir, sources):
    """Write placeholder bytes for every listed file and return sources with their true hashes."""
    doc = json.loads(json.dumps(sources))
    (sdir / "media").mkdir(parents=True, exist_ok=True)
    for rec in (*doc["panels"].values(), *doc["clips"].values()):
        data = f"placeholder {rec['copy']}".encode()
        (sdir / rec["copy"]).write_bytes(data)
        rec["copy_sha256"] = hashlib.sha256(data).hexdigest()
    return doc


@needs_blindpanel
def test_blindpanel_accepts_both_studies(tmp_path):
    for spec in (pp.BURST, pp.PUSH):
        sdir = tmp_path / spec["dir"]
        sdir.mkdir(exist_ok=True)
        pp.write_json(sdir / "media-sources.json", fill_media(sdir, full_sources(spec)))
        pp.write_study(spec, tmp_path)
        r = subprocess.run(["node", BLINDPANEL, "validate", str(sdir / "study.yaml")], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "55 clips, 11 panels, 1 questions" in r.stdout


@needs_blindpanel
def test_a_blindpanel_build_shows_and_reveals_nothing_engine_revealing(tmp_path):
    """A synthetic 55-clip study through blindpanel's own build: every built text file, reveal.json
    included, is clean under the banned terms, and reveal.json holds only "clip" labels and no meta."""
    banned, _ = pp.parse_banned(pp.BANNED_TERMS)
    for spec in (pp.BURST, pp.PUSH):
        sdir = tmp_path / spec["dir"]
        sdir.mkdir()
        pp.write_json(sdir / "media-sources.json", fill_media(sdir, full_sources(spec)))
        pp.write_study(spec, tmp_path)
        out = tmp_path / f"out-{spec['dir']}"
        r = subprocess.run(["node", BLINDPANEL, "build", str(sdir / "study.yaml"), "--out", str(out)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        reveal = json.loads((out / "reveal.json").read_text(encoding="utf-8"))
        assert len(reveal["items"]) == 55 and reveal["reference"] is None
        assert all(v == {"label": "clip", "meta": {}} for v in reveal["items"].values())
        for f in out.rglob("*"):
            if f.is_file() and f.suffix in (".html", ".json", ".txt", ".yaml", ".css") and f.name != "reveal.json":
                assert pp.find_banned(f.read_text(encoding="utf-8", errors="replace"), banned) == [], f.name
        built = "".join(f.read_text(encoding="utf-8", errors="replace") for f in out.rglob("*.json"))
        assert "wan22" not in built and "cu-line-2" not in built


# ---- two leftover minors in check_study
@pytest.mark.parametrize("doc, problem", [
    ("[]", "media-sources.json: not a JSON object"), ('"text"', "media-sources.json: not a JSON object"),
    ("null", "media-sources.json: not a JSON object"), ("3", "media-sources.json: not a JSON object")])
def test_check_study_reports_a_media_sources_file_that_is_not_an_object(tmp_path, doc, problem):
    (tmp_path / "burst").mkdir()
    pp.write_text(tmp_path / "burst/media-sources.json", doc)
    assert pp.check_study(pp.BURST, tmp_path) == ([problem], {})


def test_check_study_reports_media_sources_that_is_not_json(tmp_path):
    (tmp_path / "burst").mkdir()
    pp.write_text(tmp_path / "burst/media-sources.json", "{not json")
    (p, hashes) = pp.check_study(pp.BURST, tmp_path)
    assert hashes == {} and len(p) == 1 and p[0].startswith("media-sources.json: not valid JSON")
    (tmp_path / "burst/media-sources.json").write_bytes(b'{"clips": "\xff"}')
    (p, hashes) = pp.check_study(pp.BURST, tmp_path)
    assert hashes == {} and len(p) == 1 and p[0].startswith("media-sources.json: not valid JSON")


def one_record_sources(**overrides):
    sources = {"panels": {"cu-line-2": {"copy": "media/cu-line-2.png", "copy_sha256": "a" * 64,
                                        "width": 1280, "height": 704}},
               "clips": {"cu-line-2_burst_wan22": {"panel": "cu-line-2", "engine": "wan22",
                                                   "copy": "media/cu-line-2_burst_wan22.mp4", "copy_sha256": "b" * 64,
                                                   "source_video": {"width": 1280, "height": 704}}}}
    for path, value in overrides.items():
        kind, name, field = path.split("__")
        target = sources[kind][name]
        (target["source_video"] if field.startswith("sv_") else target)[field.removeprefix("sv_")] = value
    return sources


@pytest.mark.parametrize("override, problem", [
    ({"clips__cu-line-2_burst_wan22__sv_width": True}, "cu-line-2_burst_wan22: source_video width is not an integer"),
    ({"clips__cu-line-2_burst_wan22__sv_height": False}, "cu-line-2_burst_wan22: source_video height is not an integer"),
    ({"clips__cu-line-2_burst_wan22__sv_width": 1280.0}, "cu-line-2_burst_wan22: source_video width is not an integer"),
    ({"clips__cu-line-2_burst_wan22__sv_height": "704"}, "cu-line-2_burst_wan22: source_video height is not an integer"),
    ({"panels__cu-line-2__width": True}, "cu-line-2: width is not an integer"),
    ({"panels__cu-line-2__height": True}, "cu-line-2: height is not an integer"),
    ({"panels__cu-line-2__width": "1280"}, "cu-line-2: width is not an integer"),
])
def test_check_study_rejects_a_bool_or_other_non_integer_size(tmp_path, override, problem):
    (tmp_path / "burst").mkdir()
    pp.write_json(tmp_path / "burst/media-sources.json", one_record_sources(**override))
    assert problem in pp.check_study(pp.BURST, tmp_path)[0]


def test_check_study_accepts_integer_sizes_of_the_right_kind(tmp_path):
    (tmp_path / "burst").mkdir()
    pp.write_json(tmp_path / "burst/media-sources.json", one_record_sources())
    p, _ = pp.check_study(pp.BURST, tmp_path)
    assert not any("is not an integer" in x or "source_video has no" in x for x in p)


# ---- coordinator's three items: gen 4 with a space, the uncleared names, registered counts
def test_the_banned_terms_catch_gen_4_with_a_space_or_hyphen():
    banned, problems = pp.parse_banned(pp.BANNED_TERMS)
    assert problems == []
    for leak in ("Gen 4.5", "gen-4", "Gen4", "GEN 4 Turbo", "gen 4"):
        assert pp.find_banned(leak, banned), leak
    for clean in ("general 4", "gentle", "gen"):
        assert not pp.find_banned(clean, banned), clean


def test_the_shipped_banned_list_holds_no_private_term_in_any_form():
    banned, problems = pp.parse_banned(pp.BANNED_TERMS)
    assert problems == []
    rules = pp.release_rules(pp.ROOT)
    if rules is not None:                         # the file ships: the release must neither flag nor rewrite it
        assert rules.LEAK_RE.search(pp.BANNED_TERMS) is None
        assert rules.LEAK_RE.search(pp.deobfuscate(pp.BANNED_TERMS)) is None
        assert rules.rewrite_text("analysis/adherence/burst/banned-terms.txt", pp.BANNED_TERMS, []) == pp.BANNED_TERMS
    terms = pp.load_private_terms()[0]
    if terms:
        for t in terms:
            for form in (pp.BANNED_TERMS, pp.deobfuscate(pp.BANNED_TERMS)):
                assert pp.find_banned(form, [t]) == [], f"private-terms.txt line {t.n}"
                assert sample_of(t).strip("-").lower() not in re.sub(r"[^a-z0-9]", "", form.lower())


def test_the_private_terms_are_banned_when_their_file_is_present():
    terms = private_terms_or_skip()
    assert len(terms) >= 4
    for t in terms:
        s = sample_of(t)
        for leak in (f"a {s} b", f"a {s.upper()} b", f"The {s.title()} b"):
            assert pp.find_banned(leak, [t]) == [f"private term {t.n}"], (t.n, leak)
    for clean in ("clip", "Motion check: set 1", "c3tf9a", "media/cq4zgy.mp4"):
        assert pp.find_banned(clean, terms) == [], clean


def test_the_private_terms_file_is_tracked_in_the_private_repo_and_never_ships():
    rules = pp.release_rules(pp.ROOT)
    if rules is None:
        pytest.skip("public tree: the release rules (and the private terms file) are not here")
    assert pp.PRIVATE_TERMS_NAME not in pp.SHIPPING and pp.PRIVATE_TERMS_NAME not in pp.OPTIONAL_SHIPPING
    assert pp.PRIVATE_TERMS.is_file()
    assert not rules.a9_shippable(pp.PRIVATE_TERMS, pp.HERE, rules.ADHERENCE_SUFFIXES)
    assert pp.PRIVATE_TERMS not in rules.a9_allowlist(pp.ROOT)
    assert pp.PRIVATE_TERMS not in [src for src, _ in rules.allowlist()]
    listed, unlisted = pp.shipping_files(pp.HERE, rules)
    assert pp.PRIVATE_TERMS_NAME not in [*listed, *unlisted]


def test_a_missing_private_terms_file_is_said_and_the_public_list_alone_is_used(tmp_path):
    assert pp.load_private_terms(tmp_path / "nope.txt") == (None, [])
    note = pp.private_terms_note(tmp_path)
    assert "absent" in note and "public list only" in note
    root, here, dist = fake_build(tmp_path)
    assert chk(root, here, dist)[0] == []


def test_private_terms_are_loaded_from_beside_the_studies_and_never_echoed(tmp_path):
    stand_in = "zorblax"                                      # synthetic; tests check the mechanism only
    root, here, dist = fake_build(tmp_path)
    pp.write_text(here / pp.PRIVATE_TERMS_NAME, f"# synthetic\n{stand_in}\n/qu[o]rg\\b/i\n")
    assert "2 loaded" in pp.private_terms_note(here)
    assert chk(root, here, dist)[0] == []
    (dist / "page.html").write_text(f"<p>a {stand_in} and a QUORG</p>\n")
    (dist / f"{stand_in}.txt").write_text("harmless\n")
    p, _, _ = chk(root, here, dist)
    assert "page.html: banned term private term 2" in p and "page.html: banned term private term 3" in p
    assert f"{stand_in}.txt: path banned term private term 2" in p
    assert not any(stand_in in x.lower() or "quorg" in x.lower() for x in p if x.startswith("page.html"))   # the term is not echoed
    pp.write_text(here / pp.PRIVATE_TERMS_NAME, "# nothing\n")
    assert any(x.startswith(f"{pp.PRIVATE_TERMS_NAME}: no banned terms loaded") for x in chk(root, here, dist)[0])


def test_check_shipping_scans_the_shipping_files_for_the_private_terms_in_split_forms(tmp_path):
    stand_in = "zorblax"
    root, here = fake_rules_root(tmp_path), tmp_path / "here"
    here.mkdir()
    pp.write_text(here / "prepare.py", "clean\n")
    assert pp.check_shipping(here, root, "private", require_all=False) == ([], 1)
    pp.write_text(here / PRIVATE_NAME, f"{stand_in}\n")
    assert pp.check_shipping(here, root, "private", require_all=False)[0] == []
    for body in (f"x = '{stand_in}'\n", "x = 'zor' 'blax'\n", 'x = "zor" + "blax"\n', "x = ('zor' +\n     'blax')\n",
                 "z[o]rbl[a]x\n", "zor\\x62lax\n", "zor\\u0062lax\n", "zor\u200bblax\n"):
        pp.write_text(here / "README.md", body)
        p, _ = pp.check_shipping(here, root, "private", require_all=False)
        assert [x for x in p if x.startswith("README.md: private term 1")], body
        assert not any(stand_in in x for x in p)                                   # never echoed
    pp.write_text(here / "README.md", "zorbla and blax and zor, blax\n")
    assert pp.check_shipping(here, root, "private", require_all=False)[0] == []


def test_deobfuscate_joins_split_strings_and_opens_character_classes():
    assert pp.deobfuscate("f('ab' 'cd' + \"ef\")") == "f('abcdef\")"          # the inner quotes go, the outer stay
    assert pp.deobfuscate("a[b]c") == "abc"
    assert pp.deobfuscate("a\\x62c a\\u0062c") == "abc abc"
    assert pp.deobfuscate("a\u00adb\u200bc") == "abc"
    assert pp.deobfuscate("plain text, [1, 2] and {'k': 'v'}") == "plain text, [1, 2] and {'k': 'v'}"


@pytest.mark.parametrize("spec, clips, panels", [(pp.BURST, 54, 11), (pp.BURST, 55, 10), (pp.BURST, 56, 11),
                                                 (pp.PUSH, 3, 1), (pp.PUSH, 55, 12)])
def test_write_study_refuses_a_study_of_the_wrong_size(tmp_path, spec, clips, panels):
    doc = full_sources(spec)
    for name, n in (("clips", clips), ("panels", panels)):
        keep = sorted(doc[name])[:n]
        doc[name] = {k: doc[name][k] for k in keep} if n <= len(doc[name]) else {
            **doc[name], **{f"extra-{i}": dict(next(iter(doc[name].values()))) for i in range(n - len(doc[name]))}}
    (tmp_path / spec["dir"]).mkdir()
    pp.write_json(tmp_path / spec["dir"] / "media-sources.json", doc)
    with pytest.raises(ValueError, match=f"{spec['id']}: .*expected {spec['n_clips']} clips and {spec['n_panels']} panels"):
        pp.write_study(spec, tmp_path)
    assert not (tmp_path / spec["dir"] / "study.yaml").exists()
    assert not (tmp_path / spec["dir"] / "banned-terms.txt").exists()


def test_write_study_registered_sizes_and_the_pilots_own():
    assert (pp.BURST["n_clips"], pp.BURST["n_panels"], pp.PUSH["n_clips"], pp.PUSH["n_panels"]) == (55, 11, 55, 11)
    assert (pp.PILOT["n_clips"], pp.PILOT["n_panels"]) == (6, 6)


def test_write_study_accepts_the_pilots_six_clips_on_six_panels(tmp_path):
    doc = {"panels": {f"p{i}": {"copy": f"media/p{i}.png", "copy_sha256": "a" * 64} for i in range(6)},
           "clips": {f"p{i}_burst_x": {"panel": f"p{i}", "copy": f"media/p{i}_burst_x.mp4", "copy_sha256": "b" * 64}
                     for i in range(6)}}
    (tmp_path / "pilot").mkdir()
    pp.write_json(tmp_path / "pilot/media-sources.json", doc)
    pp.write_study(pp.PILOT, tmp_path)
    assert (tmp_path / "pilot/study.yaml").exists()


# ---------------------------------------------------------------- to_yaml: unsupported shapes are errors (C4 minors)
@pytest.mark.parametrize("doc", [
    {"a": [[1, 2]]},                      # a non-empty list inside a list
    {"a": [["x"]]},
    [[1]],
    {"a": (1, 2)},                        # a tuple is not a sequence here
    {"a": {1, 2}},
    {"a": b"bytes"},
    {"a": float("nan")}, {"a": float("inf")}, {"a": float("-inf")},
    "just a string", 3, None,             # the top level is a mapping or a sequence
])
def test_to_yaml_refuses_what_it_cannot_write(doc):
    with pytest.raises(TypeError):
        pp.to_yaml(doc)


@pytest.mark.parametrize("bad", ["\x7f", "\x85", "\x00", "\x01", "\x1b", "\x9f", "\r", " ", " ",
                                 "\ud800", "﻿", "￾", "a" + "\x85" + "b"])
def test_to_yaml_refuses_a_string_with_a_non_printable_character(bad):
    for doc in ({"s": bad}, {"s": ["ok", bad]}, {"s": [{"k": bad}]}):
        with pytest.raises(ValueError, match="non-printable"):
            pp.to_yaml(doc)


@pytest.mark.parametrize("key", ["Upper", "has space", "dash-ed", "1leading", "", "ünï", "a.b", "yes", "no", "on", "off",
                                 "null", "true", "false"])
def test_to_yaml_refuses_a_key_that_is_not_a_plain_lower_case_name(key):
    for doc in ({key: 1}, {"outer": {key: 1}}, [{key: 1}]):
        with pytest.raises(ValueError, match="key"):
            pp.to_yaml(doc)


def test_to_yaml_refuses_a_key_that_is_not_a_string():
    with pytest.raises(TypeError):
        pp.to_yaml({1: "x"})


def test_to_yaml_still_writes_what_the_studies_use():
    yaml = pytest.importorskip("yaml")
    doc = {"s": ["tab\there", "line\nbreak", "ünï · ✓ ‘q’"], "f": [1.5, -2.25, 1e22, 1e-7], "i": [0, -3, 10 ** 20],
           "t": [True, False, None], "e": [{}, []], "_k9": {"a_b": [{"x": 1, "y": {}}]}}
    assert yaml.safe_load(pp.to_yaml(doc)) == doc


# ---------------------------------------------------------------- the build, its record and the command line
SMALL = dict(pp.BURST, n_clips=3, n_panels=1)      # a three-clip stand-in for a registered study
BP_STUB = ("// A rating page, built with StillDrawn's blindpanel (a comment, not a banned word).\n"
           'export const UI_VERSION = "blindpanel@0.1.0"; const heading = "<h3>";\n')


def bld_codes(spec, sources):
    return ({c: pp.opaque_code(spec["seed"], "clip", c) for c in sources["clips"]},
            {x: pp.opaque_code(spec["seed"], "panel", x) for x in sources["panels"]})


def fake_build(tmp_path, spec=SMALL, sources=None):
    """(root, here, dist) of a clean synthetic build: blindpanel's files in its shapes, placeholder media."""
    root = fake_rules_root(tmp_path)
    here, dist = tmp_path / "here", tmp_path / "dist"
    sdir = here / spec["dir"]
    (dist / "media").mkdir(parents=True)
    (dist / "blindpanel/core").mkdir(parents=True)
    sdir.mkdir(parents=True)
    src = json.loads(json.dumps(sources or SOURCES))
    clip_code, panel_code = bld_codes(spec, src)
    for kind, table, codes, ext in (("panel", src["panels"], panel_code, ".png"),
                                    ("clip", src["clips"], clip_code, ".mp4")):
        for key, rec in table.items():
            data = f"{kind} bytes of {key}".encode()
            (dist / "media" / f"{codes[key]}{ext}").write_bytes(data)
            rec["copy_sha256"] = hashlib.sha256(data).hexdigest()
    pp.write_json(sdir / "media-sources.json", src)
    pp.write_json(sdir / "study.lock.json", LOCK)
    pp.write_text(sdir / "banned-terms.txt", pp.BANNED_TERMS)
    study = {"blindpanel": 1, "id": spec["id"], "instrument": LOCK["instrument"], "text_sha256": LOCK["text_sha256"],
             "seed": spec["seed"], "title": spec["title"],
             "questions": [{"id": "burst", "text": pp.question_text(spec)}],
             "panels": [{"code": k, "image": f"media/{k}.png"} for k in panel_code.values()],
             "parts": {"clips": {"clip_seconds": 5, "items": [
                 {"code": clip_code[c], "video": f"media/{clip_code[c]}.mp4", "reference": panel_code[r["panel"]]}
                 for c, r in src["clips"].items()]}},
             "modes": {"public": {"submit": True, "tally": False, "min_crowd_n": 5}},
             "endpoints": {"submit": "/api/submit", "tally": "/api/tally", "reveal": "reveal.json"}}
    pp.write_json(dist / "study.json", study)
    pp.write_json(dist / "reveal.json", {"study": spec["id"], "reference": None,
                                         "items": {k: {"label": "clip", "meta": {}} for k in clip_code.values()}})
    pp.write_text(dist / "index.html", "<!doctype html><title>Motion check</title><main id=app></main>\n")
    pp.write_text(dist / "blindpanel/core/payload.js", BP_STUB)
    return root, here, dist


def chk(root, here, dist, spec=SMALL, **kw):
    return pp.check_build(spec, here, dist, root, "private", **kw)


def edit_json(path, fn):
    doc = json.loads(path.read_text(encoding="utf-8"))
    fn(doc)
    pp.write_json(path, doc)


def test_check_build_passes_a_blind_build(tmp_path):
    root, here, dist = fake_build(tmp_path)
    p, tree, scanned = chk(root, here, dist)
    assert p == [] and re.fullmatch(r"[0-9a-f]{64}", tree) and tree == pp.tree_hash(dist)
    assert scanned == len([f for f in dist.rglob("*") if f.is_file()]) == 8       # 4 media files, study, reveal, index, one script
    assert chk(root, here, dist, expect_tree=tree)[0] == []
    p, _, _ = chk(root, here, dist, expect_tree="0" * 64)
    assert len(p) == 1 and "differs from the recorded" in p[0]


def test_check_build_works_in_the_public_tree_without_the_private_id(tmp_path):
    _, here, dist = fake_build(tmp_path)
    pub = tmp_path / "pub"
    pub.mkdir()
    p, tree, scanned = pp.check_build(SMALL, here, dist, pub, "public")
    assert p == [] and scanned == 8 and tree == pp.tree_hash(dist)
    p, _, _ = pp.check_build(SMALL, here, dist, tmp_path / "root", "public")        # a public run in the private tree
    assert any(x.startswith("public tree: ") for x in p)
    with pytest.raises(ValueError, match="tree"):
        pp.check_build(SMALL, here, dist, pub, "both")


@pytest.mark.parametrize("name", ["app.js", "style.css", "page.html", "data.json", "icon.svg", "app.js.map", "notes.txt",
                                  "NOTES.md", "LICENSE", "deep/er/mod.mjs", "blindpanel/ui/app.js"])
def test_check_build_scans_every_file_in_the_dist(tmp_path, name):
    root, here, dist = fake_build(tmp_path)
    f = dist / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("nothing to see here\n")
    assert chk(root, here, dist)[0] == []
    f.write_text("this one says Wan 2.2 in passing\n")
    p, _, _ = chk(root, here, dist)
    assert any(x.startswith(f"{name}: banned term") for x in p), p
    f.write_bytes(b"\xff\xfe binary-ish, then GEN-4 Turbo \x00\x01")           # undecodable bytes do not hide a term
    assert any(x.startswith(f"{name}: banned term") for x in chk(root, here, dist)[0])


def test_check_build_sees_a_term_hidden_behind_json_escapes(tmp_path):
    root, here, dist = fake_build(tmp_path)
    (dist / "data.json").write_text('{"m": "\\u0057an 2.2", "\\u006ctx": 1}\n')       # Wan 2.2 and ltx, escaped
    p, _, _ = chk(root, here, dist)
    assert sum(x.startswith("data.json: banned term") for x in p) >= 2, p
    (dist / "bad.map").write_text("{ not json but Kling\n")                           # unparseable: raw text still scanned
    assert any(x.startswith("bad.map: banned term") for x in chk(root, here, dist)[0])


def test_check_build_scans_the_text_in_the_study_and_reveal_files_themselves(tmp_path):
    root, here, dist = fake_build(tmp_path)
    edit_json(dist / "study.json", lambda s: s.update(title="Motion check: Runway set"))
    edit_json(dist / "reveal.json", lambda r: next(iter(r["items"].values())).update(label="Wan 2.2"))
    p, _, _ = chk(root, here, dist)
    assert any(x.startswith("study.json: banned term") for x in p)
    assert any(x.startswith("reveal.json: banned term") for x in p)
    assert any(x.startswith("reveal.json: item ") and "reveals something" in x for x in p)
    assert not any("Wan 2.2" in x for x in p if "reveals something" in x)         # a rater running this must not be told which clip


@pytest.mark.parametrize("rel", ["wan22/x.js", "media/gen45.txt", "a/ltx.map", "Runway.md", "x/h3-fal"])
def test_check_build_scans_every_file_path(tmp_path, rel):
    root, here, dist = fake_build(tmp_path)
    f = dist / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("harmless\n")
    p, _, _ = chk(root, here, dist)
    assert any(x.startswith(f"{rel}: path banned term") for x in p), p


OWN_SOURCES = {"panels": {"qq-panel": {"copy": "media/qq-panel.png", "copy_sha256": "a" * 64}},
               "clips": {"qq-panel_a": {"panel": "qq-panel", "copy": "media/qq-panel_a.mp4", "copy_sha256": "b" * 64},
                         "qq-panel_b": {"panel": "qq-panel", "copy": "media/qq-panel_b.mp4", "copy_sha256": "b" * 64},
                         "qq-panel_c": {"panel": "qq-panel", "copy": "media/qq-panel_c.mp4", "copy_sha256": "b" * 64}}}


def test_check_build_looks_for_the_literal_ids_the_banned_list_may_miss(tmp_path, monkeypatch):
    monkeypatch.setitem(pp.ENGINES, "newengine", "nwe9")
    root, here, dist = fake_build(tmp_path, sources=OWN_SOURCES)
    assert chk(root, here, dist)[0] == []
    for text in ("qq-panel_b", "QQ-PANEL", "see nwe9 here", PRIVATE_TANK):
        (dist / "notes.txt").write_text(text)
        p, _, _ = chk(root, here, dist)
        assert any(x.startswith("notes.txt: ") and "id" in x for x in p), (text, p)
    (dist / "notes.txt").unlink()
    (dist / "path-qq-panel_a.js").write_text("x")
    assert any(x.startswith("path-qq-panel_a.js: path ") for x in chk(root, here, dist)[0])


def test_check_build_leaves_short_ids_to_the_banned_list(tmp_path):
    root, here, dist = fake_build(tmp_path)
    (dist / "page.html").write_text("<h3>heading</h3> <h3 class=x>\n")           # the engine id h3 is two characters
    assert chk(root, here, dist)[0] == []
    (dist / "page.html").write_text("an H3 engine\n")                            # the banned list's /\bH3\b/ still bans the engine
    assert any(x.startswith("page.html: banned term") for x in chk(root, here, dist)[0])


def test_check_build_accepts_the_word_stilldrawn_in_the_bundle(tmp_path):
    root, here, dist = fake_build(tmp_path)
    assert "StillDrawn" in (dist / "blindpanel/core/payload.js").read_text()
    assert chk(root, here, dist)[0] == []


def reveal_cases():
    first = lambda r: next(iter(r["items"]))
    return [
        ("extra top-level key", lambda r: r.update(note="x"), "top-level keys"),
        ("no items key", lambda r: r.pop("items"), "top-level keys"),
        ("no reference key", lambda r: r.pop("reference"), "top-level keys"),
        ("no study key", lambda r: r.pop("study"), "top-level keys"),
        ("reference set", lambda r: r.update(reference={"raters": ["R7"]}), "reference"),
        ("reference empty object", lambda r: r.update(reference={}), "reference"),
        ("other study", lambda r: r.update(study="a9-push"), "study is"),
        ("extra item key", lambda r: r["items"][first(r)].update(link="x"), "reveals something"),
        ("other label", lambda r: r["items"][first(r)].update(label="Clip"), "reveals something"),
        ("empty label", lambda r: r["items"][first(r)].update(label=""), "reveals something"),
        ("meta filled", lambda r: r["items"][first(r)].update(meta={"k": 1}), "reveals something"),
        ("meta null", lambda r: r["items"][first(r)].update(meta=None), "reveals something"),
        ("item not an object", lambda r: r["items"].update({first(r): "clip"}), "reveals something"),
        ("one item short", lambda r: r["items"].pop(first(r)), "2 items, expected 3"),
        ("one item extra", lambda r: r["items"].update(c00000={"label": "clip", "meta": {}}), "4 items, expected 3"),
        ("foreign codes", lambda r: r.update(items={f"c0000{i}": {"label": "clip", "meta": {}} for i in range(3)}), "codes differ"),
        ("items a list", lambda r: r.update(items=[]), "items is not an object"),
        ("re-roll in a code", lambda r: r["items"].update({"c-r2x": r["items"].pop(first(r))}), "-r2"),
    ]


@pytest.mark.parametrize("name, mutate, message", reveal_cases(), ids=[c[0] for c in reveal_cases()])
def test_check_build_holds_reveal_json_to_its_exact_shape(tmp_path, name, mutate, message):
    root, here, dist = fake_build(tmp_path)
    edit_json(dist / "reveal.json", mutate)
    p, _, _ = chk(root, here, dist)
    assert any(x.startswith("reveal.json: ") and message in x for x in p), (name, p)


def test_check_build_reports_a_reveal_that_is_not_an_object_or_not_json(tmp_path):
    root, here, dist = fake_build(tmp_path)
    (dist / "reveal.json").write_text("[]")
    assert any(x.startswith("reveal.json: not a JSON object") for x in chk(root, here, dist)[0])
    (dist / "reveal.json").write_text("{nope")
    assert any(x.startswith("reveal.json: not valid JSON") for x in chk(root, here, dist)[0])
    (dist / "reveal.json").unlink()
    assert any(x.startswith("reveal.json: missing") for x in chk(root, here, dist)[0])


def test_check_build_refuses_a_re_roll_in_the_study(tmp_path):
    root, here, dist = fake_build(tmp_path)
    edit_json(here / "burst/media-sources.json",
              lambda s: s["clips"].update({"cu-line-2_burst_wan22-r2": s["clips"]["cu-line-2_burst_wan22"]}))
    assert any("-r2" in x for x in chk(root, here, dist)[0])


def study_cases():
    return [
        ("tally on", lambda s: s["modes"]["public"].update(tally=True), "tally"),
        ("other seed", lambda s: s.update(seed="other-seed"), "seed"),
        ("other instrument", lambda s: s.update(instrument="A8"), "instrument"),
        ("other wording hash", lambda s: s.update(text_sha256="d" * 64), "wording hash"),
        ("other study id", lambda s: s.update(id="a9-push"), "study id"),
        ("foreign clip code", lambda s: s["parts"]["clips"]["items"][0].update(code="c00000"), "clip codes differ"),
        ("foreign panel code", lambda s: s["panels"][0].update(code="p00000"), "panel codes differ"),
        ("a clip beside the wrong panel", lambda s: s["parts"]["clips"]["items"][0].update(reference="p00000"), "reference"),
        ("no clip list", lambda s: s["parts"]["clips"].pop("items"), "no parts.clips.items"),
        ("no panel list", lambda s: s.pop("panels"), "no panels"),
    ]


@pytest.mark.parametrize("name, mutate, message", study_cases(), ids=[c[0] for c in study_cases()])
def test_check_build_holds_study_json_to_the_spec_and_the_lock(tmp_path, name, mutate, message):
    root, here, dist = fake_build(tmp_path)
    edit_json(dist / "study.json", mutate)
    p, _, _ = chk(root, here, dist)
    assert any(x.startswith("study.json: ") and message in x for x in p), (name, p)


def test_check_build_refuses_a_spec_whose_seed_is_an_a6_seed(tmp_path):
    root, here, dist = fake_build(tmp_path)
    p, _, _ = chk(root, here, dist, spec=dict(SMALL, seed=sorted(pp.A6_SEEDS)[0]))
    assert any("A6 seed" in x for x in p)


def test_check_build_checks_the_media_against_media_sources(tmp_path):
    root, here, dist = fake_build(tmp_path)
    media = sorted((dist / "media").iterdir())
    media[0].write_bytes(b"swapped")
    p, _, _ = chk(root, here, dist)
    assert any(x.startswith(f"media/{media[0].name}: ") and "differs" in x for x in p), p
    media[0].unlink()
    assert any(x.startswith(f"media/{media[0].name}: ") and "missing" in x for x in chk(root, here, dist)[0])
    (dist / "media/stray.mp4").write_bytes(b"x")
    assert any(x.startswith("media/stray.mp4: ") and "not listed" in x for x in chk(root, here, dist)[0])


def test_check_build_holds_banned_terms_to_what_prepare_writes(tmp_path):
    root, here, dist = fake_build(tmp_path)
    pp.write_text(here / "burst/banned-terms.txt", "# emptied\nnothing-at-all\n")
    p, _, _ = chk(root, here, dist)
    assert any(x.startswith("banned-terms.txt: ") and "BANNED_TERMS" in x for x in p)


def test_check_build_reports_missing_and_broken_inputs_instead_of_crashing(tmp_path):
    root, here, dist = fake_build(tmp_path)
    (dist / "study.json").write_text("{")
    (here / "burst/study.lock.json").unlink()
    (here / "burst/media-sources.json").write_text("[]")
    p, tree, scanned = chk(root, here, dist)
    assert any(x.startswith("study.json: not valid JSON") for x in p)
    assert any(x.startswith("study.lock.json: missing") for x in p)
    assert any(x.startswith("media-sources.json: not a JSON object") for x in p)
    assert scanned > 0 and tree == pp.tree_hash(dist)
    p, tree, scanned = chk(root, here, tmp_path / "nowhere")
    assert (tree, scanned) == (None, 0) and any("is not a directory" in x for x in p)
    (tmp_path / "empty").mkdir()
    p, tree, scanned = chk(root, here, tmp_path / "empty")
    assert scanned == 0 and any("empty" in x for x in p)


def test_check_build_refuses_a_symlink_in_the_dist(tmp_path):
    root, here, dist = fake_build(tmp_path)
    os.symlink(dist / "index.html", dist / "link.html")
    os.symlink(dist / "blindpanel", dist / "dirlink")
    p, _, _ = chk(root, here, dist)
    assert any(x.startswith("link.html: ") and "symlink" in x for x in p)
    assert any(x.startswith("dirlink: ") and "symlink" in x for x in p)


def test_check_build_expects_the_registered_size(tmp_path):
    root, here, dist = fake_build(tmp_path)
    p, _, _ = chk(root, here, dist, spec=dict(SMALL, n_clips=55, n_panels=11))
    assert any("3 clips" in x and "expected 55" in x for x in p)


def test_tree_hash_sees_any_change(tmp_path):
    (tmp_path / "a").write_text("1")
    h = pp.tree_hash(tmp_path)
    assert pp.tree_hash(tmp_path) == h
    (tmp_path / "a").write_text("2")
    assert pp.tree_hash(tmp_path) != h
    (tmp_path / "a").write_text("1")
    assert pp.tree_hash(tmp_path) == h
    (tmp_path / "a").rename(tmp_path / "b")                                       # the path is part of the hash
    assert pp.tree_hash(tmp_path) != h
    (tmp_path / "b").rename(tmp_path / "a")
    (tmp_path / "d").mkdir()
    (tmp_path / "d/x").write_text("y")
    assert pp.tree_hash(tmp_path) != h


def test_tree_hash_is_a_function_of_paths_and_contents_only(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    for root, order in ((one, ("a.b", "a/b", "c")), (two, ("c", "a/b", "a.b"))):
        for rel in order:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(rel)
    assert pp.tree_hash(one) == pp.tree_hash(two)
    want = hashlib.sha256()
    for rel in ("a/b", "a.b", "c"):                      # path order: "a" sorts before "a.b", so a/b comes first
        want.update(f"{rel}\0{hashlib.sha256(rel.encode()).hexdigest()}\n".encode())
    assert pp.tree_hash(one) == want.hexdigest()


def test_record_tree_and_read_it_back(tmp_path):
    root, here, dist = fake_build(tmp_path)
    _, tree, _ = chk(root, here, dist)
    pp.record_tree(SMALL, here, dist, tree)
    doc = json.loads((here / "build-trees.json").read_text())
    assert doc == {"a9-burst": {"tree_sha256": tree, "blindpanel": ["blindpanel@0.1.0"]}}
    assert pp.recorded_tree(SMALL, here) == tree
    assert (here / "build-trees.json").read_bytes().endswith(b"}\n") and b"\r" not in (here / "build-trees.json").read_bytes()
    push = dict(SMALL, key="push", id="a9-push", dir="push")
    pp.record_tree(push, here, dist, "e" * 64)                                    # another study keeps its own entry
    assert list(json.loads((here / "build-trees.json").read_text())) == ["a9-burst", "a9-push"]
    pp.record_tree(SMALL, here, dist, "f" * 64, replace=True)                     # a re-lock at Gate C records again
    assert pp.recorded_tree(SMALL, here) == "f" * 64 and pp.recorded_tree(push, here) == "e" * 64


def test_record_tree_refuses_the_pilot_and_a_build_without_a_version(tmp_path):
    root, here, dist = fake_build(tmp_path)
    with pytest.raises(SystemExit, match="never recorded"):
        pp.record_tree(pp.PILOT, here, dist, "a" * 64)
    assert not (here / "build-trees.json").exists()
    (dist / "blindpanel/core/payload.js").write_text("no version here\n")
    with pytest.raises(SystemExit, match="version"):
        pp.record_tree(SMALL, here, dist, "a" * 64)
    assert not (here / "build-trees.json").exists()


def test_recorded_tree_says_what_is_missing(tmp_path):
    with pytest.raises(SystemExit, match="build-trees.json"):
        pp.recorded_tree(SMALL, tmp_path)
    pp.write_text(tmp_path / "build-trees.json", "{not json")
    with pytest.raises(SystemExit, match="build-trees.json"):
        pp.recorded_tree(SMALL, tmp_path)
    pp.write_json(tmp_path / "build-trees.json", {"a9-push": {"tree_sha256": "a" * 64}})
    with pytest.raises(SystemExit, match="a9-burst"):
        pp.recorded_tree(SMALL, tmp_path)
    pp.write_json(tmp_path / "build-trees.json", {"a9-burst": {"tree_sha256": "not-a-hash"}})
    with pytest.raises(SystemExit, match="a9-burst"):
        pp.recorded_tree(SMALL, tmp_path)


@needs_blindpanel
def test_check_build_passes_a_real_blindpanel_build_and_catches_a_tampered_one(tmp_path):
    """The real bundle contains the word StillDrawn in a comment and must still pass; the same build with one
    engine name added to any file, or one byte of media changed, must not."""
    root = fake_rules_root(tmp_path)
    for spec in (pp.BURST, pp.PUSH):
        sdir = tmp_path / spec["dir"]
        sdir.mkdir()
        pp.write_json(sdir / "media-sources.json", fill_media(sdir, full_sources(spec)))
        pp.write_study(spec, tmp_path)
        for args in (["lock", str(sdir / "study.yaml")],
                     ["build", str(sdir / "study.yaml"), "--out", str(tmp_path / f"out-{spec['dir']}")]):
            r = subprocess.run(["node", BLINDPANEL, *args], capture_output=True, text=True)
            assert r.returncode == 0, r.stdout + r.stderr
        dist = tmp_path / f"out-{spec['dir']}"
        assert any("StillDrawn" in f.read_text(encoding="utf-8") for f in dist.rglob("*.js"))
        p, tree, scanned = pp.check_build(spec, tmp_path, dist, root, "private")
        assert p == [] and scanned == len([f for f in dist.rglob("*") if f.is_file()]) > 66      # 66 media files and the page
        real = json.loads((dist / "study.json").read_text(encoding="utf-8"))
        assert set(real) == set(pp.STUDY_SHAPE)                                    # the allowlist is what blindpanel writes
        assert {k for i in real["parts"]["clips"]["items"] for k in i} == {"code", "video", "reference"}
        assert {k for x in real["panels"] for k in x} == {"code", "image"}
        assert set(real["parts"]["clips"]) == set(pp.STUDY_SHAPE["parts"]["clips"]) - {"items"} | {"items"}
        assert set(real["modes"]["public"]) == set(pp.STUDY_SHAPE["modes"]["public"])
        assert set(real["endpoints"]) == set(pp.STUDY_SHAPE["endpoints"])
        assert {k for q in real["questions"] for k in q} == set(pp.STUDY_SHAPE["questions"][0])
        assert pp.shape_problems(real, pp.STUDY_SHAPE) == []
        real["parts"]["clips"]["items"][0]["engine"] = "x"
        assert pp.shape_problems(real, pp.STUDY_SHAPE) == ["parts.clips.items[].engine is not an allowed key"]
        pp.record_tree(spec, tmp_path, dist, tree)
        assert pp.recorded_tree(spec, tmp_path) == tree
        target = next(dist.rglob("app.js"))
        original = target.read_text(encoding="utf-8")
        target.write_text(original + "\n// made with Wan 2.2\n", encoding="utf-8")
        p, tampered, _ = pp.check_build(spec, tmp_path, dist, root, "private", expect_tree=tree)
        assert tampered != tree and any(x.startswith("blindpanel/ui/app.js: banned term") for x in p)
        assert any("differs from the recorded" in x for x in p)
        target.write_text(original, encoding="utf-8")
        assert pp.check_build(spec, tmp_path, dist, root, "private", expect_tree=tree)[0] == []
        next((dist / "media").glob("*.mp4")).write_bytes(b"changed")
        assert any("differs" in x for x in pp.check_build(spec, tmp_path, dist, root, "private")[0])


# ---- the command line
@pytest.fixture
def cli(tmp_path, monkeypatch):
    """main() against a synthetic folder and root; HERE is where the study files and records live."""
    root, here, dist = fake_build(tmp_path)
    monkeypatch.setattr(pp, "HERE", here)
    monkeypatch.setitem(pp.STUDIES, "burst", SMALL)
    return root, here, dist


def run_cli(root, *argv):
    return pp.main([argv[0], "--root", str(root), *argv[1:]])


def test_cli_check_build_records_then_expects_the_record(cli, capsys):
    root, here, dist = cli
    assert run_cli(root, "check-build", "--study", "burst", "--dist", str(dist), "--record") == 0
    out = capsys.readouterr().out
    assert "build tree " in out and out.index("clean") < out.index("recorded in build-trees.json")     # the summary comes first
    assert run_cli(root, "check-build", "--study", "burst", "--dist", str(dist), "--expect-recorded") == 0
    assert capsys.readouterr().out.rstrip().endswith("clean")
    (dist / "index.html").write_text("changed\n")
    assert run_cli(root, "check-build", "--study", "burst", "--dist", str(dist), "--expect-recorded") == 1
    out = capsys.readouterr().out
    assert "differs from the recorded" in out and out.rstrip().endswith("1 problem(s)")
    assert run_cli(root, "check-build", "--study", "burst", "--dist", str(dist), "--expect-tree", "0" * 64) == 1


def test_cli_check_build_does_not_record_a_dirty_build(cli, capsys):
    root, here, dist = cli
    (dist / "notes.txt").write_text("Wan 2.2")
    assert run_cli(root, "check-build", "--study", "burst", "--dist", str(dist), "--record") == 1
    assert not (here / "build-trees.json").exists() and "recorded" not in capsys.readouterr().out


def test_cli_check_build_needs_one_study_and_a_dist_and_one_expectation(cli, capsys):
    root, here, dist = cli
    for argv in (["check-build", "--dist", str(dist)], ["check-build", "--study", "burst"],
                 ["check-build", "--study", "burst", "--study", "push", "--dist", str(dist)],
                 ["check-build", "--study", "burst", "--dist", str(dist), "--record", "--expect-recorded"],
                 ["check-build", "--study", "burst", "--dist", str(dist), "--record", "--expect-tree", "a" * 64],
                 ["check-build", "--study", "burst", "--dist", str(dist), "--expect-recorded", "--expect-tree", "a" * 64]):
        with pytest.raises(SystemExit) as e:
            run_cli(root, *argv)
        assert e.value.code == 2, argv
    with pytest.raises(SystemExit, match="build-trees.json"):                     # nothing recorded yet
        run_cli(root, "check-build", "--study", "burst", "--dist", str(dist), "--expect-recorded")


def test_cli_has_no_slim_command(cli):
    root, *_ = cli
    with pytest.raises(SystemExit) as e:
        pp.main(["slim", "--root", str(root)])
    assert e.value.code == 2
    assert "slim" not in pp.__doc__ and not hasattr(pp, "slim")


def test_cli_flags_belong_to_their_commands(cli):
    root, here, dist = cli
    for argv in (["cells", "--record"], ["check", "--dist", str(dist)], ["write", "--partial"],
                 ["check-build", "--study", "burst", "--dist", str(dist), "--partial"]):
        with pytest.raises(SystemExit) as e:
            run_cli(root, *argv)
        assert e.value.code == 2, argv


def test_cli_write_writes_the_study_files(cli, capsys):
    root, here, _ = cli
    assert run_cli(root, "write", "--study", "burst") == 0
    assert "wrote burst/study.yaml and burst/banned-terms.txt" in capsys.readouterr().out
    assert (here / "burst/study.yaml").read_text().startswith("# Generated by prepare.py")
    with pytest.raises(ValueError, match="expected 55 clips"):                   # this stand-in has 3 clips; the real spec 55
        pp.write_study(pp.BURST, here)


def cli_sizes(here):
    for spec in (pp.BURST, pp.PUSH):
        (here / spec["dir"]).mkdir(exist_ok=True)
        doc = {"clips": {"a": {"source_video": {"width": 1280, "height": 704}},
                         "b": {"source_video": {"width": 720, "height": 1280}}}, "panels": {}}
        pp.write_json(here / spec["dir"] / "media-sources.json", doc)


def stub_checks(monkeypatch, problems=(), seen=None):
    seen = {} if seen is None else seen

    def check_study(spec, here):
        return list(problems), {f"{spec['dir']}/media/{c}.mp4": hashlib.sha256(f"{spec['id']}{c}".encode()).hexdigest()
                                for c in "ba"}

    def check_shipping(here, root, tree, require_all=True):
        seen.update(shipping=(tree, require_all))
        return [], 7

    def positive_control(root, tree):
        seen.update(control=tree)
        return [], 3

    monkeypatch.setattr(pp, "check_study", check_study)
    monkeypatch.setattr(pp, "check_shipping", check_shipping)
    monkeypatch.setattr(pp, "positive_control", positive_control)
    return seen


def test_cli_check_writes_the_copy_hashes_for_both_studies(cli, monkeypatch, capsys):
    root, here, _ = cli
    monkeypatch.setitem(pp.STUDIES, "burst", pp.BURST)
    cli_sizes(here)
    seen = stub_checks(monkeypatch)
    assert run_cli(root, "check") == 0
    out = capsys.readouterr().out
    assert "a9-burst: 2 copies checked, 0 problem(s)" in out and "positive control: 3 hosted sources checked" in out
    assert "shipping files: 7 scanned" in out
    assert out.rstrip().endswith("wrote rating-copies.sha256 (4 copies; sizes [(704, 1280), (1280, 704)])")
    lines = (here / "rating-copies.sha256").read_text().splitlines()
    assert lines == sorted(lines, key=lambda l: l.split("  ", 1)[1]) and len(lines) == 4
    assert all(re.fullmatch(r"[0-9a-f]{64}  (burst|push)/media/[ab]\.mp4", l) for l in lines)
    assert seen == {"shipping": ("private", True), "control": "private"}


def test_cli_check_partial_lets_unwritten_shipping_files_be_absent(cli, monkeypatch, capsys):
    root, here, _ = cli
    cli_sizes(here)
    seen = stub_checks(monkeypatch)
    assert run_cli(root, "check", "--partial", "--tree-kind", "public") == 0
    assert seen == {"shipping": ("public", False), "control": "public"}


def test_cli_check_fails_on_any_problem_and_writes_nothing(cli, monkeypatch, capsys):
    root, here, _ = cli
    cli_sizes(here)
    stub_checks(monkeypatch, problems=["a1: size 1x1, expected 1280x704"])
    assert run_cli(root, "check") == 1
    out = capsys.readouterr().out
    assert "✗ a1: size 1x1" in out and "wrote" not in out
    assert not (here / "rating-copies.sha256").exists()


def test_cli_check_writes_nothing_for_one_study_or_the_pilot(cli, monkeypatch):
    root, here, _ = cli
    cli_sizes(here)
    seen = stub_checks(monkeypatch)
    assert run_cli(root, "check", "--study", "burst") == 0
    assert not (here / "rating-copies.sha256").exists() and "shipping" in seen
    seen.clear()
    assert run_cli(root, "check", "--study", "pilot") == 0                        # the pilot ships nothing
    assert not (here / "rating-copies.sha256").exists() and "shipping" not in seen and seen["control"] == "private"


def test_cli_check_reports_a_study_with_no_media_sources_instead_of_crashing(cli, capsys):
    root, here, _ = cli
    assert run_cli(root, "check", "--study", "pilot") == 1
    out = capsys.readouterr().out
    assert "✗ pilot/media-sources.json" in out and "Traceback" not in out


def test_cli_cells_selects_and_validates_without_touching_media(tmp_path, capsys):
    write_manifest(tmp_path, full_manifest())
    assert pp.main(["cells", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "a9-burst: 55 cells on 11 panels" in out and "a9-push: 55 cells on 11 panels" in out
    assert pp.main(["cells", "--root", str(tmp_path), "--study", "pilot"]) == 0
    assert capsys.readouterr().out.strip() == "a9-pilot: 6 cells on 6 panels"
    write_manifest(tmp_path, [r for r in full_manifest() if not r["cell_id"].endswith("burst_wan22")])
    assert pp.main(["cells", "--root", str(tmp_path), "--study", "burst"]) == 1
    assert "✗" in capsys.readouterr().out
    assert not (tmp_path / "analysis").exists()


def test_cli_cells_without_a_manifest_says_so(tmp_path):
    with pytest.raises(SystemExit, match="manifest.jsonl"):
        pp.main(["cells", "--root", str(tmp_path)])


def test_the_source_has_no_slim_and_the_comment_on_the_over_bans_is_there():
    src = (Path(pp.__file__)).read_text(encoding="utf-8")
    assert "def slim" not in src and "slim" not in src.split('"""')[1]
    assert "over-ban" in src.split("BANNED_TERMS = ")[0].rsplit("\n\n", 1)[-1]


# ---------------------------------------------------------------- review minors: dev == build, odd types, record message, binary files
def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@needs_blindpanel
def test_blindpanel_dev_and_build_make_the_same_tree(tmp_path):
    """Gate E rebuilds with `dev --out` and checks that tree against the one recorded from `build --out`."""
    sdir = tmp_path / "burst"
    sdir.mkdir()
    pp.write_json(sdir / "media-sources.json", fill_media(sdir, full_sources(pp.BURST)))
    pp.write_study(pp.BURST, tmp_path)
    for args in (["lock", str(sdir / "study.yaml")], ["build", str(sdir / "study.yaml"), "--out", str(tmp_path / "built")]):
        r = subprocess.run(["node", BLINDPANEL, *args], capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stdout + r.stderr
    port = free_port()
    log = (tmp_path / "dev.log").open("w")
    proc = subprocess.Popen(["node", BLINDPANEL, "dev", str(sdir / "study.yaml"), "--out", str(tmp_path / "dev-out"),
                             "--store", "file", "--data", str(tmp_path / "data"), "--port", str(port)],
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        deadline, ready = time.time() + 60, False
        while time.time() < deadline and not ready:
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/study.json", timeout=2) as r:
                    ready = r.status == 200
            except OSError:
                time.sleep(0.3)
        assert ready, (tmp_path / "dev.log").read_text()
        previous = None                                # the out folder must have stopped changing before it is hashed
        while time.time() < deadline:
            now = pp.tree_hash(tmp_path / "dev-out")
            if now == previous:
                break
            previous = now
            time.sleep(0.5)
        else:
            pytest.fail("the dev out folder never settled")
        dev_tree = now
    finally:
        try:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
        except ProcessLookupError:
            pass
        log.close()
    assert dev_tree == pp.tree_hash(tmp_path / "built")


ODD = [5, 1.5, True, None, [1], {"a": 1}, ["x"]]


@pytest.mark.parametrize("odd", ODD, ids=[repr(o) for o in ODD])
def test_check_build_reports_non_string_codes_instead_of_crashing(tmp_path, odd):
    root, here, dist = fake_build(tmp_path)

    def mangle(s):
        s["parts"]["clips"]["items"][0].update(code=odd, video=odd, reference=odd)
        s["parts"]["clips"]["items"][1]["reference"] = odd
        s["panels"][0].update(code=odd, image=odd)
    edit_json(dist / "study.json", mangle)
    p, _, _ = chk(root, here, dist)
    assert any("clip codes differ" in x for x in p) and any("panel codes differ" in x for x in p)
    edit_json(dist / "reveal.json", lambda r: r["items"].update({"c00000": odd}))
    assert any("reveals something" in x for x in chk(root, here, dist)[0])
    edit_json(here / "burst/media-sources.json",
              lambda s: next(iter(s["clips"].values())).update(panel=odd, copy_sha256=odd))
    assert chk(root, here, dist)[0]                                              # no crash, and not clean


@pytest.mark.parametrize("odd", [5, [1], {"a": 1}, None])
def test_check_build_survives_odd_media_sources(tmp_path, odd):
    root, here, dist = fake_build(tmp_path)
    edit_json(here / "burst/media-sources.json", lambda s: s.update(clips={"x_burst_a": odd, **s["clips"]}))
    assert chk(root, here, dist)[0]
    edit_json(here / "burst/media-sources.json", lambda s: s.update(panels={"p": odd}))
    assert chk(root, here, dist)[0]


def test_record_tree_returns_the_entry_it_replaced(tmp_path):
    root, here, dist = fake_build(tmp_path)
    assert pp.record_tree(SMALL, here, dist, "a" * 64) is None
    assert pp.record_tree(SMALL, here, dist, "a" * 64) == "a" * 64                # the same hash again: unchanged
    assert pp.record_tree(SMALL, here, dist, "b" * 64, replace=True) == "a" * 64
    pp.write_json(here / "build-trees.json", {"a9-burst": "broken"})
    assert pp.record_tree(SMALL, here, dist, "c" * 64) is None


def test_cli_record_says_when_it_replaces_a_different_tree(cli, capsys):
    root, here, dist = cli
    argv = ("check-build", "--study", "burst", "--dist", str(dist), "--record")
    assert run_cli(root, *argv) == 0
    first = capsys.readouterr().out
    assert "recorded in build-trees.json" in first and "replaced" not in first
    tree = pp.recorded_tree(SMALL, here)
    assert run_cli(root, *argv) == 0
    assert "unchanged" in capsys.readouterr().out
    pp.write_json(here / "build-trees.json", {"a9-burst": {"tree_sha256": "d" * 64, "blindpanel": ["blindpanel@0.1.0"]}})
    assert run_cli(root, *argv, "--replace-recorded") == 0
    out = capsys.readouterr().out
    assert f"replaced the recorded tree {'d' * 64} with {tree}" in out


def zip_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.txt", "hello")
    return buf.getvalue()


BINARIES = [("a.gz", gzip.compress(b"hello")), ("a.zip", zip_bytes()), ("blob", bytes(range(256))),
            ("x.wasm", b"\x00asm\x01\x00\x00\x00"), ("x.js", b"console.log(1)\x00"), ("x.json", b"\xff\xfe{}"),
            ("tiny.bin", b"\x1f\x8b"), ("fonts/f.woff2", b"wOF2\x00\x01\x00\x00"), ("esc.txt", b"text \x1b[0m escape")]


@pytest.mark.parametrize("name, data", BINARIES, ids=[b[0] for b in BINARIES])
def test_check_build_refuses_a_file_that_is_neither_text_nor_listed_media(tmp_path, name, data):
    root, here, dist = fake_build(tmp_path)
    f = dist / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(data)
    p, _, _ = chk(root, here, dist)
    assert f"{name}: not a text file and not listed media" in p, p


def test_check_build_accepts_ordinary_text_in_any_script(tmp_path):
    root, here, dist = fake_build(tmp_path)
    (dist / "page.html").write_text("<p>ünï · ✓ — “quotes”\ttab\r\nline</p>\n", encoding="utf-8")
    (dist / "empty.txt").write_bytes(b"")
    assert chk(root, here, dist)[0] == []




# ---------------------------------------------------------------- review round: study.json shape, atomic writes, record guard, odd entries
def shape_cases():
    item = lambda s: s["parts"]["clips"]["items"][0]
    full = lambda s: s.update(scales={"burst": {"min": 1, "max": 5, "labels": ["a"]}})
    return [
        ("top-level key", lambda s: s.update(engine="x"), "engine is not an allowed key"),
        ("item key named after an engine", lambda s: item(s).update(wan22=1), "parts.clips.items[].wan22 is not an allowed key"),
        ("item label", lambda s: item(s).update(label="clip"), "parts.clips.items[].label is not an allowed key"),
        ("item meta filled", lambda s: item(s).update(meta={"k": 1}), "parts.clips.items[].meta.k is not an allowed key"),
        ("item link", lambda s: item(s).update(link="x"), "parts.clips.items[].link is not an allowed key"),
        ("panel key", lambda s: s["panels"][0].update(label="x"), "panels[].label is not an allowed key"),
        ("panel meta filled", lambda s: s["panels"][0].update(meta={"a": 1}), "panels[].meta.a is not an allowed key"),
        ("clips part key", lambda s: s["parts"]["clips"].update(order="x"), "parts.clips.order is not an allowed key"),
        ("parts key", lambda s: s["parts"].update(extra={}), "parts.extra is not an allowed key"),
        ("a baseline part", lambda s: s["parts"].update(baseline={"items": []}), "parts.baseline should be a plain value or a list of them"),
        ("video key", lambda s: s["parts"]["clips"].update(video={"loop": True, "src": "x"}), "parts.clips.video.src is not an allowed key"),
        ("modes key", lambda s: s["modes"]["public"].update(tallies=1), "modes.public.tallies is not an allowed key"),
        ("a second mode", lambda s: s["modes"].update(admin={}), "modes.admin is not an allowed key"),
        ("endpoint key", lambda s: s["endpoints"].update(debug="/d"), "endpoints.debug is not an allowed key"),
        ("question key", lambda s: s["questions"][0].update(engine="x"), "questions[].engine is not an allowed key"),
        ("scale key", lambda s: (full(s), s["scales"]["burst"].update(extra=1)), "scales.burst.extra is not an allowed key"),
        ("a dict where a value goes", lambda s: s.update(title={"a": 1}), "title should be a plain value or a list of them"),
        ("a list of lists", lambda s: s.update(privacy=[[1]]), "privacy should be a plain value or a list of them"),
        ("parts a list", lambda s: s.update(parts=[]), "parts should be an object"),
        ("items an object", lambda s: s["parts"]["clips"].update(items={}), "parts.clips.items should be a list"),
        ("panels a string", lambda s: s.update(panels="x"), "panels should be a list"),
        ("an item a string", lambda s: s["panels"].append("x"), "panels[] should be an object"),
    ]


@pytest.mark.parametrize("name, mutate, message", shape_cases(), ids=[c[0] for c in shape_cases()])
def test_check_build_holds_study_json_to_blindpanels_exact_keys(tmp_path, name, mutate, message):
    root, here, dist = fake_build(tmp_path)
    edit_json(dist / "study.json", mutate)
    p, _, _ = chk(root, here, dist)
    assert f"study.json: {message}" in p, (name, p)


def test_study_json_may_carry_empty_meta_and_the_full_set_of_keys(tmp_path):
    root, here, dist = fake_build(tmp_path)

    def fill(s):
        s["parts"]["clips"]["items"][0]["meta"] = {}
        s["panels"][0]["meta"] = {}
        s.update(scales={"burst": {"min": 1, "max": 5, "labels": ["a", "b"]}}, privacy="p")
        s["questions"][0].update(short="s", part="clips", direction="d", notes=["n"], intro_notes=[], scale="burst")
        s["parts"]["baseline"] = None
        s["parts"]["clips"].update(intro=["i"], watch_note="w", session_size=3, extend=False,
                                   video={"loop": True, "muted": True, "autoplay": "never"})
    edit_json(dist / "study.json", fill)
    assert chk(root, here, dist)[0] == []


def test_shape_problems_never_echo_a_value_or_an_index():
    value = {"parts": {"clips": {"items": [{"code": "c1", "video": "v"}, {"code": "c2", "engine": "Wan 2.2"}]}}}
    out = pp.shape_problems(value, pp.STUDY_SHAPE)
    assert out == ["parts.clips.items[].engine is not an allowed key"]


# ---- atomic writes
def test_write_text_atomic_replaces_the_whole_file_or_none_of_it(tmp_path, monkeypatch):
    f = tmp_path / "a.txt"
    f.write_text("old\n")
    pp.write_text_atomic(f, "new ünï\n")
    assert f.read_bytes() == "new ünï\n".encode("utf-8") and sorted(x.name for x in tmp_path.iterdir()) == ["a.txt"]
    real = os.replace
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        pp.write_text_atomic(f, "never\n")
    monkeypatch.setattr(os, "replace", real)
    assert f.read_text(encoding="utf-8") == "new ünï\n" and sorted(x.name for x in tmp_path.iterdir()) == ["a.txt"]
    with pytest.raises(UnicodeEncodeError):                                       # fails half way through the write
        pp.write_text_atomic(f, "half" + "\ud800")
    assert f.read_text(encoding="utf-8") == "new ünï\n" and sorted(x.name for x in tmp_path.iterdir()) == ["a.txt"]
    pp.write_text_atomic(tmp_path / "fresh.txt", "x\n")                             # a file that did not exist
    assert (tmp_path / "fresh.txt").read_text() == "x\n"


def test_the_two_records_are_written_through_the_atomic_path(cli, monkeypatch):
    root, here, dist = cli
    spy, real = [], pp.write_text_atomic
    monkeypatch.setattr(pp, "write_text_atomic", lambda p, t: (spy.append(Path(p).name), real(p, t))[1])
    assert run_cli(root, "check-build", "--study", "burst", "--dist", str(dist), "--record") == 0
    cli_sizes(here)                                                             # replaces the stand-in media-sources.json
    stub_checks(monkeypatch)
    monkeypatch.setitem(pp.STUDIES, "burst", pp.BURST)
    assert run_cli(root, "check") == 0
    assert spy == ["build-trees.json", "rating-copies.sha256"]


def test_a_failed_write_leaves_the_previous_records_whole(cli, monkeypatch):
    root, here, dist = cli
    cli_sizes(here)
    stub_checks(monkeypatch)
    monkeypatch.setitem(pp.STUDIES, "burst", pp.BURST)
    assert run_cli(root, "check") == 0
    before = (here / "rating-copies.sha256").read_bytes()
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        run_cli(root, "check")
    assert (here / "rating-copies.sha256").read_bytes() == before
    assert not [f for f in here.iterdir() if f.name.endswith(".tmp")]


# ---- --record does not replace a recorded build by accident
def test_record_tree_will_not_replace_a_different_hash_without_being_told(tmp_path):
    root, here, dist = fake_build(tmp_path)
    pp.record_tree(SMALL, here, dist, "a" * 64)
    before = (here / "build-trees.json").read_bytes()
    with pytest.raises(SystemExit) as e:
        pp.record_tree(SMALL, here, dist, "b" * 64)
    assert "a" * 64 in str(e.value) and "b" * 64 in str(e.value) and "--replace-recorded" in str(e.value)
    assert (here / "build-trees.json").read_bytes() == before
    assert pp.record_tree(SMALL, here, dist, "a" * 64) == "a" * 64                # the same hash is fine
    assert pp.record_tree(SMALL, here, dist, "b" * 64, replace=True) == "a" * 64
    pp.write_text(here / "build-trees.json", "{broken")
    with pytest.raises(SystemExit, match="build-trees.json"):
        pp.record_tree(SMALL, here, dist, "c" * 64)
    assert (here / "build-trees.json").read_text() == "{broken"


def test_cli_record_refuses_a_different_tree_with_both_hashes(cli, capsys):
    root, here, dist = cli
    argv = ("check-build", "--study", "burst", "--dist", str(dist), "--record")
    assert run_cli(root, *argv) == 0
    old = pp.recorded_tree(SMALL, here)
    capsys.readouterr()
    (dist / "notes.txt").write_text("a harmless new file\n")
    with pytest.raises(SystemExit) as e:
        run_cli(root, *argv)
    new = pp.tree_hash(dist)
    assert old in str(e.value) and new in str(e.value) and "--replace-recorded" in str(e.value)
    out = capsys.readouterr().out
    assert out.rstrip().endswith("clean")                                          # the summary was printed first
    assert pp.recorded_tree(SMALL, here) == old
    assert run_cli(root, *argv, "--replace-recorded") == 0
    assert f"replaced the recorded tree {old} with {new}" in capsys.readouterr().out and pp.recorded_tree(SMALL, here) == new


def test_cli_replace_recorded_needs_record(cli):
    root, here, dist = cli
    for argv in (["check-build", "--study", "burst", "--dist", str(dist), "--replace-recorded"],
                 ["check", "--replace-recorded"]):
        with pytest.raises(SystemExit) as e:
            run_cli(root, *argv)
        assert e.value.code == 2


def test_the_tree_kind_flag_has_its_new_name(cli):
    root, here, dist = cli
    with pytest.raises(SystemExit) as e:
        run_cli(root, "check-build", "--study", "burst", "--dist", str(dist), "--tree", "public")
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        run_cli(root, "cells", "--tree-kind", "public")
    assert e.value.code == 2


def test_a_pilot_build_says_it_is_never_recorded(cli, tmp_path):
    root, here, dist = cli
    with pytest.raises(SystemExit, match="pilot build is never recorded"):
        pp.recorded_tree(pp.PILOT, here)
    with pytest.raises(SystemExit, match="pilot build is never recorded"):
        run_cli(root, "check-build", "--study", "pilot", "--dist", str(dist), "--expect-recorded")


# ---- entries that are not ordinary files
@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs named pipes")
def test_check_build_refuses_a_fifo_without_opening_it(tmp_path):
    root, here, dist = fake_build(tmp_path)
    os.mkfifo(dist / "pipe.txt")
    os.mkfifo(dist / "media" / "p.mp4")

    def hang(*_):
        raise TimeoutError("check_build opened a FIFO")
    old = signal.signal(signal.SIGALRM, hang)
    signal.alarm(30)
    try:
        p, tree, scanned = chk(root, here, dist)
        assert pp.tree_hash(dist) == tree
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    assert "pipe.txt: not a regular file (a FIFO, socket or device)" in p
    assert "media/p.mp4: not a regular file (a FIFO, socket or device)" in p
    assert scanned == 8


def test_check_build_refuses_a_socket(tmp_path, monkeypatch):
    root, here, dist = fake_build(tmp_path)
    monkeypatch.chdir(dist)                                                     # a relative name keeps the socket path short
    with socket.socket(socket.AF_UNIX) as sock:
        sock.bind("s.sock")
        assert "s.sock: not a regular file (a FIFO, socket or device)" in chk(root, here, dist)[0]


def test_check_build_reports_a_file_name_that_is_not_utf8(tmp_path):
    root, here, dist = fake_build(tmp_path)
    try:
        with open(os.path.join(os.fsencode(dist), b"bad\xffname.txt"), "wb") as f:
            f.write(b"x")
    except OSError:
        pytest.skip("this file system refuses names that are not UTF-8")
    p, tree, scanned = chk(root, here, dist)
    assert any("file name is not valid UTF-8" in x for x in p) and tree == pp.tree_hash(dist) and scanned == 8


def test_dist_files_reports_what_it_leaves_out(tmp_path):
    (tmp_path / "a").write_text("x")
    os.symlink(tmp_path / "a", tmp_path / "ln")
    files, odd = pp.dist_files(tmp_path)
    assert [f.as_posix() for f in files] == ["a"] and odd == ["ln: a symlink (not followed)"]


# ---- media paths
def test_check_build_refuses_a_media_file_listed_twice(tmp_path):
    root, here, dist = fake_build(tmp_path)

    def twice(s):
        items = s["parts"]["clips"]["items"]
        items[1]["video"] = items[0]["video"]
    edit_json(dist / "study.json", twice)
    p, _, _ = chk(root, here, dist)
    assert f"{json.loads((dist / 'study.json').read_text())['parts']['clips']['items'][0]['video']}: listed 2 times in study.json" in p
    edit_json(dist / "study.json", lambda s: s["parts"]["clips"]["items"][0].update(video=s["panels"][0]["image"]))
    assert any("listed 2 times" in x for x in chk(root, here, dist)[0])


def test_check_build_refuses_media_outside_the_media_folder(tmp_path):
    root, here, dist = fake_build(tmp_path)
    edit_json(dist / "study.json", lambda s: s["parts"]["clips"]["items"][0].update(video="index.html"))
    (dist / "index.html").write_text("<p>Wan 2.2</p>\n")                           # listed or not, it is still scanned
    p, _, _ = chk(root, here, dist)
    assert "index.html: media path outside media/" in p
    assert any(x.startswith("index.html: banned term") for x in p)
    edit_json(dist / "study.json", lambda s: s["parts"]["clips"]["items"][0].update(video="media/../index.html"))
    assert "study.json: a media path leaves the build" in chk(root, here, dist)[0]


# ---- what a report says
def test_no_report_line_pairs_a_code_with_an_engine_or_the_private_id(tmp_path):
    """A build that trips every check: whatever it prints, no line holds a clip or panel code together with an
    engine, a cell or panel id, or the private id."""
    root, here, dist = fake_build(tmp_path)
    clip_code, panel_code = bld_codes(SMALL, SOURCES)
    codes = [*clip_code.values(), *panel_code.values(), "c00000"]
    first = next(iter(clip_code.values()))
    engine = "Wan 2.2 gen45 gen4t ltx23 wan22 h3-fal " + PRIVATE_TANK

    def study(s):
        items = s["parts"]["clips"]["items"]
        items[0].update(wan22="gen45", label="Wan 2.2", meta={"engine": "ltx23"}, reference="p00000")
        items[1]["video"] = items[2]["video"] = "media/../" + engine.split()[0]
        s.update(id="a9-push", seed="s", instrument="A8", text_sha256="d" * 64, ltx23=1)
        s["modes"]["public"]["tally"] = True
        s["panels"][0]["code"] = "p00000"

    edit_json(dist / "study.json", study)
    edit_json(dist / "reveal.json", lambda r: (r.update(reference={"raters": ["R7"]}, study="a9-push", gen4t=1),
                                               r["items"].update({first: {"label": engine, "meta": {"m": engine}, "engine": "wan22"},
                                                                  "c00000": {"label": "clip", "meta": {}}})))
    (dist / "notes.txt").write_text(engine + " cu-line-2_burst_wan22 -r2\n")
    (dist / "media" / "stray.mp4").write_bytes(b"x")
    (dist / "blob.gz").write_bytes(gzip.compress(b"hello wan22"))
    (dist / "media" / f"{next(iter(clip_code.values()))}.mp4").write_bytes(b"swapped")
    pp.write_text(here / "burst/banned-terms.txt", "x\n")
    edit_json(here / "burst/media-sources.json", lambda s: s["clips"].update({"x_burst_wan22-r2": s["clips"][next(iter(s["clips"]))]}))
    p, _, _ = chk(root, here, dist, expect_tree="0" * 64)
    assert len(p) > 25, p
    words = [w.lower() for w in (*pp.ENGINES, *pp.ENGINES.values(), PRIVATE_TANK, "Wan 2.2", "wan", "ltx", *SOURCES["clips"], *SOURCES["panels"])
             if w != "h3"]
    paired = [x for x in p if any(c in x for c in codes) and any(w in x.lower() for w in words)]
    assert paired == []
    assert any(first in x for x in p)                                              # the codes do get reported, just not beside names


# ---- the module's own map
def test_the_module_docstring_indexes_every_section_and_its_functions_exist():
    src = Path(pp.__file__).read_text(encoding="utf-8")
    headings = re.findall(r"^# -{10,} (.+)$", src, re.M)
    assert len(headings) == 8
    index = pp.__doc__.split("Sections of this file")[1]
    for h in headings:
        assert h in index, h
    named = re.findall(r"\[([^\]]+)\]", index)
    assert len(named) == 7
    for group in named:
        for fn in group.split(", "):
            assert callable(getattr(pp, fn)), fn


@pytest.mark.parametrize("name", ["media/c0abcd.webm", "media/notes.txt", "media/sub/x.js", "media/c0abcd", "media/c0abcd.mp4"])
def test_check_build_flags_an_unlisted_file_under_media_by_path_and_never_reads_it(tmp_path, name):
    root, here, dist = fake_build(tmp_path)
    f = dist / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"\x00\x01 Wan 2.2 and wan22 and ltx23 \x02")
    p, _, _ = chk(root, here, dist)
    assert f"{name}: not listed in study.json" in p
    assert not any("banned term" in x or "wan" in x.lower() or "ltx" in x.lower() for x in p), p
    assert not any(x.startswith(f"{name}: not a text file") for x in p)
