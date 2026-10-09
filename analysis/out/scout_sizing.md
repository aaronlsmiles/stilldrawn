# Scout sizing — how many cells to place an engine in the league?

Leave-one-engine-out simulation, 4000 trials per cell, stratified sampling across content × motion. Accuracy = fraction of trials in which a k-cell scout gives the engine its true league position.

## line_chamfer_mean_px

| k cells | accuracy | cost at Seedance std |
|---|---|---|
| 4 | 54% | $6.05 ≈ £4.72 |
| 6 | 57% | $9.07 ≈ £7.09 |
| 9 | 62% | $13.61 ≈ £10.63 |
| 12 | 66% | $18.14 ≈ £14.17 |
| 15 | 67% | $22.68 ≈ £17.72 |
| 18 | 70% | $27.22 ≈ £21.26 |
| 24 | 76% | $36.29 ≈ £28.35 |

## style_terminal

| k cells | accuracy | cost at Seedance std |
|---|---|---|
| 4 | 54% | $6.05 ≈ £4.72 |
| 6 | 61% | $9.07 ≈ £7.09 |
| 9 | 67% | $13.61 ≈ £10.63 |
| 12 | 70% | $18.14 ≈ £14.17 |
| 15 | 76% | $22.68 ≈ £17.72 |
| 18 | 77% | $27.22 ≈ £21.26 |
| 24 | 82% | $36.29 ≈ £28.35 |

## edge_abs_slope

| k cells | accuracy | cost at Seedance std |
|---|---|---|
| 4 | 54% | $6.05 ≈ £4.72 |
| 6 | 58% | $9.07 ≈ £7.09 |
| 9 | 67% | $13.61 ≈ £10.63 |
| 12 | 70% | $18.14 ≈ £14.17 |
| 15 | 79% | $22.68 ≈ £17.72 |
| 18 | 81% | $27.22 ≈ £21.26 |
| 24 | 90% | $36.29 ≈ £28.35 |

## Recommendation

No k below 24 reaches 80% on all three metrics — a partial matrix is not a reliable league instrument, and the full 33 cells are the honest purchase.

Caveat: this simulates a *known* engine's own cells. A genuinely new engine could be more variable across cells than any of the five, in which case these accuracies are optimistic.
