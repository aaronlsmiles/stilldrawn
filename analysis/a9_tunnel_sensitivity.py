#!/usr/bin/env python3
"""A9 Test 2, sensitivity line declared in docs/A9-DEVIATIONS.md note 1 (6 Nov 2026, before any
masked value existed). NOT the registered analysis and never decides the verdict.

Re-runs analysis/a9_masked_drift.py unchanged, except that on the five `est-tone-1_burst` clips
Aaron's set is read as nothing-allowed. For a nothing-allowed row the measured region is the whole
grid, so each value is copied from the blind set, which marks this row nothing-allowed.
Writes to analysis/out/a9_tunnel_sensitivity/ only. Run from the repo root."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a9_masked_drift as T2

ROW = ("est-tone-1", "burst")
_load = T2.load_clips


def load_clips(root):
    clips = _load(root)
    for c in clips:
        if (c["panel"], c["motion"]) == ROW:
            for m in T2.MARGINS:
                c["masked"][("aaron", m)] = c["masked"][("agent", m)]
            c["m_empty"]["aaron"] = c["m_empty"]["agent"]
    return clips


T2.load_clips = load_clips

if __name__ == "__main__":
    res = T2.run(out_dir=T2.ROOT / "analysis" / "out" / "a9_tunnel_sensitivity")
    print(f"sensitivity only (not the verdict): {res['verdict']}")
