# Allowed-motion masks: rules

Written on 30 October 2026, before any mask was drawn. These rules govern the two mask sets in this folder, `allowed-aaron.json` and `allowed-agent.json`, and the eligibility test that `analysis/a9_eligibility.py` computes from them for amendment A9 (section A9.4). They change only by a dated note at the end of this file, and never after A9 is registered.

## What a mask is

Test 2 has 22 rows: a panel and a motion class, 11 idle and 11 burst, on 20 panels (the two A1 panels, `cip-act-tank-1` and `chain-est-cosmic-1`, carry one row per class). For each row, a mask M marks where the row's prompt allows the drawing to move.

A mask is stored as polygons in fractions of the panel: x is a fraction of the width and y of the height, with the origin at the top-left. The file format is `stilldrawn-allowed-regions/1`: top-level `schema`, `set`, `drawn_by`, `rule`, `notes` and `rows`; each row, keyed `<panel>_<idle|burst>` by public id, holds `panel`, `motion`, `panel_px` (width, height), `allowed` (polygons of at least 3 points, every coordinate in [0, 1]) and `status`. A row whose prompt allows nothing to move has the status `nothing-allowed` and no polygons; its M is empty.

## The drawing rule

Idle marks bodies (breathing), hair, cloth, foliage, smoke, water, cloud and particles. Burst marks the actor, its plausible path, whatever it strikes or sheds, and anything attached to it. Never rigid structure, ground, lettering or the camera. When unsure, leave it unmarked.

The rule decides what may be marked. The motion prompt only tells you which kind of motion the row asks for (idle or burst); its wording does not widen the rule.

The rule's sentence for the row's motion class applies to that row; its last two sentences ("Never rigid structure…" and "When unsure…") apply to every row. Both drawers get the paragraph above word for word. Leaving a doubtful region unmarked makes the measured region larger, which works against the hypothesis that masking shrinks the gap.

## Who draws, and how

- **Aaron** (set `aaron`, drawn by `AARON`) in `draw.html`, served locally. The page shows only the panel, the row's public id, its prompt verbatim and the drawing rule. No clip, frame or result is shown or reachable from it.
- **A blind second drawer** (set `agent`): one run of a Read-only agent (claude-opus-5-5, effort high) given a scratch folder that holds the 20 panels, a grid-overlay copy of each and `agent-brief.md`, and nothing else. The brief gives the prompts, the drawing rule, the paragraph that follows it here and the reply format, and does not name the study. The reply carries only notes and the rows' polygons and statuses; the header fields and each row's panel, motion and size are filled in from the row table when it is converted to `allowed-agent.json`. One attempt; a malformed reply is re-run with the same prompt, and every attempt is kept in `agent-raw/`. The paths it read, taken from its transcript, are in `agent-reads.txt`.
- Neither drawer sees the other's set until both are hashed. Neither set is drawn until the reproduction gate has passed.

## Eligibility (fixed before any mask is drawn)

For each row, on the eligibility grid of 1280 × 720 (720 × 1280 for the portrait panel):

1. **Line pixels.** The row's layer in `dataset/lineart`, binarised exactly as `metrics/inkstab.py` binarises a `--lineart` layer: greyscale, inverted, resized to the grid with anti-aliasing, then thresholded at the layer's Otsu level. n_lines is their count.
2. **M.** Each polygon scaled to the grid (x · width, y · height) and filled with `skimage.draw.polygon`.
3. **R**, the measured region: R = ~binary_dilation(M, disk(m)) with m = 32 grid pixels. R is the whole grid when M is empty.
4. **n_R**, the line pixels inside R.
5. A row is **eligible** iff n_R ≥ max(2,000, 0.10 · n_lines) under both mask sets.

Eligibility uses line art only, never a clip or a frame. No clip is excluded for any other reason; the refused idle cell stays missing.

**Agreement.** Per row, the IoU of the two sets' M on the same grid, |A ∩ B| / |A ∪ B|, taken as 1.0 when both are empty. IoU and the counts are published in `analysis/out/a9_eligible.csv`; the contact sheet `analysis/out/figures/a9_masks.png` shows both sets over the panels.

## Slips

A drawing slip (a polygon put on the wrong row, or a row saved by mistake) may be fixed before registration, and only then. Each fix is logged below with the date, the set, the row, what changed, and the file's sha256 before and after; eligibility, IoU and the contact sheet are then recomputed. Redrawing a region because it now looks too big or too small is a change of judgement, not a slip, and is not allowed. The blind set is never redrawn: its only fixable slip is a polygon the reply put under the wrong row id, moved verbatim, with the raw reply kept unchanged.

## Slip log

1. **3 November 2026, set `aaron`, row `cu-line-2_burst`.** Saved as `nothing-allowed` (no polygons) by mistake: Aaron meant the whole frame, a full-frame close-up, as allowed to move, and says so from memory of the drawing session. Changed to `drawn` with one polygon covering the whole panel, [[0, 0], [1, 0], [1, 1], [0, 1]]; no other row changed. sha256 before `9f8db769e09837bc9ad2abbe17a82c54edea8aa9f69e06c94ab8fa78834bb2e6`, after `0f80bfe30a7a34b0a1a3b9eba3c780c25276983dab86bcf61023228ccffa64d8`. Disclosure: before Aaron was asked, he had been told that the blind set covers almost the whole of this panel, so his answer was not blind to the other set. The row was already ineligible under the blind set (n_R = 0), and a whole-panel mask also leaves no measured region, so the fix changes no eligible row and no Test 2 input. Eligibility, IoU and the contact sheet were recomputed.

## Notes

**3 November 2026, how the blind drawer runs.** A subagent of the working session would have loaded that session's instructions and memory, which name the study, so the drawer runs instead as a fresh, non-interactive Claude Code session started inside its scratch folder, with project and local settings only (no user instructions, memory, hooks or plugins), no MCP servers, no skills or commands, Read as its only tool, and every permission prompt refused (so no read outside the folder can succeed). Model claude-opus-5-5, effort high. Its system prompt adds the drawer definition's text, which names no study. A probe session started the same way, given no panels and no brief, loaded no context file. The brief is copied into the folder as `brief.md`, byte-identical to `agent-brief.md` (the folder inventory in `agent-reads.txt` carries its sha256), and the dispatch prompt in `agent-raw/dispatch-prompt.txt` names that copy. Everything else is as above.

**3 November 2026, clarification.** The first note's "no read outside the folder can succeed" means that such a read would have been refused by the session's settings; the read log shows that none was attempted.
