# A9 Test 1: adherence (two raters)

Post-hoc (A9), exploratory. Status: **two raters** (both raters exported both studies by the deadline).

**Verdict: not supported.** Rule: supported iff the exact one-sided p <= 0.05 for both raters

Declaration: R7 is declared blind to engine styles: R7, a new rater who has never rated for StillDrawn, had not seen its explorer, release, clips or results as of 3 Nov 2026 (Gate A, revised).

Rows are in frozen-league order; there is no rank column. Miss = score <= 2 of 5.

## AARON

Ratings received: burst 2026-11-06, push 2026-11-06 (deadline: none).

| engine | steadiness S (median drift, px) | misses / clips | miss rate (Wilson 95%) |
|---|---|---|---|
| Wan 2.2 | 0.795 | 20 / 22 | 0.91 (0.72 to 0.97) |
| Gen-4 Turbo | 3.130 | 9 / 22 | 0.41 (0.23 to 0.61) |
| LTX-2.3 | 4.699 | 8 / 22 | 0.36 (0.20 to 0.57) |
| Gen-4.5 | 7.039 | 5 / 22 | 0.23 (0.10 to 0.43) |
| MiniMax H3 | 5.530 | 2 / 22 | 0.09 (0.03 to 0.28) |

| engine | burst misses / n (Wilson 95%) | push misses / n (Wilson 95%) |
|---|---|---|
| Wan 2.2 | 9 / 11 (0.52 to 0.95) | 11 / 11 (0.74 to 1.00) |
| Gen-4 Turbo | 8 / 11 (0.43 to 0.90) | 1 / 11 (0.02 to 0.38) |
| LTX-2.3 | 4 / 11 (0.15 to 0.65) | 4 / 11 (0.15 to 0.65) |
| Gen-4.5 | 2 / 11 (0.05 to 0.48) | 3 / 11 (0.10 to 0.57) |
| MiniMax H3 | 2 / 11 (0.05 to 0.48) | 0 / 11 (0.00 to 0.26) |

- Spearman rho(S, m) = -0.900; exact one-sided p = 0.0417 (120 permutations).
- Sensitivity, miss = score <= 3: rho = -0.667, p = 0.1333 (no verdict).
- Within-row check: mean rho(drift, score) over 22 of 22 rows = 0.540; one-sided p = 0.0001 (10000 draws, seed 20261030; no verdict).
- Motion cross-check, burst: AUC = 0.771 (30 non-misses, 25 misses): corroborates: the misses are under-animated.
- Motion cross-check, push: AUC = 0.731 (36 non-misses, 19 misses): corroborates: the misses are under-animated.
- Engine-level rho(motion, miss rate) = -0.900 (non-evidential: the engine ordering of motion was seen before registration).

## R7

Ratings received: burst 2026-11-06, push 2026-11-06 (deadline 2026-11-17: in time).

| engine | steadiness S (median drift, px) | misses / clips | miss rate (Wilson 95%) |
|---|---|---|---|
| Wan 2.2 | 0.795 | 20 / 22 | 0.91 (0.72 to 0.97) |
| Gen-4 Turbo | 3.130 | 6 / 22 | 0.27 (0.13 to 0.48) |
| LTX-2.3 | 4.699 | 11 / 22 | 0.50 (0.31 to 0.69) |
| Gen-4.5 | 7.039 | 7 / 22 | 0.32 (0.16 to 0.53) |
| MiniMax H3 | 5.530 | 2 / 22 | 0.09 (0.03 to 0.28) |

| engine | burst misses / n (Wilson 95%) | push misses / n (Wilson 95%) |
|---|---|---|
| Wan 2.2 | 10 / 11 (0.62 to 0.98) | 10 / 11 (0.62 to 0.98) |
| Gen-4 Turbo | 6 / 11 (0.28 to 0.79) | 0 / 11 (0.00 to 0.26) |
| LTX-2.3 | 7 / 11 (0.35 to 0.85) | 4 / 11 (0.15 to 0.65) |
| Gen-4.5 | 4 / 11 (0.15 to 0.65) | 3 / 11 (0.10 to 0.57) |
| MiniMax H3 | 2 / 11 (0.05 to 0.48) | 0 / 11 (0.00 to 0.26) |

- Spearman rho(S, m) = -0.500; exact one-sided p = 0.2250 (120 permutations).
- Sensitivity, miss = score <= 3: rho = -0.410, p = 0.2500 (no verdict).
- Within-row check: mean rho(drift, score) over 22 of 22 rows = 0.379; one-sided p = 0.0002 (10000 draws, seed 20261030; no verdict).
- Motion cross-check, burst: AUC = 0.663 (26 non-misses, 29 misses): inconclusive (between 0.60 and 0.70).
- Motion cross-check, push: AUC = 0.847 (38 non-misses, 17 misses): corroborates: the misses are under-animated.
- Engine-level rho(motion, miss rate) = -0.500 (non-evidential: the engine ordering of motion was seen before registration).

## Agreement

Quadratic-weighted kappa: burst 0.635, push 0.708.

## Attainable p-values (five engines, no ties)

rho -1.0: p 0.0083, rho -0.9: p 0.0417, rho -0.8: p 0.0667, rho -0.7: p 0.1167, rho -0.6: p 0.1750, rho -0.5: p 0.2250
