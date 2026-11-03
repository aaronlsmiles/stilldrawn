# A9 reproduction gate

Post-hoc (A9). The line maps of the 109 primary idle and burst clips were re-extracted
before any mask existed. They were held in memory one clip at a time and never saved.

Pass rule: every clip within max(0.01 px, 0.5 %) of its released `line_chamfer_mean_px`,
with the same frame count, grid and device. A failure blocks everything; no clip is dropped.

**Result: PASS (109 of 109 clips pass).**

## Environment

- netG_sha256: `ccabdcc3f5cf3c07cf65d58776acb21df7dfda825cdc70c9766a93fd62bfc488`
- torch: `2.13.0`
- device: `mps`
- python: `3.12.10`
- numpy: `2.5.2`
- scipy: `1.18.0`
- scikit_image: `0.26.0`
- inkstab_sha256: `da753ef545ef57d241a77a30b100964c6ed099ca49af5f254c9fdc1c0435c129`
- masked_sha256: `3ece0296d6147d97a695060a27e4a8278e7bcd436ba1653c9f2652d779feb5e6`
- git_commit: `58b69d078cba81ab79cad64735f0b5e09bc00993, c61836284adfabb7fc6078409c92aee1fab66547`
- git_dirty: `True`
- expect_device: `mps`

## Panel-to-clip mapping (frame 0 vs the panel's line-art layer)

Median chamfer per engine, rows in frozen-league order. Each engine's mapping is the one
with the lower median (stretch on a tie).

| engine | clips | stretch, median px | centre-crop, median px | mapping |
|---|---|---|---|---|
| wan22 | 22 | 1.8631161206557412 | 0.6150982312324702 | centre-crop |
| gen4_turbo | 21 | 1.2156664991571153 | 0.6320782897095544 | centre-crop |
| ltx23 | 22 | 1.7996044844635004 | 0.6673896439668403 | centre-crop |
| gen4.5 | 22 | 1.1366068983662798 | 0.5075857951091273 | centre-crop |
| h3-fal | 22 | 0.38095643184968836 | 0.38095643184968836 | stretch |

## Definitions echoed

inkstab DEFS (frozen) and masked DEFS:

```json
{
 "inkstab": {
  "version": "inkstab 1.0 (2026-08-12)",
  "line_extractor": "AnimeLineArt netG.pth (custom_controlnet_aux LineartAnimeDetector), detect_resolution=1024, same weights as the dataset extraction pass",
  "line_binarise": "per-map Otsu threshold; line pixel = map value > threshold (extractor emits white-on-black)",
  "chamfer": "symmetric: 0.5*(mean dist line-pixels A->B + mean B->A), pixels, via EDT, at native clip resolution",
  "iou_tolerance_px": 2,
  "iou": "IoU of line maps after binary dilation by disk(iou_tolerance_px) \u2014 tolerance IoU, thin-line IoU is degenerate",
  "tone_mask": "16px box-filtered source-panel greyscale in (0.15, 0.85), eroded by disk(4), resized to clip grid \u2014 local MEAN greyness, because true halftone has near-bimodal pixel values (dots are black-on-white; only the local average is mid-grey)",
  "tone_tile_px": 64,
  "tone_tile_stride_px": 32,
  "tone_tile_min_coverage": 0.8,
  "tone_min_tiles": 4,
  "tone_band": "frame-0 dominant radial FFT bin r* over r>=3 (mean over tiles, hann-windowed); band = [0.75*r*, 1.25*r*]",
  "tone_energy": "band power / total non-DC power, mean over tiles, per frame",
  "edge_decay": "Sobel-3x3 gradient magnitude 95th percentile per frame; slope = polyfit x N / g0. HEADLINE = |slope| (validated 2026-08-12, FINDINGS R1: photoreal drift can RAISE edge energy via added photographic texture \u2014 magnitude detects both directions; sign kept for taxonomy: negative = softening, positive = texturisation)",
  "style_model": "DINOv2 ViT-S/14 (torch.hub facebookresearch/dinov2 dinov2_vits14), frames 224x392, ImageNet norm, CLS embedding, cosine distance vs frame 0",
  "closure": "skeletonize binarised line map; endpoint = skeleton px with exactly 1 8-neighbour; rho = endpoints / skeleton px"
 },
 "masked": {
  "version": "masked 1.0 (A9): POST-HOC, exploratory, NOT part of the frozen five",
  "line_maps": "inkstab._line_maps under inkstab's frozen DEFS (AnimeLineArt, detect_resolution 1024, per-map Otsu, nearest resize)",
  "whole_frame": "inkstab._chamfer(frame t, frame 0) for t = 1..N-1; clip value = mean of the non-None frames (the released line_chamfer_mean_px)",
  "gate_reference": "frame-0 line map vs the dataset line-art layer, binarised as inkstab's --lineart branch (invert, anti-aliased resize onto the clip grid under the mapping, Otsu)",
  "mapping": "stretch: the panel scales to the clip grid (scaled size = grid, offsets 0); centre-crop: the panel scales by max(H/ph, W/pw) to cover the clip grid, the scaled size rounded to whole pixels (at least the grid), and the grid is the centred window (offsets floor((scaled - grid) / 2)). The gate's line-art reference is resampled to the scaled size with skimage resize (anti-aliased) and cropped to that window",
  "mask": "M = union of the row's allowed polygons (x, y in panel fractions, origin top-left), each filled with skimage.draw.polygon(r = y*scaled_h - top, c = x*scaled_w - left, shape = (H, W)) on the clip grid, boundary pixels included (stretch: r = y*H, c = x*W, sub-plan B's contract); status nothing-allowed gives an empty M",
  "region": "R = ~scipy.ndimage.binary_dilation(M, structure=skimage.morphology.disk(m)), computed exactly as scipy.ndimage.distance_transform_edt(~M) > m (unit-tested equal); R is all-true when M is empty",
  "margins_px": [
   16,
   32,
   64
  ],
  "masked_chamfer": "a = frame t, b = frame 0, full-frame EDTs. None if a or b is empty. If a&R and b&R are both non-empty: 0.5*(EDT(~b)[a&R].mean() + EDT(~a)[b&R].mean()). If only b&R is non-empty (lines vanished from R): EDT(~a)[b&R].mean(). If only a&R is non-empty (lines appeared in R): EDT(~b)[a&R].mean(). If both are empty: None",
  "clip_value": "mean of the scorable frames; +inf when no frame is scorable (stored as chamfer_px null with no_scorable_frame true)",
  "min_f0_line_px_in_R": 500,
  "gate_pass": "|recomputed - released| <= max(0.01 px, 0.5 % of released), same frame count, grid and device"
 }
}
```
