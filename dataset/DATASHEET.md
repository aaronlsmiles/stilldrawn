# StillDrawn dataset datasheet

*Structure after Gebru et al., "Datasheets for Datasets". **Status: release 1.0.**
Composition was fixed on 2026-08-12, before any benchmark generation. Pre-release
checks are complete: the provenance-mark audit (2026-08-13), the provider-terms
decision (2026-09-30, see `NOTICE-PROVIDERS.md`) and the removal of embedded
generator graphs from panel files (2026-09-30, see "Release processing"). The
benchmark was developed under the working name InkBench and renamed StillDrawn
before release.*

## Motivation

**Why was this dataset created?** To measure how well inked line art survives
image-to-video generation: line weight, screentone, contour closure and the
black-and-white register. No public dataset pairs inked panels with their
line-art layers and full generation recipes for this purpose. Created by Aaron
Smiles (independent researcher, UK) for the StillDrawn benchmark paper; no
external funding.

## Composition

**Benchmark panels (29).** These are the panels the paper's design and frozen
tests are built on.

- **27 neutral panels**: 3 content classes (character close-up · action with
  foreshortening · establishing environment) × 3 ink treatments (line only ·
  screentone · heavy blacks with one reserved white) × 3 panels. All subjects are
  original and neutral: no named properties, no franchise content, no real
  people, no text.
- **1 creator-IP panel**, `cip-act-tank-1` ("cip" = creator-IP): an inked
  tank-shatter action panel from the author's own comic project, cleared panel by
  panel by the author on 2026-08-12. Two further candidates were refused and are
  absent. Its recipe is **described, not reproducible**: the production chain is
  named (line extraction → inversion → img2img inking) but its tuned settings are
  withheld, because the benchmark ships evaluation artifacts, not the author's
  production stack.
- **1 chain-made neutral panel**, `chain-est-cosmic-1` (a cracked moon over an ice
  field; original and neutral), built for the benchmark through the same private
  chain and likewise described, not reproducible. Added under pre-registration
  amendment A1 as a space-content establishing probe. Native 1344×768;
  heavy-black and spot-white register, no screentone dots (paper-white p90 0.624,
  black fraction 0.115).

**Ground-series variants (5).** `ground-cu-line-1-v052`, `-v065`, `-v080`, `-v090`
and `-v100` are copies of `cu-line-1` with a global linear luminance scale
k ∈ {0.52, 0.65, 0.80, 0.90, 1.00} applied, so the paper darkens while no line
moves. Each has a derived recipe recording its source and transform, and a copy
of the source line-art layer. They drive the causal ground-value series of
amendment A3 (the paper's ground section). They are **not** part of the 29-panel
design and are excluded from the frozen §8 test. The k = 1.00 variant is
pixel-identical to `cu-line-1` (verified on release), which is why the paper
treats its three H3 draws as a triplicate.

**Per panel, the release ships:** `panels/<id>.png` (1344×768; the creator-IP
panel is native 1024×1792 portrait, see deviations) · `lineart/<id>-lines.png`
(extraction pass, black on white) · `recipes/<id>.json` (engine, model, prompt,
negative, seed, settings, date, reroll flag). Per-panel covariates are in
`panel-metadata.json` for the 29 benchmark panels and in the derived recipes for
the 5 ground variants.

**Generated clips (373).** The release contains every clip the study generated:

| Origin | Clips | Analysed in the paper? |
|---|---:|---|
| Primary run matrix: 33 cells × 5 engines + 6 FLINT cells on MiniMax H3 (171 cells; 1 recorded refusal) | 170 | Yes |
| Repeat-stability probe: a second draw of every primary cell on the three hosted engines (99 cells; the same refusal recurs) | 98 | Yes |
| Ground-value series, amendment A3: 5 variants × 5 engines, IDLE motion | 25 | Yes |
| Hazard-rate study, amendment A4: 8 cells on MiniMax H3, 10 draws per cell counting existing draws (71 new clips) | 71 | No — released for reuse |
| Seedance 2.0 scout, amendment A5: 6 FLINT pairs + 3 BURST draws | 9 | No — released for reuse |

By folder: `gen4_turbo` 69 · `gen4.5` 71 · `h3-fal` 148 · `wan22` 38 · `ltx23` 38 ·
`seedance` 9. How the manifest records these, including refusals and superseded
lines, is explained in `runs/README.md`.

One smoke-test panel used to validate the harness is not part of the release.

## Collection process

Panels are AI-generated, produced through `harness/gen_panel.py` with the recipe
recorded before acceptance. Engines: 9 panels via the Runway developer API
(`gemini_2.5_flash`, prose prompts); 18 panels via local Illustrious-XL v0.1
(booru-tag prompts; checkpoint SHA-256 `3e15ba00387db678ab4a099f75771c4f5ac67fda9e7100a01d263eaf30145aa9`); 2 via the private chain above. The panel pack
(`panel-pack.md`) was written for this benchmark on 2026-08-12. Each panel had
one reroll allowance; rerolls carry `"reroll": true` and are counted in
`LEDGER.md`. Line-art layers: AnimeLineArt (`netG.pth`) extraction at resolution
1024, inverted to black on white.

Clips were generated through `harness/matrix.py` and `harness/gen_video.py` under
the frozen protocol in `docs/PREREGISTRATION.md`. Engine versions, seeds,
resolutions, wall-clock and per-clip cost are pinned per clip in
`runs/manifest.jsonl`.

## Release processing

The release copies differ from the generation outputs **only in metadata**:

- **Embedded generator graphs removed.** The ComfyUI-generated panels embedded
  their full generation graph in a PNG text chunk. For the two chain panels that
  graph would have disclosed the withheld chain settings, so it was removed from
  every panel that carried one. The recipe JSONs remain the provenance record.
  Pixels are verified identical. Released hashes, and commitments to the
  original files, are in `PANEL-HASHES.csv` (see `docs/REDACTIONS.md`).
- **One identifier neutralised.** The creator-IP panel's id, and every file name
  and reference derived from it, now reads `cip-act-tank-1`. In the six
  local-engine clips of that panel the id also appeared inside the embedded
  ComfyUI workflow metadata and was rewritten there; the video stream is
  untouched. Commitments to the original files are in `runs/CLIP-HASHES.csv`.
- **Absolute paths** in the manifest and metric files were made relative to the
  repository root.
- **Human-check ratings** are released as pseudonymised per-rater scores, without
  timestamps, timings or comments (see `analysis/human_check/README.md`).
- **Frozen documents** are verbatim apart from the redactions listed in
  `docs/REDACTIONS.md`, none of which touches protocol content.

## Provenance, licensing, known marks

- Dataset licence: **CC BY 4.0** (`LICENSE-DATA`). Attribution: "StillDrawn
  dataset (Aaron Smiles, 2026)". Code: MIT (`LICENSE-CODE`).
- **Provider terms:** items generated through commercial services are listed in
  `NOTICE-PROVIDERS.md`, with the relevant Runway and fal clauses quoted. The notice is
  informational and does not modify the licence. Engine terms were reviewed
  before generation (`docs/TOS-REVIEW.md`).
- **Gemini panels:** the 9 Gemini panels carry a C2PA Content Credentials manifest
  signed by Google ("Created by Google Generative AI", recording that an
  imperceptible SynthID watermark was applied; no account identifiers), plus
  XMP/IPTC "AI-generated" metadata. These files ship byte-exact. The 5 ground
  variants derived from `cu-line-1` keep its pixels, and so its invisible SynthID
  watermark, but not its metadata.
- **SynthID:** the 9 Gemini panels carry Google's invisible SynthID watermark. Whether SynthID traces survive
  image-to-video generation is unstudied; no claim is made either way for clips
  generated from those panels.
- **Clip provenance marks** (container-level audit of the 170 primary clips on
  2026-08-13, extended to every hosted clip on release):
  - *Runway (140 clips: Gen-4 Turbo 69, Gen-4.5 71):* every clip embeds a C2PA
    Content Credentials manifest signed by RUNWAY AI, INC., asserting creation by
    "RunwayML Video Generation" (digitalSourceType: trainedAlgorithmicMedia). BMFF
    hash hard-binding only; no soft-binding or invisible-watermark assertion.
    The manifest does not distinguish Turbo from 4.5; `runs/manifest.jsonl` does.
  - *MiniMax H3 via fal (148 clips):* C2PA-signed by the serving platform ("fal –
    Features & Labels Inc.", self-issued root CA, so third-party validators report
    an unrecognised signer; that is expected, not tampering). A custom
    `ai.fal.info` assertion permanently records the endpoint and the request ID of
    the author's account: an identifier, not a credential. Stripping it would
    break the hash binding. Any MiniMax-side invisible pixel watermark is
    undocumented and locally undetectable; no visible watermark is present.
  - *Seedance 2.0 via fal (9 clips):* no C2PA manifest present.
  - *Wan 2.2 and LTX-2.3 (76 clips, local open weights):* no C2PA, no watermark.
    No watermarking code exists in either open inference stack, so none was
    bypassed. Each clip embeds its complete ComfyUI workflow JSON (model files,
    prompts, source-panel hash; no local paths) in MP4 `udta` metadata as
    provenance. The LTX-2 Community License (2026-01-05) requires an intelligible
    machine-generated disclosure; this datasheet provides it, and it covers the
    video clips as well as the panels.
  - **Release rule:** the 288 C2PA-signed clips ship byte-exact. Any re-encode or
    remux voids the manifests' hash binding.
- All content is machine-generated and labelled as such.

## Per-panel metadata

`panel-metadata.json` records, per benchmark panel: content class, treatment,
engine, model, seed, reroll flag, date, **paper-white p90 luminance** and black
pixel fraction. Paper-white p90 is the recorded covariate for the local line-only
grey-ground tendency (see deviations): local Illustrious line-art output often
renders the paper as light grey rather than white. The affected panels are kept
as authentic engine output, with the measurement in the metadata (range across
local line-only panels: p90 ≈ 0.52–0.99; hosted line-only panels are uniformly
white).

## Per-panel deviations (recorded, kept)

- **act-black-1**: keeps a white margin around the drawn area. The full-bleed
  instruction was only partly followed and the panel's single reroll was spent.
  Kept as generated; any border-induced I2V behaviour is attributable.
- **act-black-2**: breaks the "one reserved white" rule (white energy throughout).
  Kept deliberately: the heavy-blacks register is emphatic and the panel is a
  stronger stress case.
- **cu-black-3**: the reserved white fragments into several lantern glares rather
  than one region. Kept for the same reason.
- **cip-act-tank-1** (creator-IP panel): native portrait 1024×1792, a production
  plate that cannot be regenerated at the core resolution because its recipe is
  described, not reproducible. Its clip cells run at 720:1280 portrait (the same
  pixel budget as the core's 1280:720), identically on every engine
  (pre-registration amendment A1). Register note: fine line plus tone, **no true
  blacks** (black fraction 0.000 at the <0.1 luminance threshold; paper-white p90
  0.996). Its darkest marks sit above the core panels' black range, which is
  itself a covariate for the heavy-blacks comparisons.

## Uses and limitations

- **Intended:** evaluating image-to-video stability on inked and line-art
  substrates; reproducing the StillDrawn paper; extending the benchmark with new
  engines.
- **Limitations:** two panel-generation engines only (style diversity is bounded
  by them); landscape 1344×768 only (a deliberate crop-confound control); English
  prompts; synthetic subjects; the ink treatments are three discrete points on a
  continuum. Copyright in AI-generated images is weak or absent in some
  jurisdictions; the CC BY grant conveys what exists.
- **Not intended for:** training generative models to imitate any specific
  artist. The creator-IP panel must additionally not be used to imitate the
  author's comic project. See `NOTICE-PROVIDERS.md` for the provider-terms
  request covering the Runway-generated items.

## Maintenance

Versioned releases are archived on Zenodo (DOI: [`10.5281/zenodo.23072784`](https://doi.org/10.5281/zenodo.23072784), version 1.0.0); code and issues live at
https://github.com/aaronlsmiles/stilldrawn. Corrections are published as new
Zenodo versions under the same concept DOI.
