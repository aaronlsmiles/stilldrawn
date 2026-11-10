# Human check 2 (amendment A11)

A11 repeats the §6 human check at power: 40 clips that A6 did not rate, rated by raters
recruited on Prolific under opaque slots R8 to R19 (the author does not rate), with the
A6/A8 instrument word for word. The registered test (H3) and its rules are in
`docs/PREREGISTRATION.md`, amendment A11.

| File | What it holds |
|---|---|
| `build_mapping.py` | Writes the two mapping files from `analysis/out/a11_subset.json` (seed 20261104) |
| `mapping.json` | Opaque clip code (c21 to c60) to cell id; the two attention clips |
| `baseline_mapping.json` | Opaque panel code (from p15) to panel id; clip code to panel code |
| `collect.py` | The A11 analysis: A6's analysis code, imported from `../human_check/collect.py`, then the rater rules, H3 and the baseline-filtered register analysis |
| `ratings/ratings-R<n>.json` | One file per rater slot: scores only (below) |
| `human_check2_results.json`, `.md` | The analysis output |

**Rating files.** Each holds `rater`, `instrument` (`A11`), `ratings` (one entry per clip:
`clip`, `register` 1 to 5, `sameness` 1 to 5), `attention` (the second showing of each
attention clip, same fields) and `baseline` (`panel`, `hand_drawn` 1 to 5). No names,
contact details, platform ids, timings, answer timestamps, free-text comments or clip
orders are released, as in A6.

**Rules applied before any correlation** (registered in A11): a file that does not rate
every clip on both questions is excluded as incomplete; a rater whose second answers to
both attention clips differ from the first answers by two or more scale points, on either
question, is excluded. Both counts are reported.

Run: `python analysis/human_check2/collect.py`, with a Python that has numpy and scipy.
