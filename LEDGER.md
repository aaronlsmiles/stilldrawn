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
| 2026-11-03 | NOTE A9 registered | Amendment A9 (exploratory follow-up; see docs/PREREGISTRATION.md): no generation and no paid calls; existing clips are re-analysed and rated. No spend. | — | 0.00 | 0.00 | 115.37 | note |
| 2026-11-10 | NOTE Zenodo v1.1.0 | Dataset version 1.1.0 published (doi:10.5281/zenodo.24107518): adds amendment A9, its instrument, ratings and results; the six clip archives are carried over from 1.0.0 unchanged. No spend. | — | 0.00 | 0.00 | 115.37 | note |

## EXTENSION AUTHORIZATION — 2026-11-10 (the motion ladder and the grey-ground series, amendments A10 and A12)

Named questions, hypotheses and kill rules: PREREGISTRATION A10 (line stability as a function of
motion) and A12 (the grey-ground series with a noise floor), registered 2026-11-10 by the public
commit tagged `a10-registered`.
Aaron's go recorded 2026-11-10, with the registration ("This go covers the Runway batches for A10,
A12, A14 and A15 within their envelopes").
Envelope: generation about £27. Gen-4.5 ladder 48 × $0.60 = $28.80; Gen-4 Turbo 10 × $0.25 =
$2.50; one rented-GPU session for the local ladders and ground draws, about $3.20; $34.50 in all.
A re-run after a lost machine (A12.3.1) adds about an hour of pod time, under £2.
Every paid batch gets its row before the next one starts (rule 1); Aaron is told before the pod
is deployed, before each Gen-4.5 batch (a batch of 21 is $12.60, about £9.84), at each further
£10 of spend, and before any single item over £40. The FX pin is re-read at spend.

## EXTENSION AUTHORIZATION — 2026-11-10 (the human check at power and adherence at power, amendments A11 and A13; Prolific)

Named questions, hypotheses and kill rules: PREREGISTRATION A11 and A13, registered 2026-11-10
(`a10-registered`). Both are rater studies on Prolific, paid in pounds, at the account's fee of
three sevenths of the rewards plus 20% VAT on the fee (read from the account on 2026-11-10).
A11: twelve raters at £4.50, about £81.77 (the two pilot raters £13.63, the ten after them
£68.14); one top-up of up to four, at most £27.26.
A13: twelve raters at £6.00, about £109.03 (pilot £18.17, ten £90.86); £122.66 if the sitting
runs to 45 minutes and the reward rises to £6.75; one top-up of up to four, £36.34 to £40.89.
The budget for A13's twelve is £110 to £125; a top-up is outside it.
Aaron's go for the spend in total was recorded 2026-11-10 (base about £265 and worst case about
£355 across A10 to A16). Each Prolific batch is published and funded by Aaron himself, on his go
at the time; its row is written from Prolific's cost screen before it is published.

## EXTENSION AUTHORIZATION — 2026-11-10 (Seedance, Kling and Midjourney video: amendments A14, A15 and A16)

Named questions and decision rules: PREREGISTRATION A14 (A5's Seedance prediction at five fresh
draws), A15 (a Kling scout, then an A10 arm only if the scout passes) and A16 (the same for
Midjourney video, run by hand), registered 2026-11-10 (`a10-registered`).
Aaron's go recorded 2026-11-10, with the registration (the same words as the A10 and A12 block
above; A16 costs nothing beyond the Midjourney Standard plan already held).
Envelopes: A14, 20 clips × 5 s × 30 credits = $30.00, about £23.50. A15, the scout 6 clips ×
5 s × 12.56 credits ≈ $3.77, about £3; the arm 48 cells ≈ $30.14, about £24, at Runway's
promotional rate until 2026-11-30 UTC (15.7 credits a second at list: about £3.70 and £29). A16,
£0.00 beyond the plan; its jobs are logged in `runs/manifest.jsonl` and take £0.00 rows.
For these paid batches the row is written before the batch is submitted, with the day's credit
rate, the clip count and the estimate, and reconciled with the Runway dashboard once the batch
is done: a declared departure from rule 1, which appends a row after the charge. A14's batch
does not run if Runway's credit rate on the day differs from 30 credits a second at 720p. Each
scout runs before its arm, and an arm runs only if its scout's registered rule passes. The first
draw or cell of each run is watched and reported to Aaron before the rest.

| 2026-11-10 | EXT.A14 seedance2 (Runway) | A14: 20 draws (cu-line-1 IDLE and BURST and act-black-3 IDLE, five each; act-black-3 BURST -h4 to -h8), 5 s at 1280:720; Runway's rate read on the day, 30 credits a second at 720p, as A14.8. Row written before submission (the estimate) and reconciled with the dashboard after. FX re-pinned at spend: £1 = $1.3428 (2026-11-10) | 20+0 | 30.00 | 22.34 | 137.71 | estimate, before submission |
| 2026-11-10 | NOTE A14 first draw | Watched first cell `cu-line-1_idle_sd2r-h1` (part of the EXT.A14 row above; $1.50 of its $30.00): frame size 1280x720; audio not sent, 0 audio streams delivered, nothing stripped; first frame matches cu-line-1: yes; model reference: cannot fire (the task record has no model or version field), so the route verdict (match) is the only model check. The rest submitted after these checks | — | 0.00 | 0.00 | 137.71 | note |
| 2026-11-10 | NOTE A14 reconciled | EXT.A14 batch done: 20 draws delivered, 0 refused, 20 × 150 credits = 3,000 credits = $30.00, as estimated. Runway's balance read through the API: 10,109 credits before the batch, 7,109 after. No audio stream delivered on any draw; every clip 1280x720; one model version string | 20+0 | 0.00 | 0.00 | 137.71 | reconciled |
| 2026-11-11 | EXT.A15 kling_4 scout (Runway) | A15 scout: 6 clips (three FLINT pairs, first and last frame; three BURST draws of act-black-3), 5 s at auto_720p; route check: offered (`docs/A15-ROUTE.md`). Runway's rate read on the day, 12.56 credits a second at 720p under the promotion to 2026-11-30 UTC (15.7 at list), as A15.9. Runway rounds each charge up to a whole credit, 64 credits for a 5 s clip, so the estimate is 6 × 64 = 384 credits (A15.9's unrounded figure is 377). Row written before submission (the estimate) and reconciled with the dashboard after. Runway's balance read through the API before the batch: 4,867 credits (the account is shared with other work, so it is lower than the 7,109 read after A14). FX read at spend: £1 = $1.3428 (2026-11-11, unchanged from 2026-11-10) | 6+0 | 3.84 | 2.86 | 140.57 | estimate, before submission |
| 2026-11-11 | NOTE A15 first FLINT cell | Watched first cell `flint-cu-line-2--cu-line-1_kling4` (part of the EXT.A15 row above; 64 of its 384 expected credits), the first two-image request: frame size 1260x720 (shorter side 720; the 1344x768 panel's framing kept); audio: 1 audio stream delivered, stripped with the video packets unchanged, the delivered file kept privately; first frame matches cu-line-2: yes (the last frame shows cu-line-1). The other two FLINT cells submitted after these checks | — | 0.00 | 0.00 | 140.57 | note |
| 2026-11-11 | NOTE A15 first BURST cell | The other two FLINT cells delivered, none refused. Watched first BURST cell `act-black-3_burst_kling4-h1` (part of the EXT.A15 row above), the first single-image request: frame size 1260x720; audio: 1 audio stream delivered, stripped with the video packets unchanged, the delivered file kept privately; first frame matches act-black-3: yes. The last two BURST draws submitted after these checks | — | 0.00 | 0.00 | 140.57 | note |
| 2026-11-11 | NOTE A15 reconciled | EXT.A15 batch done: 6 clips delivered, 0 refused, 6 × 64 credits = 384 credits = $3.84, as estimated. Runway's balance read through the API: 4,867 credits before the batch, 4,483 after. Every clip 1260x720 with one audio stream delivered and stripped; one model version string. The scout's rule read once: "scout failed: does not move on request (1 of 3 BURST draws above the floor)" (FINDINGS R17), so the arm does not run and nothing more is spent on Kling | 6+0 | 0.00 | 0.00 | 140.57 | reconciled |
| 2026-11-11 | NOTE A15 rounding | A correction to the wording of the EXT.A15 row above, which said Runway rounds each charge up to a whole credit. Under the promotion Runway rounds the list-price charge up, takes 20% off and rounds up again (5 s at 15.7 credits a second is 78.5, so 79; less 20% is 63.2, so 64). The figures stand: 64 credits a clip, 384 for the six. The balance was read through Runway's API, which is the reconciliation the row calls the dashboard's | — | 0.00 | 0.00 | 140.57 | note |
| 2026-11-11 | EXT.A10 ladder gen4.5, batch 1 (Runway) | runway gen4.5 5 s 1280:720, seed 20260812 sent; the first 21 new cells of A10's 48 (`ladder.py run --engine gen4.5 --limit 21`). Runway's rate read on the day: 12 credits a second, 60 credits a clip, so 21 × 60 = 1,260 credits. Row written before submission (the estimate) and reconciled with Runway's balance after. Balance read through the API before the batch: 4,483 credits (unchanged since the A15 scout). It runs before the rented-GPU session because no community RTX 5090 with a public address was free at 08:50 UTC; the hosted cells do not depend on the pod (A10.6.3). FX read at spend: £1 = $1.3374 (2026-11-11) | 21+0 | 12.60 | 9.42 | 149.99 | estimate, before submission |
| 2026-11-11 | NOTE A10 gen4.5 batch 1 reconciled | Batch done: 21 new cells delivered, 0 refused, 0 resubmissions, 21 × 60 credits = 1,260 credits = $12.60, as estimated. Runway's balance read through the API: 4,483 credits before, 3,223 after. Every clip 1280x720, 121 frames, no audio stream; seed 20260812 in every line. Spend since the £115.37 baseline: £34.62 | — | 0.00 | 0.00 | 149.99 | — |
| 2026-11-11 | EXT.A10 ladder gen4.5, batch 2 (Runway) | runway gen4.5 5 s 1280:720, seed 20260812 sent; the next 21 new cells (`ladder.py run --engine gen4.5 --limit 21`), 21 × 60 = 1,260 credits at the day's rate (12 credits a second). Row written before submission (the estimate) and reconciled after. Balance before the batch: 3,223 credits. FX read at spend: £1 = $1.3374 (2026-11-11) | 21+0 | 12.60 | 9.42 | 159.41 | estimate, before submission |
| 2026-11-11 | NOTE A10 gen4.5 batch 2 reconciled | Batch done: 21 new cells delivered, 0 refused, 0 resubmissions, 1,260 credits = $12.60, as estimated. Runway's balance: 3,223 credits before, 1,963 after. Every clip 1280x720, 121 frames, no audio stream; seed 20260812 in every line. Spend since the £115.37 baseline: £44.04 | — | 0.00 | 0.00 | 159.41 | — |
| 2026-11-11 | EXT.A10 ladder gen4.5, batch 3 (Runway) | runway gen4.5 5 s 1280:720, seed 20260812 sent; the last 6 new cells (`ladder.py run --engine gen4.5`; no cell refused in batches 1 and 2), 6 × 60 = 360 credits at the day's rate. Row written before submission (the estimate) and reconciled after. Balance before the batch: 1,963 credits. FX read at spend: £1 = $1.3374 (2026-11-11) | 6+0 | 3.60 | 2.69 | 162.10 | estimate, before submission |
| 2026-11-11 | NOTE A10 gen4.5 batch 3 reconciled | Batch done: 6 new cells delivered, 0 refused, 360 credits = $3.60, as estimated. Runway's balance: 1,963 credits before, 1,603 after. The Gen-4.5 ladder is complete: 48 of 48 cells, none refused, no resubmission, 2,880 credits = $28.80 in all (A10.7's figure); every clip 1280x720, 121 frames, no audio stream, seed 20260812 sent. Spend since the £115.37 baseline: £46.73 | — | 0.00 | 0.00 | 162.10 | — |
| 2026-11-11 | EXT.A12 ground gen4_turbo d2 + d3 (Runway) | runway gen4_turbo 5 s 1280:720; draws 2 and 3 of the five ground variants, seeds 20260813 and 20260814 sent (`ground_series.py run --engine gen4_turbo --draw 2`, then `--draw 3`); 10 cells × 25 credits = 250 credits at the day's rate (5 credits a second). Row written before submission (the estimate) and reconciled after. Balance before the batch: 1,603 credits. FX read at spend: £1 = $1.3374 (2026-11-11) | 10+0 | 2.50 | 1.87 | 163.97 | estimate, before submission |
| 2026-11-11 | NOTE A12 gen4_turbo d2 + d3 reconciled | Batch done: 10 cells delivered (five ground variants at seeds 20260813 and 20260814), 0 refused, 0 resubmissions, 250 credits = $2.50, as estimated. Runway's balance: 1,603 credits before, 1,353 after. The runbook's end check reads "all 10 accounted for"; every clip 1280x720, 121 frames. The Runway spend for A10 and A12 is complete: $31.30 (A10-POD's ceiling), £23.40. Spend since the £115.37 baseline: £48.60 | — | 0.00 | 0.00 | 163.97 | — |
| 2026-11-11 | EXT.A10 ladder ltx23 + wan22, A12 ground d1–d3 ltx23 + wan22 (pod) | LTX-2.3 Q4_K_M + Wan2.2 Q5_K_M, ComfyUI 0.31.0 + ComfyUI-GGUF 6ea2651, 96 ladder + 30 ground cells on one machine (RTX5090-32GB CUDA driver 595.91.07, RunPod secure, 316 min deploy to stop). Order: LTX ground (15), Wan ground (15), LTX ladder (48), Wan ladder (48). The ComfyUI server was restarted twice, never inside a ground series: at 10:17 UTC, between the LTX and the Wan ground series, pinned to 14 cores with 14 threads (the container is capped at 14.45 cores and 134 GB but shows the host's 120 cores and 967 GB, so it had been throttled: about 180 s an LTX clip against 48 s in August); and at 13:01 UTC, after RunPod's out-of-memory kill of the server during the Wan ladder (cell `ladder-cu-black-3_high_wan22` failed twice on connection refused, left no clip and no line, and was made after the restart). No cell refused; retrieved byte-identical; merged once with all eight checks holding (126 lines) | 126+0 | 0.00 | 0.00 | 163.97 | — |
| 2026-11-11 | EXT.A10/A12 GPU rental | RunPod RTX 5090 secure cloud (no community RTX 5090 with a public address was free; Aaron's word "secure"), $1.19 an hour plus disks, deployed about 08:58 UTC, stopped 14:14 UTC, terminated 15:02 UTC with Aaron's word; the pod list and the storage list are empty. Balance $15.54 → $9.17. Budget: 5 hours, extended by Aaron to 6. FX read at spend: £1 = $1.3374 (2026-11-11). Spend since the £115.37 baseline: £53.36 | — | 6.37 | 4.76 | 168.73 | — |
| 2026-11-11 | NOTE A10/A12 row labels | The 11 Nov rows for A10 and A12 above were first written under a private project label and with a running total named for it; before publication the labels were changed to `EXT.A10`, `EXT.A12` and `EXT.A10/A12 GPU rental`, and the totals now read as spend since the £115.37 baseline. No figure changed | — | 0.00 | 0.00 | 168.73 | — |
