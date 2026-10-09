#!/usr/bin/env python3
"""Prompt-pack parser — the single module both gen scripts import.

Pack contract: a `**<SHOT> — title**` heading ENDING THE LINE, then a `>`
blockquote (the positive prompt), then optionally a `**Negative:**` line with
its own `>` blockquote. The heading regex is anchored to end-of-line so
trailing text after the bold close (e.g. `**X1 — The tank** *(note)*`) cannot
run the match into the next shot's block — a silent bug found and fixed
upstream on 2026-07-29. Do not weaken the anchor.
"""
import pathlib
import re
import sys


def _prompt_from_file(path: str, shot: str) -> str:
    """Pull the block-quoted prompt following a `**<shot> —` heading line.

    Heading matched to END OF LINE so trailing text after the bold close can't
    run the match into the next shot's block (silent bug before 2026-07-29).
    """
    txt = pathlib.Path(path).read_text()
    m = re.search(rf"^\*\*{re.escape(shot)}\b[^\n]*\n+>[ \t]*(.+?)(?=\n[ \t]*\n|\n\*\*|\Z)",
                  txt, re.S | re.M)
    if not m:
        sys.exit(f"shot {shot} not found in {path}")
    return " ".join(line.lstrip("> \t").strip() for line in m.group(1).splitlines()).strip()


def _negative_from_file(path: str, shot: str) -> str | None:
    """Optional `**Negative:**` + `>` blockquote directly after a shot's positive block.

    Hardened vs the upstream single-regex form (2026-08-12): the negative is
    matched anchored at the END of this shot's positive block, so a shot with
    no Negative of its own can never bleed into a LATER entry's negative (the
    upstream `.+?` backtracks across intervening headings until any
    `**Negative:**` satisfies it — same bug family as 2026-07-29).
    """
    txt = pathlib.Path(path).read_text()
    m = re.search(rf"^\*\*{re.escape(shot)}\b[^\n]*\n+>[ \t]*(.+?)(?=\n[ \t]*\n|\n\*\*|\Z)",
                  txt, re.S | re.M)
    if not m:
        return None
    m2 = re.compile(r"\n+\*\*Negative:\*\*[^\n]*\n+>[ \t]*(.+?)(?=\n[ \t]*\n|\n\*\*|\Z)",
                    re.S).match(txt, m.end(1))
    if not m2:
        return None
    return " ".join(line.lstrip("> \t").strip() for line in m2.group(1).splitlines()).strip()
