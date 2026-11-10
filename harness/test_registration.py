"""Tests for harness/registration.py, the A10-A16 tripwire. Synthetic files only.

    python -m pytest harness/test_registration.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import registration as reg  # noqa: E402

A9_ONLY = "## Amendments\n\n### A9 — 2026-11-03: exploratory follow-up\n\ntext\n"


def write(tmp_path, text):
    p = tmp_path / "PREREGISTRATION.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_heading_must_start_a_line_and_name_the_amendment(tmp_path):
    p = write(tmp_path, A9_ONLY + "### A1 — 2026-08-12: old\nsee ### A10 — in prose\n")
    assert reg.is_public("A9", p) and reg.is_public("A1", p)
    assert not reg.is_public("A10", p)                    # a mention mid-line, or A1's heading, does not open A10
    p = write(tmp_path, A9_ONLY + "### A10 — 2026-11-20: motion by construction\n")
    assert reg.is_public("A10", p)
    assert not reg.is_public("A1", p)                     # and A10's heading does not open A1


def test_a_missing_file_is_not_public(tmp_path):
    assert not reg.is_public("A10", tmp_path / "nope.md")


def test_require_public_refuses_with_a_clear_message(tmp_path):
    p = write(tmp_path, A9_ONLY)
    with pytest.raises(SystemExit) as e:
        reg.require_public("A12", "generate ground draws", hint="--dry-run needs no registration.", prereg=p)
    msg = str(e.value)
    assert "REFUSING to generate ground draws" in msg and "A12" in msg and "--dry-run" in msg
    assert "heading '### A12 — ' absent" in msg


def test_the_refusal_says_when_the_file_is_missing(tmp_path):
    with pytest.raises(SystemExit) as e:
        reg.require_public("A10", "build the ladder", prereg=tmp_path / "nope.md")
    assert "file not found" in str(e.value)


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root reads any file")
def test_an_unreadable_file_is_not_public_and_does_not_raise(tmp_path):
    p = write(tmp_path, "### A10 — 2026-11-20: x\n")
    p.chmod(0)
    try:
        assert not reg.is_public("A10", p)
        assert "unreadable" in reg.status("A10", p)[1]
    finally:
        p.chmod(0o644)


def test_a_private_tree_never_counts_as_public(tmp_path, monkeypatch):
    priv = tmp_path / "private-repo"
    (priv / "analysis" / "adherence").mkdir(parents=True)
    (priv / "analysis" / "adherence" / "private-terms.txt").write_text("zorbly\n", encoding="utf-8")
    (priv / "docs").mkdir()
    p = priv / "docs" / "PREREGISTRATION.md"
    p.write_text(A9_ONLY + "### A10 — 2026-11-20: motion by construction\n", encoding="utf-8")
    assert not reg.is_public("A10", p)
    assert "private tree" in reg.status("A10", p)[1]
    monkeypatch.setenv(reg.ENV, str(p))                   # named through the environment: the same refusal
    with pytest.raises(SystemExit) as e:
        reg.require_public("A10", "build the ladder")
    assert "private tree" in str(e.value)


def test_a_relative_env_path_to_this_checkout_is_refused(monkeypatch):
    monkeypatch.chdir(reg.ROOT)
    monkeypatch.setenv(reg.ENV, "docs/PREREGISTRATION.md")
    assert reg.public_prereg() == (reg.ROOT / "docs" / "PREREGISTRATION.md").resolve()
    own = reg.ROOT / "docs" / "PREREGISTRATION.md"
    if reg.private_tree(own):                                    # the private repository
        assert not reg.is_public("A9") and not reg.is_public("A1")   # its own file, whatever it holds
    else:                                                        # the public release: its own file is public
        text = own.read_text(encoding="utf-8")
        for a in ("A1", "A9"):
            assert reg.is_public(a) == bool(reg.heading(a).search(text))


def test_a_copy_of_a_public_file_in_a_temp_dir_is_accepted(tmp_path, monkeypatch):
    src = write(tmp_path, A9_ONLY + "### A11 — 2026-11-20: human check at power\n")
    dst = tmp_path / "fetched" / "docs" / "PREREGISTRATION.md"
    dst.parent.mkdir(parents=True)
    shutil.copyfile(src, dst)
    monkeypatch.setenv(reg.ENV, str(dst))
    assert reg.require_public("A11", "x") == dst.resolve()
    assert not reg.is_public("A12")


def test_require_public_passes_and_returns_the_path(tmp_path):
    p = write(tmp_path, A9_ONLY + "### A12 — 2026-11-20: grey ground\n")
    assert reg.require_public("A12", "x", prereg=p) == p


def test_the_environment_names_the_file_else_the_sibling_public_tree(tmp_path, monkeypatch):
    p = write(tmp_path, "### A11 — 2026-11-20: human check at power\n")
    monkeypatch.setenv(reg.ENV, str(p))
    assert reg.public_prereg() == p.resolve() and reg.is_public("A11")
    monkeypatch.delenv(reg.ENV)
    assert reg.public_prereg() == reg.ROOT.parent / "stilldrawn" / "docs" / "PREREGISTRATION.md"


def test_the_release_builds_rerun_in_the_staged_tree_is_accepted(tmp_path):
    rel = tmp_path / "rel"                                # the staged tree: no private-terms marker
    (rel / "harness").mkdir(parents=True)
    (rel / "docs").mkdir()
    shutil.copyfile(Path(reg.__file__), rel / "harness" / "registration.py")
    prereg = rel / "docs" / "PREREGISTRATION.md"
    prereg.write_text(A9_ONLY + "### A10 — 2026-11-20: motion by construction\n", encoding="utf-8")
    env = {**os.environ, reg.ENV: str(prereg)}
    code = "import sys; sys.path.insert(0, 'harness'); import registration as r; print(r.status('A10'))"
    out = subprocess.run([sys.executable, "-c", code], cwd=rel, env=env,
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == "(True, '')"


# ------------------------------------------------ A13 to A16: the headings their drafts use
# Registered form of each draft's heading (docs/A13-DRAFT.md; docs/A14-A16-DRAFT.md), the
# [[DATE]] token filled as it will be at registration.
DRAFT_HEADINGS = {
    "A13": "### A13 — 2026-11-20: confirmatory: adherence at power",
    "A14": "### A14 — 2026-11-20: confirmatory: A5's Seedance hazard replication completed at five "
           "fresh draws per cell",
    "A15": "### A15 — 2026-11-20: a Kling scout with a declared decision rule; Kling in A10's motion "
           "test only if it passes",
    "A16": "### A16 — 2026-11-20: a Midjourney video scout with a declared decision rule, run by hand; "
           "Midjourney in A10's motion test only if it passes",
}
NEIGHBOURS = ("A1", "A3", "A4", "A5", "A6", "A9", "A10", "A11", "A12", "A13", "A14", "A15", "A16",
              "A130", "A140", "A150", "A160")


@pytest.mark.parametrize("amendment", sorted(DRAFT_HEADINGS))
def test_each_draft_heading_opens_its_own_amendment_and_no_other(tmp_path, amendment):
    p = write(tmp_path, A9_ONLY + DRAFT_HEADINGS[amendment] + "\n\ntext\n")
    assert reg.is_public(amendment, p) and reg.require_public(amendment, "x", prereg=p) == p
    for other in NEIGHBOURS:
        if other not in (amendment, "A9"):
            assert not reg.is_public(other, p), other


@pytest.mark.parametrize("amendment", sorted(DRAFT_HEADINGS))
def test_a13_to_a16_stay_shut_on_a1_a10_a12_or_a_mention(tmp_path, amendment):
    p = write(tmp_path, A9_ONLY + "### A1 — 2026-08-12: old\n### A10 — 2026-11-20: ladder\n"
              "### A12 — 2026-11-20: grey ground\n"
              f"see ### {amendment} — in prose\n#### {amendment}.1 Seen before registration\n"
              f"### {amendment} - 2026-11-20: a hyphen, not the em dash\n")
    assert not reg.is_public(amendment, p)
    assert f"heading '### {amendment} — ' absent" in reg.status(amendment, p)[1]


def test_a15_refuses_while_only_a10_is_public(tmp_path):
    p = write(tmp_path, A9_ONLY + "### A10 — 2026-11-20: motion by construction\n")
    with pytest.raises(SystemExit) as e:
        reg.require_public("A15", "generate ladder clips on kling_4", prereg=p)
    assert "amendment A15 is not in the public pre-registration" in str(e.value)


def test_the_drafts_headings_are_the_ones_tested_here():
    """In the private repository, docs/A14-A16-DRAFT.md's own heading lines, with [[DATE]] filled,
    are the ones above, and each opens its amendment (the release tree has no draft: skipped)."""
    draft = reg.ROOT / "docs" / "A14-A16-DRAFT.md"
    if not draft.is_file():
        pytest.skip("no docs/A14-A16-DRAFT.md in this tree (the release ships no drafts)")
    lines = [ln.replace("[[DATE]]", "2026-11-20") for ln in draft.read_text(encoding="utf-8").splitlines()
             if ln.startswith("### A1")]
    assert lines == [DRAFT_HEADINGS[a] for a in ("A14", "A15", "A16")]
    for a in ("A14", "A15", "A16"):
        assert reg.heading(a).search("\n".join(lines))


def test_the_docstring_names_the_amendments_it_guards():
    assert "A10 to A16" in reg.__doc__
