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
