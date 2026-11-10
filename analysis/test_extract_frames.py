"""Tests for analysis/extract_frames.py's cell-to-clip and cell-to-panel mapping, the new engine
tags of A14 (sd2r, and A5's sd2 for the scout's draws), A15 (kling4) and A16 (mjv) among them.
Synthetic files only.

    python -m pytest analysis/test_extract_frames.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "harness"))
import extract_frames as ef  # noqa: E402


@pytest.mark.parametrize("cell,folder,panel", [
    ("cu-line-1_idle_gen4t", "gen4_turbo", "cu-line-1"),                       # existing tags, unchanged
    ("act-black-3_burst_h3", "h3-fal", "act-black-3"),
    ("ground-cu-line-1-v052_idle_gen4t-d2", "gen4_turbo", "ground-cu-line-1-v052"),
    ("act-black-3_burst_sd2-h1", "seedance", "act-black-3"),                   # A5's fal scout (A14 re-codes it)
    ("cu-line-1_idle_sd2r-h1", "seedance2", "cu-line-1"),                      # A14
    ("act-black-3_burst_sd2r-h5", "seedance2", "act-black-3"),
    ("flint-cu-line-2--cu-line-1_kling4", "kling_4", "cu-line-2"),             # A15 scout
    ("act-black-3_burst_kling4-h3", "kling_4", "act-black-3"),
    ("ladder-act-black-1_still_kling4", "kling_4", "act-black-1"),             # A15 arm
    ("flint-est-line-2--est-black-3_mjv", "midjourney", "est-line-2"),         # A16 scout
    ("act-black-3_burst_mjv-h2", "midjourney", "act-black-3"),
    ("ladder-est-tone-3_high_mjv", "midjourney", "est-tone-3"),                # A16 arm
    ("ladder-cu-black-2_mid_gen45", "gen4.5", "cu-black-2"),                   # A10
])
def test_each_cell_finds_its_clip_and_its_source_panel(cell, folder, panel):
    assert ef.clip_path(cell) == ef.ROOT / "runs" / folder / f"{cell}.mp4"
    assert ef.panel_for(cell) == ef.ROOT / "dataset" / "panels" / f"{panel}.png"


def test_the_runway_routes_folders_are_gen_videos():
    import gen_video
    assert {ef.ENGINE_DIR["sd2r"], ef.ENGINE_DIR["kling4"]} == set(gen_video.RUNWAY_ROUTED)
    assert ef.ENGINE_DIR["sd2"] == "seedance" and ef.ENGINE_DIR["mjv"] == "midjourney"


def test_an_unknown_tag_is_refused_by_name():
    with pytest.raises(SystemExit) as e:
        ef.clip_path("cu-line-1_idle_zz9-h1")
    assert "'zz9'" in str(e.value)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg needed")
def test_a_kling_strip_is_made_from_its_folder(tmp_path, monkeypatch):
    pytest.importorskip("av")
    from PIL import Image
    monkeypatch.setattr(ef, "ROOT", tmp_path)
    monkeypatch.setattr(ef, "OUT", tmp_path / "analysis" / "out" / "frames")
    cell = "act-black-3_burst_kling4-h1"
    clip = tmp_path / "runs" / "kling_4" / f"{cell}.mp4"
    clip.parent.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=64x48:d=0.3",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)], check=True)
    (tmp_path / "dataset" / "panels").mkdir(parents=True)
    Image.new("RGB", (112, 64), "white").save(tmp_path / "dataset" / "panels" / "act-black-3.png")
    ef.extract(cell)
    strip = Image.open(tmp_path / "analysis" / "out" / "frames" / cell / "strip.png")
    assert strip.height == ef.TILE_H and strip.width > 4 * ef.TILE_H
