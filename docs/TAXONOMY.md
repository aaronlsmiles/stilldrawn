# StillDrawn failure-mode taxonomy

**Naming rule (frozen §7):** a mode is named only with ≥2 independent exemplars
(different panels or different engines). Every named mode cross-references the
metric signature that detects it — or states that none does.

**Evidence base (2026-08-12, Phase 5):** the 170-cell metric corpus mined for
outliers, then a structured frame-strip review of 24 cells (six independent
review passes, one per engine group; strips in `analysis/out/frames/`, review
protocol in the session log). Cell scalars: `analysis/out/results_table.csv`.

The modes organise on **three axes** — what the ink becomes (register), what
exists in the panel (content), where the camera goes (framing). A single clip
can express several modes at once (exemplars below note co-occurrences).

Severity within the register axis is a ladder: **enrichment → transposition →
collapse** (drawn-but-more → drawn-but-different → not-drawn).

---

## A. Register axis

### A1 · Register enrichment — NAMED

The engine keeps the subject and stays "ink", but adds ink vocabulary the
source never had: screentone on skin, hatching, spot blacks.

- **Exemplars:** `cu-line-2_burst_h3` (screentone + hatching added to a
  line-only panel; ground lifted grey→white; first logged R6);
  `cu-line-2_burst_wan22` (shadow hatching + stubble strokes added under a
  re-pose). Adjacent: `cu-line-2_burst_gen45` (hatching added, register held).
- **Metric signature:** tone_variance fires on line-only panels (a halftone
  band appears where none existed); style moderate; lines stay closed.
  H3 exemplar: tone-var 1.1e-3, style 0.244. Detectable.

### A2 · Register transposition — NAMED

Wholesale re-rendering into a *different* ink idiom — noir wash becomes
woodcut; line-on-grey becomes inverted scratchboard; gradient silhouettes
become speedline burst. Still monochrome ink to a human eye; the metrics read
it as catastrophe.

- **Exemplars:** `est-black-3_burst_gen4t` (soft noir alley re-cut as hard
  woodcut linework; edge slope +2.45); `cu-line-2_burst_ltx23` (line-on-grey
  flipped to black-filled figure, white scratched lines, halftone ground);
  `act-black-3_burst_h3` (sunset silhouettes → abstract speedline impact
  burst; edge slope +8.28, the largest in the matrix).
- **Metric signature:** edge |slope| and chamfer very large while the human
  verdict is "still ink" — the central metric–human divergence the human
  check (§6) is designed to quantify. Global scalars CANNOT distinguish this
  mode from collapse (A3).

### A3 · Register collapse (photoreal drift) — NAMED

The drawn register departs toward photographic/painterly rendering. The
pilot's seed candidate (R4-smoke catastrophic form: colour quasi-photography);
in the benchmark matrix it appeared only in partial form.

- **Exemplars (in-matrix, partial):** `est-black-2_idle_h3` (volumetric
  searchlight glow — airbrushed light, not ink marks);
  `cu-tone-1_burst_wan22` (final-frame face smoothed into soft gradient
  modelling while the office background holds).
- **Recorded catastrophic instances (non-benchmark):** the R4 Wan 480p smoke
  clip (line-on-white → colour photo-render); a 2026-08-10 pilot plate that was later
  refused clearance (Gen-4 Turbo). Kept distinct from benchmark evidence.
- **Metric signature:** style_drift terminal; edge sign negative (softening)
  in partial form, positive (texturisation/grain) in collapse-with-grain
  (FINDINGS R1 established the magnitude headline for exactly this reason).

### A4 · Monochrome break — CANDIDATE (n=1, not named)

Transient departure from monochrome mid-clip with recovery.
`chain-est-cosmic-1_burst_ltx23`: one mid-clip stretch renders a salmon-pink
halftone ground (mean RGB channel spread 35.5 at frame 60 vs ~2 elsewhere),
then returns to white-on-black. Needs a second independent exemplar before
naming; the R4 Wan smoke also broke colour but as part of a full collapse
(A3 evidence), not an independent transient break.

## B. Content axis

### B1 · Element insertion — NAMED

New drawn content the panel never contained, rendered in-register.

- **Exemplars:** `chain-est-cosmic-1_campush_wan22` (a cyclist rides out of
  the empty ice field toward camera — R7's fourth candidate, confirmed);
  `est-tone-1_burst_gen45` (an entire subway train arrives at the empty
  platform — scene-plausible insertion); `cu-line-2_burst_h3` (a glossy
  gloved hand enters frame); `est-black-2_idle_wan22` (unidentified pale
  object enters at the last frame of an otherwise register-perfect clip).
- **Metric signature:** **METRIC-QUIET.** The Wan cyclist scores style 0.248,
  chamfer 0.47 px — global scalars cannot see a localized in-register
  insertion. Strongest single argument for the human check; per-region
  metrics are future work.

### B2 · Pseudo-text insertion — NAMED

Hallucinated lettering: the comics-trained prior expects text on ink panels
and supplies gibberish.

- **Exemplars:** `cu-line-1_idle_h3` (white cursive script "Wang onpiven
  fupitis" written beside the violinist over an inverted ground);
  `cu-black-3_burst_h3` (entire night-market scene replaced by a
  brush-lettered title card, "YEAALE / LVSAC", with corner frame lines);
  `est-black-1_campush_ltx23` (glyphs — a mirrored 6/9, letter-like marks —
  around a hallucinated dial).
- **Metric signature:** chamfer step-jump to a plateau + tolerance-IoU floor
  (the line map becomes a different drawing at a discrete moment); style
  moderate only. The chamfer *series shape* (step vs ramp) separates this
  from gradual drift — a series-level feature, not a headline scalar.

### B3 · Content evacuation (terminal blackout / whiteout) — NAMED

The drawing leaves: fade to a solid field, or the subject exits and the panel
empties. Reads like a learned scene-cut/transition.

- **Exemplars (blackout):** `est-tone-2_campush_h3` (coherent push-in, then
  the final frame is edge-to-edge black — nothing survives);
  `act-line-3_campush_gen45` (clean camera-push tracking mid-clip, final
  frame near-solid black). **Whiteout twin:** `act-tone-1_burst_gen45`
  (reframe to lower body, subject exits, near-empty paper + speckle).
- **Metric signature:** closure endpoints → 0 as the skeleton vanishes; edge
  terminal ratio collapses; style large. Distinguishable from A2/A3 by the
  terminal frame's near-zero ink content.

## C. Framing axis

### C1 · Framing escape — NAMED

The camera runs away: unrequested zoom-out, runaway push-in, hard re-pose.
Identity often survives; composition does not.

- **Exemplars:** `cu-line-2_burst_gen4t` (extreme close-up → full-body long
  shot on emptied ground; same pilot, entire body invented — **corrects R6**,
  which logged this cell as "subject replacement"); `est-black-1_campush_ltx23`
  (push-in swallows the hangar, landing on an abstract glyphed dial — also
  B2); `act-tone-1_burst_gen45` (zoom to lower body, subject exits — also
  B3); `act-line-3_campush_ltx23` (push-in to ground level, players leave
  frame, register held cleanly throughout).
- **Metric signature:** chamfer and style fire hard — globally
  indistinguishable from register failure. A framing-escaped clip with a
  perfect register (the LTX football cell) scores like a broken one. Same
  human-check motivation as A2, from the opposite direction.

---

## Cross-cutting observations

1. **Grey/dark grounds invite reinterpretation.** Ground inversions and
   re-paperings (visible in A2, B2 exemplars; H3's heavy-black column mean
   edge |slope| 2.05 vs 0.17 line-only) concentrate on panels whose ground is
   ambiguous — the measured paper-white p90 covariate correlates negatively
   with style drift on all five engines (exploratory, `analysis/out/tables.md`
   §5).
2. **Stability and obedience trade off.** Wan 2.2 tops four of the five
   stability headlines (Gen-4 Turbo takes edge |slope|) partly by moving least; LTX holds register while moving more.
   A stability score is only meaningful next to a motion-compliance score.
3. **H3's pathologies are prompt-independent** (worst under IDLE), and it is
   the only engine that hallucinated text twice.

## Status

Seeded 2026-08-12 (Phase 5.3) from the full 170-cell corpus + 24-cell frame
review. 7 named modes (A1–A3, B1–B3, C1), 1 candidate (A4). Human-check
ratings (§6, gated on rater recruitment) will attach perceptual scores to the
named exemplars; names may be refined — refinements are dated edits here, the
naming *rule* stays frozen §7.

---

## Addendum — 2026-08-13: reproducibility (repeat probe, hosted engines)

Dated addendum per the project's working rules (the naming rule stays frozen §7; mode
definitions unchanged). The authorised repeat probe (full 33-cell repeats,
gen4_turbo + gen4.5; H3 pending fal unblock) tested whether modes attach to
inputs or to draws. Frame-verified outcomes:

- **Modes attach to DRAWS, not (panel, prompt, engine) triples.** C1 on
  `cu-line-2_burst_gen4t` did not recur (run 2 held the close-up); A2 on
  `est-black-3_burst_gen4t` re-resolved as partial A3 (volumetric light
  shaft); B3 on `act-line-3_campush_gen45` re-resolved as a clean C1-style
  push-in. Same inputs, different modes per draw — the taxonomy is a
  vocabulary of outcomes with per-input hazard rates, estimable only by
  repetition.
- **B1 has a reproduced instance:** the `est-tone-1_burst_gen45` train
  appeared in BOTH draws — transiently in run 2 (passes through, exits),
  invisible to the terminal style scalar (0.578 → 0.062). Metric lesson:
  terminal scalars miss transient events; series maxima do not.
- **The one deterministic behaviour found is a refusal:**
  `cu-tone-3_idle_gen4t` rejected 4× identically across two days; but
  `cu-black-2_idle_gen4t` failed-then-passed and run-1's moderated gen4.5
  cell passed first-try — compliance boundaries are stochastic at the margin.
- **Cross-cutting note 1 upgraded:** the grey-ground observation is now
  CAUSAL on Turbo (A3 series: threshold below p90≈0.8, chamfer ×4, edge
  ×10 at p90 0.52) and absent-to-inverted on Gen-4.5 — engine-specific
  ambiguity resolution, designed-experiment grade for those two engines.

### Addendum update — 2026-08-13 (all three hosted engines repeated)

H3's repeat completed the probe. Three refinements to the addendum above:

1. **Engine rankings replicate perfectly** (Spearman +1.00 on all five
   headline orderings between runs) even though per-cell agreement is weak
   (+0.08 to +0.78). Engine-level statements are safe; per-cell ones are not.
2. **The hazard has structure — motion × treatment.** Reproduced *in kind*:
   both heavy-black BURST cells on H3 (`cu-black-3_burst` cut to a lettered
   title card, then to a fish graphic; `act-black-3_burst` to a speedline
   burst, then to a character on a brush-wave) and the gen4.5 train (B1).
   Vanished on repeat: every IDLE/CAMPUSH pathology tested
   (`cu-line-1_idle_h3` B2, `est-tone-2_campush_h3` B3,
   `est-black-2_idle_h3` A3-partial, plus Turbo's C1 and A2).
   **B2 pseudo-text is therefore best read as one landing of a broader
   graphic-cut hazard on BURST × heavy-black, not a property of those
   panels.** Its LTX exemplar (glyphs on a dial) was itself a push-in
   departure, consistent with that reading.
3. **The triplicate.** `ground-cu-line-1-v100.png` is pixel-identical to
   `cu-line-1.png` (k=1.00 identity transform; verified max abs diff 0), so
   three independent H3 draws of one input exist: chamfer **103.1 / 1.45 /
   51.7 px**. Any future claim that a mode "attaches" to a panel must clear
   this bar.

Naming rule unchanged (frozen §7): all seven modes retain ≥2 independent
exemplars. What changed is the *claim strength* attached to a mode's
appearance on any single clip.

### Addendum — 2026-08-15: A2 is carrying two behaviours

Raised by Aaron while piloting the rating kit, and it holds up. **A2 is
defined as re-rendering into a different ink idiom** ("noir wash becomes
woodcut", "line-on-grey becomes inverted scratchboard") — the same scene,
drawn differently. But its exemplar list includes `act-black-3_burst_h3`,
where the silhouetted figure on the ridge is **replaced** by an abstract
speedline burst. That is not a restyle; the scene is gone. The same is true of
`cu-black-3_burst_h3` (night market → lettered title card → fish graphic on
repeat) and `est-black-1_campush_ltx23` (hangar → glyphed dial), which are
currently filed under B2 and C1 respectively on the strength of their
*secondary* features (lettering, camera push) rather than their primary one.

**Proposed split, for R13 — not applied yet:**

- **A2a · Restyle.** Same scene and subject, different ink idiom. Exemplars:
  `est-black-3_burst_gen4t` (noir → woodcut), `cu-line-2_burst_ltx23`
  (line-on-grey → inverted scratchboard).
- **A2b · Scene replacement (hard cut).** The scene is abandoned and a
  different picture appears, usually abruptly. Exemplars:
  `act-black-3_burst_h3`, `cu-black-3_burst_h3` (both draws),
  `est-black-1_campush_ltx23`.

Both clear the frozen §7 naming rule (≥2 independent exemplars) on their own,
so the split does not weaken either. It matters because the two have different
severities for a working artist — a restyle is arguably usable, a replacement
never is — and plausibly different metric signatures worth checking
(replacement should show a step change in the chamfer *series*; restyle a
sustained offset).

**Not applied pending:** re-review of the affected strips against the split
definitions, and confirmation that reassigning the `cu-black-3` and
`est-black-1` exemplars does not leave B2 or C1 below the two-exemplar bar.
B2 retains `cu-line-1_idle_h3` and `est-black-1_campush_ltx23`'s glyphs; C1
retains `cu-line-2_burst_gen4t`, `act-tone-1_burst_gen45` and
`act-line-3_campush_ltx23` — both survive, but this must be verified rather
than assumed before the split is made.
