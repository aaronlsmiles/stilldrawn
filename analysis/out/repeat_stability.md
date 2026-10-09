# Repeat-stability probe (extension, 2026-08-13)

98 repeat cells scored across ['gen4.5', 'gen4_turbo', 'h3-fal'].

## 1. Engine-league stability (medians, repeated cells only)

| headline | ordering r1 | ordering r2 | Spearman |
|---|---|---|---|
| line_chamfer_mean_px | gen4_turbo<gen4.5<h3-fal | gen4_turbo<gen4.5<h3-fal | +1.00 |
| tone_variance | gen4_turbo<gen4.5<h3-fal | gen4_turbo<gen4.5<h3-fal | +1.00 |
| edge_abs_slope | gen4_turbo<h3-fal<gen4.5 | gen4_turbo<h3-fal<gen4.5 | +1.00 |
| style_terminal | gen4_turbo<h3-fal<gen4.5 | gen4_turbo<h3-fal<gen4.5 | +1.00 |
| closure_abs_terminal | gen4_turbo<gen4.5<h3-fal | gen4_turbo<gen4.5<h3-fal | +1.00 |

## 2. Per-cell repeatability

| engine | headline | n | Spearman(r1,r2) | median |Δ| | max |Δ| |
|---|---|---|---|---|---|
| gen4.5 | line_chamfer_mean_px | 33 | +0.63 | 1.54 | 36.9 |
| gen4.5 | tone_variance | 29 | +0.60 | 2.77e-05 | 0.00236 |
| gen4.5 | edge_abs_slope | 33 | +0.43 | 0.0918 | 2.48 |
| gen4.5 | style_terminal | 33 | +0.73 | 0.0624 | 0.516 |
| gen4.5 | closure_abs_terminal | 33 | +0.51 | 0.00984 | 0.0742 |
| gen4_turbo | line_chamfer_mean_px | 32 | +0.78 | 0.875 | 50.9 |
| gen4_turbo | tone_variance | 28 | +0.73 | 1.65e-06 | 0.000135 |
| gen4_turbo | edge_abs_slope | 32 | +0.31 | 0.0185 | 2 |
| gen4_turbo | style_terminal | 32 | +0.56 | 0.0236 | 0.496 |
| gen4_turbo | closure_abs_terminal | 32 | +0.49 | 0.00597 | 0.0395 |
| h3-fal | line_chamfer_mean_px | 33 | +0.55 | 2.72 | 102 |
| h3-fal | tone_variance | 29 | +0.74 | 7.09e-05 | 0.0144 |
| h3-fal | edge_abs_slope | 33 | +0.54 | 0.114 | 5.29 |
| h3-fal | style_terminal | 33 | +0.38 | 0.0965 | 0.854 |
| h3-fal | closure_abs_terminal | 33 | +0.08 | 0.0395 | 0.239 |

## 3. Taxonomy-exemplar reproducibility

| cell | mode | firing metric | r1 | r2 | regime |
|---|---|---|---|---|---|
| cu-line-2_burst_h3 | A1 enrichment | tone_variance | 0.00026 | 0.000292 | SAME |
| est-black-3_burst_gen4t | A2 transposition | edge_abs_slope | 2.45 | 0.449 | DIFFERENT — review strips |
| est-black-2_idle_h3 | A3 partial collapse | style_terminal | 0.507 | 0.0484 | DIFFERENT — review strips |
| est-tone-1_burst_gen45 | B1 insertion (train) | style_terminal | 0.578 | 0.0622 | DIFFERENT — review strips |
| cu-line-1_idle_h3 | B2 pseudo-text | line_chamfer_mean_px | 103 | 1.45 | DIFFERENT — review strips |
| cu-black-3_burst_h3 | B2 pseudo-text | line_chamfer_mean_px | 36.1 | 29.7 | SAME |
| est-tone-2_campush_h3 | B3 evacuation | closure_abs_terminal | 0.114 | 0.0316 | DIFFERENT — review strips |
| act-line-3_campush_gen45 | B3 evacuation | closure_abs_terminal | 0.0682 | 0.0542 | SAME |
| cu-line-2_burst_gen4t | C1 framing escape | line_chamfer_mean_px | 65.1 | 14.2 | DIFFERENT — review strips |
| act-tone-1_burst_gen45 | C1/B3 whiteout | style_terminal | 0.876 | 0.413 | SAME |

Regime SAME = repeat lands within 3x on the mode's firing metric; DIFFERENT cells get frame-strip review before any reproducibility claim is made either way. Scalar agreement is necessary, not sufficient — the strips decide.
