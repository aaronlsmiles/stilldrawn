# StillDrawn metric suite — `inkstab.py`

```
python3 metrics/inkstab.py CLIP.mp4 \
    --panel PANEL.png --lineart LINES.png --out runs/metrics/<cell-id>.json
```

Five stability metrics per clip, computed on all frames at native resolution, against
two references: **frame 0** (temporal stability) and the **source panel / lineart
layer** (faithfulness to the drawn substrate). The normative definitions are the
`DEFS` dict at the top of `inkstab.py`, echoed into every output JSON; the frozen
copy lives in `docs/PREREGISTRATION.md` §3. Summary:

| Metric | What it sees | Headline scalar |
|---|---|---|
| `line_drift` | contour wander / line dropout — AnimeLineArt maps (same netG.pth as the dataset's lineart layers), Otsu-binarised; symmetric chamfer (px) + tolerance-IoU (disk-2 dilation) | mean chamfer vs frame 0 |
| `tone_spectral_drift` | screentone shimmer — 64px tone tiles (local-mean mid-grey mask), hann-windowed FFT, frame-0 dominant radial band [0.75 r\*, 1.25 r\*], band-energy fraction over time | series variance |
| `edge_decay` | photoreal softening — Sobel gradient-magnitude 95th percentile per frame | normalised slope (negative = softening) |
| `style_drift` | register drift catch-all — DINOv2 ViT-S/14 CLS cosine distance vs frame 0 | terminal distance |
| `closure_proxy` | contour breakage — skeleton endpoint density per skeleton pixel | \|terminal drift\| vs frame 0 |

Notes:

- `--lineart` is the dataset's extraction layer (black-on-white). If omitted, the
  panel's own computed line map is the reference (`lineart_ref` records which).
- `tone_spectral_drift` is defined only when ≥4 tone tiles meet coverage — line-only
  panels legitimately return `n_tiles < 4` (recorded, not an error).
- `--limit N` is a dev flag (first N frames) — never for benchmark runs.
- Runs on MPS by default, `--device cpu` to force CPU (results are identical up to
  float noise; the extractor and DINOv2 are deterministic in eval mode).
- Validation: the suite must reproduce the pilot-study ranking (the establishing-shot
  clip worst on edge_decay + style_drift) before the pre-registration freezes —
  validation passed before the freeze.

## Weight provenance (added 2026-08-12, Phase 5 hardening)

The style_drift model is name-pinned in DEFS (`torch.hub facebookresearch/dinov2
dinov2_vits14`). Checksum of the checkpoint actually used for the full corpus
sweep and the one re-scored cell, recorded so a hub-side weight change is
detectable:

```
SHA256(dinov2_vits14_pretrain.pth) = b938bf1bc15cd2ec0feacfe3a1bb553fe8ea9ca46a7e1d8d00217f29aef60cd9
```

The AnimeLineArt extractor weights (`netG.pth`) are vendored locally in the
ComfyUI custom-node tree and identical to the dataset's lineart extraction pass
by construction (same file, same process).
