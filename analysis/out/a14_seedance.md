# A14: A5's Seedance prediction at five fresh draws

**Confirmatory for A5's prediction only (A14.0).** Every other number is reported without a verdict.

Route check (A14.3.3): **match** (docs/A14-ROUTE.md, sha256 437e7e4c2445…).

## The prediction (act-black-3 BURST)

- Reading: **prediction refuted: Seedance's departure rate is lower than H3's**
- Draws: act-black-3_burst_sd2r-h4, act-black-3_burst_sd2r-h5, act-black-3_burst_sd2r-h6, act-black-3_burst_sd2r-h7, act-black-3_burst_sd2r-h8
- Seedance: 0 of 5 departed, Wilson 95% [0.00, 0.43]
- H3 (A4): 8 of 10, Wilson 95% [0.49, 0.94]
- One-sided Fisher exact p (H3's rate exceeding Seedance's): 0.0070
- Rule (a) alone: **prediction refuted: Seedance's departure rate is lower than H3's** (0 of 5)

## Beside the reading: secondary, without a verdict

- A5's scout (fal), on its own: 1 of 3 under the full rule; 1 of 3 under rule (a) alone
- Pooled, the scout's three and Runway's five, full rule: 1 of 8, rate 0.12, Wilson 95% [0.02, 0.47]
- Pooled, the scout's three and Runway's five, rule (a) alone: 1 of 8, rate 0.12, Wilson 95% [0.02, 0.47]

## Per cell (no verdict)

| Cell | Seedance | rate | Wilson 95% | H3 (A4) |
|---|---|---|---|---|
| cu-line-1_idle | 0 of 5 | 0.00 | [0.00, 0.43] | 9 of 10 |
| cu-line-1_burst | 4 of 5 | 0.80 | [0.38, 0.96] | 2 of 10 |
| act-black-3_idle | 0 of 5 | 0.00 | [0.00, 0.43] | 0 of 10 |
| act-black-3_burst | 0 of 5 | 0.00 | [0.00, 0.43] | 8 of 10 |

A4's statistic, full rule: BURST x heavy-black 0 of 5 against IDLE x line-only 0 of 5, one-sided Fisher p 1.0000.

A4's statistic, rule (a) alone: BURST x heavy-black 0 of 5 against IDLE x line-only 0 of 5, one-sided Fisher p 1.0000.

Rule (a) against rule (b): 5 disagreements (act-black-3_burst_sd2-h2, cu-line-1_burst_sd2r-h1, cu-line-1_burst_sd2r-h2, cu-line-1_burst_sd2r-h3, cu-line-1_burst_sd2r-h5).

Model versions (Runway draws): seedance2 (Runway dev API, X-Runway-Version 2024-11-06)

## Per draw

| Draw | route | code | review | chamfer | rule (a) | rule (b) | motion | seed |
|---|---|---|---|---|---|---|---|---|
| act-black-3_burst_sd2-h1 | fal (A5) | s05 | held | 3.47 | False | False | 0.00613 | None |
| act-black-3_burst_sd2-h2 | fal (A5) | s22 | held | 16.94 | True | False | 0.06017 | None |
| act-black-3_burst_sd2-h3 | fal (A5) | s16 | held | 4.88 | False | False | 0.01072 | None |
| cu-line-1_idle_sd2r-h1 | Runway | s18 | held | 4.05 | False | False | 0.01328 | 20260813 |
| cu-line-1_idle_sd2r-h2 | Runway | s19 | held | 7.09 | False | False | 0.01387 | 20260814 |
| cu-line-1_idle_sd2r-h3 | Runway | s07 | held | 6.24 | False | False | 0.01719 | 20260815 |
| cu-line-1_idle_sd2r-h4 | Runway | s08 | held | 5.24 | False | False | 0.01070 | 20260816 |
| cu-line-1_idle_sd2r-h5 | Runway | s23 | held | 5.52 | False | False | 0.00730 | 20260817 |
| cu-line-1_burst_sd2r-h1 | Runway | s11 | held | 10.53 | True | False | 0.02907 | 20260813 |
| cu-line-1_burst_sd2r-h2 | Runway | s01 | held | 14.10 | True | False | 0.03517 | 20260814 |
| cu-line-1_burst_sd2r-h3 | Runway | s12 | held | 10.45 | True | False | 0.04955 | 20260815 |
| cu-line-1_burst_sd2r-h4 | Runway | s03 | held | 7.04 | False | False | 0.02636 | 20260816 |
| cu-line-1_burst_sd2r-h5 | Runway | s17 | held | 10.96 | True | False | 0.05286 | 20260817 |
| act-black-3_idle_sd2r-h1 | Runway | s15 | held | 0.20 | False | False | 0.00076 | 20260813 |
| act-black-3_idle_sd2r-h2 | Runway | s09 | held | 0.26 | False | False | 0.00090 | 20260814 |
| act-black-3_idle_sd2r-h3 | Runway | s04 | held | 0.20 | False | False | 0.00085 | 20260815 |
| act-black-3_idle_sd2r-h4 | Runway | s14 | held | 0.70 | False | False | 0.00706 | 20260816 |
| act-black-3_idle_sd2r-h5 | Runway | s21 | held | 0.34 | False | False | 0.00089 | 20260817 |
| act-black-3_burst_sd2r-h4 | Runway | s10 | held | 2.14 | False | False | 0.00085 | 20260816 |
| act-black-3_burst_sd2r-h5 | Runway | s06 | held | 5.04 | False | False | 0.00093 | 20260817 |
| act-black-3_burst_sd2r-h6 | Runway | s02 | held | 2.40 | False | False | 0.00093 | 20260818 |
| act-black-3_burst_sd2r-h7 | Runway | s20 | held | 5.65 | False | False | 0.01020 | 20260819 |
| act-black-3_burst_sd2r-h8 | Runway | s13 | held | 3.50 | False | False | 0.00118 | 20260820 |
