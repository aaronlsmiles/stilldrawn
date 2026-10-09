# runs/

Every clip the study generated (373 MP4s), the manifest that pins how each was
made, and the metric outputs for each clip.

| Path | Contents |
|---|---|
| `<engine>/*.mp4` | Clips, one folder per engine: `gen4_turbo`, `gen4.5`, `h3-fal`, `wan22`, `ltx23`, `seedance` |
| `manifest.jsonl` | One line per generation request: cell id, engine, pinned model version, prompt, seed, motion class, resolution, wall-clock, cost, output path |
| `manifest-supplement.jsonl` | Five clips generated outside the manifest (see below) |
| `metrics/` · `metrics-r2/` · `metrics-ground/` · `metrics-hazard/` · `metrics-seedance/` | Stability-metric outputs per clip, by study arm |
| `metrics-motion/` | Optical-flow motion magnitude for all 373 clips (amendment A6) |
| `CLIP-HASHES.csv` | SHA-256 of every clip; for the six clips whose metadata was edited, a commitment to the original (see `docs/REDACTIONS.md`) |
| `RECONCILIATION-2026-08-12-h3.md` | Why some H3 cells appear twice in the manifest |

## Reading the manifest

The manifest is an append-only log of generation requests, so it has more
lines (392) than there are clips (373):

- **Superseded lines (22).** 22 MiniMax H3 cells (six of them FLINT cells) were
  submitted twice during a billing incident. **The last line for a given
  `cell_id` is the operative one**; its `out` path is the clip that ships.
  `RECONCILIATION-2026-08-12-h3.md` records the incident.
- **Refusals (2).** `cu-tone-3_idle_gen4t` was refused by the engine's moderation
  in the primary run and again in the repeat. Under the frozen rule a refusal is a
  result, not a gap, so both lines stay, with no output file.
- **Missing lines (5).** The five Wan 2.2 ground-series clips
  (`ground-cu-line-1-v0XX_idle_wan22`) were generated on a rented GPU on
  2026-08-14 by `harness/pod_run_wan_ground.py`, which did not append to the
  manifest. `manifest-supplement.jsonl` lists them. Their generation parameters
  are embedded in each clip's ComfyUI workflow metadata, and their metrics are
  in `metrics-ground/`.

392 lines − 22 superseded − 2 refusals + 5 supplement = 373 clips.

## Two things not to do

- **Do not re-encode or remux the Runway or MiniMax clips** if you redistribute
  them. They carry signed C2PA Content Credentials whose hash binding breaks on
  any re-encode (see `NOTICE-PROVIDERS.md`).
- **Do not use the Runway-generated clips to train generative video models.**
  See `NOTICE-PROVIDERS.md`.
