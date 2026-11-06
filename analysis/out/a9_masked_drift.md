# A9 Test 2: masked drift

Post-hoc (A9), exploratory. Rows are in frozen-league order; there is no rank column. Masked
medians appear only beside whole-frame medians on the same cells.

**Verdict (m = 32, both mask sets): killed.**

- aaron's masks: Post-hoc (A9): on 104 cells, Gen-4.5/Wan falls from 3.8× to 3.3× outside the region the prompt allows to move (s = 0.11, 95% CI -0.41 to 0.33). The frozen league is unchanged; this qualifies how its gap is read.
- agent's masks: Post-hoc (A9): on 104 cells, Gen-4.5/Wan rises from 3.8× to 3.9× outside the region the prompt allows to move (s = -0.01, 95% CI -0.53 to 0.22). The frozen league is unchanged; this qualifies how its gap is read.

Eligible rows: 21 of 22. Bootstrap: 10000 panel resamples, seed 20261030.

## Split: all (the registered verdict's cells)

### aaron masks, m = 16 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 21 | 0.841 | 0.842 |
| Gen-4 Turbo | 20 | 1.453 | 1.311 |
| LTX-2.3 | 21 | 2.127 | 2.182 |
| Gen-4.5 | 21 | 3.237 | 2.968 |
| MiniMax H3 | 21 | 5.453 | 3.155 |

g_whole 1.944, g_masked 1.817, s 0.065 (95% CI -0.433 to 0.359), delta g 0.127 (95% CI -0.812 to 0.824), Kendall tau_b 1.000; replicates with g_whole <= 0: 0.
Excluded (frame 0 under 500 line px in R): none.

### aaron masks, m = 32 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 21 | 0.841 | 0.842 |
| Gen-4 Turbo | 20 | 1.453 | 1.231 |
| LTX-2.3 | 21 | 2.127 | 2.088 |
| Gen-4.5 | 21 | 3.237 | 2.785 |
| MiniMax H3 | 21 | 5.453 | 3.107 |

g_whole 1.944, g_masked 1.725, s 0.113 (95% CI -0.413 to 0.333), delta g 0.219 (95% CI -0.786 to 0.820), Kendall tau_b 1.000; replicates with g_whole <= 0: 0.
Excluded (frame 0 under 500 line px in R): none.

### aaron masks, m = 64 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 21 | 0.841 | 0.767 |
| Gen-4 Turbo | 20 | 1.453 | 1.028 |
| LTX-2.3 | 21 | 2.127 | 2.141 |
| Gen-4.5 | 21 | 3.237 | 2.761 |
| MiniMax H3 | 21 | 5.453 | 3.143 |

g_whole 1.944, g_masked 1.848, s 0.050 (95% CI -0.403 to 0.350), delta g 0.096 (95% CI -0.750 to 0.788), Kendall tau_b 1.000; replicates with g_whole <= 0: 0.
Excluded (frame 0 under 500 line px in R): none.

### agent masks, m = 16 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 21 | 0.841 | 0.716 |
| Gen-4 Turbo | 20 | 1.453 | 1.419 |
| LTX-2.3 | 21 | 2.127 | 2.051 |
| Gen-4.5 | 21 | 3.237 | 2.785 |
| MiniMax H3 | 21 | 5.453 | 5.676 |

g_whole 1.944, g_masked 1.960, s -0.008 (95% CI -0.461 to 0.224), delta g -0.016 (95% CI -0.766 to 0.517), Kendall tau_b 1.000; replicates with g_whole <= 0: 0.
Excluded (frame 0 under 500 line px in R): none.

### agent masks, m = 32 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 21 | 0.841 | 0.715 |
| Gen-4 Turbo | 20 | 1.453 | 1.416 |
| LTX-2.3 | 21 | 2.127 | 2.040 |
| Gen-4.5 | 21 | 3.237 | 2.785 |
| MiniMax H3 | 21 | 5.453 | 5.676 |

g_whole 1.944, g_masked 1.963, s -0.009 (95% CI -0.526 to 0.223), delta g -0.018 (95% CI -0.897 to 0.507), Kendall tau_b 1.000; replicates with g_whole <= 0: 0.
Excluded (frame 0 under 500 line px in R): none.

### agent masks, m = 64 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 21 | 0.841 | 0.692 |
| Gen-4 Turbo | 20 | 1.453 | 1.423 |
| LTX-2.3 | 21 | 2.127 | 2.075 |
| Gen-4.5 | 21 | 3.237 | 2.825 |
| MiniMax H3 | 21 | 5.453 | 5.676 |

g_whole 1.944, g_masked 2.030, s -0.044 (95% CI -0.664 to 0.241), delta g -0.086 (95% CI -1.196 to 0.511), Kendall tau_b 1.000; replicates with g_whole <= 0: 0.
Excluded (frame 0 under 500 line px in R): none.

## Split: idle (no verdict)

### aaron masks, m = 16 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 11 | 0.776 | 0.842 |
| Gen-4 Turbo | 10 | 1.453 | 1.454 |
| LTX-2.3 | 11 | 2.023 | 1.955 |
| Gen-4.5 | 11 | 2.875 | 3.081 |
| MiniMax H3 | 11 | 2.524 | 2.917 |

g_whole 1.889, g_masked 1.871, s 0.010 (95% CI -0.055 to 0.141), delta g 0.018 (95% CI -0.100 to 0.282), Kendall tau_b 1.000; replicates with g_whole <= 0: 3.
Excluded (frame 0 under 500 line px in R): none.

### aaron masks, m = 32 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 11 | 0.776 | 0.842 |
| Gen-4 Turbo | 10 | 1.453 | 1.454 |
| LTX-2.3 | 11 | 2.023 | 1.837 |
| Gen-4.5 | 11 | 2.875 | 2.759 |
| MiniMax H3 | 11 | 2.524 | 3.005 |

g_whole 1.889, g_masked 1.711, s 0.094 (95% CI -0.025 to 0.199), delta g 0.178 (95% CI -0.047 to 0.430), Kendall tau_b 0.800; replicates with g_whole <= 0: 3.
Excluded (frame 0 under 500 line px in R): none.

### aaron masks, m = 64 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 11 | 0.776 | 0.840 |
| Gen-4 Turbo | 10 | 1.453 | 1.457 |
| LTX-2.3 | 11 | 2.023 | 1.828 |
| Gen-4.5 | 11 | 2.875 | 2.761 |
| MiniMax H3 | 11 | 2.524 | 3.143 |

g_whole 1.889, g_masked 1.717, s 0.091 (95% CI -0.016 to 0.356), delta g 0.172 (95% CI -0.031 to 0.720), Kendall tau_b 0.800; replicates with g_whole <= 0: 3.
Excluded (frame 0 under 500 line px in R): none.

### agent masks, m = 16 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 11 | 0.776 | 0.716 |
| Gen-4 Turbo | 10 | 1.453 | 1.419 |
| LTX-2.3 | 11 | 2.023 | 1.828 |
| Gen-4.5 | 11 | 2.875 | 2.670 |
| MiniMax H3 | 11 | 2.524 | 1.900 |

g_whole 1.889, g_masked 1.899, s -0.005 (95% CI -0.179 to 0.289), delta g -0.010 (95% CI -0.260 to 0.564), Kendall tau_b 1.000; replicates with g_whole <= 0: 3.
Excluded (frame 0 under 500 line px in R): none.

### agent masks, m = 32 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 11 | 0.776 | 0.715 |
| Gen-4 Turbo | 10 | 1.453 | 1.416 |
| LTX-2.3 | 11 | 2.023 | 1.828 |
| Gen-4.5 | 11 | 2.875 | 2.701 |
| MiniMax H3 | 11 | 2.524 | 1.979 |

g_whole 1.889, g_masked 1.918, s -0.016 (95% CI -0.181 to 0.297), delta g -0.029 (95% CI -0.267 to 0.580), Kendall tau_b 1.000; replicates with g_whole <= 0: 3.
Excluded (frame 0 under 500 line px in R): none.

### agent masks, m = 64 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 11 | 0.776 | 0.692 |
| Gen-4 Turbo | 10 | 1.453 | 1.423 |
| LTX-2.3 | 11 | 2.023 | 1.828 |
| Gen-4.5 | 11 | 2.875 | 2.771 |
| MiniMax H3 | 11 | 2.524 | 2.247 |

g_whole 1.889, g_masked 2.002, s -0.060 (95% CI -0.225 to 0.389), delta g -0.113 (95% CI -0.354 to 0.714), Kendall tau_b 1.000; replicates with g_whole <= 0: 3.
Excluded (frame 0 under 500 line px in R): none.

## Split: burst (no verdict)

### aaron masks, m = 16 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 10 | 1.135 | 0.864 |
| Gen-4 Turbo | 10 | 1.627 | 1.069 |
| LTX-2.3 | 10 | 4.039 | 3.330 |
| Gen-4.5 | 10 | 4.873 | 2.877 |
| MiniMax H3 | 10 | 5.964 | 4.131 |

g_whole 2.102, g_masked 1.736, s 0.174 (95% CI -0.651 to 0.635), delta g 0.366 (95% CI -1.098 to 1.450), Kendall tau_b 0.800; replicates with g_whole <= 0: 0.
Excluded (frame 0 under 500 line px in R): none.

### aaron masks, m = 32 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 10 | 1.135 | 0.767 |
| Gen-4 Turbo | 10 | 1.627 | 0.986 |
| LTX-2.3 | 10 | 4.039 | 3.349 |
| Gen-4.5 | 10 | 4.873 | 2.806 |
| MiniMax H3 | 10 | 5.964 | 4.029 |

g_whole 2.102, g_masked 1.871, s 0.110 (95% CI -0.703 to 0.598), delta g 0.231 (95% CI -1.110 to 1.286), Kendall tau_b 0.800; replicates with g_whole <= 0: 0.
Excluded (frame 0 under 500 line px in R): none.

### aaron masks, m = 64 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 10 | 1.135 | 0.611 |
| Gen-4 Turbo | 10 | 1.627 | 0.870 |
| LTX-2.3 | 10 | 4.039 | 3.581 |
| Gen-4.5 | 10 | 4.873 | 2.611 |
| MiniMax H3 | 10 | 5.964 | 4.035 |

g_whole 2.102, g_masked 2.097, s 0.002 (95% CI -0.919 to 0.512), delta g 0.005 (95% CI -1.266 to 1.034), Kendall tau_b 0.800; replicates with g_whole <= 0: 0.
Excluded (frame 0 under 500 line px in R): none.

### agent masks, m = 16 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 10 | 1.135 | 0.678 |
| Gen-4 Turbo | 10 | 1.627 | 1.260 |
| LTX-2.3 | 10 | 4.039 | 5.053 |
| Gen-4.5 | 10 | 4.873 | 4.072 |
| MiniMax H3 | 10 | 5.964 | 6.132 |

g_whole 2.102, g_masked 2.585, s -0.230 (95% CI -1.227 to 0.129), delta g -0.484 (95% CI -1.271 to 0.315), Kendall tau_b 0.800; replicates with g_whole <= 0: 0.
Excluded (frame 0 under 500 line px in R): none.

### agent masks, m = 32 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 10 | 1.135 | 0.638 |
| Gen-4 Turbo | 10 | 1.627 | 1.240 |
| LTX-2.3 | 10 | 4.039 | 5.108 |
| Gen-4.5 | 10 | 4.873 | 4.066 |
| MiniMax H3 | 10 | 5.964 | 6.215 |

g_whole 2.102, g_masked 2.672, s -0.271 (95% CI -1.454 to 0.124), delta g -0.570 (95% CI -1.401 to 0.257), Kendall tau_b 0.800; replicates with g_whole <= 0: 0.
Excluded (frame 0 under 500 line px in R): none.

### agent masks, m = 64 px

| engine | clips | whole-frame median (px) | masked median (px) |
|---|---|---|---|
| Wan 2.2 | 10 | 1.135 | 0.571 |
| Gen-4 Turbo | 10 | 1.627 | 1.209 |
| LTX-2.3 | 10 | 4.039 | 5.364 |
| Gen-4.5 | 10 | 4.873 | 4.036 |
| MiniMax H3 | 10 | 5.964 | 5.914 |

g_whole 2.102, g_masked 2.822, s -0.342 (95% CI -1.608 to 0.182), delta g -0.720 (95% CI -1.629 to 0.359), Kendall tau_b 0.800; replicates with g_whole <= 0: 0.
Excluded (frame 0 under 500 line px in R): none.
