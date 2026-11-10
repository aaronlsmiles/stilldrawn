"""Tests for harness/motion-ladder.md (A10's prompt pack v2), read through the frozen parser.

    python -m pytest harness/test_motion_ladder.py
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pack_parser import _prompt_from_file  # noqa: E402

HERE = Path(__file__).resolve().parent
LADDER = HERE / "motion-ladder.md"
FROZEN = HERE / "motion-prompts.md"
# prereg §4, frozen 2026-08-12. The release rewrites the file's title line (the working name), so the
# file has two byte forms; the four prompts, as the frozen parser reads them, are one.
FROZEN_SHA256 = {"4978eb9c6044b3eb59635e725a5225ff7b07465b314bae638e0a05bee2f4a499",    # private tree
                 "43a022980cdd4884c1eaaf4702baf5bc9b6b925ac9c8a611a23b1ed354e0ef31"}    # public release
FROZEN_CLASSES = ("IDLE", "BURST", "CAMPUSH", "FLINT")
FROZEN_PROMPTS_SHA256 = "1ab2d69df7fb3d0dc401e353ca28c1df008bdcb3f5543852582f653caa329e43"
LEVELS = ("STILL", "LOW", "MID", "HIGH")
CAMERA = "Camera locked off."
LOCK = ("The image is a black-and-white inked drawing and must remain one in every frame — "
        "line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, "
        "no photorealistic rendering, no colour, no added lighting effects.")


def prompts():
    return {lv: _prompt_from_file(str(LADDER), lv) for lv in LEVELS}


def frozen_prompts_sha256(path=FROZEN):
    """sha256 of the four frozen prompts as the frozen parser reads them (JSON, sorted keys)."""
    import json
    parsed = {c: _prompt_from_file(str(path), c) for c in FROZEN_CLASSES}
    return hashlib.sha256(json.dumps(parsed, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def test_the_frozen_pack_is_untouched():
    assert frozen_prompts_sha256() == FROZEN_PROMPTS_SHA256
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() in FROZEN_SHA256


def test_the_prompt_check_ignores_the_title_line_but_not_a_prompt(tmp_path):
    lines = FROZEN.read_text().split("\n")
    retitled = tmp_path / "retitled.md"
    retitled.write_text("\n".join(["# Another title"] + lines[1:]))
    assert frozen_prompts_sha256(retitled) == FROZEN_PROMPTS_SHA256
    idle = _prompt_from_file(str(FROZEN), "IDLE")
    edited = tmp_path / "edited.md"
    edited.write_text(FROZEN.read_text().replace(idle[:40], idle[:40].upper(), 1))
    assert frozen_prompts_sha256(edited) != FROZEN_PROMPTS_SHA256


def test_four_entries_parse_and_differ():
    p = prompts()
    assert len(set(p.values())) == 4 and all(len(v) > 100 for v in p.values())


def test_still_is_the_frozen_idle_prompt_verbatim():
    assert prompts()["STILL"] == _prompt_from_file(str(FROZEN), "IDLE")


def test_every_level_ends_with_the_frozen_camera_and_style_lock_sentences():
    idle = _prompt_from_file(str(FROZEN), "IDLE")
    assert idle.endswith(f"{CAMERA} {LOCK}")            # the constants above are the frozen pack's own words
    for lv, text in prompts().items():
        assert text.endswith(f"{CAMERA} {LOCK}"), lv
        assert text.count(CAMERA) == 1 and text.count(LOCK) == 1, lv


def test_levels_differ_only_before_the_camera_sentence():
    tails = {text[text.index(CAMERA):] for text in prompts().values()}
    assert len(tails) == 1


def test_varied_part_names_no_camera_move_or_sequence():
    import re
    banned = re.compile(r"\b(camera|zoom\w*|pan|pans|panning|push\w*|settl\w*|then)\b", re.I)
    for lv in ("LOW", "MID", "HIGH"):
        text = prompts()[lv]
        varied = text[:text.index("Camera locked off")]
        assert not banned.search(varied), (lv, banned.findall(varied))
