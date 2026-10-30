# ToS / licence review — published evaluations + output redistribution

**Date:** 2026-08-12 · **Method:** agent-assisted primary-source sweep (six engines in
parallel, one adversarial completeness critique), human-reviewed. Quotes below are
verbatim from the cited documents unless marked *(analyst note)*. Negative claims
("no benchmark clause exists") rest on full-text keyword search of the cited document
for at least: benchmark, evaluat-, compar-, publicity, performance, disparag-.

**Question:** may StillDrawn (a) publish per-engine quantitative comparisons/rankings,
(b) redistribute generated outputs in an arXiv paper and a CC-BY 4.0 dataset, and
(c) do so from the UK — under each engine's current terms?

## Verdicts

| Engine | Role | Verdict | Confidence |
|---|---|---|---|
| Runway Gen-4 Turbo / Gen-4.5 (dev API) | I2V hosted | **include** (caveats) | high |
| gemini_2.5_flash via Runway API | panel stills | **include** (caveats) | high |
| MiniMax H3 hosted via fal.ai | I2V hosted | **include** (caveats) | medium |
| Wan 2.2 TI2V-5B (Apache-2.0, local) | I2V local | **include** | high |
| LTX-2.3 (LTX-2 Community License, local) | I2V local | **include** (caveats) | high |
| Illustrious-XL v0.1 (FAIPL 1.0-SD, local) | panel stills | **include** | high |

No engine is excluded. Caveats and required actions below.

## Runway (dev API — Gen-4 Turbo, Gen-4.5; also the contract layer for gemini stills)

Governing document: **Runway Terms of Use** (unified; expressly governs "APIS"),
runway.com/terms-of-use, last updated 2026-05-11, fetched 2026-08-12. Usage Policy
(2026-03-06) is content-safety only.

- **Eval publication:** unaddressed — no anti-benchmarking, publicity, or
  performance-disclosure clause exists in the ToU *(analyst note: absence verified
  against full page text)*. Permitted by default.
- **Outputs:** §4.4 — "The Company does not claim ownership of any of your Inputs or
  Outputs. Subject to your compliance with the Agreement, the Company does not restrict
  your commercial use of your Outputs." (A no-claim/no-restriction formulation, not an
  affirmative assignment.) Runway retains a non-exclusive licence-back over Inputs and
  Outputs for training — non-exclusive, so it does not block CC-BY release.
- **⚠ The one genuine tension — §5 (User Conduct):** "You shall not (and shall not
  permit any third party to) … [use] the Services (including, but not limited to,
  Outputs) to create, train, develop, or improve similar or competitive products or
  services." A CC-BY 4.0 release expressly permits downstream training, so releasing
  Runway-generated items training-ready is arguably "permitting a third party" to do
  what §5(viii) forbids. Publishing *metrics* does not plausibly trigger the clause;
  the *dataset* items do. **Action (release gate, Phase 6, Aaron's call):** either add
  a dataset-card use-note on the Runway-generated items (provider terms may restrict
  their use for training competing generative models) or accept the ambiguity with
  disclosure. Verify the clause verbatim at dev-portal signup (see Open items).
- Attribution: "Powered by Runway" attaches to end-user *applications*; a paper/dataset
  is not one. Credit the models anyway (scholarly convention).
- Territory: no exclusions; UK fine. Usage Policy: do not prompt in the style of a
  named living artist (StillDrawn prompts don't), no copyrighted characters (none).

## gemini_2.5_flash (via Runway API)

The contract is with Runway alone — the ToU contains no clause incorporating Google's
terms for third-party models on the platform; Runway's Enterprise FAQ states Runway
terms apply to third-party models. Google's own Gemini API Additional Terms (which
would bind only direct Google customers) also claim no ownership over generated content.

- **⚠ SynthID:** Google states all generated images carry an invisible SynthID
  watermark. Every gemini panel in the dataset carries it. **Action:** disclose in
  `dataset/DATASHEET.md`; no removal attempts (both Google and Runway terms prohibit
  circumventing controls).
- **Model churn:** the 2.5-flash image series is marked legacy by Google. Model ID and
  generation dates are pinned in every recipe JSON; pre-registration records versions.

## MiniMax H3 hosted via fal.ai

Governing documents: fal Terms of Service (2026-03-03), fal API Services Supplemental
Terms, fal Acceptable Use Policy — fal.ai/terms, fal.ai/legal/api-services,
fal.ai/legal/acceptable-use-policy.

- **Eval publication:** unaddressed in all three fal documents — permitted by default.
  The "similar product or competitive product" development bar does not reach a
  metrics paper.
- **Outputs:** fal disclaims warranties over Output Content and imposes only
  lawful/non-infringing use; it does not affirmatively assign output ownership.
  Redistribution in paper + dataset is permitted; ownership is left to background law.
- **⚠ Flow-through:** fal's Third-Party Content clause ("may be subject to additional
  terms … of the providers") plus the AUP's compliance hook import whatever MiniMax
  terms actually govern the hosted endpoint. Per MiniMax's own positioning these are
  API terms, **not** the H3 Community License — the open-weights licence (with its UK
  exclusion) does not govern hosted API use. The UK carve-out therefore does NOT
  apply to StillDrawn's hosted runs. It DOES apply if local/rented H3 weights are ever
  used (£100-tier item: file the MiniMax licence application first).
- Attribution: the H3 licence's mandatory "MiniMax H3" display duty attaches to
  commercial products/services; a paper/dataset is not one. Credit anyway.

## Wan 2.2 TI2V-5B (local)

Licence: **standard Apache-2.0**, verified verbatim at the GitHub LICENSE.txt the
model card points to; GGUF quant repos agree. Cleanest engine in the benchmark.

- No eval, output, territory, or field-of-use restrictions of any kind.
- Model card: "We claim no rights over the your generated contents" (typo genuine).
- The model card's single conduct sentence is card prose, not licence text.
- Housekeeping: the HF repo tree itself lacks a LICENSE file; canonical text is the
  GitHub LICENSE.txt — snapshot taken (see Open items).

## LTX-2.3 (local)

Licence: **LTX-2 Community License Agreement (2026-01-05)** — the LICENSE file inside
the Lightricks/LTX-2.3 HF repo — plus the incorporated LTX Acceptable Use Policy.
*Not* Apache-2.0, despite some secondary sources claiming so.

- **Eval publication:** expressly licensed — "Use" is defined to include "running,
  training, **evaluating** and/or re-parametrizing LTX-2".
- **Outputs:** §5 — "Licensor claims no rights in the Output you generate using
  LTX-2." Output use remains bound by Attachment A + AUP.
- **⚠ Machine-generated disclosure:** Attachment A item 5 requires disseminated
  content to be expressly labelled machine-generated. **Action:** the datasheet and
  paper state this for all clips (they would anyway — it is the paper's subject).
- Revenue threshold: commercial licence required at ≥$10M annual revenue — far above
  this project. The newer LTX-2.x licence (2026-08-11, governing 2.5+) adds an explicit
  research carve-out; 2.3 relies on the threshold. Version→licence mapping ambiguity
  (in-repo LICENSE vs model-card link) flagged in the paper's compliance note.
- Open question: whether LTX-2.3 outputs carry the latent watermark the 2.x licence
  references — check before release; disclose like SynthID if so.

## Illustrious-XL v0.1 (local — the checkpoint in use: `Illustrious-XL-v0.1.safetensors`)

Licence: **Fair AI Public License 1.0-SD** (v0.1 specifically; later variants differ —
v1.0/v1.1 RAIL++-M, v2.0 CreativeML OpenRAIL; v3.x has no verifiable open licence and
must not be used for dataset panels).

- **Outputs:** "The output of this software is not covered by this license, and no
  contributor claims any rights to it." Model card: "We do not restrict any upload or
  spread of the generation results." CC-BY release of generated panels is clean.
- FAIPL's copyleft attaches to the model, not outputs — irrelevant here (no
  fine-tuning for the benchmark).
- **Action:** pin the checkpoint hash in the paper; keep sourcing panels from v0.1.

## Cross-cutting actions (from the adversarial critique)

1. **Terms snapshots:** capture live copies + SHA-256 of the governing documents at the
   pre-registration freeze (`docs/tos-snapshots/`) — terms change with continued use
   as acceptance; the review is dated evidence.
2. **Inputs rule:** only benchmark stills are ever
   uploaded to hosted APIs — Runway §4.4's licence-back covers *Inputs* too, and fal
   transfers customer content to MiniMax. Nothing from the author's private material touches a hosted API.
3. **Watermark disclosure symmetry:** SynthID (gemini) disclosed; check Runway C2PA
   metadata and LTX latent watermark before release; disclose whatever is found.
4. **Machine-generated labelling** everywhere content ships (LTX obligation; good
   practice for all).

## Open items

- [x] Runway §5(viii) verified verbatim against the 2026-08-12 snapshot (quoted in
  `NOTICE-PROVIDERS.md`).
- [x] Any Supplemental Terms at the Runway developer-portal click-through: checked
  2026-10-30 in the signed-in portal, which links only the Terms of Use, Privacy Policy
  and Code of Conduct; no separate agreement. The sign-up screen itself could not be
  recovered (see the 2026-10-30 re-check).
- [x] `docs/tos-snapshots/` captured 2026-08-12, before generation (hashes in
  `SHA256SUMS`; the third-party pages themselves are not redistributed).
- [x] LTX-2.3 watermark check: no watermarking code in the local inference stack
  (container audit 2026-08-13; see the datasheet).
- [x] Release-gate decision (2026-09-30): licence unchanged (CC BY 4.0) plus an
  informational provider-terms notice that asks users not to train generative
  models on the Runway items — `NOTICE-PROVIDERS.md`.

The review's working notes are not part of the release; this file is the
summary of record — the paper's compliance paragraph is
written from here.

## Re-check — 2026-10-01 (before release; Runway dev-portal terms and Seedance)

Fresh captures are in `tos-snapshots/*_captured-2026-10-01.html`.

**Runway** (Terms of Use last updated 2026-09-15; the version in force when the clips
were generated was last updated 2026-05-11). §4.4 (outputs) and §5(viii) are
**character-for-character identical** in the two versions. The only substantive change is
that a Usage Policy (effective 2026-03-06) is now incorporated into the terms; it covers
real people, protected IP and style-of-a-living-artist, and sexual content, and says nothing
about training, datasets or provenance. No clause restricts publishing evaluations. The ToU
has no dedicated API section; "Supplemental Terms" shown at developer-portal sign-up would
control over the ToU, and that click-through still needs a logged-in check (not possible
from a script). Runway markets contractual no-training commitments for Runway Dev, which
concern Runway's use of data, not the user's.

**MiniMax H3 and Seedance 2.0 (both via fal).** The contract is with fal alone. fal ToS
§14.3 (last updated 2026-09-08; identical to the 2026-07-31 capture) provides: "You may
not: 1. use or access any Third-Party Materials or any outputs derived from such materials
to develop, modify, fine-tune, or improve any products or services that compete with those
Third Party Materials, including to develop, fine-tune, or train any artificial intelligence
or machine learning algorithms or models". "Third-Party Materials" includes ML models hosted
by third parties, so this reaches both engines' outputs. Unlike Runway §5, it restricts
"you" only: there is no "permit a third party" limb, so a licence grant does not itself
breach it. fal's API Services supplement says fal will not use client content to train fal's own
products, with an exception for models it marks "Pending Enterprise Ready". No fal clause restricts publishing evaluations or benchmarks.

**ByteDance / BytePlus (Seedance's developer).** BytePlus's own Terms of Service (last
updated 2024-03-18) do not address AI outputs, benchmarking, competing models or
publication. They would bind direct BytePlus customers, not fal customers; by the same
reasoning as Gemini-via-Runway above, the operative terms for these clips are fal's. The
public controversy over Seedance 2.0 concerns film and character IP replicated from
training data; every Seedance input here is an original neutral panel.

**Decision (2026-10-01).** Release all items under CC BY 4.0 and extend
`NOTICE-PROVIDERS.md` to cover the fal items, with the §14.3 text quoted verbatim, alongside
the Runway request. Not chosen: dropping the nine Seedance clips (unanalysed in the paper,
but the exposure is no greater than that of the 148 H3 clips and removal would unwind counts
across the manifest, datasheet and paper), adding a custom no-training licence (non-standard;
cuts against CC BY's no-additional-restrictions design), and asking either provider for
written permission (slow, and the clauses restrict the author's own use rather than
downstream readers).


## Re-check — 2026-10-09 (release day)

Aaron saved the Runway Terms of Use while logged in (`tos-snapshots/runway-terms-of-use_captured-2026-10-09.pdf`).
Still the 2026-09-15 version; §4.4 and §5(viii) word-for-word identical to the 2026-10-01
capture. The ToU lists no named Supplemental Terms; any would have been "presented to you for
your acceptance when you sign up". The 2026-08-12 open item closes once
Aaron confirms the developer portal presented no separate agreement at sign-up. Nothing restricts publishing evaluations or the
CC BY release beyond §5(viii), which `NOTICE-PROVIDERS.md` already addresses.

## Re-check — 2026-10-30 (the developer-portal open item)

Checked with Aaron in his signed-in Runway developer portal (dev.runwayml.com). Its only legal
links are the Terms of Use (now dated 23 Oct 2026), the Privacy Policy and the Code of Conduct,
which redirects to the Usage Policy (6 Mar 2026: content rules only, nothing on training,
datasets or evaluation). The account has no API agreement, legal or settings page, and no public
API terms exist (`/api-terms` returns 404). In the 23 Oct Terms, §5(viii) reads as quoted above, and
§1's "Powered by Runway" applies to applications built on the API. What the sign-up screen showed
in August could not be recovered. Aaron closed the item on this evidence on 30 Oct 2026.
