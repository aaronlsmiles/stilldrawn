# Known errata in the released records

Frozen and historical records ship as written. These inaccuracies were found in
the audit before release; each is corrected here rather than in the record.

1. **Budget ledger running totals.** A rate correction to one MiniMax H3 repeat
   batch (+£1.29) changed that row's £ amount but was not carried into the
   running totals after it. The £ column sums to **£115.37**, not the £114.08
   shown in the last running total; the ledger's dated correction row of
   2026-10-01 records this. Amendments A7 and A8 quote the running total as it
   stood (£114.08). The paper uses £115.37.
2. **Amendment A4, "existing draws".** A4 describes existing main-run and repeat
   draws as contributing to each cell's ten. That holds for the four cells in the
   primary rotation (three received 8 new draws; `cu-line-1_idle_h3`, which
   already had three, received 7). The four cells outside the rotation
   (`act-black-3_idle_h3`, `act-line-2_idle_h3`, `cu-black-3_idle_h3`,
   `cu-line-1_burst_h3`) had no earlier draws and received all ten new. Total new
   draws: 71.
   The eight-cell extension itself was explicitly approved on 2026-08-14; the
   approval was recorded afterwards, in an addendum to A4 and a ledger note.
3. **Rater orders in `analysis/human_check/mapping.json`.** The per-rater orders
   were generated for the offline kit's slots (the author and R1–R5). R1 never
   rated. R6 rated on the hosted instrument, whose order follows the same seeded
   scheme.
4. **Amendment label A6** is used for two separate amendments (see
   `docs/PROVENANCE.md`).
5. **`runs/RECONCILIATION-2026-08-12-h3.md`** refers to an "A2 addendum"; there is
   no separately headed addendum. The relevant text is amendment A2 itself.
6. **`docs/TOS-REVIEW.md`** refers to a "compliance paragraph" in the paper. That
   role is filled by the paper's Data and code availability section and by
   `NOTICE-PROVIDERS.md`. The Illustrious-XL checkpoint hash it promised is in the
   datasheet.
7. **Frame strips.** The released strips are the set reviewed for the failure-mode
   taxonomy. The paper's observations on the MiniMax H3 repeat draws were made
   from the clips, which are released; no strips were extracted for them.
8. **Motion-confound analysis** (`analysis/motion_confound.py`). Two corrections,
   made before the paper was posted. (a) The script computed every Spearman p from
   a normal approximation to the t tail. At n = 5 (the engine-level correlation
   and the five-step ground series) that overstated significance badly: the
   engine-level ρ = 0.90 was printed with p = 0.0003, where the exact two-sided
   permutation p is 10/120 = 0.083. The script now uses an exact permutation p
   for n ≤ 9 and the t(n − 2) tail above that. (b) Its docstring put the analysis
   on the 33-cell standard basis, but it joined every row of the results table,
   so MiniMax H3's six FLINT cells were pooled in (n = 39). FLINT cells are now
   excluded, as everywhere else in the cross-engine analysis (164 cells). On that
   basis H3's median line drift is 5.384 px (was 5.453), five engine pairs give a
   usable matched-motion band and two reverse (was three: Gen-4.5 against H3 no
   longer reverses), and the engine-level ρ and both orderings are unchanged. The
   released outputs and the motion figure
   (`analysis/out/figures/fig6_motion.png`, Figure 2 in the paper) were regenerated; the paper reports the
   corrected values.
