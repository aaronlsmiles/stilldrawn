> *Historical record, kept as written. The benchmark's working name was InkBench; it was renamed StillDrawn on 2026-09-30 after a name collision. The creator-IP panel's identifier has been neutralised to `cip-act-tank-1` throughout.*

# InkBench pre-registration

**Status: FROZEN 2026-08-12** — the pilot-clip metric validation is complete
(FINDINGS R1: style_drift passed as designed; edge_decay's headline redefined to
magnitude during validation, before this freeze). From this commit onward, every
element in this document changes only by **dated amendment** appended under
§Amendments — never by editing the frozen text. Git history is the enforcement
mechanism.

Registered before any benchmark run-matrix batch executes. The three pilot clips
(generated 2026-08-10, before this project) are the metric-validation substrate, not
benchmark data.

## 1. Research question

How stable is inked line art — line weight, screentone, contour closure, and style
register — under current image-to-video generation, across content classes and motion
classes?

## 2. Dataset (fixed)

The 27-panel neutral core described in `dataset/panel-pack.md` (3 content classes ×
3 ink treatments × 3 panels; uniform 1344×768; engine mix 9 hosted / 18 local; 1
reroll allowance per panel, recorded). Optional creator-IP subset (≤3 panels) may be
added only before the first run-matrix batch, with per-panel clearance recorded in
the datasheet; its absence changes nothing else.

## 3. Metric definitions (frozen verbatim from `metrics/inkstab.py` DEFS)

The `DEFS` dictionary in `metrics/inkstab.py` at the freeze commit is the normative
definition of all five metrics — it is echoed into every result JSON. Summary:

1. **line_drift** — per-frame line maps via the AnimeLineArt extractor (netG.pth,
   detect_resolution 1024, identical weights to the dataset's lineart layers),
   binarised at per-map Otsu. Symmetric chamfer distance (px, via EDT) and
   tolerance-IoU (maps dilated by disk(2)) of frame-t vs frame-0, and of every frame
   vs the source lineart layer. Headline scalar: mean chamfer vs frame-0.
2. **tone_spectral_drift** — tone mask = 16px box-filtered source-panel greyscale in
   (0.15, 0.85), eroded disk(4) (local-mean greyness — halftone pixels are bimodal).
   64px tiles, stride 32, ≥80% mask coverage, metric defined only at ≥4 tiles.
   Hann-windowed 2D FFT per tile; frame-0 dominant radial bin r\* (r ≥ 3) sets the
   band [0.75 r\*, 1.25 r\*]; per-frame band-energy fraction (band / non-DC, mean over
   tiles). Headline scalar: variance of the series.
3. **edge_decay** — Sobel-3×3 gradient-magnitude 95th percentile per frame; headline
   scalar: **|normalised slope|** (|polyfit slope × N / g₀|) — magnitude, because the
   pilot validation showed photoreal drift can *raise* edge energy (added photographic
   texture) as well as lower it (softening); the signed slope is reported alongside
   and its sign feeds the taxonomy (negative = softening, positive = texturisation).
   (Changed from signed slope during validation, before this freeze — FINDINGS R1.)
4. **style_drift** — DINOv2 ViT-S/14 CLS embedding (frames at 224×392, ImageNet
   norm); cosine distance frame-t vs frame-0. Headline scalar: terminal distance.
5. **closure_proxy** — skeletonised line maps; endpoints (exactly 1 8-neighbour) per
   skeleton pixel; headline scalar: |terminal drift| vs frame 0.

All frames analysed (no subsampling); native clip resolution.

## 4. Motion prompts (frozen verbatim)

`harness/motion-prompts.md` v1: four classes — IDLE, BURST, CAMPUSH, FLINT — one
engine-agnostic prompt each, identical style-lock sentence on every class. `gen_video.py`
resolves prompts from that file only; no run-time editing.

## 5. Run matrix (frozen)

- **Engines:** local Wan 2.2 TI2V-5B and LTX-2.3 (£0) first, then hosted
  cheapest-first: Runway Gen-4 Turbo → MiniMax H3 via fal → Runway Gen-4.5. Model
  IDs, versions and dates recorded per clip in `runs/manifest.jsonl`.
- **Per engine, 27 clips:** every panel runs exactly once, 5s, 1280:720, one seed
  (engine default / recorded where settable). Motion assignment is a fixed rotation
  balancing panel provenance against motion class: within content×treatment cell
  k = 0..8 (ordered cu-line, cu-tone, cu-black, act-line, act-tone, act-black,
  est-line, est-tone, est-black), panel −1 gets motion (k mod 3), panel −2 gets
  (k+1 mod 3), panel −3 gets (k+2 mod 3), where 0=IDLE, 1=BURST, 2=CAMPUSH. The same
  panel+motion+prompt cell repeats identically on every engine (cross-engine
  comparability).
- **FLINT cells (H3 only):** 6 first→last interpolation cells — per content class,
  2 panel pairs drawn within the class (the specific pairs fixed at batch time and
  recorded in the manifest before submission). Recorded n/a for engines without
  first/last conditioning.
- **Moderation/API failures:** one resubmission of the identical cell; a second
  failure records the cell as refused (a result, not a gap).
- **Budget estimate:** Gen-4 Turbo 27×$0.25 = $6.75 · Gen-4.5 27×$0.60 = $16.20 ·
  H3/fal ≈ 27×$0.35 + 6 FLINT ≈ $11.5 → ≈ $34.5 ≈ £27 hosted, inside the ≤£40
  envelope of the £50 ceiling. Ledger row per batch before the next submits.
- **£100-tier extensions** (each requires its named question + Aaron's recorded go):
  extra seeds ("are rankings stable across seeds?"); RunPod local-H3 INT8 ("does the
  open-weights model behave like its API?" — MiniMax licence application first);
  tone-density ablation ("does shimmer scale with tone frequency?").

## 6. Human check (frozen)

- **Subset:** 20 clips, stratified: every engine appears ≥3×, every content class
  ≥6×, every motion class ≥6×; selection by fixed seed (recorded) from the manifest.
- **Raters:** Aaron + 3–5 recruited raters (recruitment is Aaron's gate).
- **Task:** per clip, 5-point Likert — "How well does this clip remain a drawn
  black-and-white ink image throughout?" (1 = dissolves into photographic/painted
  rendering; 5 = every frame could be a drawn panel). Clip order randomised per
  rater; engine identity hidden; the source panel shown alongside.
- **Analysis:** Spearman ρ between each metric's headline scalar and the mean human
  rating, with bootstrap 95% CIs. Metrics that fail to track perception are reported
  as such — a finding, not a failure. Inter-rater reliability: Krippendorff's α.

## 7. Failure-mode taxonomy (seeding rule, frozen)

A failure mode is named only with **≥2 independent exemplars** (different panels or
different engines). Seed candidate from the pilot: *photoreal drift on establishing
shots*. Every named mode cross-references the metric signature that detects it (or
states that none does).

## 8. Analysis plan (frozen)

- Per-engine × per-motion-class metric tables (headline scalars, mean ± range across
  panels).
- Content-class and treatment breakdowns.
- **Pre-registered hypothesis (from the pilot):** establishing-environment panels
  degrade more than character/action panels on the edge_decay headline (|normalised
  slope|) and the style_drift headline (terminal distance).
  Test: one-sided Mann–Whitney U, establishing vs pooled other classes, per engine;
  α = 0.05; effect sizes (rank-biserial) reported; small-n caveat stated.
- Model churn: every clip's manifest line pins engine, model version string, date.

## Amendments

### A1 — 2026-08-12: extension cells for the creator-IP panel + one chain-made neutral panel

**STATUS: APPROVED — Aaron's explicit go on this text recorded 2026-08-12
(in-session, after review of the drafted amendment including the derived details
below). Run-matrix batches are cleared under this protocol.**

*(Supersession note: an earlier same-day A1 draft — commit 1f17e11, derived
single-cell logic — was replaced by this text before any batch consumed it; Aaron's
recorded decision of 2026-08-12 governs. Git history preserves the superseded draft.)*

Per frozen §2, the creator-IP subset is admitted **before the first run-matrix
batch**. Aaron's approved extension (decision recorded 2026-08-12, gate queue in
`NEXT-KICKOFF.md`, commit 570ee1f), three clauses:

1. **Tank panel cells.** `cip-act-tank-1` (author's tank-shatter action panel;
   clearance in `dataset/DATASHEET.md`; two sibling candidates refused, absent)
   receives **3 motion cells per engine** — IDLE / BURST / CAMPUSH — rather than a
   single rotation slot: the frozen §5 rotation allocated no cells to this subset,
   and a full motion sweep on the sole creator-IP panel preserves the pilot
   comparison at benchmark scale.
2. **Chain-made neutral establishing panel.** One additional panel,
   `chain-est-cosmic-1`: a neutral colour establishing plate (single cracked moon
   over an ice field — nothing resembling the author's own project [name redacted]), generated locally and
   passed through the author's production chain (line extraction → inversion →
   img2img inking; chain named, tuned settings withheld — **described-not-
   reproducible recipe**, same class as the tank panel). Purpose: retains a public
   space-content establishing probe of the pilot's photoreal-bias hypothesis and the
   chain-provenance flavour lost with the refused plates. Also receives **3 motion
   cells per engine** (IDLE / BURST / CAMPUSH). Datasheet row + lineart layer ship
   with it.
3. **No portrait replacement** for the refused ink portrait.

Derived details:

- **Cell count:** 27 frozen rotation cells + 6 amendment cells = **33 clips per
  engine** (+ the 6 FLINT cells on H3 only, unchanged, drawn from the neutral core
  only).
- **Clip format:** `cip-act-tank-1` is a native 1024×1792 portrait production plate
  (not regenerable at core resolution by design); its 3 cells run at **720:1280
  portrait** identically on every engine. `chain-est-cosmic-1` is generated at the
  core 1344×768 and runs the standard 1280:720.
- **Added hosted cost:** 6 extra cells × 3 hosted engines ≈ **+$7.2 (≈ £5.6)**
  (Gen-4 Turbo 6×$0.25 = $1.50 · H3 6×$0.35 = $2.10 · Gen-4.5 6×$0.60 = $3.60)
  → total hosted estimate ≈ $41.7 ≈ **£32.6**, inside the ≤£40 envelope of the £50
  ceiling.
- **Engine-constrained resolution:** engines whose latent grid cannot express
  exactly 1280×720 run the nearest supported size (local Wan 2.2: 1280×704 — its
  height step is 32), recorded per clip in `runs/manifest.jsonl`. The source panel
  and prompt are identical across engines; only the engine-imposed output grid
  differs, and metrics are resolution-normalised per clip.

**Aaron's go on this text:** given 2026-08-12 ("Go — run the matrix"), before any
run-matrix batch was submitted.

### A2 — 2026-08-12: local-engine execution hardware + batch-order relaxation

**STATUS: APPROVED — Aaron's explicit go on this text recorded 2026-08-12
(in-session), with his standing spend-watch condition noted in `LEDGER.md`
(track vs estimates, flag overruns, pause if far over).**

Motivation (measured, FINDINGS R4): the Wan 2.2 smoke clip on the study machine
(M-series Mac, MPS backend) runs at ≈ 2 min/sampling-step at 480p — a full
33-cell 704p matrix extrapolates to ≥ 50 hours per local engine, and LTX-2.3's
fp8 components are unreliable on Metal. The protocol intent of §5's "local"
engines is open-weights reproducibility (pinned weights, quants, versions, seeds)
— not any property of the author's hardware. Three clauses:

1. **Execution hardware.** The two open-weights engines (Wan 2.2 TI2V-5B GGUF
   Q5_K_M; LTX-2.3-22B distilled-1.1 GGUF Q4_K_M) execute on a rented
   single-GPU CUDA instance (RunPod). Weights, quantisations, graphs, seeds,
   resolutions and sampler settings are identical to the frozen/A1 protocol and
   recorded per clip in `runs/manifest.jsonl`, plus the GPU model and driver.
   The engines remain "local" in the paper's sense: fully reproducible from
   pinned open weights, no vendor API in the loop.
2. **Cost.** GPU rental estimate **≤ £12** (expected ≈ £8: both matrices, a few
   hours on one ~RTX-4090-class instance), logged as its own `LEDGER.md` row.
   If actual approaches the £12 cap, execution pauses and the overrun goes to
   Aaron before continuing.
3. **Batch order.** §5's "local engines first" relaxes to: hosted batches may
   submit once the harness is smoke-validated (done, R4); rented-GPU local runs
   proceed concurrently. Cheapest-first order within the hosted tier is
   unchanged (Gen-4 Turbo → H3 → Gen-4.5). Rationale: the order rule existed to
   validate the harness before spending, which the smoke clips now do.

**Aaron's go on this text:** given 2026-08-12 ("Go — A2 approved"), with Path-3
selection and hosted-batch pre-confirmation in the same exchange.

### A3 — 2026-08-13: ground-value causal series (£100-tier extension)

**STATUS: APPROVED — Aaron's go recorded 2026-08-13 (in-session selection:
"Ground-value causal series" from the presented extension menu, with cost
~£6–8 and design as described there).**

**Named question:** does source-panel ground value *causally* drive register
instability under I2V — converting the Phase-5 exploratory covariate
(paper-white p90 vs terminal style drift negative on all five engines,
`analysis/out/tables.md` §5) into a designed manipulation?

**Design (five clauses):**

1. **Variants, not new content.** Base panel `cu-line-1` (hosted line-only,
   true-white ground, p90 1.0). Five derived panels
   `ground-cu-line-1-v{100,090,080,065,052}`: the base image linearly scaled
   in luminance by k ∈ {1.00, 0.90, 0.80, 0.65, 0.52}, spanning the
   dataset's observed grey-ground range (p90 0.52–1.0). Pure image
   processing — content, linework, and composition are pixel-identical up to
   the global value scale; the transform is recorded verbatim in each derived
   recipe JSON. The source panel's lineart layer serves all five variants
   (geometry unchanged by a global value scale).
2. **Cells.** Each variant runs IDLE (the gentlest frozen prompt — any
   effect is not motion-driven) once per engine, frozen prompt/settings
   identical to §5. Execution order: gen4_turbo + gen4.5 immediately;
   h3-fal cells when the fal account unblocks; local engines (wan22/ltx23)
   bundled into the same later session (pod or overnight-Mac, hardware
   recorded per clip per A2). The series is complete per engine when its 5
   cells exist; cross-engine comparison uses whatever engines have complete
   series at analysis time, stated explicitly.
3. **Outputs.** Clips `runs/<engine>/ground-cu-line-1-v*_idle_<tag>.mp4`,
   manifest lines as standard, metrics to `runs/metrics-ground/` — the
   primary 171-cell corpus directory is untouched.
4. **Analysis (descriptive dose–response).** Per engine: the five headline
   scalars vs ground value k (and measured p90), with the monotonicity of
   style_terminal and edge |slope| as the question's answer. No inferential
   test is registered at n=5/engine; this is a designed descriptive series.
5. **Cost.** Hosted now: 5×($0.25+$0.60) = $4.25 ≈ £3.3; +5×$0.35 = $1.75
   H3 later; locals £0–2. Ledger rows per batch as always; £100 cap
   unchanged.

### A4 — 2026-08-14: hazard-rate estimation (£100-tier extension)

**STATUS: APPROVED — Aaron's go recorded 2026-08-14 in-session ("I want to do
the hazard-rate study"). Execution pending provider credit (see LEDGER).**

**Named question:** the repeat probe (R10/R11) established *that* failure is a
per-draw hazard rather than a property of the input. It cannot estimate a
*rate*: n=2 draws per cell (n=3 for one accidental triplicate). This amendment
registers the rate measurement, and the structural hypothesis it tests.

**Pre-registered hypothesis (stated before any draw):** hazard rate is
conditioned on motion class × ink treatment. Specifically,
*P(departure | BURST, heavy-black) > P(departure | IDLE, line-only)* on the
same engine. Derived from R11's frame review, where both BURST × heavy-black
cells departed in both draws while all five IDLE/CAMPUSH pathologies tested
vanished on repeat.

**Design (frozen):**

1. **Cells — a 2×2 core, one panel per condition:** `cu-line-1` and
   `act-black-3` × {IDLE, BURST}, i.e. four cells spanning the hypothesised
   high- and low-hazard corners. Extensible to eight (second panel per
   condition: `act-line-2`, `cu-black-3`) if budget permits; the extension is
   declared here so it cannot be chosen after seeing results.
2. **Draws:** n = 10 per cell inclusive of existing draws (main run + repeat
   already provide 2; the ground-series identity variant provides a 3rd for
   `cu-line-1_idle_h3`). New draws are suffixed `-h<k>` and land in
   `runs/metrics-hazard/`; the primary corpus is untouched.
3. **Engine:** one engine only, MiniMax H3 via fal — chosen *before* seeing
   results because R11 showed it has both the highest per-draw variance and
   the most diverse pathologies, so its event rate is furthest from 0 and 1
   and therefore the most estimable at n=10. Single-engine rates are reported
   as engine-specific and not generalised.
4. **Outcome coding — declared in advance to avoid post-hoc classification.**
   Each draw is scored **departed / held** by the frozen rule: a draw counts
   as *departed* if EITHER (a) its line-drift chamfer exceeds 10 px (an order
   of magnitude above the corpus median and above every clip the frame review
   judged "held"), OR (b) blind frame review of its strip records a subject
   replacement, a hard graphic cut, pseudo-text, evacuation, or a monochrome
   break. Rule (a) is automatic; rule (b) is adjudicated on strips with the
   cell identity hidden. Disagreements between (a) and (b) are reported, not
   resolved silently — they are themselves a metric-validity result.
5. **Analysis (descriptive + one test):** per-cell rate with Wilson 95%
   intervals; the registered hypothesis tested by Fisher's exact test on the
   2×2 of (BURST × heavy-black) vs (IDLE × line-only) pooled draws, one-sided,
   α = 0.05. Small-n caveat stated: n=10 per cell yields wide intervals by
   construction; this measures whether rates differ grossly, not precisely.
6. **Cost:** 4-cell core = 32 new draws × $0.35 ≈ **$11.20 (£8.75)**, taking
   the ledger to ≈ £88.10 of the £100 cap. The 8-cell extension adds ≈ £8.75
   (≈ £96.85 total) and requires a further explicit go.

**Addendum to A4 — 2026-10-01 (record correction; no protocol change).** Item 6
above says the 8-cell extension "requires a further explicit go". That go was
given but not written down here or in the ledger: on 2026-08-14 at 02:29, within
two hours of A4's approval, Aaron wrote that he had topped up fal by $30 "so you
can run the core study plus the pre-declared 8-cell extension too". The 71-draw
run therefore executed under an explicit authorisation for all eight cells. This
addendum records it; it changes nothing that was run or registered.

### A5 — 2026-08-14: Seedance 2.0 scout (£100-tier extension; ceilings since retired)

**STATUS: APPROVED — Aaron's go recorded 2026-08-14 in-session ("Yes let's run
the scout… I topped up $10 more so you can start the scout"). Recorded BEFORE
any Seedance batch submits, per the freeze rule.** Full option set and costs:
`docs/A5-DRAFT-seedance.md`; this amendment authorises **Option 1b (the
scout) only**. Options 1, 2, 3, 4 and 5 remain unapproved.

**Named questions.** (a) Does first→last transport-in-register replicate on a
second, independently built engine? (b) Does the motion × treatment hazard
structure of A4 appear on a 2026 flagship, or is it specific to MiniMax H3?

**Registered prediction (before any draw):** Seedance's departure rate on
`act-black-3` BURST will be **no lower** than H3's on the same cell. Rationale:
a model with confident anime priors is *more* likely to redraw a panel it
considers improvable — the graphic-cut hazard of R11. A lower rate refutes
this and is itself the headline.

**Design (frozen, 6 clips, `bytedance/seedance-2.0/image-to-video`, standard
tier, 720p, 5 s — tier declared and not mixed):**

1. **3 FLINT pairs** — the first three frozen §5 pairs in manifest order:
   `cu-line-2→cu-line-1`, `act-line-2→act-tone-3`, `est-line-2→est-black-3`.
2. **3 single-image draws** on `act-black-3` BURST — the highest-hazard cell
   of A4, ordinary (not first→last) conditioning.
3. **Outcome coding:** the frozen A4 rule verbatim (chamfer > 10 px OR blind
   strip review recording subject replacement / hard graphic cut / pseudo-text
   / evacuation / monochrome break).
4. **Pre-specified decision rule** (this is a sequential design, not optional
   stopping): ≥2 of 3 BURST draws depart → proceed to Option 2; 0 of 3 depart
   → Seedance is materially more stable, report that and prefer Option 4;
   1 of 3 → indeterminate at n=3, proceed only if FLINT also shows something.
5. **Interim-look disclosure:** the paper must state that a 3-draw look
   preceded the decision to buy more. If we stop here, the scout is reported
   as a 3-draw pilot with **no rate claim**. If we continue, scout draws pool
   into the rate and the look is disclosed.
6. **Late-addition disclosure:** Seedance was added after the main analysis;
   its cells are excluded from the frozen §8 test. Metrics land in
   `runs/metrics-seedance/`; the primary corpus is untouched.

#### A5 addendum — 2026-08-14: Option 1 completed

**Aaron's go recorded 2026-08-14** ("Run the remaining FLINT Seedance (option 1)
to complete the set"). The three FLINT pairs not covered by the Option-1b scout
— `cu-tone-3→cu-line-3`, `act-tone-1→act-black-3`, `est-tone-2→est-tone-1` —
are run on Seedance under identical settings, completing the frozen §5 set of
six on a second engine. 3 clips ≈ $4.54 (£3.55). No other option is authorised;
Options 2, 3, 4 and 5 remain undecided pending A4's rates.

### A6 — 2026-08-14: post-hoc motion-magnitude channel (exploratory, non-frozen)

**STATUS: APPROVED — Aaron's explicit go recorded 2026-08-14 ("run the £0
motion-compliance work"), following the literature-sweep finding that motivates
it. £0: no generation, no API calls; existing clips are re-analysed.**

**Why this is an amendment at all.** It adds no cells and changes no frozen
definition, but it introduces a *new measurement* over the frozen corpus after
the corpus was complete and scored. Under the freeze rule that is a protocol
change and is recorded here rather than performed silently.

**The problem it addresses.** All five frozen metrics are optimised by a clip
that does not move: a static sequence has no line drift, no tone band-energy
variance, no edge decay, no style drift and a stable register. A stability score
alone therefore cannot separate an engine that holds the inked register from an
engine that barely animates. This confound is already named in the paper's
league-table discussion, but it was named without an instrument. The novelty
sweep established that the field has both named and solved it: VBench observes
that "generating relatively static scenes can 'cheat' to get high temporal
consistency scores" and pairs its temporal dimensions with a Dynamic Degree
control estimated from RAFT optical flow.

**What is added.** `metrics/motion.py` — a separate tool, deliberately *not* part
of `inkstab.py`, so the frozen five and their `DEFS` block remain byte-untouched.
Per clip it computes optical flow between consecutive sampled frames, takes the
mean of the largest 5% of per-pixel flow magnitudes per pair (VBench's statistic,
chosen so small moving objects are not washed out by a static background), and
reports the median of that series as the headline, in px/frame at the analysis
resolution and normalised by the short side. Full definitions are echoed into
every output JSON, as with the frozen suite. Outputs land in
`runs/metrics-motion/`; `runs/metrics/` is untouched.

**Status of any result derived from it — binding.**

1. Motion is **EXPLORATORY**. It is not a sixth headline metric, and the paper's
   contribution list continues to claim five frozen metrics, not six.
2. It may be used to **qualify, condition or caveat** a frozen result — for
   example to state that a league ordering is or is not explained by motion
   differences. It may **not** be used to restate, re-rank or replace a frozen
   result, and the §8 pre-registered test is not re-run against it.
3. The pre-registered §8 test remains as reported: **null, ten of ten.** Nothing
   here reopens it.
4. Any threshold separating "static" from "non-static" is a downstream analysis
   choice and must be declared where it is applied; none is baked into the tool.
5. Because this is a post-hoc addition, **every reported motion result must be
   labelled as post-hoc in the paper**, including in any table where it appears
   alongside frozen scalars.

**A prediction registered before the analysis is run**, so that the outcome is a
test rather than a story: the engine with the lowest (best) median stability
scores will **not** be the engine with the highest motion magnitude, and we
expect the league ordering to be at least partly explained by motion
differences. Stated plainly: we expect to find that our own league table is
confounded. If instead motion is uncorrelated with the stability headlines, the
league ordering survives as a quality ranking and that is the stronger result —
either outcome is reportable, and this sentence is what makes it so.

### A6 — 2026-08-15: human-check instrument revision (§6 wording + a second axis)

**STATUS: APPROVED — Aaron's go recorded 2026-08-15 in-session. Recorded
BEFORE any rating has been collected: the `ratings/` directory is empty and no
kit has been distributed, so nothing here can be a response to data.** This is
the condition that makes an instrument change legitimate; it would not be
available after the first rater returned.

**Motivation, two parts.**

1. *The frozen anchors are not a scale.* §6 labels only the endpoints, and the
   two labels describe different things — point 1 names an outcome
   ("dissolves into photographic/painted rendering"), point 5 names a test the
   rater must construct ("every frame could be a drawn panel"). Points 2–4 are
   undefined and the direction must be inferred. Raters are volunteers, not
   trained coders.
2. *The frozen question measures one axis; the metrics respond to three.*
   §6 asks only whether the clip remains an ink image. Most failures in the
   taxonomy (`docs/TAXONOMY.md`) are **not** register failures: a hard cut to
   a lettered title card, a runaway zoom-out, an inserted cyclist — each is
   still, unarguably, a drawn black-and-white ink picture, and a conscientious
   rater would score it 5. The metrics meanwhile respond to register, content
   and framing together. Correlating a three-axis measurement against a
   one-axis rating would depress the Spearman coefficients **by construction**,
   and we would report "the metrics do not track perception" when the truth is
   that we asked humans a different question.

**Revision (frozen from this entry):**

*Question 1 — register axis (same construct as §6, re-worded).*
> **Does this clip still look like a hand-drawn black-and-white ink picture,
> all the way through?** (5 = yes, completely · 1 = no, not at all)
> 5 — Yes: every frame could be a drawn panel · 4 — Mostly: a few frames slip ·
> 3 — Half and half · 2 — Mostly not · 1 — No: it turns into something
> photographic or painted

*Question 2 — content/framing axis (new).*
> **Is this still the same picture you were shown, just moving?**
> (5 = yes · 1 = no, it became a different picture)
> 5 — Yes: the same picture, moving · 4 — Mostly: small things change ·
> 3 — Half and half · 2 — Mostly not: much of it is different ·
> 1 — No: it became a different picture

Both questions appear on the same screen per clip; both must be answered
before advancing. Everything else in §6 is unchanged: the same 20-clip
seeded subset, the same blinding (engine identity hidden, order randomised
per rater), the source panel shown alongside.

**Analysis (revises §6's analysis clause):** Spearman ρ between each metric's
headline scalar and the mean human rating is computed **separately for each
axis**, with bootstrap 95% CIs. Krippendorff's α is reported per axis. The
pre-registered expectation, stated here before any rating: metrics will
correlate more strongly with **Q2 (content/framing)** than with **Q1
(register)**, because the taxonomy's metric-loud modes (transposition,
framing escape) are content/framing events that leave the register intact.
A null or reversed result is reported as a finding.

#### A6 addendum — 2026-08-15: two instruction clarifications (still pre-data)

**Aaron's go recorded 2026-08-15. The `ratings/` directory remains empty and
no kit has been distributed** — this is still a pre-data instrument change.

Source: a pilot pass by the author (rater AARON) on clip 1 of his own kit,
which surfaced two ambiguities in Q2 that would have produced noise rather
than signal. Neither changes what is asked or which answers are desirable;
both remove ways of misreading the question.

1. **Additions count.** "Same picture" could be read as "same setting", so a
   clip that inserts a figure into an unchanged landscape might score 5 from
   one rater and 2 from another for identical perceptions. Instruction added:
   *"Anything added, removed or replaced counts as a change, even if the
   setting looks identical. A clip that adds a person to an empty landscape is
   not the same picture."* The severity judgement remains entirely the
   rater's — a small addition may still be a 4.
2. **Judge the whole clip, not the final frame.** The author nearly scored a
   clip 5 on Q2 because its closing frame resembled the source still, missing
   an inserted cyclist visible mid-clip. Instruction added: *"Watch the whole
   five seconds. Things that appear briefly and then leave still count."*
   Q2's direction line gains "at any point", and the page shows a
   non-blocking "clip played through" indicator once a clip has looped once.

**Observation recorded for the findings loop (R13):** the pilot rater
exhibited the same terminal-frame bias as the metric suite — the failure mode
that caused the terminal style scalar to miss a transient inserted train
(R10/R11). That humans share the bias is independent support for preferring
series-based over terminal measurement, and should be reported if the rater
comments corroborate it.

#### A6 addendum 2 — 2026-08-15: motion removed from Q2 (still pre-data)

**Aaron's go recorded 2026-08-15; `ratings/` still empty, kit still
undistributed.** Second issue from the author's pilot pass.

Q2 read "Is this still the same picture you were shown, **just moving**?" and
its top label read "Yes: the same picture, **moving**". Both implied that
motion was required to score 5. It is not: Q2 asks whether the *content*
survived, and the amount of motion is a separate axis this instrument
deliberately does not measure (it is the stability-vs-compliance confound
named in R7/R11/R12). Several of the best-preserving clips in the corpus are
near-static — Wan's dark-ground cells especially — and must be scorable as 5.

Revised: **"Apart from the movement itself, is this the same picture you were
shown?"** Top label becomes *"Yes: nothing has been added, removed or
replaced"*, aligning the scale with the addendum-1 clarification. Direction
line: *"5 = yes, unchanged at every point"*. The intro adds: *"How much a clip
moves is not being asked about — a clip that barely moves but keeps everything
intact is still a 5 on question 2."*

#### A6 addendum 3 — 2026-08-15: continuation vs invention (final pre-data revision)

**Aaron's go recorded 2026-08-15, after a full 20-clip pilot pass.** Study
`ratings/` remains empty; the pilot file is quarantined in
`analysis/human_check/pilot/` and must never be pooled (see its README).

Three changes, all from the pilot:

1. **Q2 reworded** to *"Apart from the movement itself, is this the same
   original image throughout?"* — matching the on-screen "ORIGINAL IMAGE"
   label, and "throughout" reinforcing whole-clip judgement.
2. **Continuation is not invention.** The frozen motion prompts ask that "the
   action implied by the drawing continues", so a shattering pane throwing
   more shards, or a figure completing a leap, is the animation working — not
   an addition. Without this, correct behaviour scored badly. Guidance added:
   count only what the original never contained (a new person, vehicle, object
   or lettering). Genuinely intermediate cases — a train arriving at an empty
   platform, which the scene arguably implies — are what the middle of the
   scale is for, and rater disagreement on them is itself informative.
3. **Subtle global tone shifts** belong to Q1, mildly (a 4 rather than a 5),
   not to Q2.

**Pilot result recorded, and the justification for A6 as a whole:** across all
twenty clips the author scored **Q1 = 5 every time — zero variance** — while
Q1 spread across all five points. A constant cannot correlate with anything,
so the pre-A6 single-question instrument would have produced an unanalysable
study. n=1 and from the most primed rater available, so indicative only; but
it also suggests the ink register survives near-universally in the benchmark
matrix, and that the measurable failures are content and framing. If that
holds across raters it is a finding in its own right, and the §6 Spearman
analysis for the register axis may be degenerate — to be reported as such
rather than treated as a failure.

**On not editing collected ratings:** the author offered to have two of his
pilot scores amended after discussing the correct interpretation. Declined.
Ratings altered by anyone other than the rater, after a conversation about
what the answer ought to be, are no longer perceptual data. The pilot is
discarded and re-run on the final instrument instead — which costs twenty
minutes and preserves the instrument's integrity.

#### A6 addendum 4 — 2026-08-15: naming the mechanical/vector failure in Q1

**Aaron's go recorded 2026-08-15, on his own argument — which corrected mine.**

I had declined to add this, reasoning that rater 1's answers were locked and a
further change would make his data incomparable with the remaining pool. That
reasoning was **wrong, and backwards**. Rater 1 rated using the written
instrument *plus* three passes through the kit *plus* an in-session discussion
establishing that a subtle global tone shift belongs to Q1 — knowledge R1–R5
would not receive. The effective instrument therefore already differed between
raters, with rater 1 the better-informed outlier. Leaving the written
instrument silent did not protect comparability; it entrenched the asymmetry.

**Change.** Q1's bottom label becomes *"No: it stops looking hand-drawn —
photographic, painted, or mechanically rendered"*, and the guidance adds:
*"Ink can stop looking hand-drawn without becoming photographic. Flat, even
fills and perfectly uniform screentone can make a clip look assembled in
graphic-design software rather than drawn by hand — no variation in line
weight, no wobble. That counts here too."*

**Why rater 1's data remains valid and poolable.** The change *names* a
failure kind he had already been applying; it does not alter the construct,
the direction, or any other point on the scale. His scores were given under
this interpretation, so the clarified instrument describes what he did rather
than asking something new. R1–R5 are now aligned *to* him rather than
diverging from him. Had the change instead altered what he was asked, the
correct remedy would have been to re-run him, not to reinterpret his answers.

**Generalisable lesson, for the paper's limitations section:** a pilot rater
accumulates interpretive knowledge across passes and discussion. Unless that
knowledge is written back into the instrument, the pilot rater silently
becomes non-comparable with the pool. Piloting is not only a search for
confusing wording — it is a process of *discovering the instrument's implicit
rules*, and those rules must be made explicit before the pool rates.

### A7 — 2026-08-16: hosted delivery of the §6 human check (conditions, not content)

**STATUS: APPROVED — Aaron's go recorded 2026-08-16 in-session, against the
four decisions D-a…D-d below, each answered explicitly before any build began.
Recorded BEFORE any pool rating exists: `analysis/human_check/ratings/`
contains exactly one file, `ratings-AARON.json` (rater 1, locked 2026-08-15),
and no kit has been distributed to R1–R5.** Nothing here can be a response to
pool data, because there is none.

**Scope, stated first and binding: this amendment changes the *conditions* of
administration, not the *instrument*.** Not one word of what a rater is asked
changes. Q1, Q2, all ten scale labels, the four guidance notes (A6 addenda
1–4), the watch-through instruction, the one-sitting instruction and the
"no right answers" framing are carried over **verbatim** from
`analysis/human_check/build_harness.py`, which remains the single source of
truth for the wording. Any future divergence between the hosted page and that
file is a defect, not a revision.

**Why an amendment is required at all.** §6 as frozen, and A6 as amended,
describe a self-contained kit: the rater downloads a zip, opens a local HTML
file, and emails back a JSON the page writes to their own disk. The hosted form
changes four things about the *situation* the rating happens in — network
delivery, a remote submission, an access token, and new passively-recorded
timing fields. None alters the question, but all alter conditions, and under
the freeze rule conditions are recorded here rather than changed silently.

**Aaron's four decisions, as answered.**

| # | Decision | Answer recorded 2026-08-16 |
|---|---|---|
| D-a | Clips on a third-party host pre-release | **Yes** — 20 clips + 20 panels deploy as Vercel static assets, reachable only behind a per-rater token, `X-Robots-Tag: noindex`. The subset is CC-BY public at release, so this is a question of *timing*, not of permanent exposure. |
| D-b | Collect rater name and email | **No.** No personal data is collected at any point. An opaque per-rater token is the sole identifier. |
| D-c | Where results land | **Supabase**, **plus** the existing client-side JSON download retained as a fallback. |
| D-d | Access control | **Per-rater token in the URL.** The token is also the rater id. |

**D-c amended the same day, before any build — the account boundary.**

> **[Redacted in the public release — hosting-account details.]** This passage
> recorded which hosting accounts and database project would serve the
> instrument, and why others were rejected. It named private hosting accounts
> and project identifiers. It carries no protocol content: the conditions the
> raters saw are recorded verbatim below. See `docs/REDACTIONS.md`.

The handoff document's §4 step 5 deploy command is superseded accordingly.

**D-d is superseded in the rater's favour: Basic Auth, not a URL token.** The
gate is HTTP Basic Auth enforced in Vercel Edge Middleware with **no `matcher`**,
so it runs on every path — the pattern already proven in another of the author's deployments
[name redacted], whose source comment records the same reasoning. This is a *strict improvement* on the approved URL-token model and is
adopted for that reason:

1. It closes a hole in the original design. The handoff placed clips in
   `public/`, where Vercel's CDN serves them directly; a token gate on the page
   would not have protected `/clips/c01.mp4`, and the ids `c01`…`c20` are
   enumerable in twenty guesses by anyone who learns the hostname from a
   Certificate Transparency log. A no-matcher middleware gate protects the
   assets themselves.
2. Credentials never appear in a URL, which eliminates recorded risk #3 —
   nothing in browser history, nothing in a `Referer` header.
3. Credentials are **per rater** (username `R1`…`R5`), so the rater id still
   drives the frozen `random.Random(f"{SEED}:{rater}")` order, and access is
   revocable individually. Still zero PII: a username is a study slot, not a
   person.

**A deployment-blocking test accompanies this**, because a self-implemented gate
can be misconfigured in a way a vendor feature cannot: an unauthenticated
`GET /clips/c01.mp4` must return **401**. If it returns the video, the
deployment is not fit to receive raters.

**What changes, itemised.**

1. **Delivery.** The instrument is served over HTTPS from a Vercel deployment
   instead of being opened from a local unzipped folder. The rater sees the same
   page; only its origin differs. The kit's one file-local sentence — *"If a
   video doesn't play, keep this file in the same folder as the `clips` and
   `panels` folders from the zip"* — is a **troubleshooting hint about the
   delivery mechanism, not part of the instrument**, and is dropped as
   inapplicable. This is the only text removed, and it asks nothing of the rater.
2. **Submission.** Answers POST to a Supabase table on completion. The kit's
   local "Download my answers" control is **kept**, so a submission failure
   cannot destroy twenty minutes of a rater's work; the rater is told which of
   the two happened. Correspondingly, the kit's sentence *"Nothing is uploaded
   anywhere by this page"* becomes **false** in the hosted form and is replaced
   by an accurate statement that answers are sent to the study's own store. A
   factually wrong sentence cannot be preserved for the sake of byte-identity;
   this is a statement about the software, not a question put to the rater.
3. **Identification.** Rater identity arrives as an opaque token in the URL
   rather than by which `rating-<name>.html` file the rater was sent. The token
   maps to the same rater slots — `R1`…`R5` — and therefore to the **same frozen
   per-rater clip order**, `random.Random(f"{SEED}:{rater}")` with
   `SEED = 20260813`. The order a rater sees is unchanged by hosting, and is
   recorded in the results row rather than only in the private `mapping.json`.
4. **New passively-recorded fields** (per clip): dwell time, whether the clip
   played through at least once, and the timestamp of each answer. These are
   **observational and non-interfering** — nothing is blocked, warned, or
   prompted on their basis, and the rater is neither timed nor told of a target.
   They exist to let a rushed or abandoned session be *identified* in analysis.

**Binding status of the new fields.** Dwell time, play-through and answer
timestamps are **EXPLORATORY and non-frozen**, on the same footing A6 gave the
motion channel. They may be used to *describe* the pool or to *qualify* a
result — for example to report that no rater completed in under some duration.
They may **not** be used to exclude a rater, re-weight a rating, or filter the
data feeding the §6 Spearman analysis or Krippendorff's α. **No exclusion rule
is registered, and none may be added after seeing the data.** If a session
looks anomalous, the finding is reported as an observation about the pool, with
the ratings retained.

**Rater 1's poolability — the condition this amendment must satisfy.** Rater 1
(AARON) completed the offline kit on 2026-08-15 under instrument A6 + addenda
1–4; his answers are locked in `analysis/human_check/ratings/ratings-AARON.json`
and are **not** re-collected. His data pools with hosted raters **only if the
hosted instrument text is byte-identical** to what he rated under. This is
verified mechanically, not by eye: the hosted page's question and label strings
are extracted and compared byte-for-byte against the constants in
`build_harness.py` (`Q1`, `Q1_LABELS`, `Q2`, `Q2_LABELS`, `Q2_NOTE`, `Q2_CONT`,
`Q1_TONE`, `Q1_MECH`, `WATCH_NOTE`), and against the `questions` block stored
inside his own JSON. **A failed comparison blocks deployment.** The two
delivery-mechanism sentences in item 1 and 2 above are the sole declared
exceptions and are excluded from the comparison by name.

**Blinding is unchanged and re-verified under the new surface.** No engine,
model or vendor name may appear in the HTML, the asset filenames, the URLs, the
API payloads, the database column values, or the deployment configuration.
Clips remain the opaque `c01`…`c20` ids. The `build_harness.py` verification
grep is re-run against the hosted build, and extended to cover the API route
and the stored rows — surfaces the offline kit did not have.

**What is NOT changed by this amendment**, listed so that absence is on the
record: the §6 subset (20 clips, seed 20260813, drawn no-retry) · the six rater
slots · the two-question construct and every word of it · the both-answered
gate before advancing · working Back navigation · the one-sitting instruction ·
the analysis path (`collect.py` reads `analysis/human_check/ratings/`; hosted
rows are fetched down into that directory in the identical JSON shape) · the
Krippendorff α verification requirement against the `krippendorff` package
before any α reaches the paper.

**Hosting risks, assessed and accepted rather than assumed away.** Recorded so
the acceptance is on the record and not rediscovered later:

1. *Irreversibility.* Vercel retains deployment copies on its edge network and
   in internal storage. A deployment can be deleted; its backups cannot be
   verified gone. The §6 subset is released CC-BY regardless, so what is spent
   here is **timing, not rights** — but the step is one-way and is taken
   knowingly.
2. *Certificate Transparency.* Every deployment hostname is published in public
   CT logs when TLS is issued; `noindex` has no bearing on this. The *existence*
   of a hostname is therefore public. Consequence, binding: **the project and
   deployment names must themselves be blind** — no engine, model or vendor
   name, and nothing identifying the study's hypotheses.
3. *Token-in-URL leakage.* The token appears in browser history and would leak
   via `Referer` to any third-party request. Mitigated by the page loading **zero
   external resources** (all CSS/JS inline, all media same-origin) and by
   `Referrer-Policy: no-referrer`. Preserving the no-external-resources property
   is a requirement, not an implementation detail.
4. *Enlarged blinding surface.* Project name, deployment URL, API route, stored
   column values and the hosting dashboard are all new surfaces the offline kit
   did not have. The grep is extended to cover them (see the blinding paragraph
   above).

Not treated as risks, with reasons: permanent public exposure (release makes the
subset public anyway); personal data (D-b collects none, so there is no data
subject); cost (£0 tiers).

**Cost.** £0. Vercel Hobby and Supabase free tiers cover this; no generation
spend. Ledger stays **£114.08**. The standing variance rule applies if anything
here turns out to cost money.

**Housekeeping note, recorded rather than silently fixed:** this document
contains **two amendments numbered A6** — the 2026-08-14 motion-magnitude
channel and the 2026-08-15 human-check instrument revision. They are distinct
and both approved; the collision is a numbering error made when the second was
written. It is left as-is because both numbers are cited by date elsewhere in
the repo, in `FINDINGS.md`, and in the manuscript. Cite them by date. A7 is
unaffected.

### A8 — 2026-08-17: Q1 guidance corrected; a per-panel baseline added (Q3)

**STATUS: APPROVED — Aaron's go recorded 2026-08-17 in-session, on his own
argument and against a reference page he supplied. Recorded BEFORE any pool
rating exists: the hosted store contains zero rows, R1–R6 have not rated, and
the only collected data remains rater 1's locked offline file.** This is the
same condition that legitimised A6 and its addenda; it would not be available
after the first pool rating.

#### Part 1 — A6 addendum 4's guidance was wrong and is replaced

Addendum 4 told raters that ink can stop looking hand-drawn without becoming
photographic, and operationalised that as: *"Flat, even fills and perfectly
uniform screentone can make a clip look assembled in graphic-design software
rather than drawn by hand — no variation in line weight, no wobble."*

**Every property it names is ordinary in modern manga.** Screentone has been
mechanical since the 1960s (Letratone sheets, now digital) and is uniform by
construction; digital inking with a stabiliser is routinely even-weighted;
flat solid blacks are the norm. The claim was tested against a reference page
Aaron supplied — Dragon Ball Super, stored privately [path redacted] — which
has uniform mechanical tone, flat untextured blacks, and smooth even contours
with almost no wobble, and is unmistakably hand-drawn. **The old guidance would
have scored that page a departure.** A rule that misclassifies the reference
case is not a marginal wording issue.

**Where it came from, stated because the mechanism matters more than the
error.** R13 records rater 1 marking two clips down as *"vector-like"*.
Addendum 4 generalised that into a rule about flat fills and uniform
screentone. But what he was responding to was machine-made *appearance* in
those two specific clips, not cleanliness as such. The written rule was
therefore **broader than the judgement it claimed to describe**. Encountering it
on screen during the 2026-08-17 hosted smoke test led rater 1 to question his
own understanding of the construct — a doubt he raised in session immediately,
which is how the defect was found.

**No rating has ever been given under the withdrawn wording — this is a
statement about the instrument, not about any data.** Recorded explicitly
because the distinction is easy to lose and would otherwise read as a
data-integrity problem, which it is not:

1. Rater 1's locked pass (`ratings/ratings-AARON.json`, 2026-08-15) was
   completed **before** addendum 4's text appeared on any screen he used. It is
   unaffected.
2. The 2026-08-17 smoke test carried **dummy answers only** — 5 on every item,
   entered to exercise the submission path, never as perceptual judgements. That
   row was deleted from the store the same day at his instruction and entered no
   analysis path. `fetch_ratings.py` would have skipped it regardless, the AARON
   slot being locked.
3. R1–R6 have not rated at all, and will see only the corrected wording.

The defective artefact is therefore the written rule alone. It was caught by a
rater reading it and objecting, before it could reach a single real judgement.

**Replacement**, approved by Aaron and then refined twice at his request, both
times on 2026-08-17 and both still before any pool rating existed. "inker" was
removed as jargon. *"shapes that look traced or melted rather than drawn"* was
then replaced as well: **traced** names a legitimate drawing technique rather
than a defect, and **melted** is too vague to act on. Final text:

*"Ink can stop looking hand-drawn without becoming photographic. Look for marks
that no one drawing by hand would make: contours gone soft or blurred, edges
that fade instead of ending crisply, lines that smear, warp or run together in
ways a pen or brush would not, or shading that has turned into a smooth
gradient instead of line or tone. Clean, even linework, flat solid blacks and
regular screentone are normal in manga and are not, by themselves, a
departure."*

It points at **machine artefacts** rather than at **cleanliness**, and its
final sentence explicitly rules the misclassified properties back in. The word
"inker" was removed from an earlier draft at Aaron's request as jargon.

**Effect on rater 1's poolability — it improves.** Addendum 4 pulled the
written instrument *away* from what he was applying; this correction pulls it
back. His locked answers were given without addendum 4's text on screen and
reflect the interpretation the corrected wording now states. He is therefore
**more** comparable with the pool under A8 than under A6+4, not less. His data
is not re-collected and is not edited.

#### Part 2 — Q3, a per-panel baseline, asked first

**The gap.** Q2 is *relative* — it asks whether the clip is the same image as
the original displayed beside it, so it anchors itself. **Q1 is absolute**: it
asks whether the clip looks hand-drawn, with no baseline. If a source panel
already reads as mechanical, a low Q1 is charged to the engine when it is a
property of the corpus. This is precisely where the instrument was already
known to be weak (R13's vector-look ambiguity; addendum 4; Part 1 above).

**What is added.** A third question, mirroring Q1's construct, asked of each
**distinct source panel**: *"Does this original still image look like a
hand-drawn black-and-white ink picture?"* on the same 5-point labelled scale.
The 20-clip subset draws on **14 distinct panels** (`chain-est-cosmic-1` alone
serves 3 clips), so this is 14 judgements, roughly three minutes — not 20.

**Order — asked FIRST, before any clip is seen.** An earlier draft placed it
last, to protect rater 1's poolability. That was constraint-driven rather than
principled and is rejected: a baseline judged after watching twenty animations
of those same panels is anchored by them. Baseline-first is the sound
measurement design and is adopted.

**Analysis status — EXPLORATORY, on the same footing A6 gave the motion
channel.** Q3 is not a fourth frozen metric and does not enter the §8
pre-registered test. It may be used to *qualify or condition* the §6 register
result — chiefly as the difference `clip_Q1 − panel_Q3`, which isolates the
engine's contribution from the panel's own register — and to adjudicate whether
a low α on Q1 reflects the instrument or the corpus. It may not restate or
replace a frozen result.

**Registered prediction, before any Q3 data exists:** panel baselines will be
high and low-variance (most panels scoring 4–5), because the corpus is inked
line art by construction. If instead baselines vary materially across panels,
then absolute Q1 scores are partly a corpus property and the register axis
**must** be reported as the difference rather than as a level — and that would
be the more consequential outcome.

#### Part 3 — R6, and a pre-registered sensitivity analysis

A seventh rater slot (**R6**) is added. Rater 1 is the author, knows the
hypotheses, and — unlike R1–R6 — rated clips before the Q3 baseline task
existed, so received no warm-up. **Primary analysis pools all raters**;
alongside it, the identical §6 analysis is run **excluding rater 1**, and both
are reported. Registered now so it cannot be chosen after seeing which is more
favourable. The caveats stated for the record: rater 1 knows the hypotheses,
and rater 1 has no baseline warm-up preceding his clip pass.

**Rater 1's Q3 baseline is collected separately and offline**, on a standalone
14-panel instrument carrying the corrected Part 1 wording, so that his baseline
is given without the withdrawn guidance in mind.

**Passively-recorded fields on the baseline — recorded here because A8 as first
written omitted them.** The baseline captures the same observational fields A7
registered for the clip task. Precisely, because the two delivery routes differ:
the **hosted** baseline records per-panel **dwell time and the timestamp of each
answer**; the **standalone offline kit** records **dwell time only** (rater 1's
file therefore has no per-panel answer timestamps). A7's binding
status carries over unchanged and in full: these are **EXPLORATORY and
non-frozen**, may be used to describe the pool or qualify a result, and may
**not** be used to exclude a rater, re-weight a judgement, or filter the data.
No exclusion rule is registered and none may be added after seeing the data.

Two properties of the measure, stated so it is not over-read:

- **Dwell accumulates across revisits.** Time is added to whichever item is on
  screen, so navigating Back and reconsidering resumes accruing to that item's
  existing total. A high dwell therefore marks a judgement that was *worked
  at*, not one that was rushed — which is the opposite of what a naive reading
  of "time on task" might suggest, and another reason it cannot ground an
  exclusion.
- Time with the browser tab in the background is not counted, and the baseline
  and clip timers each gate on their own card's visibility, so the two parts
  cannot double-count.

**Disclosure gap, recorded rather than quietly closed:** these fields were
capturing data on the baseline instrument before this clause existed — A7
covered the clip task only, and A8 carried the same capture across without
recording it. Rater 1 asked whether dwell had been collected from him, which is
how the omission surfaced. No datum is affected, the fields being observational
and barred from any exclusion rule; the defect is in the record, and this
paragraph is the repair. It is the same failure mode as A6 addendum 4 and the
`answers/` directory: a rule that operated before it was written down.

**Rater 1 has no clip-level dwell.** His locked pass (2026-08-15) predates A7
and carries only `started` and `finished` timestamps. Clip dwell will exist for
R1–R6 and not for him. Listed with the other asymmetries in Part 3; it changes
nothing, telemetry being barred from the analysis path, but the record should
not imply a completeness the data lacks.

**Cost.** £0. No generation, no new infrastructure. Ledger remains £114.08.

#### A8 correction — 2026-08-17, same day, before any pool rating

The "Where it came from" paragraph above originally read that reading addendum
4 back *"caused him to doubt clips he had correctly scored high"*. **Aaron
corrected this and the text has been rewritten.** The original phrasing implied
that ratings existed which were influenced by the withdrawn wording. None do.
What the wording affected was his *understanding* as he read it during the
smoke test — a thought he raised immediately, not a response he recorded.

Corrected in place rather than by a further amendment because A8 was recorded
hours earlier on the same day and no rating of any kind exists against it; the
audit trail is preserved by this note and by git history, which retains the
superseded text. Recording it matters more than tidiness: a pre-registration
that misstates whether data was contaminated is a worse defect than the
instrument error it was written to fix.

**Generalisable point, for the paper's limitations:** the defect was found
because a rater read the instrument critically and objected before rating, and
because the objection was checked against a real reference case rather than
resolved by argument. Neither the six-agent structured review nor the piloting
process caught it — the same pattern R13 records for the A2 taxonomy conflation.

### A9 — 2026-11-03: exploratory follow-up: did each engine do the motion, and drift where nothing should move

*The manuscript submitted on 9 Oct 2026 describes A1–A8 (nine entries). This is
the tenth; it postdates the manuscript and changes no result it reports.*

**STATUS: APPROVED — Aaron's go recorded 2026-11-03 ("Yes to all"), approving
this text, its predictions, verdict rules, wording and dates, after an
adversarial review whose two blocking findings he decided. Registered 2026-11-03
(UTC) by the public commit tagged `a9-registered`, with a Software Heritage
"save code now" of the public repository requested within the hour (its visit
date is cited in the provenance row). £0: no generation and no paid calls;
existing clips are re-analysed and rated. The ledger is unchanged.**

**Why this is an amendment at all.** It adds no cells and changes no frozen
definition, but it introduces two new measurements over the frozen corpus after
the corpus was complete and scored: human ratings of whether each clip carried
out its requested motion, and line drift measured only outside the region the
prompt allows to move. Under the freeze rule that is a protocol change, so it is
recorded here, with its analysis fixed, before any of its numbers exist.

**The problem it addresses.** A6 found that the frozen league tracks how little
each engine moves (engine-level ρ = 0.90 between median motion and median line
drift, exact p = 0.083). Two readings of that remain open. First, an engine may
look steady because it does not do what it was asked: a clip that ignores "one
fast, committed burst" holds its lines by not moving. Second, the frozen
line-drift metric counts every line that moves, including lines the prompt asked
to move: a burst that does happen is scored as drift. Test 1 asks the first
question with blind human ratings; Test 2 asks the second by measuring drift
only where nothing should move.

#### A9.0 Status of any result derived from it — binding

1. A9 is **EXPLORATORY and POST-HOC**. Its hypotheses were written on 30 Oct
   2026, after the league and A6's motion medians had been seen (A9.1). It adds
   no headline metric; the paper's contribution list is unchanged.
2. A9 results may **qualify, condition or caveat** the frozen league. They may
   **not** restate, re-rank or replace it, and the §8 test is not re-run against
   them.
3. The pre-registered §8 test remains as reported: **null, ten of ten.**
4. Every threshold A9 uses is declared below where it is applied.
5. **Every A9 number is labelled post-hoc** wherever it appears, including
   beside frozen values.

#### A9.1 Seen before registration

Seen by Aaron, by Claude (the agent that built A9's tools) or by both, before
registration:

- The frozen league (33-cell medians), A6's engine-level motion medians and ρ;
  `analysis/out/tables.md` §1 (per-engine × class **mean** line drift, already
  public); `analysis/out/motion_confound.md`.
- The fifteen per-class motion medians below, computed on 30 Oct 2026 during
  planning by an exploration agent from the released per-clip motion JSONs
  (median `headline_median_norm` per engine and motion class). Reproduced
  verbatim, not recomputed:

  | Engine | IDLE | BURST | CAMPUSH |
  |---|---|---|---|
  | Turbo | 0.00118 | 0.00138 | 0.00300 |
  | Gen-4.5 | 0.00251 | 0.02444 | 0.00849 |
  | H3 | 0.00201 | 0.00162 | 0.00438 |
  | Wan 2.2 | 0.00085 | 0.00074 | 0.00080 |
  | LTX | 0.00158 | 0.00264 | 0.00679 |

  Given these and A6's ρ, ρ(S, m) < 0 in Test 1 is the expected outcome if
  raters' misses simply track motion magnitude; the within-row check and the
  motion cross-check (A9.3) carry most of Test 1's information beyond that.

- Aaron's earlier viewing of these clips while building the benchmark (frame
  reviews, the failure taxonomy). He is not naive to them (A9.3).
- Until 3 Nov 2026 the plan named R2, a rater from the §6 human check, as the
  second rater; R2's A6 ratings cover 12 of Test 1's 110 clips, and to list them
  Claude printed one A6 rating row (A6's questions only). R2 does not rate in A9
  (A9.3).
- The reproduction-gate table and the per-engine mapping medians (A9.4, A9.5).
- Both mask sets, their per-row IoU, the eligibility counts and the contact
  sheet `analysis/out/figures/a9_masks.png`. Aaron drew his set before the blind
  set existed. Before he reported his one slip (A9.4, `dataset/masks/RULES.md`
  slip log), he had been told how the blind set treated that row.
- A discarded pilot of the rating instrument on A3, A4 and ground clips only,
  answered with fixed scores by a script, to prove the mapping from opaque codes
  back to clips. No A9 clip was in it; every pilot file was deleted.

**Not computed by anyone before registration:** any adherence rating; any masked
line-drift value; the steadiness values S_e of A9.3; the drift medians or gap g
on the eligible rows of A9.4. No masked value can be read from any saved file:
none of the tools saves a line map, flow field or other spatial data, and none
is held, so one would need a fresh extraction. The masked tool's A9 run refuses
until this amendment is public, and its general scoring command refuses any A9
clip it recognises by path, name or identical bytes until then; that is a
tripwire, not a proof, since the underlying library functions are not guarded.
The whole-frame gap on the eligible rows follows in seconds from public per-clip
values and `a9_eligible.csv`; it was not computed, but its rough size was known
from the league's 2.6 doublings and `tables.md`, and the "not testable"
threshold of A9.4 was set with that knowledge.

#### A9.2 Frozen artefacts

`docs/A9-MANIFEST.sha256` (sha256
`95291df0d3477f69f5f83254885095aea5c3414d31e1a216202fa2595bf7fb93`) lists, at
their release paths and hashed in release form:

- Tools and analysis: `metrics/masked.py` and `metrics/test_masked.py`;
  `metrics/inkstab.py`; `analysis/a9_eligibility.py`,
  `analysis/a9_adherence.py`, `analysis/a9_masked_drift.py`,
  `analysis/test_a9_adherence.py` and `analysis/test_a9_masked_drift.py`;
  `analysis/adherence/prepare.py`; the input `analysis/out/results_table.json`.
- Masks: `dataset/masks/allowed-aaron.json`, `allowed-agent.json`, `RULES.md`,
  `agent-brief.md`, `agent-raw/` (the dispatch prompt, the system-prompt text,
  both attempts and their normalisation notes), `agent-reads.txt`, and the
  drawing page `draw.html`.
- Gate and eligibility: `analysis/out/a9_repro_gate.csv`, `a9_geometry.csv`,
  `a9_repro_gate.md`, `a9_eligible.csv`.
- Instrument: for each study (`analysis/adherence/burst/`, `push/`)
  `study.yaml`, `study.lock.json`, `media-sources.json` and `banned-terms.txt`;
  `rating-copies.sha256` (the hashes of the 110 rating copies, which are local
  and never released); `build-trees.json` (the hashes of both built studies);
  `a9-config.json` (registration day, R7's deadline, the R7 declaration).
- The 110 motion JSONs of Test 1's clips (`runs/metrics-motion/`).

The masked tool's run command checks every entry against this manifest, at the
tagged public commit, before it computes anything.

#### A9.3 Test 1: adherence (110 primary burst and camera-push clips, 22 per engine)

**Steadiness.** S_e = the median released `line_chamfer_mean_px` over engine e's
22 burst and camera-push cells, read from `analysis/out/results_table.json`.

**Instrument.** Two blindpanel studies, `a9-burst` (55 clips) and `a9-push` (55
clips), instrument `A9`, titled "Motion check: set 1" and "set 2", seeds
`a9-burst-2026-10-31` and `a9-push-2026-10-31`. Each asks one question, quoting
only the motion clause of the clip's frozen prompt:

- Burst: *The clip was asked for this motion: "The action implied by the drawing
  continues in one fast, committed burst of motion, then settles." Does the clip
  do it?* Note: "Rate only this motion. How the clip looks, and anything else
  that changes, is not being asked about." Scale 1–5: 1 "No: the implied action
  doesn't happen (still, idle movement only, or something else)", 2 "Barely:
  small or hesitant, not a burst", 3 "Partly", 4 "Mostly: a burst, a little weak
  or incomplete", 5 "Yes: one fast, committed burst".
- Push: *The clip was asked for this motion: "Slow, steady camera push-in toward
  the focal point of the drawing." Does the clip do it?* Note: "Rate only the
  camera's move. What the subject does, and how the clip looks, is not being
  asked about." Scale 1–5: 1 "No push-in (holds, pulls back, pans or cuts)", 2
  "Barely: a slight or hesitant move in, not a clear push-in", 3 "Partly", 4
  "Mostly: a push-in, a little uneven, quick or off the main subject", 5 "A
  slow, steady push-in toward the main subject".
- Both: direction line "5 = yes, fully · 1 = no, not at all"; watch note "Watch
  the whole five seconds before answering."; intro lines: "Each screen shows an
  original image (left) and a 5-second clip made from it (right, plays on loop).
  You answer one question about each clip." / "Every clip was asked for the same
  motion, quoted in the question. Rate how fully the clip carries it out." / "Go
  with your eye. There are no right answers. You can change an answer with Back
  before finishing."

`blindpanel lock` hashes the scale labels, each question's id, part, text,
direction, notes and scale, and the intro lines and watch note: `text_sha256`
`de27cc1ec585ee6d0eac879d7cf28eaea6aee2fa50b23fc3b1b897278ec35125` (burst) and
`9e44cba7976eca542add7685a248d79d8f41b892fbf4b93465c2660725f7f43a` (push).
Everything else in each `study.yaml` is covered by the manifest.

**Blinding, in the files.** Every screen shows the clip's source panel as
"original image" and nothing else: no engine name, no metric, no label. Each
rating copy is re-encoded from its source: retimed to 24 fps by frame timing
(never relabelled), cover-scaled (lanczos) and centre-cropped to 1280×704
(704×1280 for the portrait tank row, 10 clips), the first 121 frames, libx264
CRF 16, yuv420p, constant frame rate, no audio, all metadata, chapters, the
encoder tag and all SEI NAL units removed, bitexact flags; panels are rewritten
with only their image chunks. All 110 copies have 121 frames and one size per
orientation, and no C2PA or JUMBF bytes; their hashes are in
`rating-copies.sha256`. The copies are local and never released. Clip order is a
fresh seeded shuffle per session, with each clip's position recorded. Opaque
codes are derived from the study seed and the cell id, and the seed reaches the
page, so a determined rater could work out which code is which engine (as in
A6); the protection is conduct, below. blindpanel's fixed end screen (an offer
to reveal the engines, a public tally opt-in) appears only after the last
answer; no rater presses the reveal before exporting both studies.

**Raters.** Two, each alone and unobserved, on Aaron's Mac through
`blindpanel dev` on localhost, at the builds recorded in `build-trees.json`. Who
rates is procedural: each rater has their own store folder, and nobody else's
session is in it.
- **AARON** built the benchmark and has seen these clips; that is declared, and
  the label "author-rated" carries it. AARON rates on a later UTC day than
  registration, burst then push, at least an hour apart, and before any Test 2
  number exists.
- **R7**, a new rater (the next free pseudonym after the §6 pool's R1–R6). Per
  Aaron's declaration (3 Nov 2026), R7 has never rated for StillDrawn and has
  never seen its explorer, its release, these clips or any result;
  `a9-config.json` records R7 as blind to engine styles. Before rating, R7 signs
  a short written declaration: they rate alone and unobserved, have not opened
  anything about StillDrawn, will not before finishing, and consent to their
  ratings being published under the pseudonym. R7 rates on any later UTC day
  than registration, up to and including the deadline, 2026-11-17 (14 days after
  registration). Anything R7 sees before rating that the declaration does not
  cover is recorded in the written record and the write-up; it does not change
  the analysis files.
- Neither rater sees the other's ratings.

**Collection.** The analysis reads `blindpanel export` together with the stored
session row, never `report` (which silently drops flagged sessions); flags never
exclude a session (A7). The day of a rating is the stored session's
`received_day`, the UTC day blindpanel records at submission, read from the
rating computer's clock. One session per rater per study counts: the first
complete one. Any later rows in that rater's store are moved aside unchanged to
`raw/<study>-<RATER>/extra-sessions.jsonl` and never analysed; their sha256 is
published in `analysis/adherence/sessions.sha256` (A9.5).

**Primary statistic, per rater.** A miss is a score ≤ 2. m_e = misses / 22 for
engine e. ρ = Spearman(S_e, m_e) over the five engines, with midranks for ties.
The exact one-sided p-value is #{π : ρ_π ≤ ρ_obs} / 120 over all 120
permutations of the miss rates, counted with multiplicity. **Prediction: ρ < 0**
(the steadier the engine, the more it misses). Without ties the attainable
values are: ρ = −1.0, p = 1/120 = 0.0083; ρ = −0.9, p = 5/120 = 0.0417; ρ =
−0.8, p = 8/120 = 0.0667; ρ = −0.7, p = 14/120 = 0.1167. So without ties only ρ
≤ −0.9 passes. The actual ρ and p are always printed. Equal miss rates for every
engine leave ρ undefined and read "not supported".

**Verdict.** **Supported iff p ≤ 0.05 for both raters**; otherwise not
supported. Only two raters give a verdict: there is no verdict on AARON's
ratings alone.

**Reporting states.**
- *Pending* (R7's ratings not yet in, deadline not passed): Test 1 is published
  as "author-rated; second rater pending", with AARON's ρ and p marked
  "provisional (AARON only)". No verdict.
- *Two-rater:* when both R7 studies are in and dated within the deadline, the
  two-rater verdict above is issued.
- *Fallback:* if R7 has not completed both studies by the deadline, Test 1 has
  **no verdict**: AARON's ρ and p are reported, labelled "author-rated", and H1
  reads "not tested by two raters". Missing the second rater can therefore never
  make H1 supported. The fallback is recorded by
  `analysis/adherence/r7-status.json` with `deadline_passed: true`, written by
  hand on the first UTC day after the deadline, or by an R7 file whose
  `received_day` is after the deadline. If both R7 files are present and in
  time, the two-rater state applies even if a status file exists. A late R7 file
  is still analysed and printed (R7's statistic and κ) under the "author-rated"
  label, with no verdict.

**Secondary, no verdict.**
- Agreement: quadratic-weighted κ between the raters, per study. κ is undefined
  only when both raters gave every clip the same single score; one constant
  rater, or both constant on different scores, gives κ = 0.
- Miss rates per engine and class, and per engine overall, with Wilson 95%
  intervals.
- Within-row check: Test 1's 22 rows (11 burst, 11 camera-push panels). Per row,
  Spearman(released drift, score) across its five engines; the statistic is the
  mean over rows with a defined ρ (a positive mean means higher drift goes with
  higher adherence). The null permutes scores within rows, 10,000 draws,
  `numpy.random.default_rng(20261030)`, only rows with a defined ρ drawing a
  permutation, in sorted row order; p = (k + 1) / (draws + 1), where k counts
  draws whose mean is ≥ the observed mean (tolerance 1e-12): one-sided, for a
  positive mean. Ties use midranks within rows. Same seed for each rater.
- Sensitivity: the primary statistic with a miss defined as score ≤ 3.
- Motion cross-check per class, threshold-free (A6 rule 4): AUC = P(motion of a
  non-miss clip > motion of a miss clip), ties ½, on the released
  `headline_median_norm` of the base clips (never the `-r2` replicates), using
  each rater's misses. An AUC ≥ 0.70 corroborates the ratings. An AUC ≤ 0.60 is
  reported prominently as "the misses are not under-animation"; between the two
  it reads "inconclusive". It is undefined when a class has no misses or no
  non-misses. The engine-level correlation of median motion with miss rate is
  reported as non-evidential, because its ordering was seen.
- Outputs are rounded to 12 significant digits after every decision is taken.
  numpy 2.5.2 is pinned; it fixes the permutation draws here and the bootstrap
  of A9.4.

#### A9.4 Test 2: masked drift (109 primary idle and burst clips)

**Rows.** 22 rows of a panel and a motion class (11 idle, 11 burst) on 20
panels; the two A1 panels (`cip-act-tank-1`, `chain-est-cosmic-1`) carry one row
per class. 109 clips: Gen-4 Turbo's `cu-tone-3_idle` was refused at generation
and stays missing.

**Masks.** For each row a mask M marks where the row's prompt allows the drawing
to move, stored as polygons in panel fractions (`stilldrawn-allowed-regions/1`,
public ids). The drawing rule, given word for word to both drawers: "Idle marks
bodies (breathing), hair, cloth, foliage, smoke, water, cloud and particles.
Burst marks the actor, its plausible path, whatever it strikes or sheds, and
anything attached to it. Never rigid structure, ground, lettering or the camera.
When unsure, leave it unmarked." with the note that the rule decides what may be
marked and the motion prompt only names the kind of motion. Leaving a doubtful
region unmarked enlarges the measured region, which works against H2. A row
whose prompt allows nothing to move is `nothing-allowed` (M empty).
`dataset/masks/RULES.md` holds the full rules, written on 30 Oct 2026 before any
mask was drawn; a dated note on how the blind drawer runs (3 Nov, after Aaron's
set and before the blind set) and the slip log have been added since, as the
file allows.

Two sets, drawn after the reproduction gate passed and before registration:
- **Aaron's** (`allowed-aaron.json`), drawn on 3 Nov 2026 in `draw.html`, a
  local page that showed only the panel, its public id, its prompt and the
  drawing rule. One slip was fixed, as RULES.md allows and logs:
  `cu-line-2_burst` had been saved as nothing-allowed by mistake; Aaron meant
  the whole frame, and the row now holds one whole-panel polygon. The row is
  ineligible either way (below).
- **The blind set** (`allowed-agent.json`), drawn by Claude Opus 5.5
  (`claude-opus-5-5`, effort high) with Read as its only tool, in a fresh
  non-interactive Claude Code session started inside a scratch folder holding
  only the 20 panels, a grid-overlay copy of each, and the frozen brief
  (`agent-brief.md`, copied in as `brief.md`, sha256
  `0a7ba7b7e7a3386b17e9da140728539c643f890faff6bcd1839218abef1e2377`). The
  session loaded no user or project instructions, memory, hooks, plugins, MCP
  servers or skills, and refused any permission prompt. Its system prompt
  carried, besides Claude Code's own, the drawer definition's text, shipped as
  `agent-raw/system-prompt.txt`, which names no study. The brief gives the
  prompts, the drawing rule and the reply format and does not name the study
  either. A session started as a subagent of the working session was ruled out
  because that session's instructions name this study. The first attempt was
  malformed (a sentence before the JSON) and was kept unedited; the second, with
  the identical prompt, was converted and needed no normalisation. The read log
  (`agent-reads.txt`, extracted from both transcripts) shows 41 reads per
  attempt, all inside the folder, every file read, no other tool and no context
  file loaded. The transcripts are not released; their sha256 are in the read
  log.

Agreement and eligibility (from `analysis/out/a9_eligible.csv`):

| Row | Aaron | Blind | IoU | Eligible |
|---|---|---|---|---|
| act-black-2_idle | drawn | drawn | 0.1310 | yes |
| act-black-3_burst | drawn | drawn | 0.3706 | yes |
| act-line-1_idle | drawn | drawn | 0.4225 | yes |
| act-line-2_burst | drawn | drawn | 0.6043 | yes |
| act-tone-1_burst | drawn | drawn | 0.4052 | yes |
| act-tone-3_idle | drawn | drawn | 0.1282 | yes |
| chain-est-cosmic-1_burst | nothing | nothing | 1.0000 | yes |
| chain-est-cosmic-1_idle | nothing | nothing | 1.0000 | yes |
| cip-act-tank-1_burst | drawn | drawn | 0.5694 | yes |
| cip-act-tank-1_idle | drawn | drawn | 0.1882 | yes |
| cu-black-2_idle | drawn | drawn | 0.0314 | yes |
| cu-black-3_burst | drawn | drawn | 0.3545 | yes |
| cu-line-1_idle | drawn | drawn | 0.1004 | yes |
| cu-line-2_burst | drawn | drawn | 0.9588 | **no** |
| cu-tone-1_burst | drawn | drawn | 0.3380 | yes |
| cu-tone-3_idle | drawn | drawn | 0.0446 | yes |
| est-black-2_idle | drawn | drawn | 0.0778 | yes |
| est-black-3_burst | nothing | nothing | 1.0000 | yes |
| est-line-1_idle | nothing | nothing | 1.0000 | yes |
| est-line-2_burst | drawn | nothing | 0.0000 | yes |
| est-tone-1_burst | drawn | nothing | 0.0000 | yes |
| est-tone-3_idle | drawn | drawn | 0.0893 | yes |

**21 of 22 rows are eligible** (104 clips before the 500-pixel rule below).
Median IoU 0.3463, minimum 0.0000. `cu-line-2_burst` is out because both sets
allow the whole frame or nearly so, leaving no line pixels to measure. The blind
set gives its two `cip-act-tank-1` rows identical polygons. Four rows are
nothing-allowed in both sets; for them, masked drift equals whole-frame drift,
which dilutes s. The blind set also marks `est-line-2_burst` and
`est-tone-1_burst` nothing-allowed, so 6 of the 21 eligible rows are unmasked
under it against 4 under Aaron's: it dilutes s more, which tilts a split outcome
towards "mask-dependent" with Aaron's set the higher.

**Eligibility rule, fixed before any mask was drawn.** Per row, on a 1280×720
grid (720×1280 for the portrait tank panel), under the stretch mapping: the
row's line-art layer from `dataset/lineart`, binarised exactly as `inkstab.py`'s
`--lineart` branch (greyscale, inverted, anti-aliased resize, the layer's Otsu
threshold), gives n_lines. Each polygon is filled with `skimage.draw.polygon`; R
= ~binary_dilation(M, disk(32)), the whole grid when M is empty; n_R = line
pixels in R. A row is eligible iff 10 · n_R ≥ max(20,000, n_lines) (that is, n_R
≥ max(2,000, 0.10 · n_lines), in integers) under both sets. A drawn row that
fills no pixel counts as nothing-allowed. A layer whose aspect is more than 1%
off its panel's is refused. All five engines' clips of a row are in or out
together; no clip is excluded for any other reason except the frame-0 rule
below.

**Mapping a mask onto a clip.** Masks are rasterised straight onto each clip's
own grid under that engine's mapping: stretch (the panel scaled to the grid) or
centre-crop (the panel scaled by max(H/ph, W/pw) to cover the grid, the scaled
size rounded to whole pixels and at least the grid, offsets floor((scaled −
grid) / 2)). A point (x, y) maps to row y · scaled_h − top and column x ·
scaled_w − left, with no half-pixel offset and boundary pixels included. M is
clipped to the grid before dilation, so allowed area outside a centre-crop
window gives no margin inside it. Rows whose drawn mask rasterises empty on a
grid are flagged and counted (`n_m_empty`). Each engine's mapping was fixed by
the reproduction gate, before any mask existed, as the one with the lower median
chamfer between frame 0 and the panel's line-art layer over its idle and burst
clips (stretch on a tie):

| Engine | Clips | Stretch, median px | Centre-crop, median px | Mapping |
|---|---|---|---|---|
| Wan 2.2 | 22 | 1.863 | 0.615 | centre-crop |
| Gen-4 Turbo | 21 | 1.216 | 0.632 | centre-crop |
| LTX-2.3 | 22 | 1.800 | 0.667 | centre-crop |
| Gen-4.5 | 22 | 1.137 | 0.508 | centre-crop |
| MiniMax H3 | 22 | 0.381 | 0.381 | stretch (tie: its grid has the panel's aspect ratio) |

**Measured region.** R = ~binary_dilation(M, disk(m)), computed as
`distance_transform_edt(~M) > m` (unit-tested equal), all-true when M is empty.
Primary margin m = 32 clip pixels (about twice the ≈14 px worst-case border
misalignment); sensitivity m = 16 and 64, on the rows eligible at m = 32.

**Masked chamfer** (`masked.py`'s `masked_frame(a, b, R)`, the one
implementation both its commands use). For each frame t = 1…N−1 against frame 0
(a = frame t, b = frame 0), with full-frame distance transforms and the frozen
line maps: None if a or b is entirely empty, as the frozen metric does; if a∩R
and b∩R are both non-empty, 0.5 · (EDT(~b)[a∩R].mean() + EDT(~a)[b∩R].mean());
if only b∩R is non-empty (lines vanished from the region), EDT(~a)[b∩R].mean();
if only a∩R is non-empty (lines appeared in it), EDT(~b)[a∩R].mean(); if both
are empty, None. The clip value is the mean of its scorable frames; a clip with
no scorable frame scores +∞ (stored as `chamfer_px: null` with
`no_scorable_frame: true`). With R all-true the function equals the frozen
`_chamfer` bit for bit (unit test). A clip whose frame 0 has fewer than 500 line
pixels in R is excluded from both columns for that engine, per condition (mask
set × margin), and reported; each engine keeps its own clips, with no
re-matching across engines.

**Statistic.** For each condition, D_e = engine e's median over its kept clips
(`np.median`, which averages the two middle values; +∞ allowed). Both columns
come from one extraction per clip in the registered run: the whole-frame value
is the run's recomputed headline, which must equal the gate's recomputed value
to within 1e-6 px on the same device (mps), otherwise the run stops. The
registered run therefore reproduces only on Apple-silicon `mps`; on other
hardware, `masked.py score` computes the same masked values for any clip, row
and mask file (from a second checkout of the public repository passed as
`--public-repo`), without the tie to the gate. g = log2(D_Gen-4.5 / D_Wan 2.2),
in log2 units; s = 1 − g_masked / g_whole; Δg = g_whole − g_masked. g_whole is
recomputed per condition (set × margin × split) on that condition's kept clips.

**Verdict at m = 32, on idle and burst rows together, in this order:**
1. **Not testable** if g_whole < 1.0 (exactly 1.0 is testable), or undefined,
   under either set. This takes precedence over every other outcome.
2. **Supported** if s ≥ 0.5 under both sets and the lower endpoint of the
   bootstrap 95% interval for s under Aaron's set is above 0 (an endpoint of
   exactly 0, or a missing or non-finite interval, fails).
3. **Mask-dependent** if s ≥ 0.5 under one set only (including when s is
   undefined under the other).
4. **Killed** (the plan's "same order, similar gaps", made numeric) if Kendall
   τ_b between the whole-frame and masked engine medians is 1 over all five
   engines under both sets, and s < 0.25 under both. A tie between two masked
   medians gives τ_b < 1; an infinite median makes τ_b undefined, so it cannot
   be killed.
5. **Not supported** otherwise, including s ≥ 0.5 under both sets with the lower
   endpoint of Aaron's interval at or below 0.

An undefined s (g_whole = 0, or a masked median of 0 or +∞) counts as neither ≥
0.5 nor < 0.25. Any outcome other than supported closes the masked line: new
masks, margins or classes would need a new amendment. Requiring both sets is the
defence against masks drawn from memory.

**Bootstrap.** Resample eligible panels (an A1 panel carries both its rows) from
the sorted panel list:
`numpy.random.default_rng(20261030).integers(0, n, size=(10000, n))`, one
generator per split shared by all six conditions. Percentile intervals
(`np.percentile`, linear) for s and Δg over finite replicates only. Replicates
with g_whole < 0 stay in the s interval; g_whole = 0 or a non-finite g leaves s
undefined and the replicate out of it; every replicate with g_whole ≤ 0 is
counted (`n_g_whole_le_0`), and `n_s_finite` is reported. numpy 2.5.2 is pinned
(it fixes the generator's draws).

**Reported whatever happens.** The full grid (two mask sets × three margins) and
idle-only and burst-only splits, with clip counts, exclusions and `n_m_empty`.

**Wording.** Rows in frozen-league order, no rank column; masked medians only
beside whole-frame medians on the same cells; g and Δg never called "doublings"
and never compared with the league's 2.6. Headline, one per mask set at m = 32
over all eligible rows: "Post-hoc (A9): on N cells, Gen-4.5/Wan falls from X× to
Y× outside the region the prompt allows to move (s, CI). The frozen league is
unchanged; this qualifies how its gap is read." N is the total kept clips over
the five engines; X and Y are ratios of medians (2^g) to one decimal; the verb
is falls, rises or stays; s and its interval to two decimals.

#### A9.5 Order that makes "before any number" true and checkable

1. **Reproduction gate, before any mask existed (done, 30 Oct 2026).** The line
   maps of all 109 clips were re-extracted, held in memory one clip at a time
   and never saved. Pass rule: every clip within max(0.01 px, 0.5 %) of its
   released `line_chamfer_mean_px`, same frame count, grid and device; a failure
   would block everything and no clip may be dropped to pass. **Result: PASS,
   109 of 109**, every recomputed value equal to its released value (largest
   difference 0.000 px), on mps. The gate ran with an earlier
   `metrics/masked.py` (sha256
   `3ece0296d6147d97a695060a27e4a8278e7bcd436ba1653c9f2652d779feb5e6`, not
   released), before its masked-scoring code was added; the registered file adds
   that code and changes only definition text and file-encoding arguments in the
   gate's path. `a9_repro_gate.md` was re-finalised by the registered file with
   both gate CSVs byte-identical; it records `git_dirty: True` because the
   working tree then held untracked files unrelated to the gate. Anyone can
   re-run the gate with the registered file (`masked.py gate`, on mps) and
   compare it with `a9_repro_gate.csv`.
2. **Both mask sets drawn; eligibility and IoU computed (done, 3 Nov 2026).**
3. **Rating copies encoded; both studies built, locked and verified (done, 30
   Oct 2026).**
4. **Registration:** this amendment and the manifest committed, the provenance
   row added, the public release refreshed in place, pushed without force and
   tagged `a9-registered`; within the hour, a Software Heritage "save code now"
   of the public repository as an independent timestamp. Registration day
   2026-11-03 is the UTC date of the tag push; every calendar day in A9 is a UTC
   date.
5. **Ratings, published before Test 2.** AARON rates on a later UTC day than
   registration. AARON's two rating files are then pushed to the public
   repository in an in-place refresh, with a Software Heritage save requested,
   **before the masked tool runs**: its A9 run refuses unless both files are on
   the public `main`, byte-identical in release form, each dated after
   registration. R7 rates on any later UTC day up to and including 2026-11-17;
   R7's files are published in the same way after they arrive. The sha256 of
   every session that is not analysed (a rater's extra sessions) and of every
   rating file replaced after it was first written is published in
   `analysis/adherence/sessions.sha256`, so nothing set aside is invisible.
6. **Test 2 in one pass:** one extraction per clip, whole-frame plus all six
   masked conditions; an interrupted clip is re-extracted on resume; the first
   gate-tie failure stops the run and keeps records already written. Results are
   published in a second in-place refresh whose manifest check passes.

#### Registered predictions

- **H1 (Test 1):** the steadier an engine's lines on burst and camera-push
  cells, the more often it fails to do the requested motion: ρ(S, m) < 0,
  supported only if p ≤ 0.05 for both raters.
- **H2 (Test 2):** measured only where the requested motion should not reach,
  Gen-4.5's line-drift gap to Wan 2.2 shrinks by at least half (s ≥ 0.5) under
  both mask sets, with the lower end of Aaron's bootstrap interval above 0.

Stated plainly: we expect part of the league's gap to be the cost of doing the
motion. If instead the steadiest engines do the motion as often as the others,
and the gap survives masking, the league reads more strongly as a measure of
holding the drawing, and that is the stronger result. Either outcome is
reported, and both tests are reported whatever they show.

#### A9 results — 2026-11-06 (exploratory, post-hoc; recorded after both tests ran)

Both tests ran as registered. Neither registered prediction held. No analysis
beyond A9's was run, except the one sensitivity line declared in
`docs/A9-DEVIATIONS.md` note 1 before any masked value existed.

**Order, as it happened (UTC).**
- 2026-11-03 06:06:50: tag `a9-registered` pushed. Software Heritage visit
  06:06:55, snapshot `swh:1:snp:1431f5449301f32c5db264af54179524c3aa9d83`.
- 2026-11-06: four rating sessions, all on Aaron's Mac at the recorded builds.
  The times are when each session was stored:

  | Rater | burst | push |
  |---|---|---|
  | R7 | 16:07 | 17:20 |
  | AARON | 17:01 | 18:22 |

  R7 signed her written declaration before her first session. One complete
  session per store, so nothing was set aside and `sessions.sha256` does not exist.
- 18:31:48: all four slim rating files pushed to the public `main` (commit
  `f5fd0df`), byte-identical to the private copies.
- About 18:32: `metrics/masked.py a9-run` started. Its guard passed, and it wrote
  its first record at 18:33:48. An earlier launch the same minute started in the
  wrong working directory and exited before importing anything.
- 18:34:47: Software Heritage save requested by Aaron (visit 18:34:49, snapshot
  `swh:1:snp:e0d5776084a41c3e42b441041833858428608161`). That is about two
  minutes after the masked run started, not before it as A9.5 step 5 has it; see
  deviation 3.
- 21:12:45: the run finished, 109 of 109 clips with every gate tie held. Both
  analysis scripts then ran twice, and their outputs were byte-identical both times.

Hashes:
- `metrics/masked.py` `9707ba7b…`, `a9_masked_drift.py` `31f902cd…` and
  `a9_adherence.py` `9d966cfc…` (as registered);
- mask sets `allowed-aaron.json` `0f80bfe3…` and `allowed-agent.json` `96b6ccba…`;
- outputs `a9_masked_drift.json` `a48b7059…` and `a9_adherence.json` `01d1c458…`.

**Test 2: killed.** At m = 32, over all 21 eligible rows (104 clips under each
set):

- Aaron's masks: Gen-4.5/Wan falls from 3.8× to 3.3× (s = 0.11, 95% CI −0.41 to
  0.33).
- Blind set: Gen-4.5/Wan rises from 3.8× to 3.9× (s = −0.01, 95% CI −0.53 to
  0.22).

Kendall τ_b between the whole-frame and masked engine medians is 1 under both
sets, and s < 0.25 under both. That is the registered kill rule, so the masked
line is closed. At m = 16 and m = 64, and in the idle-only and burst-only splits,
s stays at or below 0.18 under Aaron's set and at or below 0 under the blind set.
No condition comes near 0.5.

Read as A9's "Stated plainly" paragraph registered it: the league's gap survives
masking. Gen-4.5's extra drift is not the cost of moving where the prompt allows;
it lies where nothing should move.

**Test 1: not supported** (two raters, both in time).

| Rater | ρ(S, m) | Exact one-sided p |
|---|---|---|
| AARON | −0.90 | 0.0417 |
| R7 | −0.50 | 0.2250 |

The rule needs p ≤ 0.05 for both raters, so the result is not supported.
Quadratic-weighted κ between the raters: burst 0.635, push 0.708.

What both raters show (no verdict):
- Wan 2.2, the steadiest engine, misses the requested motion on 20 of its 22
  cells for each rater.
- Within rows, the clips with more drift are rated as doing the motion more fully:
  mean ρ is 0.54 for AARON (p = 0.0001) and 0.38 for R7 (p = 0.0002).
- The motion cross-check finds the misses under-animated. Three of its four
  readings corroborate; R7's burst reading is inconclusive (AUC 0.663).

Where the raters part is the middle of the league. R7 misses more on LTX-2.3
(11/22) and Gen-4.5 (7/22) than on Gen-4 Turbo (6/22). AARON's misses fall
steadily from Wan 2.2 (20/22) to MiniMax H3 (2/22), with one exception: H3's
median drift (5.53 px) is below Gen-4.5's (7.04 px), yet it misses least. A
five-engine rank test can reach p ≤ 0.05 only at ρ ≤ −0.9, so one swap in the
middle is enough to miss it.

**Deviations.** Each was recorded before the numbers it could touch existed,
except deviation 3, which concerns a timestamp, not a number.
1. *End screen.* Raters pressed blindpanel's two end-screen buttons, "See where
   you land" then "Add my ratings…". A blindpanel session is stored only after
   both, whereas A9.3 says no rater presses the reveal before exporting both
   studies. In this build the end screen identifies no clip or engine: every
   clip is labelled "clip". Decided 3 Nov, before any rating.
2. *Aaron's `est-tone-1_burst` mask* reflects a primed judgement: a generated
   clip he had seen shows a train leaving the tunnel. It is kept as registered
   (`docs/A9-DEVIATIONS.md` note 1). Sensitivity line, no verdict: read as
   nothing-allowed, Aaron's set gives 3.8× to 3.4× (s = 0.10, 95% CI −0.43 to
   0.25), still killed (`analysis/a9_tunnel_sensitivity.py`).
3. *The second Software Heritage save* was requested about two minutes after the
   masked run started, not before. The public order rests on the GitHub push at
   18:31:48, which the run's guard checked against `origin/main` before writing
   anything. The Software Heritage visit is a second witness that came slightly late.
4. *Descriptive only:* a mask-agreement measure added after registration
   (`docs/A9-DEVIATIONS.md` note 2). It changes no registered number.

**What this does and does not change.** The frozen league and its headline are
unchanged. A9 qualifies how to read them. The gap between Gen-4.5 and Wan 2.2 is
drift where nothing should move, under either mask set. And the steadiest
engine's steadiness comes largely from not doing the requested motion: both
raters agree on that, though the five-engine test of it holds for one rater only.

### A10 — 2026-11-10: confirmatory: line stability as a function of motion, by construction

*A10, A11 and A12 were drafted together on 4 Nov 2026 for the journal version of the paper
and registered together; each stands alone. None restates a frozen result.*

**STATUS: APPROVED — Aaron's go recorded 2026-11-10 ("Go to register A10–A16 once the open fixes below are made and two-stage reviewed"), after an independent review of the drafts whose findings he ruled on; every fix was made and reviewed before registration. Registered 2026-11-10 (UTC) by the public commit tagged
`a10-registered`, with a Software Heritage "save code now" of the public repository
requested within the hour. Cost: about £25 (A10.7).**

**Why this is an amendment at all.** It adds cells: a second prompt pack and 144 new clips
on three engines. Under the freeze rule new cells need a dated amendment, recorded with
their analysis before any of them exists.

**The problem it addresses.** A6 found that the frozen league tracks how little each engine
moves (engine-level ρ = 0.90 between median motion and median line drift, exact p = 0.083),
and A9 asks, post hoc, whether each engine did the motion it was asked for and how its lines
drift where nothing should move. Both work on the frozen corpus, where motion was only
requested, in three classes, once per panel and engine. A10 manipulates motion directly: the
same twelve panels at four requested intensities on three engines, with the motion each clip
actually shows measured, never assumed. It asks whether line drift rises with realised
motion within an engine (A10-H1), and whether Gen-4.5's gap to Wan 2.2 survives on cells where
the two engines moved by similar amounts (A10-H2).

#### A10.0 Status of any result derived from it — binding

1. A10 is **CONFIRMATORY**. A10-H1 replicates, by construction and with its direction stated in
   advance, an association first seen post hoc on the frozen corpus (A10.1). A10-H2 is
   confirmatory in the same sense.
2. A10 adds no headline metric. Its measures are the five frozen metrics, unchanged, and
   A6's motion tool, unchanged. The paper's five-metric claim stands.
3. A10 results may **qualify, condition or caveat** the frozen league. They may **not**
   restate, re-rank or replace it, and the §8 test is not re-run against them.
4. The pre-registered §8 test remains as reported: **null, ten of ten.**
5. Every threshold A10 uses is declared below where it is applied.
6. Ladder cells are reported as A10 cells wherever they appear. They are never pooled with
   the frozen corpus, and A10-H2 is never pooled with A9's masked-drift result: the two are
   different conditions (a motion band, a region).
7. The hypotheses are named A10-H1 and A10-H2 (A10) and A11-H3 (A11) wherever they are
   reported, the paper included: A9's H1 and H2 are different tests.

#### A10.1 Seen before registration

Seen by Aaron, by Claude (the agent that planned A10 and built its tools) or by both,
before registration:

- Everything A9.1 lists, and A9's registration (3 Nov 2026). At registration, A9's ratings
  were made and published on 6 Nov 2026. A10 to A12 were drafted on 4 Nov 2026, before A9's Test 2 and Test 1 results
  existed, and were not changed in the light of them; A13 was added after those results were read and
  says so in A13.1.
- Numbers computed on 4 Nov 2026 during planning, reproduced verbatim from the plan, not
  recomputed:

  > From the released per-clip JSONs (`runs/metrics/*.json`, `runs/metrics-motion/*.json`,
  > primary cells, FLINT and -r2 excluded), within-engine Spearman ρ between A6 realised
  > motion (`headline_median_norm`) and mean chamfer vs frame 0, n≈33 per engine: Gen-4
  > Turbo +0.58, LTX-2.3 +0.46, Gen-4.5 +0.43, H3 +0.38, Wan 2.2 −0.01; pooled n=164 ρ
  > +0.59. Also ρ(motion, edge |slope|) +0.12 to +0.36 and ρ(motion, style terminal) +0.23
  > to +0.54 on the four moving engines. Per-class median motion per engine was printed too
  > (Wan: IDLE 0.0009, BURST 0.0007, CAMPUSH 0.0008; Gen-4.5: IDLE 0.0025, CAMPUSH 0.0085,
  > BURST 0.0244). Wan's whole motion range (0.0005–0.0167) sits below the other engines'
  > medians: the league leader does not do the motion it is asked for.

  These numbers set A10's power assumptions, and they are why A10-H1 is registered with a
  direction: it replicates, by construction, an association already seen. They are also the
  source of the engine-specific expectation for Wan 2.2 in the registered predictions.
- The twelve ladder panels (A10.3), drawn on 4 Nov 2026 before registration. The draw is
  deterministic and reads no clip.
- The four ladder prompts, written by Claude on 4 Nov 2026 and revised at review the same
  day, before the pack was frozen (A10.3). None was tried on any engine.
- Synthetic test fixtures for every A10 tool. No ladder clip existed.

**Not computed by anyone before registration:** any ladder clip; any metric or motion value
on a ladder cell; the manipulation check; the common band; g_band or g_whole. The ladder
driver (`harness/ladder.py run`) refuses to generate, and the analysis
(`analysis/a10_ladder.py`) refuses to read real ladder data, until this amendment's heading
is in the public pre-registration. That is a tripwire, not a proof:
`harness/registration.py` reads a file.

#### A10.2 Frozen artefacts

`docs/A10-MANIFEST.sha256` (sha256 `1fe57d9bacc9b056ab30596eb2f95080789bbba447a386d45ac323f725c7ffa1`) lists, at their release paths
and hashed in release form, as A9.2's manifest is: the prompt pack
`harness/motion-ladder.md` and the frozen pack `harness/motion-prompts.md` (STILL is its
IDLE prompt); the twelve drawn panels in `dataset/panels/` and their line-art layers in
`dataset/lineart/` (`<panel>-lines.png`, the reference `metrics/inkstab.py` reads);
`harness/ladder.py`,
`harness/registration.py`, `harness/gen_video.py` (with `--pack` and `--seed`) and
`harness/runway_task.py` (the Runway client a seeded Gen-4.5 cell goes through),
`harness/pack_parser.py` and both ComfyUI graphs; `metrics/inkstab.py` and `metrics/motion.py`;
`analysis/draw_ladder_panels.py` and its output `analysis/out/a10_panels.json`; the cell
list `analysis/out/a10_cells.json`; `analysis/rank_stats.py` and `analysis/a10_ladder.py`;
and the tests of each.


#### A10.3 Design

1. **Prompt pack v2** (`harness/motion-ladder.md`, parsed by `harness/pack_parser.py` like
   the frozen pack). Four levels. STILL is the frozen IDLE prompt verbatim. LOW, MID and
   HIGH share one template and differ only in the words before "Camera locked off.": one
   fixed list of what moves (the drawn subject and any loose elements), scaled on three
   slots only, amount, distance and pace. The kind of action is never varied, so intensity
   is not confounded with action type, and no level asks for a body action that a panel
   without a figure would force an engine to invent. The camera sentence and the
   style-lock sentence are the frozen pack's, verbatim, on all four. Frozen here verbatim:
   - **STILL:** "Subtle idle motion only: gentle breathing, faint sway of cloth or foliage,
     slight ambient drift. Camera locked off. The image is a black-and-white inked drawing
     and must remain one in every frame — line weight, screentone dots, and flat black ink
     shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no
     added lighting effects."
   - **LOW:** "Small, slow subject motion: the drawn subject and any loose elements (hair,
     cloth, foliage, water, smoke) move a little from where they are drawn, slowly. Camera
     locked off. The image is a black-and-white inked drawing and must remain one in every
     frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn;
     no repainting, no photorealistic rendering, no colour, no added lighting effects."
   - **MID:** "Moderate, steady subject motion: the drawn subject and any loose elements
     (hair, cloth, foliage, water, smoke) move a clear distance from where they are drawn,
     at a steady pace. Camera locked off. The image is a black-and-white inked drawing and
     must remain one in every frame — line weight, screentone dots, and flat black ink
     shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no
     added lighting effects."
   - **HIGH:** "Large, fast subject motion: the drawn subject and any loose elements (hair,
     cloth, foliage, water, smoke) move a long way from where they are drawn, quickly.
     Camera locked off. The image is a black-and-white inked drawing and must remain one in
     every frame — line weight, screentone dots, and flat black ink shapes stay exactly as
     drawn; no repainting, no photorealistic rendering, no colour, no added lighting
     effects."

   A design note, declared before any clip: the STILL → LOW step also changes the sentence
   template (STILL's "Subtle idle motion only: …" against the shared ladder template), so
   any monotone-trend claim rests mainly on LOW, MID and HIGH, with STILL as the bridge to
   the frozen corpus. A10-H1 is unaffected: its regressor is realised motion, not the level.
2. **Panels.** 12 of the 27 core panels, drawn by `analysis/draw_ladder_panels.py` with seed
   20261104: 4 per content class, 4 per ink treatment, every class × treatment cell at least
   once, so three cells, one per class and one per treatment, give two panels. The two A1
   panels are excluded (their class rows are unbalanced). The draw is uniform over the
   118,098 admissible draws (6 assignments of the three doubled cells × 3^9 ways to fill the
   nine cells), and its record carries the Python version it ran under (3.12.10), because
   the standard library's random stream is defined per version; a test ties the shipped
   record to a fresh run of the code. Drawn before registration: `act-black-1`,
   `act-line-2`, `act-tone-1`, `act-tone-3`, `cu-black-2`, `cu-black-3`, `cu-line-3`,
   `cu-tone-1`, `est-black-3`, `est-line-1`, `est-line-2`, `est-tone-3` (cells giving two
   panels: `act-tone`, `cu-black`, `est-line`).
3. **Cells.** 12 panels × 4 levels = 48 cells per engine on Wan 2.2 TI2V-5B and LTX-2.3
   (open weights on a rented GPU, hardware recorded per clip as A2; seed 20260812, as §5)
   and Gen-4.5 (Runway; sent seed 20260812, as §5, recorded in each manifest line; one draw
   per cell: Runway accepts a seed, but its own words are that the same seed gives "similar
   results", so on Runway a seed fixes the request, not the bytes): 144 clips, 5 s, 1280:720
   requested (the local engines run 1280×704, A1). Gen-4 Turbo and MiniMax H3 are not run
   (budget; and H3's draw-to-draw variance, shown by the repeat probe, would swamp a 48-cell
   ladder). Cell ids `ladder-<panel>_<still|low|mid|high>_<wan22|ltx23|gen45>`; clips
   `runs/<engine>/<cell id>.mp4`; manifest lines as standard plus `prompt_pack` (Gen-4.5's
   also carry the request as sent, its seed included, and Runway's task id and task record);
   inkstab JSONs in `runs/metrics-ladder/` and motion JSONs in `runs/metrics-motion-ladder/`. The
   primary corpus folders are untouched. The full list is `analysis/out/a10_cells.json`.
   All 48 ladder cells of a local engine run on one machine, named in every manifest line
   (the driver refuses a local run unless `INKBENCH_HW` names it), after that engine's A12
   draws (A12.3). A12's lost-machine rule (A12.3.1) does not apply to ladder cells; a ladder
   that spans machines is flagged (A10.4.5). If a lost machine's ground series is re-run
   (A12.3.1) after that engine's ladder cells made on the lost machine were kept, the ladder
   precedes the series and ran on another machine; the paper reports this, and it changes no
   reading.
4. **Refusals.** §5's rule, as `harness/ladder.py` applies it: a hosted cell that fails is
   resubmitted once, identically, and is recorded as refused only when both attempts end in
   a task-level FAILED outcome from Runway; n is stated. Any other failure is a harness
   fault, fixed and resumed, and a CANCELLED task stops the run. A local-engine failure is
   always a harness fault, never a refusal.
5. **Realised motion** is `metrics/motion.py`'s `headline_median_norm` (A6's definitions,
   unchanged), never the prompt level. The prompt level is the manipulation; realised motion
   is the regressor.
6. **Measurement.** Every metric, for A10 and A12 alike, runs on the study Mac
   (Apple-silicon mps), as the frozen corpus (inkstab) and A6 (motion) were measured;
   `metrics/motion.py` has no CUDA path. The rented GPU generates only.

#### A10.4 Analysis (`analysis/a10_ladder.py`)

**Coverage, read with the manipulation check.** Per engine, the expected cells are those of
`analysis/out/a10_cells.json`. A refused cell is listed and reduces n. Any other expected
cell without both a finite motion value and a finite mean chamfer is missing: it is listed,
never dropped silently, and every verdict it could touch reads "incomplete" instead (A10-H1,
A10-H2 below), with its numbers still reported.

1. **Manipulation check, read first and alone.** Per engine, the median realised motion at
   each level, over every non-refused cell with a motion value. It passes when at least two
   of the three steps STILL → LOW → MID → HIGH rise and the HIGH median exceeds the STILL
   median. An engine that fails it reads "manipulation failed" for A10-H1; its numbers are
   reported without a verdict. The check is printed (`a10_ladder.py --manipulation-only`)
   and logged before any drift number is read.
2. **A10-H1, per engine.** Spearman ρ(realised motion, mean chamfer vs frame 0) over the
   engine's ladder cells (48, less refusals), one-sided (ρ > 0), α = 0.05. p is a Monte
   Carlo permutation p, (k + 1)/(B + 1), over B = 10,000 permutations of the chamfer ranks,
   `numpy.random.default_rng(20261104)` fresh for each engine and metric; at n = 48 exact
   enumeration is not possible, and this p is valid. Readings, in this order:
   "incomplete: N cells missing" if a cell of the engine is missing; "no cells";
   "manipulation failed"; "undefined (fewer than 4 cells, or no variation)"; "supported" if
   ρ > 0 and p ≤ 0.05; otherwise "null". Each engine's A10-H1 is its own test at α = 0.05,
   uncorrected for the three engines, and all three are reported whatever they show.
   Secondary, without a verdict: the same ρ and p for edge |slope| and style terminal.
   Every ρ is reported with a percentile bootstrap 95% interval over cells (B = 10,000, the
   same seed). Power, by Fisher's z with variance 1.06/(n − 3), one-sided α = 0.05,
   n = 48: about 0.87 at ρ = 0.40 and 0.91 at ρ = 0.43 (A10.1 saw 0.38 to 0.58 on the four
   moving engines).

   What the reading measures, declared. Chamfer vs frame 0 (`metrics/inkstab.py`) is the
   symmetric mean distance between the line pixels of a frame and the line pixels of frame 0,
   averaged over the clip. It rises when intact lines move away from where frame 0 has them,
   as well as when lines break, blur or vanish. Realised motion (`metrics/motion.py`) is
   optical-flow magnitude, which also rises when lines move. Support for A10-H1 is therefore
   expected in part from how the metric is defined, on any engine that moves as asked. The
   readings that do not compare line positions are the two secondaries, and neither is a
   motion-free control. Edge |slope| is the size of the trend, over the clip, of the 95th
   percentile of gradient magnitude over each whole frame, normalised by frame 0's value; an
   intact line that moves within the frame does not by itself change it, but motion blur
   does. Style terminal is the distance between whole-frame image embeddings of the last
   frame and frame 0, and it changes when the content of the frame moves. A10-H2 does not
   remove displacement: it matches the two engines on realised motion, reading the chamfer
   gap on the cells whose realised motion lies in a band common to both, against the gap
   over the whole ladder.
3. **A10-H2, the gap on motion-matched cells.** The band is the overlap of Gen-4.5's and
   Wan 2.2's realised-motion interquartile ranges over their ladder cells (`np.percentile`,
   linear), fixed by this rule before any cell exists. g = log2(median chamfer Gen-4.5 /
   median chamfer Wan 2.2): g_band over the cells inside the band (bounds included), g_whole
   over all their ladder cells with a chamfer value. Supported if g_band ≤ ½ · g_whole with
   at least 8 cells of each engine in the band, read in the order of A10.5. A10-H2 is read
   whatever the manipulation checks show. This is A9's gap statistic applied to
   motion-matched cells; A9's masked-region result is reported beside it and never pooled
   with it.
4. **Pooling, declared.** A10-H1 and A10-H2 pool between- and within-panel variation;
   differences between panels can contribute to either, and the paper says so. Secondary,
   without a verdict: per engine, the A10-H1 ρ with a permutation p in which chamfer is
   permuted only within panel (the same B and seed), and the within-panel ρ (ranks centred
   on each panel's mean rank) with its one-sided p from the same permutations, fresh per
   engine, and the panel make-up of the A10-H2 band (the cells of each panel inside it, per
   engine), so a reader can see how much of either effect lies between panels.
5. **Model versions, reported.** Per engine, the distinct `model_version` strings of its
   non-refused expected cells (from `runs/manifest.jsonl`, the last line of a cell
   winning); on Wan 2.2 and LTX-2.3, the distinct machine names in them, flagged
   `hardware_mixed` when there is more than one. The flag is noted and changes no verdict.

#### A10.5 Kill rules and A10-H2's readings, applied in this order

The strings are the analysis's own.
1. "incomplete: N cells missing (Gen-4.5 and Wan 2.2)": a cell of either engine is missing
   (A10.4).
2. "not testable: Wan 2.2 does not move on request": the upper quartile of Wan's realised
   motion at HIGH is below every other engine's median at STILL (the engines compared are
   recorded). That is reported as the finding, beside A9's adherence result.
3. "not testable: fewer than 8 cells of an engine": fewer than 8 cells of Gen-4.5 or Wan 2.2
   with both values.
4. "undefined: the Wan 2.2 motion check cannot be made (<reason>)": no Wan HIGH cell, or
   another engine without a STILL cell.
5. "not testable: band too thin (fewer than 8 cells of an engine in the common band)",
   which covers interquartile ranges that do not overlap; the gap is then reported over the
   whole ladder only.
6. "not testable: no whole-ladder gap (g_whole <= 0)", which covers an undefined g_whole.
7. "undefined: g_band (a median chamfer in the band is not positive)".
8. "supported" if g_band ≤ ½ · g_whole; otherwise "not supported".

A null A10-H1 is reported as a null. No follow-up test is added on that engine, and an
A10-H1 null does not cancel A10-H2.

#### A10.6 Order that makes "before any clip" true

1. Tools, tests, the panel draw and the cell list (done before registration).
2. Registration: this amendment and its manifest committed, the public release refreshed in
   place, pushed without force and tagged `a10-registered`; within the hour, a Software
   Heritage save request.
3. Generation: LTX-2.3 and Wan 2.2 in one rented-GPU session, each engine's A12 draws first
   (A12.3); Gen-4.5 from the study Mac in steps of about £10, each with a ledger row.
4. Metrics on the study Mac; the manipulation check printed and logged first.
5. The analysis in one pass; results published in an in-place refresh.

#### A10.7 Cost

Gen-4.5: 48 × $0.60 = $28.80, about £22.50 at the ledger's pinned rate (re-pinned at
spend). The rented GPU: about £3 for the session shared with A12. One ledger row per batch;
Aaron is told at each further £10 of cumulative spend.

#### Registered predictions

- **A10-H1:** realised motion predicts line drift within an engine (ρ > 0), supported on LTX-2.3
  and Gen-4.5. On Wan 2.2 we expect the manipulation check to fail or A10-H1 to be null: Wan
  barely moved in the frozen corpus (A10.1).
- **A10-H2:** on motion-matched cells Gen-4.5's line-drift gap to Wan 2.2 shrinks by at least
  half, if a common band exists at all; kill rule 2 is a live possibility.

Stated plainly: we expect part of the league's gap to be the cost of moving. If instead drift
does not rise with motion, or the gap survives on motion-matched cells, the league reads more
strongly as a measure of holding the drawing, and that is the stronger result. Either outcome
is reported, and every reading above is reported whatever it shows.

### A11 — 2026-11-10: confirmatory replication of the §6 human check at power

**STATUS: APPROVED — Aaron's go recorded 2026-11-10 ("Go to register A10–A16 once the open fixes below are made and two-stage reviewed"), after an independent review of the drafts whose findings he ruled on; every fix was made and reviewed before registration. Registered 2026-11-10 (UTC) with A10, by the same tagged
public commit. Cost: about £81.77 in rater payments, the platform fee and VAT on it (A11.7).**

**Why this is an amendment at all.** It collects new ratings, from new raters, on clips §6
did not rate, through a changed delivery. Under the freeze rule that is a protocol change,
recorded here with its analysis before any rating exists.

**The problem it addresses.** §6, as A6, A7 and A8 revised it, ran with six raters on 20
clips. Its strongest result, edge |slope| against the "same image" question (ρ = −0.74,
p = 0.0002, 95% CI [−0.89, −0.43], n = 16), was strong but small, and no hypothesis had been
registered for it. A11 replicates the check at twice the clips and twice the raters, with
the author not rating, and registers that result as a directional test (A11-H3).

#### A11.0 Status of any result derived from it — binding

1. A11-H3 is **CONFIRMATORY**. Everything else A11 reports (the other headlines, both questions,
   Krippendorff's α, the baseline, A11-H3's secondary reading against −0.5) is reported as §6
   reports it, with intervals and without a verdict.
2. A6's published numbers stand as the pilot. A11's ratings are never pooled with A6's.
3. A11 adds no headline metric and changes no frozen definition. Its results may qualify
   the frozen metrics' validity; they may not restate, re-rank or replace a frozen result,
   and the §8 test is not re-run against them. §8 remains **null, ten of ten.**
4. Every threshold A11 uses is declared below where it is applied.
5. A7's rule holds: rater data are collected and held in the private rating app.
   Pseudonymised scores, attention answers and the order each rater saw enter the private
   repository; the public release ships scores and attention answers only, sorted by code.
   Timings, answer timestamps, comments and any platform identifier enter neither.

#### A11.1 Seen before registration

- §6's results as published (`analysis/human_check/human_check_results.json`), and
  everything A9.1 and A10.1 list.
- The A11 subset (A11.3), drawn on 4 Nov 2026 before registration. The draw is deterministic
  and reads only the strata labels (engine, class, motion) of the results table.
- The opaque codes and the two attention clips, assigned the same day from the same seed.
- Tests that run A11's analysis on A6's own ratings re-pointed. They assert only that it
  reproduces A6's published numbers, and that A11-H3's ρ equals A6's; they print nothing else.
- Synthetic fixtures for every other test.
- Facts about §6, found while building A11 and disclosed here:
  - **A6's served clips carried the engine in their file metadata.** All 20 clips A6 served
    still held provenance inside the file: signed content-credential (C2PA) metadata naming
    Runway or fal.ai on the hosted engines' clips, and the generator's workflow settings
    naming the Wan or LTX model on the local engines' clips. A rater who opened a file in a
    metadata tool could have read the engine. No A6 rater is known to have done so. This is
    a disclosure, not a correction: A6's media and numbers stand as published, and the
    paper's limitations state the gap. A11's served clips carry no metadata (A11.3.6).
  - **Five of A6's served clips had sound.** The five fal clips carried an AAC audio track;
    the others were silent, and the page lets a rater unmute, so a rater who did could have
    told those clips apart. A11 serves the video stream only (A11.3.6).
  - **The encoder's version string differs by engine family.** The x264 version string in
    the video stream reads core 159 on the Runway clips, 163 on the fal clips and 165 on
    the local engines' clips, in A6's clips and in A11's. It can be read only with a media
    inspector. It is left in place in A11 (A11.8).
  - **§6's draw did not reproduce in the public release.** `analysis/draw_subset.py` sorted
    the private cell ids before its shuffle; the release renames the creator-IP panel, whose
    cells then sort elsewhere, so the released script drew other cells than §6's record. The
    script now keeps the frozen sort order in either tree. §6's draw and its record
    (`analysis/out/human_subset.json`) are unchanged (tested byte for byte), and the
    release's errata state the fix.

**Not computed by anyone before registration:** any A11 rating, and so every A11 number.
The delivery pilot (A11.6) uses two real raters after registration.

#### A11.2 Frozen artefacts

`docs/A11-MANIFEST.sha256` (sha256 `f337dbc819b46edcce225af1543a0565df9f0e9a7c8f29db04716eae0b90dae6`) lists, in release form:
`analysis/draw_subset.py` and its test; its inputs `analysis/out/results_table.json` and
`analysis/out/human_subset.json`; its output `analysis/out/a11_subset.json`;
`analysis/human_check/collect.py` (A6's analysis, refactored into functions with its output
unchanged byte for byte) and `analysis/human_check/build_harness.py` (the instrument's
single source); in `analysis/human_check2/`, `build_mapping.py`, `mapping.json`,
`baseline_mapping.json`, `collect.py` and `README.md`; `analysis/rank_stats.py`;
`harness/registration.py` (the tripwire); the tests of each; and the rating app's hash file of the built pages, the orders and every stimulus, `analysis/human_check2/instrument.sha256` (sha256 `4d913c6bbf4c6e424f1765ed529f3dfc32802f5c4a1e8a11dd4067883add0c2b`; the clips were stripped with ffmpeg 9.0.2 and are byte-reproducible only with that version).

#### A11.3 Design

1. **Subset.** 40 clips from the 164 standard cells of §6 less the 20 that §6 drew (FLINT
   excluded, the refused cell absent): 144 candidates; every engine at least 6, every content
   class at least 12, every motion class at least 12; seed 20261104 (`seed_used`
   20261104), by the registered command

   `python analysis/draw_subset.py --protocol a11 --n 40 --seed 20261104 --exclude analysis/out/human_subset.json --min-engine 6 --min-class 12 --min-motion 12 --out analysis/out/a11_subset.json`

   (`--protocol a11` alone is the same run: the protocol's presets cannot be changed).
   Strata of the draw: engine Gen-4.5 8, Gen-4 Turbo 10, MiniMax H3 7, LTX-2.3 8, Wan 2.2 7;
   content class act 15, cu 12, est 13; motion BURST 13, CAMPUSH 15, IDLE 12. Ladder clips
   are not in it: A11 replicates §6, and the ladder is a separate claim. The script sorts
   A11's candidates by public id before the shuffle, so the draw reproduces in the public
   release; §6's own draw keeps its frozen order, and the same script reproduces it in both
   trees (tested; A11.1).
2. **Instrument.** §6's questions as A6 and A8 left them: Q1 (register) and Q2 ("same
   image") with their labelled five-point scales and guidance, and the per-panel baseline
   (Q3) asked first, verbatim, for every source panel of the 40 clips. The single source is
   `analysis/human_check/build_harness.py`; the rating app imports it, and its verifier
   asserts byte equality. Clip and baseline order per rater by fixed seed (20261104, drawn
   per slot); engine identity hidden; the
   source panel shown beside each clip.
3. **Codes.** Clips c21 to c60 and panels p15 to p35 (21 panels), after A6's c01 to c20 and
   p01 to p14, so no code means two things (`analysis/human_check2/build_mapping.py`, seed
   20261104). The baseline covers exactly the distinct source panels of the 40 clips; the
   rating app's build refuses if its panel list and this mapping disagree.
4. **Attention items.** Two of the 40 clips, c35 and c55, are shown a second time to every
   rater; the second answers are recorded apart from the first. The two originals are
   the seeded draw of 4 Nov 2026 (`analysis/human_check2/build_mapping.py`, seed 20261104),
   registered in `analysis/human_check2/mapping.json` (`attention_clips`,
   `attention_rule`). The repeats carry their own codes, c61 (of c55) and c62 (of c35),
   inserted at positions 22 and 38 (1-based) of each rater's sequence, each at least 5
   places after its original, so a rater sees 42 items. The rating app's build refuses
   until its config agrees with `mapping.json`.
5. **Raters.** Twelve, recruited on Prolific (pre-screen: normal or corrected vision,
   desktop, English fluency; no other screen), one to each opaque slot R8 to R19, each
   through their own link. The author does not rate. Reserve slots R20 to R23 serve the one
   top-up batch (A11.5) and no other purpose. A TEST slot is used only to check the deployed
   app; its rows are deleted after each check and never analysed. The platform's participant
   id never enters this repository. Two raters rate first, as a pilot of the delivery; their
   ratings count if the instrument did not change between the pilot and the rest, which
   means the built pages' hashes (A11.2) are the same for both. About 30 minutes each (the
   page's stated total, A11.3.6), paid at Prolific's recommended rate.
6. **Delivery (conditions, not content, as A7).** The hosted rating app gains a per-slot
   token link; a consent and data-handling screen before the baseline task (what is
   collected, that ratings are published under opaque slots, that no names are collected,
   that a rater may withdraw by closing the tab before submitting); and a completion page
   that shows the platform's completion code only after the app confirms the ratings were
   stored. A11 serves each clip's video stream only, with no audio track and all file
   metadata stripped, without re-encoding. The build accepts a clip only after checking
   that its video-packet md5 equals its source clip's (the released clip, byte for byte), that its container tags are empty
   and that no provenance byte pattern remains; every served image is scanned the same way.
   The instrument hash (A11.2) covers the stimuli (the clips and the panel images) as well
   as the pages, the orders and the config (A11.1). The rating page is A6's hosted page, built unchanged from the single
   source, with thirteen declared text changes, each applied where its old text occurs
   exactly once (the app's build stops otherwise). Before → after:
   1. "Rating 20 short clips — about 20 minutes" → "Rating 42 short clips — about 25
      minutes" (the heading: the clip part's count and duration).
   2. "Rating task — about 25 minutes" → "Rating task — about 30 minutes" (total
      duration).
   3. "Part 1 — 14 still drawings." → "Part 1 — 21 still drawings." (the overview's
      drawing count: every source panel of the 40 clips).
   4. "Part 2 — 20 short clips" → "Part 2 — 42 short clips" (the overview's clip count).
   5. "Two questions about each. Roughly 20 minutes." → "Two questions about each.
      Roughly 25 minutes." (the clip part's duration in the overview).
   6. "This saves a small file called `ratings-<slot>.json` — please send it back to
      Aaron." → "Press "Copy my answers", then paste the text into a message to the
      researcher on Prolific." (the failed-send hint: platform raters cannot email, and a
      Prolific message takes text, so the page shows the answers instead of offering a
      file).
   7. "Please use the download button below and send Aaron the file." → "Your answers are
      not lost. Please copy the text in the box below and paste it into a message to the
      researcher on Prolific. Then finish the study on Prolific without a completion code;
      you will still be paid." (the same fallback, in the failure message).
   8. The "Download my answers instead" button → a read-only box ("Your answers, to copy")
      with a "Copy my answers" button (the box replaces the file download).
   9. On a failed send, the page now also fills that box with the same JSON it submits
      (`JSON.stringify(payload())`), beside showing the hint.
   10. The stored row's `instrument: "A6", delivery: "hosted-A7"` → `instrument: "A11",
       delivery: "hosted-A11"` (which study and delivery the row came through).
   11. On a successful send, "Sent — thank you. Nothing else to do." → no message; the page
       waits for the server's reply and fails unless it carries a completion code, then
       shows the completion card (the server releases the code only after the database
       confirms the row).
   12. A completion card is added, hidden until the code arrives: "Your answers are saved —
       thank you", "Your Prolific completion code is:", the code, a "Return to Prolific ▶"
       link, and "If the button does not work, copy the code above into Prolific. You can
       close this tab afterwards."
   13. The completion card's script is added (it shows the card and sets the return link),
       with the Copy button's handler (it copies the box, then says "Copied. Now paste it
       into a message to the researcher on Prolific.", or, where the browser blocks copying,
       asks the rater to press Ctrl+C or Cmd+C on the selected text).

   The pasted text is the page's own submission, so it carries the per-item timings and the
   comment as well as the answers, as the consent page states. The study's runbook imports
   it under its slot through the live app, which validates it and stores the row exactly as
   for a normal send.

   No question, scale label or guidance note changes, and the order rules are unchanged;
   the app's verifier asserts that every instrument string survives verbatim.

#### A11.4 Analysis (`analysis/human_check2/collect.py`)

In this order, the first two before any correlation:
1. **Completeness.** A rating file must answer every shown item on both questions: the
   first showing of each of the 40 clips and the repeat of each attention clip, 42 items.
   A rater with any missing or invalid answer, on a repeat or anywhere else, is excluded
   as incomplete, and the count is reported.
2. **Attention.** Read only on two recorded repeats (rule 1 guarantees them): an attention
   item fails when the repeat's answer differs from the first showing's by two or more
   scale points on either question. A rater who fails both items is excluded, and the count
   is reported. Rules 1 and 2 are the only rules that exclude a rater: no rater is excluded
   on time (A11.5). Only first showings enter any correlation.
3. **§6's analysis, unchanged** (A6's code, imported): per question, Krippendorff's ordinal
   α, and Spearman ρ of each frozen headline against the clip's mean rating with a bootstrap
   95% interval (tone where it is defined), seed 20261104. Only where A6's code would stop
   on a bootstrap with no finite resample (a constant side), a line-for-line copy of its
   loop, drawing the same numbers, reports that metric's ρ and interval as None instead;
   A6's own file is untouched, and a test pins the copy to A6's output.
4. **A11-H3.** Spearman ρ(edge |slope|, mean "same image" rating) over the 40 clips ≤ −0.4,
   one-sided, α = 0.05, by a bootstrap over clips (B = 10,000, `default_rng(20261104)`):
   p = (#{ρ* ≥ −0.4} + 1)/(n_finite + 1). Readings: "supported" if p ≤ 0.05, otherwise
   "not supported"; "undefined (fewer than 4 clips, or no variation)"; "undefined (no
   finite bootstrap replicate)". A11-H3 is read with any n ≥ 4 clips' means; n is stated.
   Reported with ρ, its 95% interval and its one-sided upper bound. The bound −0.4 is the
   smallest correlation that would make edge decay usable as a proxy for perceived
   sameness (in A6 the non-significant line-drift ρ was −0.42 and the weakest significant
   metric −0.54). Power, by Fisher's z with variance 1.06/(n − 3), n = 40: about 0.93 if the
   true ρ is A6's −0.74. Secondary, without a verdict: the same bootstrap p against −0.5,
   from the same resamples, with the same readings (power about 0.77 at −0.74).
5. **Register, baseline-filtered (secondary, declared).** Q1 is analysed again on the clips
   whose panel's baseline mean (Q3, included raters) is at least 2.5. A8's difference-score
   remedy is not re-run: it failed in A8 and is reported as failed.
6. Krippendorff's α of the baseline question.

#### A11.5 Kill rules

1. α(sameness) < 0.3 across the included raters: reported, and A11-H3 is still tested (the
   unit of analysis is the clip).
2. Fewer than 10 included raters (complete, and not excluded by the attention rule) after
   one top-up batch (slots R20 to R23): the analysis runs on those included, and n is
   stated.
3. Telemetry stays observational, as A7 and A8 bind it: no rater is excluded on time, dwell
   or answer timestamps.

#### A11.6 Order

1. Subset, codes and attention clips (done before registration); the rating app built and
   verified for the twelve slots, the reserve and the TEST slot, its pages hashed into the
   manifest.
2. Registration, with A10.
3. Two pilot raters; their submissions checked for order and baseline; ten more; one top-up
   batch if fewer than ten raters are included. Only the completeness and attention rules
   are applied before that decision, and no correlation is computed.
4. Ratings fetched from the app and pseudonymised to their slots, R8 to R19 (and R20 to R23
   if the top-up runs): scores, attention answers and the order each rater saw, into
   `analysis/human_check2/ratings/` in the private repository. The public release ships
   scores and attention answers only, sorted by code.
5. The analysis in one pass; results published in an in-place refresh.

#### A11.7 Cost

About £81.77 for twelve raters at about 30 minutes a sitting. Each rater is paid £4.50, at
£9 an hour; the rate is confirmed on Prolific's screen. The rewards, £54.00, carry
Prolific's fee of three sevenths of the rewards (£23.14) and VAT at 20% on the fee (£4.63).
The two pilot raters cost £13.63 and the ten after them £68.14. A top-up of up to four adds
£27.26. No generation.

#### A11.8 Limits

The x264 encoder version string inside each clip's video stream is left in place, so the
engine family (Runway, fal, local) remains readable to a rater who opens a clip in a media
inspector. Removing it would change the video stream, and the stimuli could then be checked
against the released clips only by comparing decoded frames, not packet hashes. No rater
is asked to inspect files, and the paper's limitations state this.

#### Registered prediction

- **A11-H3:** ρ(edge |slope|, mean "same image" rating) ≤ −0.4, near A6's −0.74.

Stated plainly: we expect the strongest §6 result to hold at twice the clips with new raters.
If it does not, the metric's validity against people rests on the six-rater pilot alone, and
the paper says so. Either outcome is reported.

### A12 — 2026-11-10: descriptive: the grey-ground series with a noise floor

**STATUS: APPROVED — Aaron's go recorded 2026-11-10 ("Go to register A10–A16 once the open fixes below are made and two-stage reviewed"), after an independent review of the drafts whose findings he ruled on; every fix was made and reviewed before registration. Registered 2026-11-10 (UTC) with A10, by the same tagged
public commit. Cost: about £2 hosted, plus a share of A10's rented-GPU session (A12.6).**

**Why this is an amendment at all.** It adds 40 cells: three fresh draws of A3's five ground
variants on Wan 2.2 and LTX-2.3, on one machine, and two further draws on Gen-4 Turbo.

**The problem it addresses.** A3's series is one draw per step, and the repeat probe that
followed showed that a single draw can move by more than a whole dose step on some engines;
`analysis/out/ground_response.md` set a readability rule for that reason. A12 measures the
draw-to-draw spread at each step, so the dose effect can be read against a noise floor
measured on the same cells.

#### A12.0 Status of any result derived from it — binding

1. A12 is **DESCRIPTIVE**, with a registered read-out (A12.4). It makes no inferential claim;
   its permutation p is descriptive support.
2. It may qualify A3's dose-response; A3's single-draw figures stand as reported.
3. It restates no frozen result; the §8 test remains **null, ten of ten.**

#### A12.1 Seen before registration

- A3's series and `analysis/out/ground_response.md`; the repeat probe
  (`analysis/out/repeat_stability.md`); A6's ground check in `motion_confound.md`; and
  everything A9.1 and A10.1 list.
- Two provenance facts about A3's cells, found while planning A12, which shape the design:
  - **Hardware.** A3's Wan 2.2 cells ran on a rented RTX A6000 (ledger, 14 Aug 2026) and its
    LTX-2.3 cells on the study Mac (their manifest lines carry no hardware tag and 38 to 50
    minutes of wall time each). A3's local cells therefore cannot be draw 1 of a
    same-hardware series. On Wan 2.2 and LTX-2.3 all three of A12's draws are fresh, on one
    rented GPU in A10's session, and A3's cell is reported beside them as a separate point
    labelled `a3` (other hardware), never in the noise floor or the ρ. On Gen-4 Turbo,
    hosted, A3's cell is draw 1.
  - **Wan 2.2's five A3 manifest lines are missing.** The five Wan cells were generated on
    the pod, whose own manifest received their lines; that file was copied back to a
    temporary location and never merged into `runs/manifest.jsonl`. The clips and their
    metrics are released; the generation is recorded in the run log and the ledger.
    They are left absent, and this paragraph is the record.
- Synthetic fixtures only for A12's analysis. No further draw existed.

**Not computed by anyone before registration:** any A12 clip or value; any noise floor or
reading.

#### A12.2 Frozen artefacts

`docs/A12-MANIFEST.sha256` (sha256 `97702e9a49103d1f7f8f44d4054c5372bbd2d684d788c3d960bc2d7e24d2b1f9`) lists, in release form:
`harness/ground_series.py` (with `--draw` and `abandon`), `harness/gen_video.py`, `harness/runway_task.py`
(the Runway client a seeded Turbo draw goes through), `harness/registration.py` and their
tests; `harness/pack_parser.py`, the frozen pack `harness/motion-prompts.md` and both ComfyUI
graphs; the five variant panels
`dataset/panels/ground-cu-line-1-v{100,090,080,065,052}.png` and their line-art layers
`dataset/lineart/ground-cu-line-1-v{100,090,080,065,052}-lines.png` (the reference
`metrics/inkstab.py` reads); A3's fifteen metric files of
the three engines in `runs/metrics-ground/` (Gen-4 Turbo's draw 1, and the `a3` points of
the local engines); `metrics/inkstab.py`; and `analysis/rank_stats.py`,
`analysis/a12_ground_repeats.py` and their tests.

#### A12.3 Design

1. The five A3 variants `ground-cu-line-1-v{100,090,080,065,052}`, IDLE, frozen prompt and
   settings. Wan 2.2 and LTX-2.3: draws 1, 2 and 3, all fresh, on one rented GPU, at seeds
   20260812, 20260813 and 20260814 (§5's seed plus 0, 1 and 2); 15 new clips per engine. A
   local draw refuses to run unless the machine is named (`INKBENCH_HW`), so the same-hardware
   claim is in every manifest line. Each local engine's three draws run on one machine, before
   its ladder cells. Draws are never mixed across machines. **A lost machine.** A machine is
   lost when the provider evicts or terminates it of its own accord, or when it stops
   answering or fails and does not come back, and the fifteen draws of an engine's series,
   with their manifest lines, cannot then be retrieved to the study Mac. A series retrieved
   whole is merged as it stands. A machine stopped for any other reason, the session's budget
   among them, is not lost: what of its series can be retrieved is merged as it stands, and
   nothing is re-run. The first time an engine's series is lost this way, it is re-run whole,
   once, on one fresh machine, with the same cell ids and the same seeds. The lost series is
   written to the manifest as abandoned (machine lost): one line for each of its fifteen
   cells, with no output file (`ground_series.py abandon`). Whatever clips of it could be
   retrieved are kept privately. They are never measured, analysed or released; only the
   manifest lines ship. The read-out reports that the series was re-run (A12.4), and that
   changes no reading. If the fresh machine is lost as well, the series is not re-run again:
   the draws it made whose clips and manifest lines both come back enter the series as they
   stand, and the series reads "incomplete: N points missing" (A12.4). A12's rule covers the
   ground draws only; the ladder keeps A10's (A10.3.3). Gen-4 Turbo: A3's cell is draw 1 (it
   was sent no seed), plus draws 2 and 3, sent seeds 20260813 and 20260814 (§5's seed plus 1
   and 2, as on the local engines), each recorded in its manifest line. Runway accepts a seed,
   but its own words are that the same seed gives "similar results", so on Runway a seed fixes
   the request, not the bytes, and each submission is a fresh draw; 10 new clips. A3's Turbo
   draw dates from 14 Aug 2026, and Runway may have changed the model it serves since; each
   draw's model version, from its manifest line, is reported beside the read-out. §5's refusal
   rule applies to each Turbo draw as `harness/ground_series.py --draw` applies it, the same
   rule as A10.3.4: one identical resubmission, and a refused manifest line only when both
   attempts end in a task-level FAILED outcome from Runway; any other double failure stops the
   run, and n is stated. 40 new clips in all.
2. File stems come from one helper, `ground_series.draw_stem`: the local draws carry `-d1`,
   `-d2` and `-d3`; Gen-4 Turbo's draw 1 is A3's unsuffixed cell and its further draws carry
   `-d2` and `-d3`. Clips `runs/<engine>/<stem>.mp4`; metrics in `runs/metrics-ground/`,
   computed on the study Mac (A10.3).
3. Gen-4.5 and MiniMax H3 are not extended (A3 found Gen-4.5 flat and H3's series
   unreadable).

#### A12.4 Read-out (`analysis/a12_ground_repeats.py`)

Per engine and metric (mean chamfer vs frame 0 is the read-out; edge |slope| and style
terminal get the same read-out and readings, as secondary; tone excluded, as the paper's
limitations explain): Spearman ρ of the metric against k over the series' 15 points, with a
two-sided Monte Carlo permutation p (B = 10,000, `default_rng(20261104)`, fresh per engine
and metric) as descriptive support; at each step, the range across draws; the noise floor,
the median of those five ranges; the dose effect, the median at k = 0.52 minus the median
at k = 1.00. Readings, the analysis's own strings: "monotone claim allowed (darker ground,
more drift)" or "monotone claim allowed (darker ground, less drift)" where |dose effect|
exceeds twice the noise floor, the sign of the dose effect giving the direction; otherwise
"not readable at three draws" (A12.5); and "incomplete: N points missing" for a series with
any of its 15 points absent, its numbers still reported. Whether ρ's sign agrees with the
dose effect's direction (`rho_agrees`) is reported and changes no reading. On the local
engines A3's point is shown beside the series, labelled `a3`, and enters neither the noise
floor nor the ρ. Each draw's `model_version` (from `runs/manifest.jsonl`, the last line of a
cell winning) is reported per draw, and the `a3` point's beside it; per local engine the
distinct machine names in those strings are reported, flagged `hardware_mixed` when there
is more than one. The flag is noted and changes no reading. An abandoned manifest line
(A12.3.1) is never a draw: it gives no model version, and its clip and metrics are never
read. Per local engine, whether its series was re-run after a lost machine is reported
(`series_rerun`), and that changes no reading either.

#### A12.5 Kill rule

Where |dose effect| ≤ twice the noise floor, the engine reads "not readable at three
draws", and that is reported. No fourth draw is taken.

#### A12.6 Cost

Gen-4 Turbo: 10 × $0.25 = $2.50, about £2. The 30 local draws share A10's rented-GPU
session. A re-run after a lost machine (A12.3.1) adds about an hour of pod time, under £2.
One ledger row per batch.

### A13 — 2026-11-10: confirmatory: adherence at power

**STATUS: APPROVED — Aaron's go recorded 2026-11-10 ("Go to register A10–A16 once the open fixes below are made and two-stage reviewed"), after an independent review of the drafts whose findings he ruled on; every fix was made and reviewed before registration. Registered 2026-11-10 (UTC) with A10 to A12, by the same tagged public
commit. Cost: about £109.03 in rater payments, the platform fee and VAT on it for twelve raters,
budgeted at £110 to £125 (A13.7). No generation.**

**Why this is an amendment at all.** It collects new ratings, from new raters, of the 110 clips A9's
Test 1 rated, through a changed delivery, and tests a hypothesis A9 did not register. Under the freeze
rule that is a protocol change, recorded here with its analysis before any rating exists.

**The problem it addresses.** A9's Test 1 asked whether the steadier an engine, the more often it fails
to do the requested motion. It was not supported: AARON ρ = −0.90 (p = 0.042), R7 ρ = −0.50
(p = 0.225). With five engines the rank test passes only at ρ ≤ −0.9, so one swap in the middle sinks
it. A9's within-row check, which carried no verdict, found the clip-level version for both raters: on
the same drawing, the clips that drift more were rated as doing the motion more (mean within-row ρ 0.54
and 0.38, p ≤ 0.0002). A13 tests that clip-level claim confirmatorily, with naive raters and enough of
them. A9 is not re-run and no rater is added to A9.

#### A13.0 Status of any result derived from it — binding

1. A13-H4 is **CONFIRMATORY**. Everything else A13 reports (the engine-level statistic, the miss rates,
   Krippendorff's α, A9's weighted κ, the mixed model, A9's motion AUC on these clips) is reported with
   intervals where they exist and without a verdict.
2. A9's results stand as recorded. A13's ratings are never pooled with A9's, and A9's Test 1 verdict is
   not revisited.
3. A13 adds no headline metric and changes no frozen definition. It may qualify how the league is read;
   it may not restate, re-rank or replace a frozen result, and the §8 test is not re-run against it.
   §8 remains **null, ten of ten.**
4. Every threshold A13 uses is declared below where it is applied.
5. A7's rule holds: rater data are collected and held in the private rating app. Pseudonymised scores,
   attention answers and the order each rater saw enter the private repository; the public release
   ships scores and attention answers only, sorted by code. Timings, session ids and any platform
   identifier enter neither.

#### A13.1 Seen before registration

- Everything A9.1, A10.1 and A11.1 list, and A9's results as recorded on 2026-11-06, including both
  raters' ratings of these 110 clips, Test 1's statistics, the within-row check (mean ρ 0.54 and 0.38)
  and the per-engine miss rates. A13 was added to the plan after those results were read, and its
  hypotheses were set with them in view; A10 to A12 were drafted before them (A10.1).
- The two A13 studies, written and built on 8 Nov 2026, before registration, from A9's instrument with
  new seeds (commits 23bb2b0 and 4ec616a), and their codes and the four attention clips, drawn by the
  declared seeded draw: in the burst study, position 30 `cjh38d` repeats `cdzcnq` (`est-line-2_burst_h3`) and position 52 `c2zked` repeats `c0yvb5` (`act-black-3_burst_wan22`); in the push study, position 30 `cxkg5q` repeats `cgw7bk` (`est-black-1_campush_wan22`) and position 52 `cydfer` repeats `cdbvcs` (`est-line-3_campush_gen45`). The draw reads only the clip ids. Both studies were rebuilt
  on 9 Nov 2026 on blindpanel 0.3.1 with A13's own privacy line (commit 3bba702), with the same wording
  hashes (A9's) and codes as the 8 Nov build; their build trees are
  `c53fdc74bd7f58b45dbbcb2ff74591fcefc95d11ec7fed5397e2ac9566e50d33` (a13-burst) and
  `220a19d278f4ed5ba009f842c95afe6ff52b7dbf41d24d532d142d9613239b18` (a13-push).
- Every rater's order: derived before registration from the order seed and the slot (A13.3), by the
  same code the server checks with. The orders read no rating.
- Synthetic fixtures for every test. No test reads an A9 or A13 rating.

**Not computed by anyone before registration:** any A13 rating, and so every A13 number; the pooled
clip-level ρ of A13-H4 on A9's own ratings.

**After registration.** The rating app's checks that store rows through the live deployment with the
operator slot `TEST13` precede the pilot: the scripted end-to-end check and the author's own pass
through the live pages; the scripted check runs again after any later redeploy. Every row they store
holds the answer 3 on every item; each check's rows are deleted when it ends and are never analysed. No
clip is rated for its content in either.

#### A13.2 Frozen artefacts

`docs/A13-MANIFEST.sha256` (sha256 `69dbc5b678b97fe25c6d1b65af08bcb6628303bd60d07f96f916517b19d1d091`) lists, in release form:
`analysis/a13_adherence.py` and its test; `analysis/a13_mixed.R` and `analysis/a13-r-lock.txt`
(R 4.6.2; ordinal 2026.7.26, ucminf 1.2.3, numDeriv 2016.8.1.1, Matrix 1.7.6); `analysis/a9_adherence.py` (A9's cells, steadiness, exact test and Wilson interval,
weighted κ, load_motion and motion_check, imported); `analysis/rank_stats.py` and its test;
`analysis/human_check/collect.py` (the ordinal α); the inputs `analysis/out/results_table.json` and the
110 released motion files `runs/metrics-motion/<cell>.json`; A9's `analysis/adherence/prepare.py`,
`rating-copies.sha256` and both A9 `study.lock.json` files; in `analysis/adherence_a13/`, `build_a13.py`
and its test, `README.md`, `mapping.json`, `build-trees.json` and, per study, `study.yaml`,
`study.lock.json`, `banned-terms.txt` and `media-sources.json`; `harness/registration.py` and its test;
and the rating app's two hash lists, `analysis/adherence_a13/instrument.sha256` (sha256 `04ff324fbfccef667a42688fdc162115fd59b867a772a92b8bfa1f1bab3f529c`: its
pages, orders, handler, middleware and vendored kit) and `analysis/adherence_a13/served.sha256` (every
study file it serves). The studies run on blindpanel 0.3.1 (tag `v0.3.1`, tag commit `b291fc4b566ec96a07be54b323031ff4b5ba631b`, tarball sha256 `fe34aee66661785d5d1c6f36b8e9095c121467c7d22150aaebe50eccbe9b0356`); the two builds' tree hashes are
`c53fdc74bd7f58b45dbbcb2ff74591fcefc95d11ec7fed5397e2ac9566e50d33` (a13-burst) and `220a19d278f4ed5ba009f842c95afe6ff52b7dbf41d24d532d142d9613239b18` (a13-push). The rating app writes the two hash lists after its A13 build. The instrument hash file has
its own hash above; `served.sha256` has none of its own and is covered by the manifest hash. In the release,
`analysis/adherence_a13/` ships exactly the files listed here and its ratings as scores and attention
answers only (A13.0.5); its links to A9's rating copies, its two blindpanel builds and its raw rating
files never ship. `analysis/out/a13_mixed.json` ships with the analysis outputs and is not re-run by the
release, which has no R.

#### A13.3 Design

1. **Clips.** A9's Test 1 clips: the 110 primary burst and camera-push cells, 22 per engine, in 22 rows
   (a panel and a motion class; 11 burst and 11 camera-push rows on 20 drawings, since two drawings
   appear in both studies). The rating copies are A9's own files, byte for byte (`rating-copies.sha256`).
2. **Instrument.** A9's two studies and A9's question, verbatim: "The clip was asked for this motion:
   … Does the clip do it?", the same scale labels, notes, intro lines, watch note and titles, imported
   from A9's `prepare.py`. blindpanel's wording hash of each A13 study equals A9's (`study.lock.json`,
   identical). Study ids `a13-burst` and `a13-push`; blinding seeds `a13-burst-20261104` and
   `a13-push-20261104`, so every clip and panel code is new and none equals an A9 code; tally off; every
   clip labelled "clip".
3. **Attention items.** In each study two clips are shown a second time, at positions 30 and 52 of 57,
   each at least 5 places after its original. The originals are the seeded draw
   `random.Random("20261104:a13:burst:attention")` and `random.Random("20261104:a13:push:attention")`,
   each `.sample(<the study's 55 public clip ids, sorted>, 2)` (A13.1). A repeat has
   its own code and shows its original's clip beside its original's drawing; nothing on the page says a
   clip repeats.
4. **Order.** Burst first, then camera push, in one sitting, with a break screen between the two (the
   rater presses a button to go on). Within a study the order is blindpanel's published scheme with
   repeats (blindpanel `docs/order.md`), from a session id fixed per slot and study:
   `derivedSession("20261104:<study id>:session:<slot>")`. The server refuses any other session for the
   slot, so each rater's order is the one fixed before registration.
5. **Raters.** Twelve, recruited on Prolific (pre-screen: normal or corrected vision, desktop, English
   fluency; participants of any A11 study excluded), one to each opaque slot R24 to R35, each through their
   own link. The author does not rate, nor does R7 or any A6 to A9 rater. Reserve slots R36 to R39 serve
   the one top-up (A13.5) and no other purpose. A `TEST13` slot is used only to check the deployed app;
   its rows are deleted after each check and never analysed. The platform's participant id never enters
   the app or this repository. Two raters rate first, as a pilot of the delivery; their ratings count if
   the instrument did not change between the pilot and the rest (the instrument hash, A13.2). About 40
   minutes a sitting (R7 took 18 and 17 minutes for A9's two studies), paid at Prolific's recommended rate.
6. **Delivery (conditions, not content, as A7).** A9 rated on the author's computer through
   `blindpanel dev` on localhost, one study per sitting at least an hour apart, on blindpanel 0.1.0. A13
   rates through the hosted rating app, on blindpanel 0.3.1, with A11's delivery: a per-slot link that
   sets a signed cookie and gates every page and file (and serves only each study's `study.json`, media
   and kit files: blindpanel's own `index.html` and `reveal.json` are never served; `mapping.json`, the
   key from codes to cells, ships in the release (A13.2) but never enters the app's `public/`); a consent and
   data-handling screen first, whose lawful-basis ruling is A11's words and whose purpose and retention
   sentences (and researcher sentence, item 9) are A13's own: "The study is academic research on how
   computer animation moves a still drawing when it is asked to. Your answers are compared with automatic measurements of the
   clips." and "Your answers stay public under your code as part of the research dataset for as long as it
   is online. The private records (the order you saw, the time each part took and the database rows of
   the study) are kept for five years from the end of the study and then deleted."; and a completion page
   that shows the platform's completion code only after the app confirms both studies' answers are stored.
   The changes a rater can see, declared:
   1. The end screen of each study reads "That was the last clip of this part. Press Send to save your
      answers." with a button "Send my answers", in place of blindpanel's "Next you'll see which model
      made each clip and how your answers compare with the reference panel's." and "See where you land".
      No results, reveal or tally screen appears; the app never serves `reveal.json`. (In A9 a rater
      pressed the end screen's buttons to store a session: A9 deviation 1.)
   2. A break card between the studies: "Part 1 of 2 is saved — thank you. Take a short break if you
      like. Part 2 shows new clips and asks about a different motion; its question is on every screen."
      and a "Start part 2" button.
   3. A completion card, A11's: "Your answers are saved — thank you", "Your Prolific completion code
      is:", the code, a "Return to Prolific ▶" link and A11's fallback sentence.
   4. If a send fails: a "Try again" button that sends the same answers again (the app answers a repeat
      as stored), then, as the second resort, A11's failure text and a box of the answers to copy into a
      message to the researcher on Prolific; the runbook imports a pasted part under its slot through the
      live app.
   5. Each study's session is 57 items (55 clips and 2 repeats), where A9's was 55.
   6. blindpanel 0.3.1's page, where A9's was 0.1.0's: the same wording but for items 7 and 8; the
      keyboard hint names the keys of the questions on screen (a 0.2 fix).
   7. On the intro screen the kit shows the clip count alone, without its line "Model names stay hidden
      until you finish." The app sets this through blindpanel's host option `intro: false`.
   8. The intro screen's privacy line is A13's own, set in the build (`build_a13.py`, `PRIVACY`), in
      place of A9's: "This page sets one cookie and the hosting service logs page requests, as the
      consent page says. Pressing Send sends your answers, their order and a rounded duration under your
      study code."
   9. The consent screen's researcher sentence is A13's own: "The name of the researcher is on the
      Prolific page for this study, not on these pages. The pages are built with an open-source rating
      kit; please do not look the study or the kit up until you have answered, since knowing more about
      it would change what the study measures." It departs from A11's rule that nothing on the pages
      points to the project, because the pages are built with an open-source rating kit whose name the
      server validates.
   No study question, scale label, note or intro line (the yaml's) changes; the wording hash proves it.

#### A13.4 Analysis (`analysis/a13_adherence.py`)

Before any rule, the run refuses a broken contract and stops: `mapping.json` must be A13's (55 codes and
2 repeats per study, the repeats' originals as its attention clips, its cells exactly A9's 110 in the
right study); every rating file must name one of the slots R24 to R39 (A13.3.5), no slot twice,
instrument A13, and only its study's codes; and no rating file may lie anywhere under
`analysis/adherence_a13/` except in `ratings/`, since a file elsewhere would be skipped in silence.
Then, in this order, the first two before any correlation:
1. **Completeness.** A rater must answer all 110 first showings and all 4 repeats with a score 1 to 5;
   otherwise they are excluded as incomplete, and the count is reported.
2. **Attention.** An attention item fails when the repeat's score differs from the first showing's by 2
   or more points. A rater who fails both items of either study is excluded from every statistic except
   the κ of A13.4.4(c), which measures the instrument over all complete raters; the count is reported.
   These are the only rules that exclude a rater: no rule on time (A7, A8).
   Only first showings enter any statistic.
3. **A13-H4.** For each clip, the mean score over the included raters. Spearman ρ between each clip's
   released line drift (`line_chamfer_mean_px`, `analysis/out/results_table.json`) and its mean score,
   over the 110 clips. One-sided, α = 0.05. The p-value comes from permuting the mean scores within the
   22 rows (each row's five clips are the five engines' clips of one drawing in one study), B = 10,000,
   `numpy.random.default_rng(20261104)`, p = (k + 1)/(B + 1) where k counts permutations whose pooled ρ
   is at least the observed ρ (`analysis/rank_stats.py`, `within_strata`). Permuting within rows keeps
   the drawing's own content from driving the result. **Supported iff p ≤ 0.05 and ρ > 0.** If the mean
   scores (or the drifts) do not vary, so that ρ is undefined, the reading is "undefined (no variation)",
   with no verdict; if p ≤ 0.05 but ρ ≤ 0, it is "not supported (p <= 0.05 but rho <= 0)". Reported
   beside it, without a verdict: the same ρ computed on within-row ranks, with its p from the same
   permutations. Power, by Fisher's z with variance 1.06/(n − 3) and n = 110: about 0.93 if the true
   ρ is 0.3 and 0.65 if it is 0.2; the within-row permutation is more conservative than this
   approximation when rows differ.
4. **Beside it, no verdict.** (a) The engine-level ρ(S, miss rate), A9 Test 1's statistic, on all
   included raters' ratings pooled (a miss is a score ≤ 2; S is A9's steadiness), with A9's exact
   one-sided p over the 120 orderings; five engines still cap it. (b) Per-engine miss rates with
   Wilson 95% intervals. (c) Krippendorff's ordinal α over all 110 clips (the included raters; the
   flag of A13.5.2) and per study; and A9's statistic, the quadratic-weighted κ (`a9_adherence.py`,
   `weighted_kappa`), for every pair of complete raters, per study, reported as its mean over the pairs
   where it is defined, with the number of pairs. (d) An ordinal mixed model, rating ~ drift + study +
   (1 | row) + (1 | rater), a cumulative link mixed model with a logit link fitted by `ordinal::clmm` in
   R (version 4.6.2; ordinal 2026.7.26, ucminf 1.2.3, numDeriv 2016.8.1.1, Matrix 1.7.6), over the included raters' first showings; the study term is there because the two
   studies ask different questions. The fit counts as converged only when the optimizer returned code 0,
   with R and its four packages (ordinal, ucminf, numDeriv, Matrix) as `analysis/a13-r-lock.txt` names
   them; any other version refuses the run. Non-convergence is a recorded outcome, not a failure:
   `analysis/out/a13_mixed.json` records it with the optimizer's message and no coefficients, and the
   report says "ordinal mixed model: did not converge (no verdict; error recorded)". A fit made on other
   raters than the included ones is reported as stale, never as converged: the report says
   "ordinal mixed model: stale (re-run --mixed)". (e) A9's objective check on
   these clips, the motion AUC
   (`a9_adherence.py`, `motion_check`): per study, AUC = P(released `headline_median_norm` of a non-miss
   clip > that of a miss clip), ties ½, with A9's readings (≥ 0.70 corroborates; ≤ 0.60 "the misses are
   not under-animation"; between, inconclusive; a class with no misses or no non-misses, "undefined (no
   misses or no non-misses in this class)"). A clip is a **miss when its mean score over the included
   raters is ≤ 2**: A9's per-rater miss carried to the clip, A13's unit. (The pooled-ratings form, every
   rating a miss or not, would count each clip once per rater and make the AUC's n the number of ratings,
   which A9's AUC never was.)

#### A13.5 Kill rules

1. Fewer than 8 included raters (complete, and not excluded by the attention rule) after one top-up
   batch: the analysis runs on those included, and n is stated. The top-up, as A11's, is published only
   if fewer than 10 are included after the main batch, with `12 − included` places, at most 4, on R36 to
   R39. Only rules 1 and 2 of A13.4 are applied before that decision, and no statistic is computed.
2. Krippendorff's ordinal α over all clips below 0.3: reported, and A13-H4 is still tested (the unit of
   analysis is the clip).
3. The attention rule of A13.4.2, applied before any correlation; the count is reported.

#### A13.6 Order

1. The two studies built and checked, codes and attention clips drawn, orders derived, the rating app
   built, its build verified locally and its preview deployment's served files checked against it (no
   row stored), for the twelve slots, the reserve and `TEST13`, its pages and orders hashed into the
   manifest (done before registration).
2. Registration, with A10 to A12.
3. The live checks with `TEST13` (A13.1), their rows deleted; then two pilot raters (R24, R25); their
   submissions checked for delivery only (rows present, order as derived, attention block present); ten
   more (R26 to R35); one top-up if A13.5.1 requires it.
4. Ratings fetched from the app and pseudonymised to their slots into
   `analysis/adherence_a13/ratings/` in the private repository; the release ships scores and attention
   answers only, sorted by code.
5. The analysis in one pass, `--mixed` included; results published in an in-place refresh.

#### A13.7 Cost

About £109.03 for twelve raters at about 40 minutes a sitting. Each rater is paid £6.00, at £9 an hour;
the rate is confirmed on Prolific's screen. The rewards, £72.00, carry Prolific's fee of three sevenths
of the rewards (£30.86) and VAT at 20% on the fee (£6.17). The two pilot raters cost £18.17 and the ten
after them £90.86. Naive raters on 114 items may take about 45 minutes, and Prolific's median-time
check can then raise the reward to £6.75: twelve raters would cost £122.66. The budget is £110 to £125,
for the twelve; a top-up is outside it. A top-up of up to four adds £36.34 at 40 minutes,
or £40.89 at 45 minutes. No generation.

#### A13.8 Limits

The rating copies carry no metadata, audio or encoder message (A9.3), and the seed reaches the page, so
a determined rater could match codes to engines, as in A9; the protection is conduct, and no rater is
asked to inspect files. `mapping.json` ships at registration (A13.2), as A11's mapping does, so the
code-to-clip key is public before anyone rates; the protection against unblinding is conduct, as stated.
Raters are a paid online panel, not the trained raters of A6 to A9. The two
studies use different questions on the same five-point frame; A13-H4 pools them by design, and α is
reported per study as well.

#### Registered prediction

- **A13-H4:** across the 110 clips, ρ(released line drift, mean adherence score) > 0, tested by
  permutation within rows.

Stated plainly: on the same drawing, we expect the clips that move their lines more to be the ones that
actually do the motion asked for. If they are not, the steadiness of the league's leaders is not
explained by their doing less, and the paper says so. Either outcome is reported.

### A14 — 2026-11-10: confirmatory: A5's Seedance hazard replication completed at five fresh draws per cell

*A14, A15 and A16 were drafted together on 7 Nov 2026 for the journal version of the paper
and registered with A10; each stands alone. None restates a frozen result, and none makes an
engine a league row: the frozen league (§5, R12) stands as it is.*

**STATUS: APPROVED — Aaron's go recorded 2026-11-10 ("Go to register A10–A16 once the open fixes below are made and two-stage reviewed"), after an independent review of the drafts whose findings he ruled on; every fix was made and reviewed before registration. Registered 2026-11-10 (UTC) with A10, by the same tagged
public commit (`a10-registered`). Cost: about £23.50 (A14.8).**

**Why this is an amendment at all.** It adds 20 clips through a route the study has never
used for Seedance (Runway's API), and it reads A5's registered prediction on five fresh draws,
a reading that A5 did not buy. Under the freeze rule new cells need a dated amendment, recorded
with their analysis before any of them exists.

**The problem it addresses.** A5 (14 Aug 2026) registered a capability-versus-preservation
prediction for Seedance and authorised a 6-clip scout only (Option 1b), later completed by
three FLINT clips (A5 addendum). The scout's three BURST draws gave 1 departure in 3 under the
frozen automatic rule, which A5's own rule calls indeterminate (FINDINGS R12). A5's draft
priced the purchase that resolves it, Option 2: A4's four-cell core at five draws each, the
scout's three draws counted. A14 buys that core at five draws each through Runway, 20 clips,
and reads A5's prediction on the five draws of `act-black-3` BURST, none of which anyone has
seen. It departs from Option 2 in its reading: the scout's three draws are not counted in it,
but reported beside it (A14.1 says why). Beyond the draw count, the route and what the route
requires, A14 registers that departure and what goes with it: the secondary figures beside the
reading, the rule that withholds the pooled figure after a route mismatch, its own kill rules
(A5 registered none) and a blind reviewer for the strips.

#### A14.0 Status of any result derived from it — binding

1. A14 is **CONFIRMATORY** for one prediction only: A5's, quoted in A14.4, read on five fresh
   Runway draws of `act-black-3` BURST. Everything else A14 reports (the scout's three draws and
   the pooled eight-draw figure, A14.4; the other three cells' rates, A4's stratum statistic
   computed on Seedance, agreement between the two halves of the coding rule, realised motion,
   A14.5) is reported without a verdict.
2. A14 adds no headline metric and changes no frozen definition. Its cells are excluded from
   the frozen §8 test (A5.6), and the §8 test remains as reported: **null, ten of ten.**
3. A14's draws are never pooled with the frozen corpus, with A4's H3 draws or with A10's
   ladder cells. They pool with A5's scout draws only in the secondary figure of A14.4, never
   in the confirmatory reading, and not at all after a route mismatch, found at the check or
   during the run (A14.3.4).
4. A5.5's interim-look disclosure binds the paper: a 3-draw look preceded the decision to buy
   more, and the paper says so. A5.5 also says that the scout's draws pool into the rate if the
   study continues. A14 departs from that: the confirmatory rate is read on five fresh draws,
   and the pooled rate is reported beside it, without a verdict, unless a route mismatch was
   found, at the check or during the run (A14.1, A14.3.4, A14.4).
5. Every threshold A14 uses is declared below where it is applied.

#### A14.1 Seen before registration

Seen by Aaron, by Claude (the agent that drafted A14) or by both, before registration:

- Everything A10.1 lists; A4's per-cell rates on MiniMax H3 (`analysis/out/hazard_rates.md`),
  among them `act-black-3_burst_h3` at 8 of 10 (80%, Wilson 95% interval 49%–94%), and the
  cross-engine stratum table of FINDINGS R12.
- A5's nine Seedance clips (through fal), their metrics in `runs/metrics-seedance/` and their
  motion values, and two readings of the scout's three BURST draws: under the frozen automatic
  rule (mean chamfer vs frame 0 > 10 px), 1 of 3 departed (`act-black-3_burst_sd2-h2`,
  16.94 px); a frame-strip read by Claude, not blind, first reported 0 of 3 and was corrected
  to the rule's count (FINDINGS R12). The scout's strips have therefore been seen, unblinded;
  A14.3.6 codes them again, blind, beside the new draws.
- A5's draft (`docs/A5-DRAFT-seedance.md`): its Option 2 and price, and its reassessment of
  14 Aug 2026, which recommended Option 2 if any more Seedance money was spent.
- Runway's model reference as read on 31 Oct 2026: `seedance2` on `/v1/image_to_video` takes a
  first frame (or first and last), an integer duration, ratio 1280:720 among its 720p ratios
  and a seed, generates audio by default, and costs 30 credits a second at 720p.
- Runway's OpenAPI file as read on 8 Nov 2026 (`docs/RUNWAY-MODELS-2026-11-08.md`): `seedance2`
  lists 1280:720 among its 24 ratios, an optional integer seed (the same seed on an identical
  request gives, in the file's words, "similar results") and an `audio` boolean that defaults
  to true and can be set false; its `promptImage` takes first and last frames by position.
- The decision to continue was taken on 7 Nov 2026, about twelve weeks after the scout, with
  all of the above in view. For a 1-of-3 scout, A5.4 reads "proceed only if FLINT
  also shows something". That condition was met in the frozen record: FINDINGS R12 reports
  FLINT replicated 6 of 6 on Seedance ("promoting it from observation to finding"), and the
  only reading of "shows something" that fits A5's purpose (the hazard appearing on a second
  engine) is FLINT departures replicating there, which 6 of 6 satisfies under any threshold.
  What was missing was the record that the decision to go on to Option 2 rested on A5.4; the
  decision was taken for A14's own reason (completing the replication) and matched to A5.4
  afterwards, on the same day. A14 therefore proceeds under A5.4 as written, not as a
  deviation, and A5.5's interim-look disclosure applies: a 3-draw look preceded the purchase,
  and the paper says so. The scout's draws do not pool into the confirmatory rate, a departure
  from A5.5 that the next paragraph explains; they are reported beside it, and pooled only in a
  secondary figure, and only when no route mismatch is found, at the check or during the run
  (A14.3.3, A14.3.4, A14.4). Both the sequence and the late matching are disclosed in the paper.

**Why the prediction is read on five fresh draws.** A5's Option 2 would have counted the
scout's three draws among the five of `act-black-3` BURST. Those three were seen before
registration, and under rule (a), the automatic half of the coding rule (A14.3.6), they stand
at 1 of 3. A pooled five-draw reading could therefore reach at most 3 of 5 under rule (a),
below the 4 of 5 that "prediction holds" needs (A14.4); only rule (b), adjudicated on three
strips already seen, could have lifted it. That limit was known before the purchase: an
independent review of this draft found it on 10 Nov 2026, before any A14 clip existed. A14
therefore reads the prediction on five draws that nobody has seen (`-h4` to `-h8`), and reports
the scout's three draws, and the pooled eight-draw figure, beside the reading without a verdict.
This departs from A5's Option 2, which counted the scout's draws, and from A5.5, which pools
them into the rate if the study continues. The departure is declared here, before any A14 clip,
and costs three more clips (about £3.50, A14.8).

**Not computed by anyone before registration:** any A14 clip; any coding of an A14 draw; the
blind strip review of any Seedance draw, the scout's included; every A14 reading. The A14
driver (`harness/a14_draws.py`) refuses to generate, and the analysis
(`analysis/a14_seedance.py`) refuses to read A14 data, until this amendment's heading is in
the public pre-registration (`harness/registration.py`, as A10.1). That is a tripwire, not a
proof.

#### A14.2 Frozen artefacts

`docs/A14-MANIFEST.sha256` (sha256 `d438f5bb5efc37b04d9f3d93081e2adbc7003c2928fa0c5ae7625c5b83ae864a`) lists, at their release paths
and hashed in release form, as A10.2's manifest does: the frozen pack
`harness/motion-prompts.md` (IDLE and BURST are A14's prompts) and `harness/pack_parser.py`;
the two panels `dataset/panels/cu-line-1.png` and `dataset/panels/act-black-3.png` and their
line-art layers in `dataset/lineart/`; `harness/gen_video.py` and `harness/runway_task.py` (the
`seedance2` route), `harness/a14_draws.py` with `harness/ladder.py` (whose run loop and refusal
rule it uses, A14.3.5), and `harness/registration.py`; `metrics/inkstab.py` and
`metrics/motion.py`; `analysis/extract_frames.py`; `analysis/a14_seedance.py`, its cell list
`analysis/out/a14_cells.json` and its strip codes `analysis/out/a14_codes.json`;
`analysis/hazard_rates.py` (the source of H3's comparison rate) and its output
`analysis/out/hazard_rates.json`; A5's three fal draws `runs/seedance/act-black-3_burst_sd2-h1.mp4`
to `-h3.mp4`, with their files in `runs/metrics-seedance/` and `runs/metrics-motion/`; and the
tests of each.

#### A14.3 Design

1. **Cells.** A4's four-cell core as A5's Option 2 defines it: `cu-line-1` and `act-black-3` ×
   {IDLE, BURST}, frozen prompts and settings, five fresh Runway draws per cell: 20 new clips,
   whatever the route verdict (A14.3.4). Unlike Option 2, the scout's three draws are not among
   the five (A14.1).
   - `cu-line-1_idle_sd2r-h1` to `-h5`, `cu-line-1_burst_sd2r-h1` to `-h5` and
     `act-black-3_idle_sd2r-h1` to `-h5`: 15 clips.
   - `act-black-3_burst_sd2r-h4` to `-h8`: 5 clips, numbered after the scout's
     `act-black-3_burst_sd2-h1` to `-h3`, so that the cell's eight draws, the scout's three and
     Runway's five, carry eight distinct numbers.

   The tag `sd2r` (Seedance 2.0 through Runway) carries the route in every cell id; A5's fal
   cells keep `sd2`. Clips `runs/seedance2/<cell id>.mp4`; inkstab JSONs in
   `runs/metrics-seedance/` (A5.6's folder); motion JSONs (A6's tool, unchanged) in
   `runs/metrics-motion-seedance/`. The primary corpus folders are untouched. The full list is
   `analysis/out/a14_cells.json`. The route check's verdict (A14.3.3) is recorded, with the
   sha256 of `docs/A14-ROUTE.md`, in `analysis/out/a14_route.json` (`harness/a14_draws.py
   route`), and is never changed; `docs/A14-ROUTE.md` ships in the release. `harness/a14_draws.py
   run` refuses once that document's current sha256 differs from the one recorded in the verdict
   file, as `harness/scout.py run` does for A15's (A15.3.5). The three record documents
   (`docs/A14-ROUTE.md`, `docs/A15-ROUTE.md`, `docs/A16-SETUP.md`) are written by the operator
   (the author, or the Claude agent running the session under his direction) as the operator's
   own record: the verdict, the date, the URL checked, the field names read, and the sha256 of
   any captured page; never a verbatim copy of Runway's or Midjourney's pages, whose text stays
   private and only whose hash ships, as `docs/tos-snapshots/SHA256SUMS` does.
2. **Engine and route.** `seedance2` through Runway's API (`/v1/image_to_video`), first frame
   only, ratio 1280:720 (this model's 720p tier, among the ratios Runway's OpenAPI file lists
   for it), duration 5 s, every draw at the same settings. **Seeds, one per draw:** draw
   `-h<k>` of a cell is sent seed 20260812 + k (`-h1` 20260813 to `-h5` 20260817; on
   `act-black-3` BURST, `-h4` to `-h8`, 20260816 to 20260820), written into its manifest line
   with any seed Runway's task record reports, so the draws differ and each request can be
   repeated.
   Runway's own words are that the same seed gives "similar results", so a seed fixes the
   request, not the bytes. The scout's three fal draws keep what fal recorded. **Audio is
   switched off in the request** (`audio: false`, which the manifest line's request records).
   The tool also counts the delivered file's audio streams; should one be present, it is
   removed before any measure by copying the video stream without re-encoding (its
   video-packet md5 checked equal to the delivered file's) and the delivered file's sha256 is
   recorded. Audio plays no part in any measure, review or release. Every clip's manifest line
   records the route (`Runway`), the model id, the API version header, `model_version` and the
   date, as §5 requires.
3. **Route check, before the first submission.** Runway's Seedance may not be the model fal
   served in August (`bytedance/seedance-2.0/image-to-video`, standard tier, 720p). Before the
   first A14 submission, Runway's documentation for `seedance2` is captured (a dated snapshot,
   kept privately, with its sha256) and `docs/A14-ROUTE.md` records, with the URL checked, what
   it names: the model, its version and its tier. The route **matches** when that
   documentation names ByteDance's Seedance 2.0 at its standard tier (not a fast or mini tier,
   not a later version); otherwise it is a **mismatch**. A match means only that no difference
   is documented: it does not show that the two routes serve the same model, and the paper says
   so.
4. **On a mismatch.** A mismatch at the route check adds no draw and changes nothing in the
   batch: the same 20 draws are made, and the prediction is read on the same five as on a match
   (A14.4). It is recorded and reported as a finding in its own right. The scout's three draws
   are then never pooled with Runway's: the pooled eight-draw figure of A14.4 is not computed,
   and the scout is reported on its own beside the reading. Whatever the verdict, the first
   draw runs alone (`run --limit 1`) and is watched: its frame size, its audio (A14.3.2) and its
   first frame are checked before the rest are submitted, the first frame matched to the panel
   by eye from the draw's strip (`analysis/extract_frames.py`) and the result recorded in the
   batch's ledger note. Before the next submission the reference is captured from its Runway task
   record into `analysis/out/a14_route.json`, beside the verdict: its `model` field if present,
   otherwise every Runway-reported field whose name contains "model" or "version", recorded by
   name. The harness's own version string is never compared. If the record has neither, the
   route record says so, the in-run check cannot fire, and the route verdict (A14.3.3) is the
   only model check. If a later task record reports a captured field, present and different,
   after generation has begun, generation stops, Aaron is told, the prediction reads "not
   testable at five draws: route mismatch found during the run", and every draw is reported
   without a verdict. The pooled eight-draw figure of A14.4 is then not computed either: the
   scout is never pooled across a known model change. A later record that lacks a captured
   field is a harness fault, not a mismatch: the run stops, the operator records in
   `analysis/out/a14_route.json` why the field was absent, and the run then resumes; if the
   absence cannot be explained, the run stays stopped and Aaron is told. The reading "not
   testable at five draws: route mismatch found during the run" is reserved for a captured
   field present and different.
5. **Refusals.** §5's rule, as `harness/ladder.py` applies it on Runway (A10.3.4): a draw that
   fails is resubmitted once, identically, and is recorded as refused only when both attempts
   end in a task-level FAILED outcome from Runway; any other double failure is a harness
   fault, fixed and resumed, and a CANCELLED task stops the run. A refused draw is listed, is
   neither departed nor held, and reduces its cell's n. No draw replaces it.
6. **Outcome coding: the frozen A4 rule, which A5.3 applies verbatim.** A4's clause 4, quoted:

   > Each draw is scored **departed / held** by the frozen rule: a draw counts
   > as *departed* if EITHER (a) its line-drift chamfer exceeds 10 px (an order
   > of magnitude above the corpus median and above every clip the frame review
   > judged "held"), OR (b) blind frame review of its strip records a subject
   > replacement, a hard graphic cut, pseudo-text, evacuation, or a monochrome
   > break. Rule (a) is automatic; rule (b) is adjudicated on strips with the
   > cell identity hidden. Disagreements between (a) and (b) are reported, not
   > resolved silently — they are themselves a metric-validity result.

   Rule (a) is computed by `metrics/inkstab.py`. Rule (b) is adjudicated by a fresh, blind, read-only Claude agent, which the operator dispatches with only the coded strip folder and the five named failures, on
   strips made by `analysis/extract_frames.py` (source panel, first, middle and last frame) for
   every draw with a clip (at most 23: the 20 Runway draws and the scout's three), coded blind
   in one sitting under one set of opaque codes, in an order drawn by
   `analysis/a14_seedance.py --codes` (seed 20261104), whatever the route verdict. The reviewer
   sees no cell id, engine, route, draw number or metric, and records one of the five named
   failures or "held" per strip. The review's record is `analysis/out/a14_review.json`,
   `{"reviewer": ..., "codes": {code: "held" or one of the five named failures}}`; a code
   outside the set, or any other label, is refused. It is committed before any rule (a) value is
   joined to it.
7. **Measurement.** Every metric runs on the study Mac (Apple-silicon mps), as A10.3.6.

#### A14.4 The registered test: A5's prediction at five fresh draws

A5's registered prediction, quoted:

> **Registered prediction (before any draw):** Seedance's departure rate on
> `act-black-3` BURST will be **no lower** than H3's on the same cell. Rationale:
> a model with confident anime priors is *more* likely to redraw a panel it
> considers improvable — the graphic-cut hazard of R11. A lower rate refutes
> this and is itself the headline.

A5's composition, quoted:

> 1. **3 FLINT pairs** — the first three frozen §5 pairs in manifest order:
>    `cu-line-2→cu-line-1`, `act-line-2→act-tone-3`, `est-line-2→est-black-3`.
> 2. **3 single-image draws** on `act-black-3` BURST — the highest-hazard cell
>    of A4, ordinary (not first→last) conditioning.

A5's decision rule, quoted:

> 4. **Pre-specified decision rule** (this is a sequential design, not optional
>    stopping): ≥2 of 3 BURST draws depart → proceed to Option 2; 0 of 3 depart
>    → Seedance is materially more stable, report that and prefer Option 4;
>    1 of 3 → indeterminate at n=3, proceed only if FLINT also shows something.

The decision rule decided a purchase after a three-draw look. It was applied once, to the
scout (1 of 3: indeterminate), and A14 is the purchase it pointed to (A14.1 records how the
decision was taken). At five draws there is no purchase left to decide, so the rule is not
applied again; what A14 reads is the prediction.

**Reading (`analysis/a14_seedance.py`).** On `act-black-3` BURST: Seedance's departures k over
its n coded draws among the five fresh Runway draws `-h4` to `-h8` (five, less refusals),
whatever the route verdict, against H3's published 8 of 10 on the same cell
(`act-black-3_burst_h3`, A4). The scout's three draws are not counted (A14.1). Readings, the
analysis's own strings, in this order:

1. "not testable at five draws: route mismatch found during the run", where A14.3.4 applies: a
   run stopped by a model change is read so, and this reading precedes "incomplete", whatever
   draws the stop left missing. (A mismatch found at the route check changes nothing here: the
   five are read as below, A14.3.4.)
2. "incomplete: N draws missing": a draw of the cell that is neither refused nor fully coded
   (its clip, its chamfer or its strip code is missing). Its numbers are still reported.
3. "not testable: fewer than 3 coded draws", when refusals leave fewer than three (preceded by
   "refused" when every draw of the cell is refused, A14.6.3).
4. "prediction holds: Seedance's departure rate is no lower than H3's" if k/n ≥ 8/10.
5. Otherwise "prediction refuted: Seedance's departure rate is lower than H3's". A5's words
   apply: a lower rate "is itself the headline."

The comparison is of rates, as A5 states it; A5 registered no test statistic, and A14 adds
none with a verdict. At n = 5, "holds" needs at least 4 departures. Reported beside the
reading, without a verdict: both Wilson 95% intervals; a one-sided Fisher exact p for H3's
rate exceeding Seedance's; the same reading with rule (a) alone, which is how H3's 8 of 10 was
coded (`analysis/hazard_rates.py`), so a reader can see whether rule (b) moved it; the scout's
three draws on their own, k of 3 under the full rule and under rule (a) alone; and the pooled
eight-draw figure (the scout's three and Runway's five), with its rate and Wilson 95% interval
under both codings. After a route mismatch at the check, or after a route mismatch found
during the run, the pooled figure is not computed, and the analysis prints, respectively, "not
computed: the route check recorded a mismatch, and A5's fal draws are never pooled with
Runway's (A14.3.4)" or "not computed: a route mismatch was found during the run, and A5's fal
draws are never pooled across a model change (A14.3.4)"; after both, the first.

#### A14.5 Reported without a verdict

- Per cell: departures, n, rate and Wilson 95% interval, beside H3's published rates on the
  same four cells (A4). Every cell is Runway's five draws; the scout's are reported in A14.4.
- A4's registered statistic computed the same way on Seedance's Runway draws: BURST × heavy-black
  (`act-black-3` BURST) against IDLE × line-only (`cu-line-1` IDLE), one-sided Fisher exact,
  under both codings: A4's full rule, as A14.3.6 codes the draws, and rule (a) alone, as H3's
  rates were coded.
  A4 registered it for H3 alone ("Single-engine rates are reported as engine-specific and not
  generalised"), so on Seedance it answers A5's named question (b) descriptively. With one
  panel per condition, panel and condition are confounded, as R12 found on H3.
- Rule (a) against rule (b), draw by draw, and the number of disagreements (A4.4).
- Per draw: mean chamfer vs frame 0, edge |slope|, style terminal and A6's realised motion.
- Per draw: route, `model_version` and date; the route record (A14.3.3); the distinct
  `model_version` strings among A14's draws, flagged when there is more than one. The flag is
  noted and changes no reading.

#### A14.6 Kill rules

1. No draw beyond the registered 20 is taken on any cell, whatever the reading, and no refused
   draw is replaced.
2. A "not testable" or "incomplete" reading is reported as the result, with every draw's
   numbers.
3. A cell whose every draw is refused reads "refused", and its rate is not computed. On the
   predicted cell this reading precedes "not testable: fewer than 3 coded draws" (A14.4), which
   such a cell would otherwise also meet.
4. If Runway withdraws `seedance2`, or changes its settings so that 5 s at 1280:720 is no
   longer offered, before all 20 draws exist: generation stops, Aaron is told, and nothing is
   substituted (no other Seedance tier, no other route). The prediction reads "incomplete: N
   draws missing" (A14.4), and every cell's numbers are reported.

#### A14.7 Order that makes "before any clip" true

1. The `seedance2` route in `harness/gen_video.py`, the A14 driver, the cell list, the strip
   codes and the analysis, with tests on fixtures (before registration).
2. Registration, with A10.
3. The route check (A14.3.3), committed before the first submission; a mismatch is recorded
   and reported (A14.3.4), and changes nothing in the batch.
4. Generation from the study Mac in one batch, with a ledger row.
5. Metrics; strips; the blind review of every strip (at most 23: the 20 Runway draws and the
   scout's three) in one sitting, under one code set, its record committed.
6. The analysis in one pass; results published in an in-place refresh.

#### A14.8 Cost

20 clips × 5 s × 30 credits = 3,000 credits = $30.00, about £23.50 at the ledger's pinned
rate (re-pinned at spend), at Runway's price as read on 31 Oct 2026. Three of the 20 clips,
about £3.50, are the cost of reading the prediction on five fresh draws (A14.1). The price is
checked against Runway's published credit rate on the day, recorded in the ledger row, before
the batch, and the batch stops if they differ. One ledger row.

#### Registered prediction

- **A5's prediction, at five draws:** Seedance's departure rate on `act-black-3` BURST, read on
  five fresh Runway draws, is no lower than H3's 8 of 10.

Stated plainly: A5 expected an engine with strong anime priors to redraw a panel it thinks it
can improve. The scout's 1 of 3 pointed the other way, at n = 3. Those three were already seen,
so the test is made on five new draws, and the scout is shown beside them. If Seedance departs less
than H3 on the worst cell, a 2026 flagship holds our drawings better than the incumbent, and
that is the headline A5 named. Either outcome is reported, and every reading above is
reported whatever it shows.

### A15 — 2026-11-10: a Kling scout with a declared decision rule; Kling in A10's motion test only if it passes

**STATUS: APPROVED — Aaron's go recorded 2026-11-10 ("Go to register A10–A16 once the open fixes below are made and two-stage reviewed"), after an independent review of the drafts whose findings he ruled on; every fix was made and reviewed before registration. Registered 2026-11-10 (UTC) with A10, by the same tagged
public commit. Cost: about £3 for the scout, and about £24 more if it passes (A15.9).**

**Why this is an amendment at all.** It adds six clips on an engine the study has never run,
and, only if they pass a rule, 48 cells in A10's motion test. Under the freeze rule both sets
of cells, and the rule that links them, are declared before any of them exists.

**The problem it addresses.** A10-H1 tests the motion law on three engines. A reviewer can
ask whether it holds beyond them, and an engine from another vendor answers that. A 48-cell
arm is worth running only on an engine that will take our panels, whose clips the frozen
tools can measure, and that moves when asked to; Wan 2.2 in the frozen corpus is the warning
(A10.1). A15 checks those three things on six clips first, with a rule fixed now.

#### A15.0 Status of any result derived from it — binding

1. The scout is a decision instrument, as A5's was: it makes no rate claim and no claim about
   Kling's line stability. Its numbers are reported as a 6-clip pilot.
2. The arm, if it runs, is **CONFIRMATORY** for A10-H1 on Kling, in A10.0's sense: a further
   engine read exactly as A10.4 reads Wan 2.2, LTX-2.3 and Gen-4.5. It is reported as
   "A10-H1 (Kling, A15)" wherever it appears, the paper included.
3. Kling's cells enter no part of A10-H2, its readings or its kill rules (A10.5). A10's three
   engines' readings are computed as registered and are the same whether Kling's cells are
   present or not.
4. A15 adds no headline metric and changes no frozen definition. Its cells are never pooled
   with the frozen corpus and are never a league row; §8 remains **null, ten of ten.**
5. Every threshold A15 uses is declared below where it is applied.

#### A15.1 Seen before registration

- Everything A10.1 and A14.1 list.
- Runway's model reference as read on 31 Oct 2026, for `kling_4` on `/v1/image_to_video`: a
  first frame, or a first frame with an optional middle and last; 3 to 30 s; ratio
  `auto_720p` or `auto_1080p` only; no seed; audio always generated; 12.56 credits a second at
  720p until 30 Nov 2026 (list price 15.7).
- The scout's motion floor, 0.00160571 (A15.5), computed before registration from released
  files of the frozen corpus (`analysis/out/scout_floor.json`).
- No Kling clip of any benchmark panel existed for this study.

**Not computed by anyone before registration:** any Kling clip; any value or reading on one.
The scout driver and the ladder driver refuse to generate on `kling_4`, and the analysis
refuses to read Kling data, until this amendment's heading is in the public
pre-registration.

#### A15.2 Frozen artefacts

`docs/A15-MANIFEST.sha256` (sha256 `d3f4c861d081f11a33a86924947242efa9c461d3da7f576a586b7e64f4133c0a`) lists, in release form: the
frozen pack `harness/motion-prompts.md` (FLINT and BURST) and A10's ladder pack
`harness/motion-ladder.md`; `harness/pack_parser.py`; the scout's panels (`cu-line-2`,
`cu-line-1`, `act-line-2`, `act-tone-3`, `est-line-2`, `est-black-3`, `act-black-3`) and
A10's twelve, in `dataset/panels/`, with their line-art layers in `dataset/lineart/`;
`harness/gen_video.py` and `harness/runway_task.py` (the `kling_4` route, first and last frame
included),
`harness/scout.py` (the scout driver), `harness/ladder.py` (with `kling_4` as a further
engine) and `harness/registration.py`; `metrics/inkstab.py` and `metrics/motion.py`;
`analysis/scout_rule.py` and its outputs `analysis/out/scout_cells.json` and
`analysis/out/scout_floor.json`; the arm's cell list `analysis/out/a15_cells.json`;
`analysis/a10_ladder.py` (reading further engines, A15.6) with `analysis/rank_stats.py`, which
it imports, and `analysis/out/a10_panels.json` (A10's twelve, which `harness/ladder.py` reads);
and the tests of each.

#### A15.3 Engine, route and version

1. `kling_4` through Runway's API (`/v1/image_to_video`). FLINT cells pass the first panel as
   the first frame and the last panel as the last frame; every other cell passes the first
   frame only. No middle frame and no reference image is ever sent.
2. Ratio `auto_720p` (the model's only 720p setting; it keeps the input's framing, and the
   panels are 1344×768), duration 5 s. The delivered frame size is recorded per clip as
   `ratio`, with `requested_ratio` `auto_720p`, under A1's rule for engine-constrained
   resolutions.
3. Kling exposes no seed. The manifest records `seed: null`, and each cell is one draw, as
   Gen-4.5's are in A10.3.3.
4. `kling_4` always generates audio, and the API has no switch for it. The audio is removed
   before any measure by copying the video stream without re-encoding; the tool checks that
   the stripped file's video-packet md5 equals the delivered file's, and the delivered file's
   sha256 is recorded in the manifest line; the delivered file is kept privately
   (`runs/delivered/kling_4/`). The audio plays no part in any measure, review or figure, and
   no released clip carries it.
5. Every clip's version and date in `runs/manifest.jsonl`: route (`Runway`), model id, API
   version header, `model_version` and date. Before the scout's first submission, Runway's
   documentation for `kling_4` is captured (dated, kept privately, with its sha256) and
   `docs/A15-ROUTE.md` records, with the URL checked, what it names; if 5 s at `auto_720p` is no
   longer offered, nothing runs and Aaron is told. The verdict ("offered" or "not-offered") is
   recorded once, with that file's sha256, in `analysis/out/a15_route.json` (`harness/scout.py
   route --verdict`, refused until A15 is public) and never changed; `harness/scout.py run`
   refuses without it, on "not-offered", and once the document's sha256 no longer matches the
   one recorded. `docs/A15-ROUTE.md` ships in the release as the operator's own record (A14.3.1),
   never as a copy of Runway's page. The first cell of each request shape, the two-image FLINT
   cell and the single-image BURST cell, runs alone. The tool refuses to start the scout's first
   cell unless it is the only cell run (`scout.py run --limit 1`), and refuses to run on to the first
   BURST cell together with others: the run must stop before that cell, or run it alone. The
   operator checks each of these cells as A14's first draw is checked (A14.3.4: frame size, audio stripped, first frame
   matched to the panel by eye from its strip) and records the checks in the ledger note; if a
   check fails, nothing more is submitted. No other Kling model is substituted at any point, in
   the scout or the arm.
6. **Refusals.** A10.3.4's rule: a cell that fails is resubmitted once, identically, and is
   recorded as refused only when both attempts end in a task-level FAILED outcome from Runway;
   any other failure is a harness fault, fixed and resumed; a CANCELLED task stops the run;
   n is stated.

#### A15.4 The scout

A5's composition, quoted from A5's design:

> 1. **3 FLINT pairs** — the first three frozen §5 pairs in manifest order:
>    `cu-line-2→cu-line-1`, `act-line-2→act-tone-3`, `est-line-2→est-black-3`.
> 2. **3 single-image draws** on `act-black-3` BURST — the highest-hazard cell
>    of A4, ordinary (not first→last) conditioning.

run on `kling_4` as A15.3 sets it, with the frozen FLINT prompt for the pairs and the frozen
BURST prompt for the draws. Cell ids `flint-cu-line-2--cu-line-1_kling4`,
`flint-act-line-2--act-tone-3_kling4`, `flint-est-line-2--est-black-3_kling4` and
`act-black-3_burst_kling4-h1` to `-h3`; clips `runs/kling_4/<cell id>.mp4`; inkstab JSONs in
`runs/metrics-scout/`, motion JSONs in `runs/metrics-motion-scout/`. The scout's clips never
enter A10.

#### A15.5 The decision rule, declared before the scout runs (`analysis/scout_rule.py`)

The rule is read once, when every scout cell has a clip or a refused line and the metrics
step has run on every clip (harness faults are fixed and resumed first), and its reading is
logged in FINDINGS before any arm clip is submitted. The metrics step (`harness/scout.py
metrics`) writes `analysis/out/a15_scout_metrics.json`, naming every delivered clip it measured
with the sha256 of each metric file; the rule refuses to write a reading ("metrics step not
complete") unless that file names every delivered clip; a tool failure is recorded there with its
reason, and a clip left without a metric file reads "not measurable" (reading 2) only after one
confirming re-run of the metrics step has failed on it again (until then the rule refuses:
"metrics step not complete: N clips await a confirming re-run"), the recorded reasons printed
beside the reading; a non-finite metric also reads "not measurable"; a metric file deleted or
changed since the record is refused; and the rule is "not read yet" only while a cell has
neither clip nor refused line. Its inputs are the manifest's refused lines and,
for each clip, the mean chamfer vs frame 0 and A6's realised motion (`headline_median_norm`).

**The motion floor** is 0.00160571: the median `headline_median_norm` over the frozen
corpus's primary IDLE cells of all five engines, from the released
`runs/metrics-motion/*.json` (FLINT and -r2 cells excluded, as in A10.1), computed by
`analysis/scout_rule.py --floor` and written, with the 54 primary IDLE cells it covers, to
`analysis/out/scout_floor.json` before registration.

Readings, in this order, each a fixed string:

1. "scout failed: refused (R of N cells)" if two or more of the scout's cells are refused.
2. "scout failed: not measurable (<cell ids>)" if any clip that was not refused lacks a finite
   mean chamfer or a finite motion value from the frozen tools.
3. "scout failed: does not move on request (B of 3 BURST draws above the floor)" if fewer than
   two of the three BURST draws have realised motion above the floor; a refused BURST draw
   counts as not above it.
4. Otherwise "scout passed: Kling joins A10's motion test as a further engine".

"scout passed" starts the arm (A15.6). Any "scout failed" ends A15: the scout is reported, and
nothing more runs on Kling. Reading 2's cell ids are joined by ", ". The reading is written,
with every input, the floor and each cell's manifest seed, to `analysis/out/a15_scout.json`,
and FINDINGS takes the line the tool prints: `FINDINGS: A15 scout (kling_4), <date>: <reading>
[analysis/out/a15_scout.json; floor 0.00160571]`.

Why these three, declared before any clip: a refusal rate of a third of cells or more would
leave A10-H1 far short of 48 cells; the frozen tools must measure the clips unchanged, or
Kling's numbers would not be A10's; and an engine whose burst moves less than the corpus's
typical idle clip would be expected to fail A10's manipulation check (A10.4.1), as A10.5 rule
2 anticipates for Wan 2.2. Departures play no part: drift under motion is what A10 measures.
The FLINT half is reported (each pair measured, and departed or held under rule (a) of A4's
rule), and plays no part either.

#### A15.6 If the scout passes: Kling in A10's motion test

1. **Cells.** A10.3's twelve panels × four levels with A10's prompt pack v2, verbatim: 48
   cells `ladder-<panel>_<still|low|mid|high>_kling4`; clips `runs/kling_4/<cell id>.mp4`;
   inkstab JSONs in `runs/metrics-ladder/`, motion JSONs in `runs/metrics-motion-ladder/`;
   manifest lines as A10.3.3 plus `prompt_pack`; settings as A15.3. The cell list is written
   by A10's builder to its own file, `analysis/out/a15_cells.json`; A10's
   `analysis/out/a10_cells.json` is unchanged. The arm makes no clip unless
   `analysis/out/a15_scout.json` exists and its logged reading is exactly "scout passed: Kling
   joins A10's motion test as a further engine" (`harness/ladder.py` refuses otherwise).
2. **Analysis.** `analysis/a10_ladder.py` reads Kling as it reads Wan 2.2, LTX-2.3 and
   Gen-4.5: coverage (A10.4's opening paragraph); the manipulation check, printed and logged
   first and alone (A10.4.1); A10-H1 (A10.4.2) with its readings in its order, its B, a fresh
   `default_rng(20261104)` for the engine, one-sided α = 0.05, uncorrected; its secondary
   metrics and bootstrap intervals; the within-panel secondary of A10.4.4 (not the A10-H2
   band's make-up); and model versions (A10.4.5). The reading strings are A10's. The arm is
   analysed only once this amendment is in the public pre-registration; until then the
   analysis lists it as "not analysed: A15 not public". If the scout fails, the arm is listed
   as "not run: " followed by the scout's logged reading, taken from
   `analysis/out/a15_scout.json`, which `analysis/scout_rule.py` writes beside its FINDINGS
   entry (A15.5); any logged reading other than A15.5's own refuses the arm.
3. **Not in A10-H2.** Kling's cells enter neither A10-H2 nor any reading or kill rule of
   A10.5. The engines compared in A10.5 rule 2 ("every other engine's median at STILL") stay
   A10's three. A test asserts that the three engines' outputs are identical with and without
   Kling's cells.
4. **Power,** as A10.4.2: about 0.87 at ρ = 0.40 with n = 48.
5. **Measurement** on the study Mac (A10.3.6).

#### A15.7 Kill rules

1. One scout. Its reading is final: no second scout, no other Kling model, no change of
   setting after it.
2. Nothing from the scout changes A10's panels, prompts or settings; the arm runs them as
   frozen.
3. An A10-H1 null on Kling is reported as a null, and no follow-up test is added on it.
   "manipulation failed" is reported as the finding.
4. `kling_4` withdrawn or changed during the arm: generation stops, Aaron is told, nothing is
   substituted; the engine reads "incomplete: N cells missing" and its numbers are reported.

#### A15.8 Order

1. The `kling_4` route (first and last frame), the scout driver, the floor, the scout rule and
   the ladder and analysis changes, with tests on fixtures (before registration).
2. Registration, with A10.
3. The route record (A15.3.5); the scout from the study Mac in one batch, with a ledger row;
   its metrics; the decision rule printed and logged in FINDINGS.
4. If passed: the arm from the study Mac in steps of about £10, each with a ledger row; its
   metrics; the manipulation check printed and logged first.
5. The analysis in one pass, with A10's or after it; results published in an in-place
   refresh.

#### A15.9 Cost

Scout: 6 clips × 5 s × 12.56 credits ≈ 377 credits ≈ $3.77, about £3 at the promotional price
(to 30 Nov 2026 UTC); at the list price of 15.7 credits a second, ≈ $4.71, about £3.70. Arm, if
run: 48 clips ≈ 3,014 credits ≈ $30.14, about £24 at the promotional price; ≈ $37.68, about
£29, at list. Prices are re-checked against Runway's published credit rate on the day before
each batch, recorded in the ledger row, and the pinned rate is re-pinned at spend. One ledger
row per batch; Aaron is told at each further £10.

#### Registered predictions

- **Scout:** passes.
- **A10-H1 (Kling, A15):** realised motion predicts line drift (ρ > 0), supported, as A10
  predicts for LTX-2.3 and Gen-4.5.

Stated plainly: we expect Kling to take our panels, to move when asked, and to show the same
cost of moving as the other moving engines. If the scout fails, that is reported and no more
is spent. If the arm runs and the law does not hold on Kling, the motion law is narrower than
A10's three engines suggest, and the paper says so.

### A16 — 2026-11-10: a Midjourney video scout with a declared decision rule, run by hand; Midjourney in A10's motion test only if it passes

**STATUS: APPROVED — Aaron's go recorded 2026-11-10 ("Go to register A10–A16 once the open fixes below are made and two-stage reviewed"), after an independent review of the drafts whose findings he ruled on; every fix was made and reviewed before registration. Registered 2026-11-10 (UTC) with A10, by the same tagged
public commit. Cost: no money beyond Aaron's Midjourney Standard subscription, if its GPU time
covers the jobs (A16.11).**

**Why this is an amendment at all.** The same as A15's, on a third route: a hand-run web app
with no API, where each job's settings are typed, not sent by code.

**The problem it addresses.** Midjourney's image-to-video is the engine illustrators most use,
so its absence is the one an art-side reviewer would notice first. A16 has A15's shape: a
6-clip scout with A5's composition and A15's decision rule, then, only if it passes, a further
arm in A10's motion test. Two facts about the engine were unknown at registration (A16.4).
The rules that settle them are declared here, before either is found out.

#### A16.0 Status of any result derived from it — binding

1. As A15.0, with Midjourney for Kling. The arm, if it runs, is reported as "A10-H1
   (Midjourney, A16)".
2. **Niji is not run.** It makes drawings rather than animating them, so it would change the
   panels, not test an engine.
3. Every threshold A16 uses is declared below where it is applied.

#### A16.1 Seen before registration

- Everything A10.1, A14.1 and A15.1 list, the scout's motion floor included.
- Midjourney's web app, as Aaron and Claude knew it on 7 Nov 2026 (Aaron joined Midjourney
  that day, on its Standard plan). Whether its video honours a seed, and which motion
  setting to pin, were not known (A16.4).
- No Midjourney video of any benchmark panel existed for this study.

**Not computed by anyone before registration:** any Midjourney video of a benchmark panel; any
value or reading on one; the answers to A16.4. The job log refuses to print a scout or arm job,
and the analysis refuses to read Midjourney data, until this amendment's heading is in the
public pre-registration.

#### A16.2 Frozen artefacts

`docs/A16-MANIFEST.sha256` (sha256 `9bbfb5051f4baa7cdad593fbac32c72f618394e53bbc5613f4911b43fe1ceeb8`) lists, in release form: the
frozen pack and A10's ladder pack; `harness/pack_parser.py`; the scout's panels and A10's
twelve with their line-art layers; `harness/mj_log.py` (the hand-run job log, A16.5) and its
job list `analysis/out/a16_jobs.json` (every scout and arm job, with its cell id, panel, prompt
and settings, the A16.4 fields marked as unknown at registration); `harness/registration.py`;
`metrics/inkstab.py` and `metrics/motion.py`; `harness/scout.py` (the scout's metrics step,
`metrics --engine midjourney`); `analysis/scout_rule.py` with `analysis/out/scout_floor.json`
and the scout's cell list `analysis/out/scout_cells.json`; the
arm's cell list `analysis/out/a16_cells.json`, its builder `harness/ladder.py` (`build --arm
midjourney`, which also holds the scout readings the analysis reads) with
`harness/gen_video.py`, which it imports, and the panel list that builder reads,
`analysis/out/a10_panels.json`; `analysis/a10_ladder.py` with `analysis/rank_stats.py`,
which it imports; and the tests of each.

#### A16.3 Engine, route and version

1. **Route.** Midjourney's image-to-video through its web app, by hand, by Aaron, on his
   Standard plan. If the Midjourney MCP opens to Aaron before the arm begins, the arm may run
   through it instead; through the MCP too, each job is started by hand, one at a time through
   the job log (A16.5), and the route and its job ids are recorded in `docs/A16-SETUP.md`. The
   arm's route is fixed before its first job, is the same for all 48
   jobs, and is recorded in every manifest line; the scout and the arm each keep one route
   throughout.
2. **Every job.** The panel uploaded as the start frame (FLINT cells: the last panel as the end
   frame, if Midjourney takes one, A16.4.3); the manual mode, with the frozen prompt pasted
   verbatim as the prompt, never a mode that writes its own; HD (720p) and 5 s, one clip, never
   extended; the motion setting pinned by A16.4.2; personalisation, style references and
   moodboards off; every other setting at Midjourney's default, recorded as shown; no
   parameter added to the prompt beyond those A16.4 declares.
3. **Manifest line per job:** cell id, Midjourney job id, panel, prompt, the model version as
   Midjourney labels it, every setting as the job page shows it, seed (A16.4.1), delivered frame
   size and duration, date and time, route, the download option used, the delivered file's
   sha256, and the result of the check (A16.5).
4. **More than one video per job.** If a job returns more than one video, the draw is the
   first in Midjourney's own order, fixed here before any job. The others are kept privately,
   recorded by sha256, and never measured, viewed to choose between, or released.
5. **Audio,** if a file carries any, is removed as A15.3.4.
6. **Public by plan.** On Standard every upload and every clip appears in Midjourney's public
   gallery and is licensed to Midjourney under its terms. The panels are CC BY already. No
   rater in any study is pointed to the gallery, and no A16 clip is rated by anyone.

#### A16.4 Unknown at registration, and the rules declared for each

Two facts were unknown when A16 was registered: whether Midjourney's video honours a seed, and
which motion setting to pin. Both are found out after registration and before the scout's
first job, recorded with the date in `docs/A16-SETUP.md` (the screenshots are kept privately and
named there by sha256), committed, and quoted in FINDINGS; `docs/A16-SETUP.md` ships in the release as
the operator's own record (A14.3.1), never as a copy of Midjourney's pages. Neither is found out
by looking at a video of a benchmark panel. The
answers below are then written once, from that file, to `analysis/out/a16_setup.json` with
the file's sha256 (`harness/mj_log.py setup`), and never changed. `harness/mj_log.py` refuses to
print or log a job once `docs/A16-SETUP.md`'s current sha256 differs from the one in that setup file, as
`harness/scout.py run` does for A15.3.5's route document.

1. **Seed.** Two jobs with the same image, prompt and settings and an explicit seed,
   20260812, on a test image that is not in the dataset and is cleared for public posting.
   The seed is honoured when the two jobs' first videos have identical decoded frames (the md5
   of every decoded frame equal); otherwise it is not. If honoured, every A16 job carries seed
   20260812 (§5's seed), recorded. If not, or if Midjourney's video takes no seed, no seed is
   sent, the manifest records `seed: null` with the reason, and each cell is one draw, as
   Gen-4.5's are in A10.3.3. The two jobs are run by hand and recorded, with their job ids, in
   `docs/A16-SETUP.md`; their videos are recorded and never measured.
2. **Motion setting.** The pinned value is Midjourney's default motion setting for
   image-to-video as the interface presents it on the day of the scout's first job, recorded
   verbatim with a screenshot. It is the same for every A16 job, scout and arm, at all four
   ladder levels. It is never changed to make the engine move: the prompt is the manipulation
   (A10.3.5).

Settled the same way and recorded in the same file, before the scout:

3. **End frame.** If Midjourney's video takes an end frame, the three FLINT cells run as A5
   composed them. If not, they are recorded "n/a (no last-frame conditioning)", as §5 records
   FLINT for such engines, and the scout is its three BURST draws.
4. **Resolution.** If HD (720p) video is not available on Aaron's plan, nothing runs at
   another resolution, and Aaron is told.
5. **The frozen prompt, verbatim.** If the interface rejects or rewrites any part of a frozen
   prompt (a character it reads as a parameter, for example), nothing runs, and Aaron is told:
   the frozen prompt is never edited to suit an engine.
6. **Videos per job.** How many videos one job returns, and whether that can be set to one;
   A16.3.4 decides the draw either way.

#### A16.5 The hand run: checks, void jobs, refusals and failures

1. **Each job checked before the next.** Jobs run in the order of
   `analysis/out/a16_jobs.json`. Before each job, `harness/mj_log.py` prints its cell id,
   panel, exact prompt and settings. After it, the job page is checked against them field by
   field (image, end image, prompt, settings, resolution, duration, model version); the job id
   and the downloaded file are entered; the tool checks the file (it plays, lasts 5 s within
   one frame, has the recorded frame size) and writes the manifest line. Downloads are saved to
   `runs/midjourney/incoming/`, which is never tracked or released, and the tool records only
   from there. Every job and its
   outcome is logged in `runs/a16_job_log.jsonl`. The next job is printed only after that line
   exists. One slip in a hand run spoils a cell, and this check is what catches it. The tool
   refuses to print the scout's second job until the first is recorded. The operator checks the
   scout's first job as A14's first draw is checked (A14.3.4): frame size, audio stripped, and its
   first frame matched to the panel by eye from its strip (`analysis/extract_frames.py`), and
   records the checks in the ledger note; if a check fails, no further job is run.
2. **Void job:** a job whose image, prompt, settings or resolution (the delivered frame
   size) differs from its line; a video of the wrong length is a failed job (A16.5.4), not a
   void one. Its video is never measured or used; it is kept privately and recorded as void,
   with the reason. The cell is submitted once more, correctly. A second void on the same cell
   stops the run, and Aaron is told.
3. **Refused job:** Midjourney declines to run the job on moderation grounds (a block or flag
   message, recorded verbatim with a screenshot). It is resubmitted once, identically. Refused
   on both attempts, the cell is recorded as refused, a result and not a gap (§5), and n is
   stated.
4. **Failed job:** any job that ends without a playable video, or with one that does not last
   5 s within one frame (an error, a job that stalls or vanishes, a download that does not
   play, a video of the wrong length). It is not a draw: it
   is recorded in the job log and resubmitted identically. Three failed attempts on one cell
   stop the run, and Aaron is told; that is a service or operator fault, never a refusal.
5. **Nothing is chosen between attempts.** A cell's draw is the first job that completes and
   passes the check.

#### A16.6 The scout

A15.4's composition (A5's, quoted there) on Midjourney as A16.3 and A16.4 set it, with the
frozen FLINT and BURST prompts. Cell ids `flint-<first>--<last>_mjv` and
`act-black-3_burst_mjv-h1` to `-h3`; clips `runs/midjourney/<cell id>.mp4`; metrics in
`runs/metrics-scout/` and `runs/metrics-motion-scout/`. The scout's clips never enter A10.

#### A16.7 The decision rule

A15.5's rule, verbatim, with "Midjourney" for "Kling" in its last reading and the same motion
floor, 0.00160571; read once, under the same conditions (the metrics step's record,
`analysis/out/a16_scout_metrics.json`, must name every delivered clip with the sha256 of each
metric file, or the rule refuses to write a reading, "metrics step not complete"; a clip left
without a metric file by a tool failure reads "not measurable" only after one confirming re-run
of the metrics step has failed on it again, its recorded reasons printed beside the reading; a
non-finite metric also reads "not measurable"; a metric file deleted or changed since the
record is refused; the rule is "not read yet" only while a cell has neither clip nor refused
line), and logged in FINDINGS before any arm job is printed. Reading 2's cell ids are joined by
", "; the reading, with every input, the floor and each cell's manifest seed, is written to
`analysis/out/a16_scout.json`, and FINDINGS takes the line the tool prints (`FINDINGS: A16
scout (midjourney), <date>: <reading> [...]`). If the FLINT cells are "n/a" (A16.4.3), the
scout's cells are its three BURST draws, and reading 1 counts refusals among those three.

#### A16.8 If the scout passes: Midjourney in A10's motion test

A15.6, item by item, with Midjourney for Kling: 48 cells
`ladder-<panel>_<still|low|mid|high>_mjv`, clips `runs/midjourney/<cell id>.mp4`, the cell list
in `analysis/out/a16_cells.json`, run through the job log (A16.5), read as A10 reads its
engines (the arm's metrics step is `harness/ladder.py metrics --engine midjourney`), and kept
out of A10-H2. The job list runs the 48 jobs panel by panel, in the order of
A10's cell list. No arm job is printed and no arm clip is made unless
`analysis/out/a16_scout.json` exists and its logged reading is exactly "scout passed:
Midjourney joins A10's motion test as a further engine" (`harness/ladder.py` refuses
otherwise; the job log, A16.5, is to do the same). The arm is analysed only once this
amendment is in the public
pre-registration; until then the analysis lists it as "not analysed: A16 not public". If the
scout fails, the arm is listed as "not run: " followed by the scout's logged reading, taken
from `analysis/out/a16_scout.json`, which `analysis/scout_rule.py` writes beside its FINDINGS
entry (A16.7); any logged reading other than A16.7's own refuses the arm.

#### A16.9 Kill rules

1. A15.7, with Midjourney for Kling.
2. A16.4's answers, once recorded, are fixed for every A16 job.
3. If Midjourney's video model changes during the scout or the arm (a new version label on
   the job page), generation stops and Aaron is told; versions are never mixed, and the engine
   reads "incomplete: N cells missing", its numbers reported. A change between the scout and the
   arm stops the arm at its first job, because the arm would otherwise run a model that was
   never scouted.

#### A16.10 Order

1. The job list, the job log and the analysis changes, with tests on fixtures (before
   registration).
2. Registration, with A10.
3. A16.4, found out and committed.
4. The scout by hand; its metrics on the study Mac; the decision rule printed and logged in
   FINDINGS.
5. If passed: the arm, through the route fixed for it; its metrics; the manipulation check
   printed and logged first.
6. The analysis in one pass; results published in an in-place refresh.

#### A16.11 Cost

No money beyond Aaron's Standard subscription, if its GPU time covers about 60 HD video jobs
(two seed-check jobs, six scout jobs, 48 arm jobs and any resubmissions); whether it does is
recorded with A16.4, and any extra GPU time bought is a ledger row. About one day of
attention.

#### Registered predictions

- **Scout:** passes.
- **A10-H1 (Midjourney, A16):** realised motion predicts line drift (ρ > 0), supported.

Stated plainly: we expect the engine illustrators use most to move when asked and to pay the
same cost of moving in its lines. Either outcome is reported, and every reading above is
reported whatever it shows.
