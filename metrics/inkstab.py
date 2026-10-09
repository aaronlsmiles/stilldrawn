#!/usr/bin/env python3
"""inkstab — the StillDrawn stability metric suite (five metrics, frozen definitions).

    python metrics/inkstab.py CLIP.mp4 --panel PANEL.png [--lineart LINES.png] \
        --out runs/metrics/<cell-id>.json

Computes, per clip, against the frame-0 reference and the source panel:

  1. line_drift            line-map temporal drift (chamfer + tolerance-IoU)
  2. tone_spectral_drift   halftone band-energy instability (FFT on tone tiles)
  3. edge_decay            gradient-magnitude 95th-percentile slope
  4. style_drift           DINOv2 ViT-S/14 embedding distance vs frame 0
  5. closure_proxy         skeleton endpoint density drift

Every definitional constant is in DEFS and echoed into the output JSON, so each
result file self-documents the definitions it was computed under. After the
pre-registration freeze, DEFS changes only with a dated amendment.

Run with the ComfyUI venv python (torch/skimage/av live there). The line
extractor is the same AnimeLineArt netG.pth the dataset's lineart layers were
produced with, imported in-process (batched, no server round-trips).
"""
import argparse
import json
import pathlib
import sys

import numpy as np

CAUX_SRC = pathlib.Path(__import__("os").environ.get(   # AnimeLineArt extractor source
    "STILLDRAWN_CONTROLNET_AUX_SRC", "comfyui_controlnet_aux/src"))
sys.path.insert(0, str(CAUX_SRC))

DEFS = {
    "version": "inkstab 1.0 (2026-08-12)",
    "line_extractor": "AnimeLineArt netG.pth (custom_controlnet_aux LineartAnimeDetector), detect_resolution=1024, same weights as the dataset extraction pass",
    "line_binarise": "per-map Otsu threshold; line pixel = map value > threshold (extractor emits white-on-black)",
    "chamfer": "symmetric: 0.5*(mean dist line-pixels A->B + mean B->A), pixels, via EDT, at native clip resolution",
    "iou_tolerance_px": 2,
    "iou": "IoU of line maps after binary dilation by disk(iou_tolerance_px) — tolerance IoU, thin-line IoU is degenerate",
    "tone_mask": "16px box-filtered source-panel greyscale in (0.15, 0.85), eroded by disk(4), resized to clip grid — local MEAN greyness, because true halftone has near-bimodal pixel values (dots are black-on-white; only the local average is mid-grey)",
    "tone_tile_px": 64,
    "tone_tile_stride_px": 32,
    "tone_tile_min_coverage": 0.80,
    "tone_min_tiles": 4,
    "tone_band": "frame-0 dominant radial FFT bin r* over r>=3 (mean over tiles, hann-windowed); band = [0.75*r*, 1.25*r*]",
    "tone_energy": "band power / total non-DC power, mean over tiles, per frame",
    "edge_decay": "Sobel-3x3 gradient magnitude 95th percentile per frame; slope = polyfit x N / g0. HEADLINE = |slope| (validated 2026-08-12, FINDINGS R1: photoreal drift can RAISE edge energy via added photographic texture — magnitude detects both directions; sign kept for taxonomy: negative = softening, positive = texturisation)",
    "style_model": "DINOv2 ViT-S/14 (torch.hub facebookresearch/dinov2 dinov2_vits14), frames 224x392, ImageNet norm, CLS embedding, cosine distance vs frame 0",
    "closure": "skeletonize binarised line map; endpoint = skeleton px with exactly 1 8-neighbour; rho = endpoints / skeleton px",
}


def _grey(img):
    """uint8 HxWx3 -> float32 HxW in [0,1]."""
    if img.ndim == 3:
        img = img[..., :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)
        return img / 255.0
    return img.astype(np.float32) / 255.0


def _load_frames(clip):
    import imageio.v3 as iio
    frames = iio.imread(clip, plugin="pyav")           # (N,H,W,3) uint8
    try:
        fps = iio.immeta(clip, plugin="pyav").get("fps")
    except Exception:
        fps = None
    return frames, fps


def _device():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


def _line_maps(frames, device):
    """Binary line masks per frame via the AnimeLineArt extractor."""
    from skimage.filters import threshold_otsu
    from custom_controlnet_aux.lineart_anime import LineartAnimeDetector
    det = LineartAnimeDetector.from_pretrained().to(device)
    masks = []
    for f in frames:
        m = det(f, detect_resolution=1024, output_type="np")
        g = _grey(m)
        thr = threshold_otsu(g) if g.max() > g.min() else 0.5
        mask = g > thr
        if mask.shape != f.shape[:2]:
            from skimage.transform import resize
            mask = resize(mask.astype(float), f.shape[:2], order=0, anti_aliasing=False) > 0.5
        masks.append(mask)
    del det
    return masks


def _chamfer(a, b):
    from scipy.ndimage import distance_transform_edt
    if not a.any() or not b.any():
        return None
    da = distance_transform_edt(~b)   # distance of every px to nearest b line px
    db = distance_transform_edt(~a)
    return float(0.5 * (da[a].mean() + db[b].mean()))


def _tol_iou(a, b, r):
    from skimage.morphology import binary_dilation, disk
    ad, bd = binary_dilation(a, disk(r)), binary_dilation(b, disk(r))
    u = np.logical_or(ad, bd).sum()
    return float(np.logical_and(ad, bd).sum() / u) if u else None


def _stats(series):
    s = [x for x in series if x is not None]
    if not s:
        return {"mean": None, "max": None, "terminal": None}
    return {"mean": float(np.mean(s)), "max": float(np.max(s)), "terminal": float(s[-1])}


def metric_line_drift(masks, ref_mask):
    r = DEFS["iou_tolerance_px"]
    ch0 = [_chamfer(m, masks[0]) for m in masks[1:]]
    iou0 = [_tol_iou(m, masks[0], r) for m in masks[1:]]
    chs = [_chamfer(m, ref_mask) for m in masks]
    ious = [_tol_iou(m, ref_mask, r) for m in masks]
    return {
        "vs_frame0": {"chamfer_px": _stats(ch0), "tol_iou": _stats(iou0),
                      "chamfer_series": ch0, "iou_series": iou0},
        "vs_source": {"chamfer_px": _stats(chs), "tol_iou": _stats(ious),
                      "chamfer_series": chs, "iou_series": ious},
    }


def metric_tone_spectral(frames_g, panel_g):
    from skimage.morphology import binary_erosion, disk
    from skimage.transform import resize
    from scipy.ndimage import uniform_filter
    H, W = frames_g[0].shape
    pg = resize(panel_g, (H, W), anti_aliasing=True)
    local_mean = uniform_filter(pg, size=16)
    mask = binary_erosion((local_mean > 0.15) & (local_mean < 0.85), disk(4))
    T, S = DEFS["tone_tile_px"], DEFS["tone_tile_stride_px"]
    tiles = [(y, x) for y in range(0, H - T + 1, S) for x in range(0, W - T + 1, S)
             if mask[y:y + T, x:x + T].mean() >= DEFS["tone_tile_min_coverage"]]
    if len(tiles) < DEFS["tone_min_tiles"]:
        return {"n_tiles": len(tiles),
                "note": "below tone_min_tiles — metric undefined for this panel"}

    win = np.hanning(T)[:, None] * np.hanning(T)[None, :]
    yy, xx = np.mgrid[0:T, 0:T]
    rr = np.sqrt((yy - T // 2) ** 2 + (xx - T // 2) ** 2).astype(int)
    rmax = T // 2

    def radial_power(tile):
        F = np.fft.fftshift(np.abs(np.fft.fft2(tile * win)) ** 2)
        return np.bincount(rr.ravel(), F.ravel(), minlength=rmax + 1)[:rmax + 1]

    rp0 = np.mean([radial_power(f0tile) for f0tile in
                   (frames_g[0][y:y + T, x:x + T] for y, x in tiles)], axis=0)
    rstar = int(np.argmax(rp0[3:]) + 3)
    lo, hi = max(3, int(0.75 * rstar)), min(rmax, int(np.ceil(1.25 * rstar)))

    series = []
    for g in frames_g:
        fracs = []
        for y, x in tiles:
            rp = radial_power(g[y:y + T, x:x + T])
            tot = rp[1:].sum()
            fracs.append(rp[lo:hi + 1].sum() / tot if tot > 0 else 0.0)
        series.append(float(np.mean(fracs)))
    e0 = series[0]
    n = len(series)
    slope = float(np.polyfit(np.arange(n), series, 1)[0]) if n > 1 else 0.0
    return {
        "n_tiles": len(tiles), "band_bins": [lo, hi], "r_star": rstar,
        "e0": e0, "variance": float(np.var(series)),
        "slope_norm": slope * n / e0 if e0 else None,
        "terminal_ratio": series[-1] / e0 if e0 else None,
        "series": series,
    }


def metric_edge_decay(frames_g):
    import cv2
    series = []
    for g in frames_g:
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
        series.append(float(np.percentile(np.sqrt(gx * gx + gy * gy), 95)))
    g0, n = series[0], len(series)
    slope = float(np.polyfit(np.arange(n), series, 1)[0]) if n > 1 else 0.0
    slope_norm = slope * n / g0 if g0 else None
    return {"g0": g0, "slope_norm": slope_norm,
            "abs_slope_norm": abs(slope_norm) if slope_norm is not None else None,
            "terminal_ratio": series[-1] / g0 if g0 else None, "series": series}


def metric_style_drift(frames, device):
    import torch
    try:
        model = torch.hub.load("facebookresearch/dinov2", "dinov2_vits14", verbose=False)
    except Exception as e:
        return {"error": f"DINOv2 load failed: {e}"}
    model = model.to(device).eval()
    mean = torch.tensor([0.485, 0.456, 0.406], device=device).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], device=device).view(1, 3, 1, 1)
    embs = []
    with torch.no_grad():
        for i in range(0, len(frames), 16):
            batch = torch.from_numpy(frames[i:i + 16][..., :3].copy()).float().to(device)
            batch = batch.permute(0, 3, 1, 2) / 255.0
            batch = torch.nn.functional.interpolate(batch, size=(224, 392),
                                                    mode="bilinear", align_corners=False)
            embs.append(model((batch - mean) / std).cpu())
    embs = torch.cat(embs)
    f0 = embs[0] / embs[0].norm()
    d = (1 - (embs / embs.norm(dim=1, keepdim=True)) @ f0).numpy()
    series = [float(x) for x in d[1:]]
    return {**_stats(series), "series": series}


def metric_closure(masks):
    from skimage.morphology import skeletonize
    from scipy.ndimage import convolve
    k = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]])
    series = []
    for m in masks:
        sk = skeletonize(m)
        n_sk = int(sk.sum())
        if n_sk == 0:
            series.append(None)
            continue
        nb = convolve(sk.astype(np.uint8), k, mode="constant")
        endpoints = int(((nb == 1) & sk).sum())
        series.append(endpoints / n_sk)
    valid = [x for x in series if x is not None]
    rho0 = valid[0] if valid else None
    drift = [x - rho0 for x in valid[1:]] if rho0 is not None else []
    return {"rho0": rho0, "series": series,
            "drift_terminal": drift[-1] if drift else None,
            "drift_max_abs": float(np.max(np.abs(drift))) if drift else None}


def main():
    p = argparse.ArgumentParser(description="StillDrawn stability metrics")
    p.add_argument("clip")
    p.add_argument("--panel", required=True, help="source still the clip was generated from")
    p.add_argument("--lineart", help="extraction-pass lineart layer (black-on-white); "
                                     "if omitted, the panel's own computed line map is the reference")
    p.add_argument("--out", required=True)
    p.add_argument("--device", default=None)
    p.add_argument("--limit", type=int, help="dev only: analyse first N frames (never for real runs)")
    a = p.parse_args()

    import imageio.v3 as iio
    device = a.device or _device()
    frames, fps = _load_frames(a.clip)
    if a.limit:
        frames = frames[:a.limit]
        print(f"[inkstab] DEV LIMIT: first {a.limit} frames only", file=sys.stderr)
    frames_g = [_grey(f) for f in frames]
    panel = iio.imread(a.panel)
    panel_g = _grey(panel)

    print(f"[inkstab] {a.clip}: {len(frames)} frames @ {fps} fps, device={device}", file=sys.stderr)

    print("[inkstab] line maps…", file=sys.stderr)
    masks = _line_maps(frames, device)
    if a.lineart:
        from skimage.filters import threshold_otsu
        from skimage.transform import resize
        lg = _grey(iio.imread(a.lineart))
        lg = 1.0 - lg                               # provided layers are black-on-white
        lg = resize(lg, masks[0].shape, anti_aliasing=True)
        ref_mask = lg > (threshold_otsu(lg) if lg.max() > lg.min() else 0.5)
        ref_src = "provided-lineart-layer"
    else:
        det_frames = np.asarray(panel[None, ..., :3]) if panel.ndim == 3 else None
        ref_mask = _line_maps([panel[..., :3] if panel.ndim == 3 else
                               np.stack([panel] * 3, -1)], device)[0]
        from skimage.transform import resize
        if ref_mask.shape != masks[0].shape:
            ref_mask = resize(ref_mask.astype(float), masks[0].shape, order=0) > 0.5
        ref_src = "panel-computed"

    print("[inkstab] metrics…", file=sys.stderr)
    result = {
        "clip": a.clip, "panel": a.panel, "lineart": a.lineart, "lineart_ref": ref_src,
        "n_frames": int(len(frames)), "fps": fps, "resolution": list(frames[0].shape[:2]),
        "defs": DEFS,
        "metrics": {
            "line_drift": metric_line_drift(masks, ref_mask),
            "tone_spectral_drift": metric_tone_spectral(frames_g, panel_g),
            "edge_decay": metric_edge_decay(frames_g),
            "style_drift": metric_style_drift(frames, device),
            "closure_proxy": metric_closure(masks),
        },
    }
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, default=float) + "\n")
    print(f"[inkstab] -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
