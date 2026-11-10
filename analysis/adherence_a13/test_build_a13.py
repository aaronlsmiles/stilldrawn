"""Tests for analysis/adherence_a13/build_a13.py. They read A9's frozen instrument files (the study
specs in prepare.py, media-sources.json, study.lock.json), which ship, and nothing derived from ratings.

    python -m pytest analysis/adherence_a13/test_build_a13.py
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_a13 as B  # noqa: E402

P = B.P
SAME = ("key", "dir", "motion_class", "title", "clause", "n_clips", "n_panels", "question", "labels")


def sources(key):
    return json.loads((B.A9 / B.SPECS[key]["dir"] / "media-sources.json").read_text())


@pytest.mark.parametrize("key, a9", [("burst", P.BURST), ("push", P.PUSH)])
def test_specs_are_a9s_but_for_the_id_and_the_seed(key, a9):
    s = B.SPECS[key]
    assert {k: s[k] for k in SAME} == {k: a9[k] for k in SAME}
    assert (s["id"], s["seed"]) == (f"a13-{key}", f"a13-{key}-20261104")
    assert s["seed"] != a9["seed"] and s["seed"] not in P.A6_SEEDS


@pytest.mark.parametrize("key", ["burst", "push"])
def test_the_attention_draw_is_seeded_and_two_distinct_clips_of_the_study(key):
    src = sources(key)
    a = B.attention_ids(key, src["clips"])
    assert a == B.attention_ids(key, src["clips"])
    assert len(set(a)) == 2 and set(a) <= set(src["clips"])


@pytest.mark.parametrize("key", ["burst", "push"])
def test_the_study_is_a9s_plus_the_repeats_and_their_session_size(key):
    src = sources(key)
    cfg, att = B.study_config(key, src)
    base = P.study_config(B.SPECS[key], src)
    clips = cfg["parts"]["clips"]
    assert clips.pop("repeats") == {"min_gap": 5, "items": [{"of": att[0], "position": 30},
                                                            {"of": att[1], "position": 52}]}
    assert clips["session_size"] == 57
    clips["session_size"] = base["parts"]["clips"]["session_size"]
    assert "privacy" not in base and cfg.pop("privacy") == B.PRIVACY
    assert cfg == base                                    # nothing else differs from A9's own builder
    assert cfg["instrument"] == "A9" and cfg["modes"]["public"]["tally"] is False


A13_PRIVACY = ("This page sets one cookie and the hosting service logs page requests, as the consent page says. "
               "Pressing Send sends your answers, their order and a rounded duration under your study code.")


def test_the_privacy_line_is_a13s_own():
    """A13's privacy line, the one its consent page agrees with, replaces A9's."""
    assert B.PRIVACY == A13_PRIVACY


@pytest.mark.parametrize("key", ["burst", "push"])
def test_each_study_yaml_is_the_builders_output_and_carries_a13s_privacy_line(key):
    """The committed study.yaml is what `write` writes: A9's study, the repeats, and A13's privacy line,
    which is outside the instrument lock (blindpanel hashes the scales, questions and intros only)."""
    text = (B.HERE / B.SPECS[key]["dir"] / "study.yaml").read_text()
    cfg, _att = B.study_config(key, sources(key))
    assert text == B.HEAD + P.to_yaml(cfg) + "\n"
    assert text.count("privacy: ") == 1 and f"privacy: {json.dumps(A13_PRIVACY, ensure_ascii=False)}\n" in text


@pytest.mark.parametrize("study, ok", [({"privacy": A13_PRIVACY}, True), ({}, False), ({"privacy": "x"}, False),
                                       ({"privacy": [A13_PRIVACY]}, False)])
def test_check_build_wants_a13s_privacy_line_in_the_built_study(study, ok):
    assert (B.privacy_problems(study) == []) is ok


def test_the_mapping_is_seeded_new_and_release_safe():
    configs, atts = {}, {}
    for key in B.SPECS:
        configs[key], atts[key] = B.study_config(key, sources(key))
    m = B.mapping(configs, atts)
    assert m["instrument"] == "A13" and m["seed"] == 20261104
    for key, st in m["studies"].items():
        seed = B.SPECS[key]["seed"]
        assert len(st["code_to_cell"]) == 55
        assert all(P.opaque_code(seed, "clip", cell) == code for code, cell in st["code_to_cell"].items())
        assert [r["alias"] for r in st["repeats"]] == [P.opaque_code(seed, "clip", f"{a}#repeat") for a in atts[key]]
        assert [r["position"] for r in st["repeats"]] == [30, 52]
        assert m["attention_clips"][key] == [r["of"] for r in st["repeats"]]
    assert not (B.a9_codes() & B.all_codes(m))
    assert str(Path.home()) not in json.dumps(m)         # no local path (no path literal either: it ships)


def test_the_motion_list_names_the_110_released_motion_files(tmp_path, monkeypatch):
    configs, atts = {}, {}
    for key in B.SPECS:
        configs[key], atts[key] = B.study_config(key, sources(key))
    monkeypatch.setattr(B, "HERE", tmp_path)
    (tmp_path / "mapping.json").write_text(json.dumps(B.mapping(configs, atts)))
    lines = B.motion_list()
    assert len(lines) == 110 and len(set(lines)) == 110
    assert all(x.startswith("runs/metrics-motion/") and x.endswith(".json") for x in lines)


def test_the_attention_seed_strings_are_the_registered_ones():
    assert [B.attention_key(k) for k in B.SPECS] == ["20261104:a13:burst:attention", "20261104:a13:push:attention"]


def test_link_media_refuses_without_a9s_copies_and_links_only_checked_ones(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "HERE", tmp_path / "a13")
    monkeypatch.setenv(B.A9_MEDIA_ENV, str(tmp_path / "nowhere"))
    with pytest.raises(SystemExit, match="A13_A9_MEDIA"):
        B.link_media("burst", sources("burst"))
    root = tmp_path / "a9"
    for spec in B.SPECS.values():
        (root / spec["dir"] / "media").mkdir(parents=True)
    good = {"copy": "media/x.mp4", "copy_sha256": hashlib.sha256(b"right").hexdigest()}
    (root / "burst" / "media" / "x.mp4").write_bytes(b"right")
    monkeypatch.setenv(B.A9_MEDIA_ENV, str(root))
    assert B.link_media("burst", {"clips": {"x": good}, "panels": {}}) == 1
    assert (tmp_path / "a13" / "burst" / "media" / "x.mp4").read_bytes() == b"right"
    (root / "burst" / "media" / "y.mp4").write_bytes(b"wrong")
    with pytest.raises(SystemExit, match="differs from A9's rating copy"):
        B.link_media("burst", {"clips": {"y": dict(good, copy="media/y.mp4")}, "panels": {}})


def test_check_locks_refuses_a_lock_that_is_not_a9s(tmp_path, monkeypatch):
    monkeypatch.setattr(B, "HERE", tmp_path)
    for key in B.SPECS:
        (tmp_path / key).mkdir()
        (tmp_path / key / "study.lock.json").write_text(json.dumps({"instrument": "A9", "text_sha256": "0" * 64}))
    with pytest.raises(SystemExit, match="not A9's"):
        B.check_locks()
    for key in B.SPECS:
        (tmp_path / key / "study.lock.json").write_bytes((B.A9 / key / "study.lock.json").read_bytes())
    B.check_locks()


OTHERS = [f"cc{n:04d}" for n in range(55)]


def _built(alias="ca0000", of="cb0000"):
    """A minimal 0.3 study.json and reveal.json: one original, its repeat and 55 other clips (57 items)."""
    item = {"code": of, "video": "media/cb0000.mp4", "reference": "pa0000"}
    others = [{"code": c, "video": f"media/{c}.mp4", "reference": "pa0000"} for c in OTHERS]
    study = {"scales": {"burst": {"kind": "ordinal", "min": 1, "max": 5, "labels": ["a", "b", "c", "d", "e"]}},
             "parts": {"clips": {"session_size": 57, "items": [item, dict(item, code=alias), *others],
                                 "repeats": {"min_gap": 5, "items": [{"alias": alias, "of": of, "position": 30}]}}}}
    reveal = {"study": "a13-burst", "reference": None,
              "items": {of: {"label": "clip", "meta": {}}, alias: {"label": "clip", "meta": {}}}}
    mst = {"min_gap": 5, "repeats": [{"alias": alias, "of": of, "position": 30}]}
    return study, reveal, mst


def test_repeat_view_checks_the_repeats_then_hands_a9_the_study_it_knows():
    study, reveal, mst = _built()
    p, view, rv = B.repeat_view(study, reveal, mst)
    assert p == []
    assert [i["code"] for i in view["parts"]["clips"]["items"]] == ["cb0000", *OTHERS]
    assert "repeats" not in view["parts"]["clips"] and view["parts"]["clips"]["session_size"] == 55
    assert "kind" not in view["scales"]["burst"] and list(rv["items"]) == ["cb0000"]


@pytest.mark.parametrize("edit, msg", [
    (lambda s, r: s["parts"]["clips"]["repeats"]["items"][0].update(position=31), "differs from mapping.json"),
    (lambda s, r: s["parts"]["clips"]["items"][1].update(video="media/other.mp4"), "its original's clip"),
    (lambda s, r: r["items"]["ca0000"].update(label="H3"), "reveals something"),
    (lambda s, r: s["scales"]["burst"].update(kind="choice"), "not ordinal"),
])
def test_repeat_view_finds_a_wrong_repeat(edit, msg):
    study, reveal, mst = _built()
    edit(study, reveal)
    p, _view, _rv = B.repeat_view(study, reveal, mst)
    assert any(msg in x for x in p), p


def test_repeat_view_refuses_an_alias_item_with_a_meta_key():
    study, reveal, mst = _built()
    study["parts"]["clips"]["items"][1]["meta"] = {"note": "x"}         # A9's shape check never sees an alias
    p, _view, _rv = B.repeat_view(study, reveal, mst)
    assert any("ca0000 is not its original's item with only the code changed" in x for x in p), p


def test_repeat_view_refuses_an_alias_item_with_a_key_blindpanel_never_writes():
    study, reveal, mst = _built()
    study["parts"]["clips"]["items"][1]["label"] = "x"
    p, _view, _rv = B.repeat_view(study, reveal, mst)
    assert any("ca0000 is not its original's item with only the code changed" in x for x in p), p


def test_repeat_view_refuses_a_second_alias_item_showing_the_wrong_clip_before_the_right_one():
    study, reveal, mst = _built()
    items = study["parts"]["clips"]["items"]
    right = items[1]
    items[1:3] = [dict(right, video=items[2]["video"]), right]           # still 57 items; the wrong one first
    assert len(items) == 57
    p, _view, _rv = B.repeat_view(study, reveal, mst)
    assert any("repeat ca0000 appears 2 times, expected once" in x for x in p), p
    assert any("ca0000 is not its original's item with only the code changed" in x for x in p), p


def test_repeat_view_wants_exactly_57_clip_items():
    study, reveal, mst = _built()
    study["parts"]["clips"]["items"].pop()
    p, _view, _rv = B.repeat_view(study, reveal, mst)
    assert any("56 clip items, expected 57" in x for x in p), p


@pytest.mark.parametrize("key", ["burst", "push"])
def test_the_built_studies_still_read_clean_and_match_their_recorded_trees(key, capsys):
    """The local builds only: they are gitignored (they hold the rating copies), so a clone or the release skips."""
    dist = B.HERE / ".build" / f"a13-{key}"
    if not (dist / "study.json").is_file():
        pytest.skip(f"no local build of a13-{key} (gitignored)")
    assert B.check_build_cli(key, dist, record=False, expect_recorded=True) == 0      # check-build --expect-recorded
    assert f"a13-{key}: clean (83 files); tree {P.recorded_tree(B.SPECS[key], B.HERE)}" in capsys.readouterr().out


def test_check_build_replaces_a_recorded_tree_only_when_asked(tmp_path, monkeypatch):
    """A9's rule: a recorded build is the one raters sit at; re-recording is deliberate (before any rating)."""
    seen = []
    monkeypatch.setattr(B, "MANIFEST", tmp_path / "A13-MANIFEST.sha256")      # before registration, always
    monkeypatch.setattr(B, "check_build_cli", lambda *a, **k: seen.append((a, k)) or 0)
    for extra in ([], ["--replace-recorded"]):
        with pytest.raises(SystemExit) as e:
            B.main(["check-build", "--study", "burst", "--dist", "x", "--record", *extra])
        assert e.value.code == 0
    assert [k["replace"] for _a, k in seen] == [False, True]
    for argv in (["--replace-recorded"], ["--expect-recorded", "--replace-recorded"]):
        with pytest.raises(SystemExit) as e:
            B.main(["check-build", "--study", "burst", "--dist", "x", *argv])
        assert e.value.code == 2


def test_replace_recorded_is_refused_once_the_manifest_exists(tmp_path, monkeypatch):
    """After registration the tree hashes are frozen inputs (docs/A13-MANIFEST.sha256): no re-record."""
    seen = []
    monkeypatch.setattr(B, "check_build_cli", lambda *a, **k: seen.append(k) or 0)
    monkeypatch.setattr(B, "MANIFEST", tmp_path / "A13-MANIFEST.sha256")
    argv = ["check-build", "--study", "burst", "--dist", "x", "--record", "--replace-recorded"]
    with pytest.raises(SystemExit) as e:
        B.main(argv)                                      # no manifest yet: still works
    assert e.value.code == 0 and seen == [{"replace": True}]
    B.MANIFEST.write_text("0" * 64 + "  analysis/a13_adherence.py\n")
    with pytest.raises(SystemExit, match="a recorded tree cannot be replaced after registration"):
        B.main(argv)
    assert len(seen) == 1
    with pytest.raises(SystemExit) as e:
        B.main(argv[:-1])                                 # recording the same tree stays allowed
    assert e.value.code == 0 and seen[-1] == {"replace": False}


def test_check_build_cli_refuses_to_replace_a_tree_after_registration_whoever_calls_it(tmp_path, monkeypatch):
    """The guard sits beside record_tree, so a module caller cannot pass it; recording the same tree still works."""
    recorded = []
    monkeypatch.setattr(B, "MANIFEST", tmp_path / "A13-MANIFEST.sha256")
    monkeypatch.setattr(B, "check_build", lambda *a, **k: ([], "f" * 64, 83))
    monkeypatch.setattr(P, "record_tree", lambda spec, here, dist, tree, replace=False: recorded.append(replace))
    assert B.check_build_cli("burst", tmp_path, record=True, expect_recorded=False, replace=True) == 0
    B.MANIFEST.write_text("0" * 64 + "  analysis/a13_adherence.py\n")
    with pytest.raises(SystemExit, match="a recorded tree cannot be replaced after registration"):
        B.check_build_cli("burst", tmp_path, record=True, expect_recorded=False, replace=True)
    assert B.check_build_cli("burst", tmp_path, record=True, expect_recorded=False) == 0
    assert recorded == [True, False]
