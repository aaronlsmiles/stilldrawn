# Hazard rates — A4 as registered, plus the cross-engine view

Automatic coding rule (frozen A4): mean chamfer vs frame 0 > 10 px counts as a departure. Wilson 95% intervals throughout.

## 1. A4 — MiniMax H3, per cell

| cell | n | departed | rate | 95% CI |
|---|---|---|---|---|
| `act-black-3_burst_h3` | 10 | 8 | **80%** | 49%–94% |
| `act-black-3_idle_h3` | 10 | 0 | **0%** | 0%–28% |
| `act-line-2_burst_h3` | 10 | 1 | **10%** | 2%–40% |
| `act-line-2_idle_h3` | 10 | 0 | **0%** | 0%–28% |
| `cu-black-3_burst_h3` | 10 | 4 | **40%** | 17%–69% |
| `cu-black-3_idle_h3` | 10 | 1 | **10%** | 2%–40% |
| `cu-line-1_burst_h3` | 10 | 2 | **20%** | 6%–51% |
| `cu-line-1_idle_h3` | 10 | 9 | **90%** | 60%–98% |

## 2. The registered test (frozen A4 clause 5)

BURST x heavy-black **12/20 = 60%** vs IDLE x line-only **9/20 = 45%**.
One-sided Fisher exact: OR = 1.83, **p = 0.2636** — NOT significant at alpha 0.05.

### Panel identity dominates the stratum

Within the single stratum IDLE x line-only, cell rates are `act-line-2` 0%, `cu-line-1` 90%. The spread *within* a stratum is as large as the spread between strata, so risk is a property of the individual panel rather than of its category — a category cannot be used to predict it.

## 3. Cross-engine departure rates (no extra generation)

Each cell is one Bernoulli draw from the engine's cell population.

| engine | draws | departed | rate | 95% CI |
|---|---|---|---|---|
| gen4_turbo | 64 | 4 | **6%** | 2%–15% |
| h3-fal | 97 | 34 | **35%** | 26%–45% |
| gen4.5 | 66 | 13 | **20%** | 12%–31% |
| wan22 | 33 | 1 | **3%** | 1%–15% |
| ltx23 | 33 | 7 | **21%** | 11%–38% |

### Stratum rates per engine (is the ordering consistent?)

| engine | BURST×black | BURST×line | IDLE×black | IDLE×line |
|---|---|---|---|---|
| gen4_turbo | 0% | 33% | 0% | 0% |
| h3-fal | 55% | 7% | 17% | 62% |
| gen4.5 | 0% | 50% | 17% | 33% |
| wan22 | 0% | 33% | 0% | 0% |
| ltx23 | 0% | 0% | 0% | 33% |

The claim that generalises is the *ordering* of strata, not the absolute rates: those are engine-specific and range widely.

