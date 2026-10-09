#!/usr/bin/env python3
"""motion — post-hoc motion-magnitude channel for StillDrawn clips.

    python metrics/motion.py CLIP.mp4 --out runs/metrics-motion/<cell-id>.json

*** THIS IS NOT ONE OF THE FIVE FROZEN METRICS. ***

`inkstab.py` holds the five metrics whose definitions were frozen before any
benchmark generation. This tool was written on 2026-08-14, after the corpus was
complete and scored, and exists to answer a confound the frozen suite cannot
address on its own: every one of the five stability metrics is optimised by a
clip that does not move, so a stability score alone cannot distinguish an engine
that holds the inked register from an engine that barely animates.

That confound is not ours to discover. VBench states it directly --- "generating
relatively static scenes can 'cheat' to get high temporal consistency scores"
--- and remedies it with a paired Dynamic Degree control estimated from optical
flow. This tool implements the same control for our corpus.

Because it is post-hoc, results computed here are EXPLORATORY and must be
reported as such. They may be used to qualify, condition or caveat a frozen
result; they may not be used to restate one. See PREREGISTRATION.md amendment A6.

Definition (following VBench's Dynamic Degree, adapted to give a continuous
per-clip magnitude rather than only a binary static/non-static verdict):

  * optical flow between consecutive sampled frames, RAFT (torchvision),
    falling back to Farneback (OpenCV) if RAFT is unavailable;
  * per frame pair, take the mean of the LARGEST 5% of per-pixel flow
    magnitudes --- VBench's choice, so that small moving objects are not washed
    out by a static background;
  * headline is the MEDIAN of that per-pair series over the clip, reported both
    in pixels/frame at the analysis resolution and normalised by min(H, W) so
    clips at different native grids are comparable.

Run with the ComfyUI venv python (torch/torchvision live there).
"""
import argparse
import json
import pathlib
import sys

import numpy as np

DEFS = {
    "version": "motion 1.0 (2026-08-14) — POST-HOC, exploratory, NOT part of the frozen five",
    "status": "added after corpus completion; see PREREGISTRATION.md amendment A6",
    "provenance": "implements the paired motion control of VBench's Dynamic Degree (Huang et al. 2023), which uses RAFT optical flow and the mean of the largest 5% of flows",
    "flow_model": "torchvision RAFT (raft_small, C_T_V2 weights — Chairs+Things, the only pretrained pair torchvision ships for raft_small); Farneback (OpenCV) fallback recorded in output when used",
    "analysis_long_side_px": 512,
    "analysis_resize": "bilinear, aspect preserved, both frames of a pair resized identically; RAFT requires dims divisible by 8 so dims are rounded down to the nearest multiple of 8",
    "frame_stride": 2,
    "flow_percentile": 95,
    "flow_statistic": "mean of per-pixel flow magnitudes at or above the 95th percentile (i.e. the largest 5%), per consecutive sampled frame pair",
    "headline": "median of the per-pair series, in px/frame at analysis resolution",
    "headline_normalised": "median_px divided by min(H, W) of the analysis grid — dimensionless, comparable across native grids",
    "static_threshold_note": "no static/non-static threshold is baked in; VBench thresholds for a model-level proportion, whereas we keep the continuous value and let the analysis choose. Any threshold used downstream must be declared there.",
}


def load_frames(path, stride):
    """Return sampled RGB frames as a uint8 array (N, H, W, 3), plus fps."""
    import imageio.v3 as iio

    frames = []
    meta_fps = None
    try:
        meta = iio.immeta(path, plugin="pyav")
        meta_fps = meta.get("fps")
    except Exception:
        pass
    for i, frame in enumerate(iio.imiter(path, plugin="pyav")):
        if i % stride == 0:
            frames.append(np.asarray(frame)[:, :, :3])
    if len(frames) < 2:
        raise SystemExit(f"clip has fewer than 2 sampled frames: {path}")
    return np.stack(frames), meta_fps


def resize_batch(frames, long_side):
    """Resize to long_side (aspect preserved), dims floored to multiples of 8."""
    import torch
    import torch.nn.functional as F

    t = torch.from_numpy(frames).permute(0, 3, 1, 2).float()
    _, _, h, w = t.shape
    scale = long_side / max(h, w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    nh, nw = max(8, nh - nh % 8), max(8, nw - nw % 8)
    return F.interpolate(t, size=(nh, nw), mode="bilinear", align_corners=False)


def build_raft(device):
    """Load RAFT once; batch runs reuse it across clips."""
    from torchvision.models.optical_flow import Raft_Small_Weights, raft_small

    weights = Raft_Small_Weights.C_T_V2
    return raft_small(weights=weights, progress=False).to(device).eval()


def flow_raft(frames_t, device, model):
    """Per-pair mean-of-top-5% flow magnitude using torchvision RAFT."""
    import torch

    # RAFT expects inputs normalised to [-1, 1].
    x = (frames_t / 255.0) * 2.0 - 1.0
    series = []
    with torch.no_grad():
        for i in range(x.shape[0] - 1):
            a = x[i : i + 1].to(device)
            b = x[i + 1 : i + 2].to(device)
            flow = model(a, b)[-1]  # final refinement, (1, 2, H, W)
            mag = torch.linalg.vector_norm(flow, dim=1).flatten()
            thr = torch.quantile(mag.float(), DEFS["flow_percentile"] / 100.0)
            top = mag[mag >= thr]
            series.append(float(top.mean().item()) if top.numel() else 0.0)
    return series, "raft_small"


def flow_farneback(frames, long_side):
    """Fallback: OpenCV Farneback on greyscale, same top-5% statistic."""
    import cv2

    series = []
    prev = None
    for f in frames:
        g = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY)
        h, w = g.shape
        scale = long_side / max(h, w)
        g = cv2.resize(g, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)
        if prev is not None:
            fl = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag = np.linalg.norm(fl, axis=2).ravel()
            thr = np.percentile(mag, DEFS["flow_percentile"])
            top = mag[mag >= thr]
            series.append(float(top.mean()) if top.size else 0.0)
        prev = g
    return series, "farneback"


def score_clip(clip, args, device, model):
    """Compute the motion record for one clip. Returns the output dict."""
    frames, fps = load_frames(clip, args.stride)

    backend_note = None
    grid = None
    if args.force_farneback or model is None:
        series, backend = flow_farneback(frames, args.long_side)
    else:
        try:
            frames_t = resize_batch(frames, args.long_side)
            grid = [int(frames_t.shape[2]), int(frames_t.shape[3])]
            series, backend = flow_raft(frames_t, device, model)
            backend = f"{backend}@{device}"
        except Exception as exc:  # noqa: BLE001 — fallback is deliberate and recorded
            backend_note = f"RAFT failed ({type(exc).__name__}: {exc}); used Farneback"
            series, backend = flow_farneback(frames, args.long_side)
            grid = None

    if grid is None:
        h, w = frames.shape[1], frames.shape[2]
        scale = args.long_side / max(h, w)
        grid = [int(h * scale), int(w * scale)]

    arr = np.asarray(series, dtype=float)
    norm = float(min(grid))
    out = {
        "clip": str(clip),
        "n_frames_sampled": int(frames.shape[0]),
        "n_pairs": int(arr.size),
        "fps": fps,
        "native_resolution": [int(frames.shape[1]), int(frames.shape[2])],
        "analysis_grid": grid,
        "backend": backend,
        "backend_note": backend_note,
        "defs": DEFS,
        "motion": {
            "headline_median_px": float(np.median(arr)),
            "headline_median_norm": float(np.median(arr) / norm),
            "mean_px": float(arr.mean()),
            "p90_px": float(np.percentile(arr, 90)),
            "max_px": float(arr.max()),
            "min_px": float(arr.min()),
            "series": [round(v, 5) for v in arr.tolist()],
        },
    }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips", nargs="+", help="one or more clip paths")
    ap.add_argument("--out", help="output JSON path (single clip only)")
    ap.add_argument("--out-dir", help="output directory; filename is <clip stem>.json")
    ap.add_argument("--stride", type=int, default=DEFS["frame_stride"])
    ap.add_argument("--long-side", type=int, default=DEFS["analysis_long_side_px"])
    ap.add_argument("--force-farneback", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()

    if not args.out and not args.out_dir:
        ap.error("one of --out or --out-dir is required")
    if args.out and len(args.clips) > 1:
        ap.error("--out takes a single clip; use --out-dir for batches")

    device, model = "cpu", None
    if not args.force_farneback:
        try:
            import torch

            device = "mps" if torch.backends.mps.is_available() else "cpu"
            model = build_raft(device)
        except Exception as exc:  # noqa: BLE001
            print(f"RAFT unavailable ({type(exc).__name__}: {exc}); falling back to Farneback", file=sys.stderr)

    failures = []
    for i, c in enumerate(args.clips, 1):
        clip = pathlib.Path(c)
        outp = pathlib.Path(args.out) if args.out else pathlib.Path(args.out_dir) / f"{clip.stem}.json"
        if args.skip_existing and outp.exists():
            continue
        try:
            out = score_clip(clip, args, device, model)
        except Exception as exc:  # noqa: BLE001 — record and continue the batch
            failures.append((clip.name, f"{type(exc).__name__}: {exc}"))
            print(f"[{i}/{len(args.clips)}] FAILED {clip.name}: {exc}", file=sys.stderr)
            continue
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(out, indent=2))
        m = out["motion"]
        print(f"[{i}/{len(args.clips)}] {clip.name}: median {m['headline_median_px']:.3f} px/frame "
              f"({m['headline_median_norm']:.5f} norm) [{out['backend']}, {out['n_pairs']} pairs]")

    if failures:
        print(f"\n{len(failures)} FAILED:", file=sys.stderr)
        for name, err in failures:
            print(f"  {name}: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
