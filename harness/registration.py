#!/usr/bin/env python3
"""Registration tripwire for amendments A10 to A16.

A tool that makes or reads an amendment's new data refuses to run until that
amendment's heading (`### A10 — ` and so on, at the start of a line, with the
em dash the drafts use: `### A13 — `, `### A14 — `, `### A15 — `, `### A16 — `)
is in the PUBLIC release's docs/PREREGISTRATION.md. `### A1 — ` does not open
A13 to A16, nor `### A14 — ` A1 or A4; a mention in prose, a subsection heading
(`#### A14.1`) or a hyphen in place of the em dash opens nothing. A9 set the pattern (metrics/masked.py);
this is its light form: a file check, not a git check.

Where the public pre-registration is looked for:
  1. the file named by STILLDRAWN_PUBLIC_PREREG, if set (on the rented GPU, a copy
     fetched from the public repository on GitHub; in the release build's re-run,
     the release tree's own file);
  2. otherwise docs/PREREGISTRATION.md in the folder `stilldrawn` beside this
     repository's folder (the public checkout the release build refreshes).

A file inside a private tree never counts, whatever the path says: a file is in a
private tree when any folder above it carries analysis/adherence/private-terms.txt.
The main checkout and every worktree do, and so does any copy made under them; the
public tree and the release build's staged tree never do (the build's verify fails
on that file if it ever ships). So pointing STILLDRAWN_PUBLIC_PREREG at the private
docs/PREREGISTRATION.md, or a relative path that resolves to it, cannot open the
tripwire, while the build's re-run in the staged tree, which names that tree's own
file, can.

It is a tripwire, not a proof: a file can be edited by hand. The registered
sequence (dated amendment, in-place refresh, pushed tag, Software Heritage save)
is what makes registration checkable.
"""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = "STILLDRAWN_PUBLIC_PREREG"


def public_prereg():
    """Path of the public pre-registration this checkout trusts."""
    env = os.environ.get(ENV)
    return Path(env).expanduser().resolve() if env else ROOT.parent / "stilldrawn" / "docs" / "PREREGISTRATION.md"


def heading(amendment):
    """`### A10 — ` at the start of a line. `### A1 — ` does not open A10, nor the reverse."""
    return re.compile(rf"^### {re.escape(amendment)} — ", re.M)


def private_tree(prereg):
    """True when any folder above `prereg` carries analysis/adherence/private-terms.txt,
    the private repository's marker (main checkout, worktrees, copies under them)."""
    rp = Path(prereg).expanduser().resolve()
    return any((d / "analysis" / "adherence" / "private-terms.txt").is_file() for d in rp.parents)


def status(amendment, prereg=None):
    """(public, reason): reason says why not, or is "" when the heading is there."""
    p = Path(prereg) if prereg is not None else public_prereg()
    if private_tree(p):
        return False, "the file is in the private tree, not the public release"
    try:
        text = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False, "file not found"
    except (OSError, UnicodeDecodeError) as e:
        return False, f"file unreadable ({type(e).__name__})"
    if heading(amendment).search(text) is None:
        return False, f"heading '### {amendment} — ' absent"
    return True, ""


def is_public(amendment, prereg=None):
    return status(amendment, prereg)[0]


def require_public(amendment, action, hint="", prereg=None):
    """Return the path checked, or exit non-zero with a message naming the amendment."""
    p = Path(prereg) if prereg is not None else public_prereg()
    ok, reason = status(amendment, p)
    if not ok:
        msg = (f"REFUSING to {action}: amendment {amendment} is not in the public "
               f"pre-registration ({p}: {reason}). It must be registered first.")
        if hint:
            msg += f" {hint}"
        raise SystemExit(msg)
    return p
