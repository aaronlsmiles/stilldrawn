> *Historical record, kept as written. The benchmark's working name was InkBench; it was renamed StillDrawn on 2026-09-30 after a name collision. The creator-IP panel's identifier has been neutralised to `cip-act-tank-1` throughout.*

# H3 batch reconciliation — 2026-08-12 (double-submission incident)

**What happened.** Two `matrix.py --engine h3-fal` drivers ran concurrently. The
first was launched immediately after the fal account unlocked and initially
failed every cell (data-URI submits, later fixed); it was **left running** when a
second driver was launched after the `fal_client` upload patch and billing fix.
Because each cell invocation loads `gen_video.py` fresh from disk, the stale
driver's later cells picked up the patched code and began succeeding **in
parallel** with the second driver. `gen_video.py`'s cells-run-once guard only
protects cells whose `.mp4` already exists — two in-flight submissions of the
same cell pass the check before either file lands.

**Impact.**

- 22 cell_ids have two manifest lines each (both generations billed); 60 h3-fal
  manifest lines for 39 protocol cells + 1 late resubmission of
  `cu-line-1_idle_h3` (which had only billing-lock failures, no valid attempt).
- Recorded h3-fal spend **$24.40** vs the A1 estimate **$15.60** (+$8.80, +56%).
- The `.mp4` on disk for each duplicated cell is the **last** manifest line's
  generation (the later download overwrote the earlier file). For analysis,
  the operative record per cell_id is its **final** manifest line; earlier
  duplicate lines are superseded provenance, retained because the manifest is
  append-only.

**Cause.** Operator error (agent): the stale driver was not stopped before
relaunching. Not an engine or protocol fault.

**Fixes applied.**

1. `gen_video.py` now takes an exclusive lock on `runs/<engine>/<cell-id>.lock`
   for the duration of a cell, so concurrent drivers cannot double-submit.
2. Batch-driver hygiene rule (session log): stop the previous driver (TaskStop /
   pkill) and verify with `pgrep -f "matrix.py --engine <engine>"` before
   relaunching a batch.

**Ledger.** Row `4.2.batch-2 h3-fal` records the full $24.40 actual with this
file referenced. The prereg §5/A1 hosted envelope arithmetic is updated by a
dated note in the amendments (see A2 addendum).
