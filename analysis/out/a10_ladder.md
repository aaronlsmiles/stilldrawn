# A10 motion ladder: line stability as a function of realised motion

**Confirmatory (amendment A10).** Realised motion is measured (motion.py, A6's definitions), never assumed from the prompt level. The frozen league and the §8 test are unchanged.

## Cells

Expected cells: analysis/out/a10_cells.json.

| Engine | expected | refused | complete | missing |
|---|---|---|---|---|
| Wan 2.2 | 48 | 0 | 48 | 0 |
| LTX-2.3 | 48 | 0 | 48 | 0 |
| Gen-4.5 | 48 | 0 | 48 | 0 |


Model versions (runs/manifest.jsonl, expected non-refused cells; reported only, no verdict depends on them):

- Wan 2.2: Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M (city96) + Wan2.2_VAE, ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)]; machine: RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12).
- LTX-2.3: LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), ComfyUI 0.31.0 [RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12)]; machine: RTX5090-32GB CUDA driver 595.91.07 (RunPod secure, A10/A12).
- Gen-4.5: gen4.5 (Runway dev API, X-Runway-Version 2024-11-06).

## Manipulation check (read first)

| Engine | STILL | LOW | MID | HIGH | rising steps | passed |
|---|---|---|---|---|---|---|
| Wan 2.2 | 0.00082 | 0.00101 | 0.00161 | 0.02057 | 3 of 3 | yes |
| LTX-2.3 | 0.00228 | 0.00554 | 0.00652 | 0.06105 | 3 of 3 | yes |
| Gen-4.5 | 0.00431 | 0.00291 | 0.01091 | 0.02238 | 2 of 3 | yes |

## A10-H1: rho(realised motion, drift), per engine

One-sided permutation p (B = 10,000); bootstrap 95% CI. Only mean chamfer carries the verdict.

| Engine | Metric | n | rho | p (one-sided) | 95% CI | A10-H1 |
|---|---|---|---|---|---|---|
| Wan 2.2 | mean chamfer vs frame 0 (px) | 48 | 0.56 | 0.0001 | [0.30, 0.73] | supported |
| Wan 2.2 | edge |slope| (abs_slope_norm) | 48 | 0.37 | 0.0038 | [0.07, 0.61] | secondary |
| Wan 2.2 | style drift, terminal | 48 | 0.51 | 0.0002 | [0.25, 0.71] | secondary |
| LTX-2.3 | mean chamfer vs frame 0 (px) | 48 | 0.63 | 0.0001 | [0.43, 0.77] | supported |
| LTX-2.3 | edge |slope| (abs_slope_norm) | 48 | 0.11 | 0.2298 | [-0.20, 0.41] | secondary |
| LTX-2.3 | style drift, terminal | 48 | 0.59 | 0.0001 | [0.37, 0.76] | secondary |
| Gen-4.5 | mean chamfer vs frame 0 (px) | 48 | 0.63 | 0.0001 | [0.41, 0.77] | supported |
| Gen-4.5 | edge |slope| (abs_slope_norm) | 48 | 0.44 | 0.0011 | [0.17, 0.65] | secondary |
| Gen-4.5 | style drift, terminal | 48 | 0.36 | 0.0081 | [0.07, 0.59] | secondary |

### A10-H1 within panel (secondary, no verdict)

Mean chamfer only. Both p are one-sided, from the same B = 10,000 permutations of mean chamfer inside each panel. A pooled rho that these permutations reproduce (a large p), beside a within-panel rho near 0, is an association between panels rather than within them.

| Engine | n | panels | pooled rho | p (within-panel permutation) | within-panel rho | p |
|---|---|---|---|---|---|---|
| Wan 2.2 | 48 | 12 | 0.56 | 0.0001 | 0.73 | 0.0001 |
| LTX-2.3 | 48 | 12 | 0.63 | 0.0001 | 0.85 | 0.0001 |
| Gen-4.5 | 48 | 12 | 0.63 | 0.0002 | 0.47 | 0.0028 |

## A10-H2: the Gen-4.5 / Wan 2.2 gap on motion-matched cells

- Reading: **not supported**
- Common band (realised motion): [0.002767265205168062, 0.004957338316099984]
- Cells in the band: {"Gen-4.5": 9, "Wan 2.2": 9}
- Cells in the band, by panel (secondary): {"Gen-4.5": {"act-black-1": 2, "act-line-2": 0, "act-tone-1": 1, "act-tone-3": 2, "cu-black-2": 0, "cu-black-3": 1, "cu-line-3": 0, "cu-tone-1": 0, "est-black-3": 2, "est-line-1": 1, "est-line-2": 0, "est-tone-3": 0}, "Wan 2.2": {"act-black-1": 0, "act-line-2": 0, "act-tone-1": 1, "act-tone-3": 0, "cu-black-2": 0, "cu-black-3": 3, "cu-line-3": 1, "cu-tone-1": 0, "est-black-3": 0, "est-line-1": 3, "est-line-2": 1, "est-tone-3": 0}}
- Cells with a chamfer value, whole ladder: {"Gen-4.5": 48, "Wan 2.2": 48}
- g_band: 2.358510296639742
- g_whole: 1.6866951946520046
- Wan 2.2 HIGH upper quartile: 0.02931861132383347
- Other engines' STILL medians: {"LTX-2.3": 0.002278118474142892, "Gen-4.5": 0.004313333580891291}
- Engines without STILL cells (Wan 2.2 check): []

A9's masked-region result is a different condition (a region, not a motion band); it is reported beside this one and never pooled with it.

## Further engines (A15, A16): A10-H1 only, under their own amendments

Never part of A10's summary or verdicts: A10-H2 and its kill rules read A10's three engines only.

### A10-H1 (Kling, A15)

- Reading: **not run: scout failed: does not move on request (1 of 3 BURST draws above the floor)**
- Cell list: analysis/out/a15_cells.json
- Scout (A15.5): scout failed: does not move on request (1 of 3 BURST draws above the floor)

### A10-H1 (Midjourney, A16)

- Reading: **incomplete: 48 cells missing**
- Cell list: analysis/out/a16_cells.json
- Cells: expected 48, refused 0, complete 0, missing 48.
  - missing a motion value: ladder-act-black-1_high_mjv, ladder-act-black-1_low_mjv, ladder-act-black-1_mid_mjv, ladder-act-black-1_still_mjv, ladder-act-line-2_high_mjv, ladder-act-line-2_low_mjv, ladder-act-line-2_mid_mjv, ladder-act-line-2_still_mjv, ladder-act-tone-1_high_mjv, ladder-act-tone-1_low_mjv, ladder-act-tone-1_mid_mjv, ladder-act-tone-1_still_mjv, ladder-act-tone-3_high_mjv, ladder-act-tone-3_low_mjv, ladder-act-tone-3_mid_mjv, ladder-act-tone-3_still_mjv, ladder-cu-black-2_high_mjv, ladder-cu-black-2_low_mjv, ladder-cu-black-2_mid_mjv, ladder-cu-black-2_still_mjv, ladder-cu-black-3_high_mjv, ladder-cu-black-3_low_mjv, ladder-cu-black-3_mid_mjv, ladder-cu-black-3_still_mjv, ladder-cu-line-3_high_mjv, ladder-cu-line-3_low_mjv, ladder-cu-line-3_mid_mjv, ladder-cu-line-3_still_mjv, ladder-cu-tone-1_high_mjv, ladder-cu-tone-1_low_mjv, ladder-cu-tone-1_mid_mjv, ladder-cu-tone-1_still_mjv, ladder-est-black-3_high_mjv, ladder-est-black-3_low_mjv, ladder-est-black-3_mid_mjv, ladder-est-black-3_still_mjv, ladder-est-line-1_high_mjv, ladder-est-line-1_low_mjv, ladder-est-line-1_mid_mjv, ladder-est-line-1_still_mjv, ladder-est-line-2_high_mjv, ladder-est-line-2_low_mjv, ladder-est-line-2_mid_mjv, ladder-est-line-2_still_mjv, ladder-est-tone-3_high_mjv, ladder-est-tone-3_low_mjv, ladder-est-tone-3_mid_mjv, ladder-est-tone-3_still_mjv.
- Manipulation check (read first): STILL n/a, LOW n/a, MID n/a, HIGH n/a; 0 of 3 steps rise; failed.

| Metric | n | rho | p (one-sided) | 95% CI | A10-H1 |
|---|---|---|---|---|---|
| mean chamfer vs frame 0 (px) | 0 | n/a | n/a | n/a | incomplete: 48 cells missing |
| edge |slope| (abs_slope_norm) | 0 | n/a | n/a | n/a | secondary |
| style drift, terminal | 0 | n/a | n/a | n/a | secondary |

Within panel (secondary, no verdict): n 0, panels 0, pooled rho n/a (p n/a), within-panel rho n/a (p n/a).
Model versions: n/a (48 cells without a manifest line).

