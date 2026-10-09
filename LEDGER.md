> *Historical record, kept as written. The benchmark's working name was InkBench; it was renamed StillDrawn on 2026-09-30 after a name collision. The creator-IP panel's identifier has been neutralised to `cip-act-tank-1` throughout.*

# Budget ledger — InkBench (append-only)

**CEILING £50.00 · EXTENSION GATE £100.00 (per-item, named research question, Aaron's go)**

FX pin **£1 = $1.28** (re-verify at spend). Interlocks:

1. One row per hosted batch, appended **before** the next batch is submitted.
2. No batch may be submitted if running total + batch estimate exceeds the ceiling
   (or the approved extension total).
3. Aaron confirms any single batch expected to exceed ~$3.
4. Extensions past £50.00 are per-item: each names the research question it buys and
   records Aaron's explicit go in this file before spending.

Local rows cost £0.00 — logged anyway, with wall-clock, so £/result and time/result
stay comparable across engines.

**Authorizations (2026-08-12, Aaron, in-session):** interlock-3 pre-confirmation for
the three hosted run-matrix batches at their A1-approved estimates — Gen-4 Turbo
33 × $0.25 ≈ $8.25 · H3/fal 39 × $0.40 ≈ $15.60 · Gen-4.5 33 × $0.60 ≈ $19.80
(≈ $43.7 ≈ £34.1 total) — plus GPU rental for the local engines ≤ £12 (A2, expected
≈ £8). Standing condition attached: track running spend against these estimates;
**flag any material overrun; pause and escalate to Aaron if far over estimate or if
the ceiling is at risk.** Projected end-state if all estimates hold: ≈ £42.8 of
£50.00.

| date | phase.task | engine/model | gens (new+reroll) | $ | £ | running £ | headroom £ |
|---|---|---|---|---|---|---|---|
| 2026-08-12 | 0.2/1.1 eval gate | runway gemini_2.5_flash still + gen4_turbo 5s clip | 1+0 each | 0.29 | 0.23 | 0.23 | 49.77 |
| 2026-08-12 | 1.1.hosted | runway gemini_2.5_flash 1344:768 | 9+0 | 0.36 | 0.28 | 0.51 | 49.49 |
| 2026-08-12 | 1.1.local | local Illustrious 1344x768 (32m36s wall) | 18+0 | 0.00 | 0.00 | 0.51 | 49.49 |
| 2026-08-12 | 1.1.reroll-hosted (R2 fixes) | runway gemini_2.5_flash 1344:768 | 0+1 | 0.04 | 0.03 | 0.54 | 49.46 |
| 2026-08-12 | 1.1.reroll-local (R2 fixes) | local Illustrious 1344x768 (15m wall) | 0+8 | 0.00 | 0.00 | 0.54 | 49.46 |
| 2026-08-12 | 4.2.batch-1 gen4_turbo | runway gen4_turbo 5s 1280:720/720:1280 (15m wall; 32 ok, 1 refused ×2 BAD_OUTPUT @ 0 credits) | 32+1 | 8.00 | 6.25 | 6.79 | 43.21 |
| 2026-08-12 | 4.2.diag fal billing | minimax/h3 probe jobs during workspace-lock diagnosis — H3 inference outruns cancels, probes billed (fal dashboard $0.80 + $0.08 1s-probe) | ~4 probes | 0.88 | 0.69 | 7.48 | 42.52 |
| 2026-08-12 | 4.2.batch-2 h3-fal | minimax/h3 768P 5s (39 protocol cells + 22 DOUBLE-SUBMITTED cells — two concurrent drivers, agent process error, see runs/RECONCILIATION-2026-08-12-h3.md — + 1 clean resubmit of cu-line-1_idle) | 39+22dup | 24.40 | 19.06 | 26.54 | 23.46 |
| 2026-08-12 | 4.2.batch-3 wan22 (A2 pod) | Wan2.2-TI2V-5B Q5_K_M, 33 cells 1280x704/704x1280 (79 min wall, RTX5090) | 33+0 | 0.00 | 0.00 | 26.54 | 23.46 |
| 2026-08-12 | 4.2.batch-4 ltx23 (A2 pod) | LTX-2.3-22B distilled-1.1 Q4_K_M, 33 cells (26 min wall, RTX5090) | 33+0 | 0.00 | 0.00 | 26.54 | 23.46 |
| 2026-08-12 | 4.2.A2 GPU rental | RunPod RTX5090 community, deploy→terminate (setup + both matrices + idle-wait) — balance delta $9.5583→$7.6212 | — | 1.94 | 1.52 | 28.06 | 21.94 |
| 2026-08-12 | 4.2.batch-5 gen4.5 | runway gen4.5 5s (75 min wall; 32 first-pass + act-tone-3_idle resubmit cleared output-moderation on retry @ 0 credits for the refusal) | 33+1 | 19.80 | 15.47 | 43.53 | 6.47 |

## EXTENSION AUTHORIZATION — 2026-08-13 (repeat-stability probe)

**Named research question** (pre-registered extension candidate, prereg §5):
*"Are the cross-engine rankings stable across repeated generations — and are
the named taxonomy modes deterministic properties of (panel, prompt, engine)
or stochastic draws?"*

**Aaron's go** (recorded from session, 2026-08-13): "I love what has been
done, so I really don't care if we go over budget now. If there is anything
else you think is good to squeeze out do it. But keep me informed at every
£10 additional point." — interpreted conservatively: the £100.00 extension
gate REMAINS the hard cap (past it = dated amendment + fresh go); reporting
cadence every ~£10 of new spend; his blanket confirmation covers interlock 3
for these batches.

**Scope:** one full repeat (`-r2` cell_ids, runs/metrics-r2/) of the 33
standard cells on the three hosted engines, cheapest-first per A2
(gen4_turbo → h3-fal → gen4.5). FLINT excluded (outside cross-engine
comparisons). Local engines deferred (seeded → needs different-seed plumbing
+ pod; separate item if wanted). Estimate: $8.25 + $11.55 + $19.80 = $39.60
≈ £30.94 → projected running total ≈ £74.47 of £100.00.
| 2026-08-13 | EXT.repeat-1 gen4_turbo-r2 | repeat-stability probe batch 1: 33 cells → 32 clips + 1 refusal (cu-tone-3_idle REPRODUCES run-1's deterministic BAD_OUTPUT ×2 @ 0 credits; cu-black-2_idle failed then passed on identical §5 resubmit — stochastic boundary). Incl. $0.25 orphan from a client-side-killed smoke task (balance-reconciled: 3683→2858 credits, exact) | 32+1 | 8.25 | 6.45 | 49.98 | 50.02 vs £100 ext. cap |
| 2026-08-13 | EXT.repeat-2 h3-fal-r2 ATTEMPT | repeat batch blocked: fal storage-token 403 on ALL 33 cells BEFORE upload/submit — account-level block, consistent with the outstanding fal invoice overrun (gate queue since 2026-08-12). ZERO submissions, zero spend. Relaunch after Aaron settles billing | 0 | 0.00 | 0.00 | 49.98 | 50.02 vs £100 ext. cap |

## EXTENSION AUTHORIZATION — 2026-08-13 (ground-value causal series, amendment A3)

Named question + design: PREREGISTRATION amendment A3 (this date). Aaron's go:
in-session menu selection "Ground-value causal series (Recommended)".
Estimate £3.3 hosted now (+£1.4 H3 later, locals ≤£2). £100.00 cap unchanged.
| 2026-08-13 | EXT.repeat-3 gen4.5-r2 | repeat-stability probe batch 2: 33/33 clean, 71 min (run-1's output-moderated act-tone-3_idle passed FIRST TRY — stochastic moderation confirmed from the other direction) | 33+0 | 19.80 | 15.47 | 65.45 | 34.55 vs £100 ext. cap |
| 2026-08-13 | EXT.A3-1 ground gen4_turbo | A3 ground-value series, Turbo: 5/5 IDLE cells | 5+0 | 1.25 | 0.98 | 66.43 | 33.57 vs £100 ext. cap |
| 2026-08-13 | EXT.A3-2 ground gen4.5 | A3 ground-value series, Gen-4.5: 5/5 IDLE cells | 5+0 | 3.00 | 2.34 | 68.77 | 31.23 vs £100 ext. cap |
| 2026-08-13 | EXT.repeat-4 h3-fal-r2 | repeat-stability probe batch 3 (post-topup relaunch; pre-flight account check passed per R10 rule): 33/33 clean, 46 min | 33+0 | 13.20 | 10.31 | 79.44 | (cap since retired) |
| 2026-08-13 | EXT.A3-3 ground h3-fal | A3 ground-value series, MiniMax H3: 5/5 IDLE cells | 5+0 | 2.00 | 1.56 | 79.35 | 20.65 vs £100 ext. cap |

## EXTENSION AUTHORIZATION — 2026-08-14 (hazard-rate estimation, amendment A4)

Named question, hypothesis and outcome-coding rule: PREREGISTRATION A4.
Aaron's go recorded 2026-08-14 ("I want to do the hazard-rate study").
4-cell core estimate £8.75 → projected £88.10 of the £100 cap.
**BLOCKED ON PROVIDER CREDIT** — not on authorisation. Balances at
authorisation time: Runway 478 credits (19 Turbo clips); fal balance low after
the R11 batches. Requires ≈$12 fal top-up before the batch can submit.
Pre-flight account check (R10 rule) applies before launch.

---

## GOVERNANCE CHANGE — 2026-08-14: ceiling lifted, variance rule replaces it

**Aaron's instruction, recorded verbatim in effect:** "Ignore the £100 budget
ceiling now, that was just at the start when I didn't know how much things
were going to cost… Just keep me informed regularly of where costs sit and
anything that behaves excessively differently to planned pause and flag to me
so I don't spend an excessive amount without knowing."

The £50/£100 ceilings are **retired** as of this entry. They are preserved
above as the historical rule under which every batch through R11 was run —
the pre-registration's budget-disclosure claims refer to that period and stay
accurate. The paper reports the study as run under a disclosed ceiling; that
statement remains true of the frozen matrix and amendments A1–A4.

**Replacement interlocks (in force from 2026-08-14):**

1. **Every batch still gets its ledger row before the next submits.** Unchanged
   — this is what makes the running total trustworthy.
2. **Running total reported at every batch completion**, and a checkpoint
   message at each further ~£10 of cumulative spend.
3. **PAUSE-AND-FLAG on cost variance.** Stop and ask before continuing if any
   of these is true:
   - a batch's actual cost exceeds its estimate by **>25% or >£5**;
   - a **per-unit price differs from the rate card below** (this is exactly
     what the H3 $0.35→$0.40 error would have caught);
   - an **unattributable charge** appears (e.g. the R6 double-submission, the
     killed-task orphan);
   - a rented resource **overruns its wall-clock estimate by >2×**;
   - any single new item is estimated **>£40**.
4. **Provider-balance pre-flight before every hosted batch** (R10 rule) —
   with the balance recorded, so unexplained drops are visible.

### Verified rate card (per 5 s clip at protocol resolution unless noted)

| Item | Verified rate | Source |
|---|---|---|
| Runway Gen-4 Turbo | **$0.25** (25 credits) | manifest, all batches |
| Runway Gen-4.5 | **$0.60** (60 credits) | manifest, all batches |
| MiniMax H3 (fal) | **$0.40** | manifest — *corrected from a $0.35 estimate 2026-08-14* |
| Wan 2.2 / LTX-2.3 (local) | £0 + rental | open weights |
| RunPod secure ~4090 | ≈$0.69/hr; ≈$0.06 per failed short attempt | 2026-08-14 job |
| Seedance 2.0 std / fast / mini | $1.512 / $1.210 / $0.464 | fal model page, 2026-08-14 (unused — A5 draft) |

FX pin unchanged at £1 = $1.28.

### CORRECTION — 2026-08-14 (rate error, caught by Aaron's balance challenge)

Two rows were costed at an assumed $0.35/clip for H3; the verified rate is
**$0.40** (rate card above). Corrected: `EXT.repeat-4` $11.55 → **$13.20**
(£9.02 → £10.31). The A4 authorization estimate ($24.85) was likewise low; the
true 71-draw cost is **$28.40 ≈ £22.19**.

**Reconciled fal position** (all H3 spend ever: 136 clips, $54.40):
$50.00 topped up since the lockout − $13.20 repeat − $2.00 ground − $28.40 A4
= **≈$6.40 remaining once A4 finishes**.

This invalidates a claim made in `docs/A5-DRAFT-seedance.md` that Option 1
(Seedance FLINT, $9.07) "runs without a further fal top-up" — it is short by
**≈$2.67**. Corrected in that document. This is exactly the failure mode the
new pause-and-flag rule exists to catch, and it was caught by Aaron rather
than by me, which is the wrong way round; the rate card is the fix.
| 2026-08-14 | EXT.A4 hazard h3-fal | hazard-rate estimation (amendment A4): 8 cells x 10 draws, 71 new | 71+0 | 28.40 | 22.19 | 101.54 | ceilings retired |
| 2026-08-14 | EXT.A3-4 wan pod attempts | RunPod attempts 1-6 for the Wan ground cells; 5 failed on harness bugs (all fixed), all pods terminated cleanly | 0 clips | 0.36 | 0.28 | 101.82 | — |

## EXTENSION AUTHORIZATION — 2026-08-14 (Seedance scout, amendment A5 / Option 1b)

Aaron's go recorded 2026-08-14. 6 clips × $1.512 = **$9.07 ≈ £7.09**.

**Balance-estimate failure, logged:** my manifest-derived estimate said $6.40
remained; the dashboard showed **$1.60** — I was $4.80 optimistic. The gap is
almost certainly a negative starting balance at the lockout (fal permits
in-flight jobs to overdraw before locking), which a manifest cannot see.
**New rule: fal balance is authoritative from Aaron's dashboard only.**
Manifest-derived figures are indicative and must be labelled as such; ask for
the dashboard number before any batch that depends on headroom.
After Aaron's $10 top-up: ≈$11.60 available, scout $9.07, ≈$2.53 left after.
| 2026-08-14 | EXT.A5-scout seedance | A5 Option 1b scout: 3 FLINT pairs + 3 act-black-3 BURST draws | 6+0 | 9.07 | 7.09 | 108.91 | — |
| 2026-08-14 | EXT.A5-flint seedance | A5 addendum: 3 remaining frozen FLINT pairs — set complete at 6/6 on a second engine | 3+0 | 4.54 | 3.55 | 112.46 | — |
| 2026-08-14 | EXT.A3-4 ground wan22 (pod) | A3 ground series completed on the 5th engine: 5/5 cells, RTX A6000, 30 min. Includes 8 prior failed attempts (harness bugs + one 90-min provisioning stall, $1.39 — flagged) | 5+0 | 2.07 | 1.62 | 114.08 | — |
| 2026-10-01 | CORRECTION running total | Audit before release: the EXT.repeat-4 rate correction (+£1.29, $11.55 → $13.20) was applied to that row's £ amount but never carried into the running totals after it. The £ column sums to **£115.37**; EXT.repeat-4's own running total reads 79.44 where 79.08 is correct, and every running total after it is £1.29 low. No spend is added by this row. | — | 0.00 | 0.00 | 115.37 | correction |
| 2026-10-01 | NOTE A4 authorisation | Record correction: A4's 8-cell extension had an explicit go from Aaron on 2026-08-14 02:29 (a $30 fal top-up "so you can run the core study plus the pre-declared 8-cell extension too"); the 4-cell £8.75 figure in the authorisation block above covers only the core. See the addendum to A4 in docs/PREREGISTRATION.md. No spend added. | — | 0.00 | 0.00 | 115.37 | note |
