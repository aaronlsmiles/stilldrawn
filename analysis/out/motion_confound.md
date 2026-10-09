# Motion confound — tables (EXPLORATORY, amendment A6)

Post-hoc. May qualify a frozen result, never restate one.

## Per engine

| engine | n | motion (norm. median) | line drift (px) |
|---|---:|---:|---:|
| wan22 | 33 | 0.00080 | 0.780 |
| gen4_turbo | 32 | 0.00194 | 2.642 |
| ltx23 | 33 | 0.00248 | 2.798 |
| gen4.5 | 33 | 0.00734 | 4.788 |
| h3-fal | 33 | 0.00396 | 5.384 |

Engine-level Spearman rho(motion, drift) = **0.90** (p = 0.08333, n = 5 engines).

## Route 1 — pairwise matched-motion bands

Comparisons restricted to the overlap of each pair's motion IQR, so both
engines are judged at comparable movement. `n` is cells surviving in band.

| pair | status | in-band drift | winner at matched motion | vs raw league |
|---|---|---|---|---|
| gen4.5 vs gen4_turbo | overlap too thin | — | not comparable | — |
| gen4.5 vs h3-fal | usable (n=10,12) | 4.97 vs 5.44 | gen4.5 | same |
| gen4.5 vs ltx23 | usable (n=10,6) | 4.97 vs 3.27 | ltx23 | same |
| gen4.5 vs wan22 | **no overlap** | — | not comparable | — |
| gen4_turbo vs h3-fal | usable (n=11,6) | 2.88 vs 2.46 | h3-fal | **INVERTS** |
| gen4_turbo vs ltx23 | usable (n=9,11) | 2.88 vs 1.83 | ltx23 | **INVERTS** |
| gen4_turbo vs wan22 | overlap too thin | — | not comparable | — |
| h3-fal vs ltx23 | usable (n=15,16) | 3.38 vs 2.55 | ltx23 | same |
| h3-fal vs wan22 | overlap too thin | — | not comparable | — |
| ltx23 vs wan22 | **no overlap** | — | not comparable | — |

## Route 2 — model-based matching

Per-engine linear fit of drift on motion, compared at a common motion level (0.00243).

| engine | fitted drift (px) | observed motion range | extrapolating |
|---|---:|---|---|
| wan22 | 1.711 | 0.00054–0.01674 | False |
| gen4_turbo | 5.324 | 0.00059–0.03934 | False |
| ltx23 | 5.676 | 0.00076–0.12585 | False |
| gen4.5 | 6.096 | 0.00155–0.09962 | False |
| h3-fal | 10.906 | 0.00060–0.07311 | False |

Ordering at common motion: **wan22 < gen4_turbo < ltx23 < gen4.5 < h3-fal** — which preserves the raw league and therefore *disagrees with Route 1*. Route 1 assumes nothing about functional form; Route 2 assumes drift is linear in motion and leans on sparse tails. The disagreement is the finding: the ordering is not robust to how motion is controlled.

## Route 3 — Pareto

Frontier (not rankable without a stated trade-off): **gen4.5, gen4_turbo, ltx23, wan22**

- `h3-fal` is dominated by `gen4.5` — that engine both moves more and drifts less.
