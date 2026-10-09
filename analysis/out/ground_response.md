# A3 ground-value series — dose–response

One draw per step per engine. **Interpretability rule (added 2026-08-13 after the repeat probe): a 5-point n=1 series is readable only where the engine's per-draw variance is small relative to the dose effect.** Per-cell median |Δ| between runs (repeat_stability.md §2) is the yardstick: gen4_turbo 0.88px chamfer vs a 4.7→15.8px effect (readable); gen4.5 1.54px vs 5.8→12.3px (marginal); h3-fal 2.72px median but 102px max swing (NOT readable — see the triplicate below).

## Accidental triplicate — the same input drawn three times (h3-fal)

`ground-cu-line-1-v100.png` is **pixel-identical** to `cu-line-1.png` (k=1.00 is the identity transform; verified max abs diff 0), so three independent draws of the same (panel, prompt, engine) exist:

| draw | chamfer px | style terminal | edge \|slope\| |
|---|---|---|---|
| main run 1 | 103.13 | 0.315 | 0.206 |
| repeat r2 | 1.45 | 0.197 | 0.034 |
| A3 v100 | 51.73 | 0.166 | 0.094 |

The corpus maximum and a near-perfect clip from identical inputs. This is the strongest single evidence for the hazard framing (R10/R11) — and it is why h3-fal's ground series below cannot be read as a dose–response: its k=1.00 point is a pathological draw, not a ground effect.

## gen4_turbo

| k | chamfer px | edge |slope| | style terminal |
|---|---|---|---|
| 1.00 | 4.68 | 0.001 | 0.043 |
| 0.90 | 2.66 | 0.003 | 0.039 |
| 0.80 | 3.12 | 0.005 | 0.035 |
| 0.65 | 7.76 | 0.000 | 0.062 |
| 0.52 | 15.80 | 0.064 | 0.052 |

## gen4.5

| k | chamfer px | edge |slope| | style terminal |
|---|---|---|---|
| 1.00 | 7.55 | 0.031 | 0.254 |
| 0.90 | 12.30 | 0.061 | 0.137 |
| 0.80 | 9.34 | 0.012 | 0.064 |
| 0.65 | 10.56 | 0.007 | 0.069 |
| 0.52 | 5.82 | 0.005 | 0.087 |

## h3-fal

| k | chamfer px | edge |slope| | style terminal |
|---|---|---|---|
| 1.00 | 51.73 | 0.094 | 0.166 |
| 0.90 | 0.66 | 0.021 | 0.024 |
| 0.80 | 2.43 | 0.051 | 0.321 |
| 0.65 | 0.39 | 0.005 | 0.010 |
| 0.52 | 0.76 | 0.013 | 0.010 |

## wan22

| k | chamfer px | edge |slope| | style terminal |
|---|---|---|---|
| 1.00 | 1.88 | 0.027 | 0.047 |
| 0.90 | 1.33 | 0.046 | 0.026 |
| 0.80 | 1.41 | 0.069 | 0.034 |
| 0.65 | 0.08 | 0.059 | 0.009 |
| 0.52 | 0.09 | 0.061 | 0.006 |

## ltx23

| k | chamfer px | edge |slope| | style terminal |
|---|---|---|---|
| 1.00 | 10.04 | 0.678 | 0.688 |
| 0.90 | 1.51 | 0.496 | 0.171 |
| 0.80 | 13.38 | 0.354 | 0.183 |
| 0.65 | 19.77 | 0.357 | 0.185 |
| 0.52 | 27.07 | 0.306 | 0.137 |
