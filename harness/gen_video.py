#!/usr/bin/env python3
"""I2V run wrapper — every benchmark clip is born through this script.

Same provenance contract as gen_panel.py: motion prompts are resolved here
(from the frozen harness/motion-prompts.md via pack_parser) and passed to the
engine client as explicit strings; every clip appends one line to
runs/manifest.jsonl BEFORE the next run submits.

Usage
  gen_video.py --engine gen4_turbo --panel dataset/panels/cu-line-1.png \
      --motion IDLE --cell-id cu-line-1_idle_gen4t

Engines
  gen4_turbo / gen4.5   Runway dev API image_to_video (wired; key via `op run`
                        inside the child call). $0.05/s and $0.12/s respectively.
  wan22 / ltx23         Local ComfyUI (127.0.0.1:8188), GGUF quants; graphs in
                        harness/graphs/. £0; wall-clock recorded in the manifest.
                        Latent grids are step-32, so 1280:720 runs 1280x704 and
                        720:1280 runs 704x1280 — prereg amendment A1, recorded
                        per clip.
  h3-fal                MiniMax H3 via fal.ai queue API; key via
                        `op run --env-file harness/fal.env`. Supports --last-panel
                        for FLINT (first→last) cells. Endpoint id comes from
                        $STILLDRAWN_FAL_H3_MODEL (verified at batch time).
"""
import argparse
import datetime as _dt
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid

from pack_parser import _prompt_from_file

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
# Thin engine clients (ComfyUI / hosted-API wrappers) are not part of the
# release; point STILLDRAWN_BACKEND at your own. See harness/README.md.
BACKEND_SCRIPTS = pathlib.Path(__import__("os").environ.get(
    "STILLDRAWN_BACKEND", "backend"))
MOTION_PACK = HERE / "motion-prompts.md"
RUNWAY_API_VERSION = "2024-11-06"
COMFY = "http://127.0.0.1:8188"

RUNWAY_MODELS = {"gen4_turbo": 0.05, "gen4.5": 0.12}   # $/second
# Amendment A5: Seedance 2.0 via fal. Standard tier, 720p, $0.3024/s (verified
# on the fal model page 2026-08-14). Supports end_image_url, so FLINT works.
FAL_SEEDANCE_MODEL = os.environ.get("STILLDRAWN_FAL_SEEDANCE_MODEL",
                                    "bytedance/seedance-2.0/image-to-video")
SEEDANCE_RATE = 0.3024   # $/second at 720p, standard tier
LOCAL_MODELS = {
    "wan22": {
        "graph": "wan22-i2v.json",
        "version": "Wan2.2-TI2V-5B GGUF Q5_K_M (QuantStack) + umt5-xxl GGUF Q5_K_M "
                   "(city96) + Wan2.2_VAE, ComfyUI 0.31.0",
        "seed_node": ("9", "seed"),
    },
    "ltx23": {
        "graph": "ltx23-i2v.json",
        "version": "LTX-2.3-22B distilled-1.1 GGUF Q4_K_M (unsloth) + gemma-3-12B-it "
                   "fp8_scaled (Comfy-Org) + LTX23 bf16 VAEs (Kijai), "
                   "ComfyUI 0.31.0",
        "seed_node": ("13", "noise_seed"),
    },
}
# fal.ai queue endpoint for MiniMax H3 image-to-video — verified 2026-08-12 from
# the fal registry + OpenAPI schema; see docs/TOS-REVIEW.md for terms. 768P is the
# nearest supported tier to the frozen 1280:720 (A1 engine-constrained-resolution
# rule); $0.08/s at 768P => $0.40 per 5s clip (vs prereg estimate $0.35 — noted in
# the ledger row). enable_prompt_expansion is forced OFF: prompts are frozen.
FAL_H3_MODEL = os.environ.get("STILLDRAWN_FAL_H3_MODEL", "minimax/h3/image-to-video")
FAL_H3_COST = 0.40   # $/clip at 768P x 5s; reconcile from dashboard


def _comfy_api(path, body=None, headers=None, timeout=120):
    req = urllib.request.Request(COMFY + path, data=body, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _comfy_upload(path: pathlib.Path) -> str:
    boundary = uuid.uuid4().hex
    data = path.read_bytes()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; "
        f"filename=\"{path.name}\"\r\nContent-Type: image/png\r\n\r\n"
    ).encode() + data + (
        f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue"
        f"\r\n--{boundary}--\r\n"
    ).encode()
    out = _comfy_api("/upload/image", body,
                     {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return out.get("name", path.name)


def _nearest32(ratio: str):
    """'1280:720' -> (1280, 704): step-32 latent grids (prereg amendment A1)."""
    w, h = (int(x) for x in ratio.split(":"))
    return max(32, round(w / 32) * 32), max(32, round(h / 32) * 32)


def _run_local(a, prompt, out):
    cfg = LOCAL_MODELS[a.engine]
    graph = json.loads((HERE / "graphs" / cfg["graph"]).read_text())
    w, h = _nearest32(a.ratio)
    frames = a.duration * 24 + 1
    stored = _comfy_upload(pathlib.Path(a.panel))
    if a.engine == "wan22":
        graph["4"]["inputs"]["text"] = prompt
        graph["6"]["inputs"]["image"] = stored
        graph["7"]["inputs"].update({"width": w, "height": h, "length": frames})
    else:   # ltx23
        graph["3"]["inputs"]["text"] = prompt
        graph["8"]["inputs"]["image"] = stored
        graph["9"]["inputs"].update({"width": w, "height": h, "length": frames})
        graph["11"]["inputs"]["frames_number"] = frames
    node, key = cfg["seed_node"]
    graph[node]["inputs"][key] = a.seed
    save_node = [k for k, v in graph.items() if v["class_type"] == "SaveVideo"][0]
    graph[save_node]["inputs"]["filename_prefix"] = f"stilldrawn/{a.engine}/{a.cell_id}"

    t0 = time.time()
    resp = _comfy_api("/prompt",
                      json.dumps({"prompt": graph, "client_id": "stilldrawn"}).encode(),
                      {"Content-Type": "application/json"})
    pid = resp.get("prompt_id")
    if not pid:
        sys.exit(f"comfy queue rejected: {json.dumps(resp)[:500]}")
    while True:
        time.sleep(10)
        hist = _comfy_api(f"/history/{pid}")
        if pid in hist:
            entry = hist[pid]
            if entry.get("status", {}).get("status_str") == "error":
                msgs = [m for m in entry["status"].get("messages", [])
                        if m[0] == "execution_error"]
                sys.exit("comfy execution error: " + json.dumps(msgs)[:1200])
            files = [it for node_out in entry.get("outputs", {}).values()
                     for k in ("images", "video", "videos", "gifs")
                     for it in (node_out.get(k) or [])
                     if isinstance(it, dict) and "filename" in it]
            if files:
                it = files[0]
                q = urllib.parse.urlencode({"filename": it["filename"],
                                            "subfolder": it.get("subfolder", ""),
                                            "type": it.get("type", "output")})
                with urllib.request.urlopen(f"{COMFY}/view?{q}", timeout=600) as r:
                    out.write_bytes(r.read())
                return time.time() - t0, f"{w}x{h}"
        if time.time() - t0 > 7200:
            sys.exit("local run timed out after 2h")


def _run_fal(a, prompt, out):
    if a.engine != "seedance" and not FAL_H3_MODEL:
        sys.exit("h3-fal endpoint not set — export STILLDRAWN_FAL_H3_MODEL "
                 "(verify the model id on fal.ai first)")
    key = os.environ.get("FAL_KEY")
    if not key:
        sys.exit("FAL_KEY missing — invoke via: op run --env-file harness/fal.env -- ...")
    # Panels go up via fal storage (fal_client) — multi-MB base64 data-URIs are
    # rejected at the edge with an opaque 403. The uploaded URL is recorded in
    # the manifest via the payload.
    import fal_client
    if a.engine == "seedance":
        model, payload = FAL_SEEDANCE_MODEL, {
            "prompt": prompt,
            "image_url": fal_client.upload_file(a.panel),
            "resolution": "720p", "duration": int(a.duration)}
    else:
        model, payload = FAL_H3_MODEL, {
            "prompt": prompt,
            "image_url": fal_client.upload_file(a.panel),
            "resolution": "768P", "duration": a.duration,
            "enable_prompt_expansion": False}
    if a.last_panel:
        payload["end_image_url"] = fal_client.upload_file(a.last_panel)
    body = json.dumps(payload).encode()
    # queue.fal.run sits behind Cloudflare, which 403s python-urllib's default
    # User-Agent — send a real one (same fix as the RunPod GraphQL calls).
    hdrs = {"Authorization": f"Key {key}", "Content-Type": "application/json",
            "User-Agent": "stilldrawn-harness/1.0 (+https://fal.ai; curl-compatible)"}
    t0 = time.time()
    sub = json.loads(urllib.request.urlopen(urllib.request.Request(
        f"https://queue.fal.run/{model}", data=body, headers=hdrs),
        timeout=120).read())
    status_url = sub.get("status_url")
    if not status_url:
        sys.exit(f"fal submit failed: {json.dumps(sub)[:500]}")
    resp_url = sub["response_url"]
    while True:
        time.sleep(10)
        st = json.loads(urllib.request.urlopen(urllib.request.Request(
            status_url, headers=hdrs), timeout=60).read())
        if st.get("status") == "COMPLETED":
            break
        if st.get("status") in ("FAILED", "ERROR"):
            sys.exit(f"fal job failed: {json.dumps(st)[:800]}")
        if time.time() - t0 > 1800:
            sys.exit("fal job timed out after 30min")
    res = json.loads(urllib.request.urlopen(urllib.request.Request(
        resp_url, headers=hdrs), timeout=120).read())
    video = res.get("video") or {}
    url = video.get("url") if isinstance(video, dict) else video
    if not url:
        sys.exit(f"fal result has no video url: {json.dumps(res)[:500]}")
    dl = urllib.request.Request(url, headers={"User-Agent": hdrs["User-Agent"]})
    with urllib.request.urlopen(dl, timeout=600) as r:
        out.write_bytes(r.read())
    return time.time() - t0


def main():
    p = argparse.ArgumentParser(description="StillDrawn I2V run (provenance-recording wrapper)")
    p.add_argument("--engine", required=True)
    p.add_argument("--panel", required=True, help="source still (dataset/panels/*.png)")
    p.add_argument("--motion", required=True,
                   help="motion-class shot id in harness/motion-prompts.md (e.g. IDLE / BURST / CAMPUSH / FLINT)")
    p.add_argument("--cell-id", required=True, help="runs/<engine>/<cell-id>.mp4")
    p.add_argument("--duration", type=int, default=5)
    p.add_argument("--ratio", default="1280:720")
    p.add_argument("--seed", type=int, default=20260812,
                   help="recorded where settable (local engines); hosted engines ignore it")
    p.add_argument("--last-panel", default=None,
                   help="h3-fal FLINT cells: the last-frame panel")
    a = p.parse_args()

    known = set(RUNWAY_MODELS) | set(LOCAL_MODELS) | {"h3-fal", "seedance"}
    if a.engine not in known:
        sys.exit(f"unknown engine {a.engine} (wired: {', '.join(sorted(known))})")

    prompt = _prompt_from_file(str(MOTION_PACK), a.motion)
    out = ROOT / "runs" / a.engine / f"{a.cell_id}.mp4"
    if out.exists():
        sys.exit(f"{out} exists — cells run once; a rerun needs its own cell-id (and ledger row)")
    out.parent.mkdir(parents=True, exist_ok=True)

    # Exclusive per-cell lock: two concurrent drivers double-submitted 22 H3
    # cells on 2026-08-12 (runs/RECONCILIATION-2026-08-12-h3.md) — the
    # exists-check alone cannot guard cells that are mid-flight.
    lock = out.with_suffix(".lock")
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        sys.exit(f"{lock} held — another driver is generating this cell; not double-submitting")
    import atexit
    atexit.register(lambda: (os.close(lock_fd), lock.unlink(missing_ok=True)))

    t0 = _dt.datetime.now()
    wall_s = None
    actual_ratio = a.ratio
    seed = a.seed
    cost = 0.0

    if a.engine in RUNWAY_MODELS:
        cmd = ["op", "run", "--env-file", str(BACKEND_SCRIPTS / "runway.env"), "--",
               "python3", str(BACKEND_SCRIPTS / "runway_gen.py"), "video",
               "--model", a.engine, "--image", a.panel, "--prompt", prompt,
               "--ratio", a.ratio, "--duration", str(a.duration), "--out", str(out)]
        t_start = time.time()
        subprocess.run(cmd, check=True)
        wall_s = time.time() - t_start
        model_version = f"{a.engine} (Runway dev API, X-Runway-Version {RUNWAY_API_VERSION})"
        seed = None   # Runway image_to_video exposes no seed parameter
        cost = round(RUNWAY_MODELS[a.engine] * a.duration, 2)
    elif a.engine in LOCAL_MODELS:
        wall_s, actual_ratio = _run_local(a, prompt, out)
        model_version = LOCAL_MODELS[a.engine]["version"]
        hw = os.environ.get("STILLDRAWN_HW")   # A2: record execution hardware
        if hw:
            model_version += f" [{hw}]"
    else:   # h3-fal
        wall_s = _run_fal(a, prompt, out)
        if a.engine == "seedance":
            model_version = (f"Seedance 2.0 via fal.ai ({FAL_SEEDANCE_MODEL}, "
                             f"720p, standard tier)")
        else:
            model_version = f"MiniMax H3 via fal.ai ({FAL_H3_MODEL}, 768P)"
        seed = None
        cost = (round(SEEDANCE_RATE * a.duration, 3)
                if a.engine == "seedance" else FAL_H3_COST)

    line = {
        "cell_id": a.cell_id,
        "panel": a.panel,
        "motion_class": a.motion,
        "prompt": prompt,
        "engine": a.engine,
        "model_version": model_version,
        "seed": seed,
        "duration_s": a.duration,
        "ratio": actual_ratio,
        "requested_ratio": a.ratio,
        "wall_s": round(wall_s, 1) if wall_s else None,
        "cost_usd": cost,
        "date": t0.strftime("%Y-%m-%d"),
        "out": str(out.relative_to(ROOT)),
    }
    if a.last_panel:
        line["last_panel"] = a.last_panel
    manifest = ROOT / "runs/manifest.jsonl"
    with manifest.open("a") as f:
        f.write(json.dumps(line) + "\n")
    print(f"manifest += {a.cell_id}  (${cost:.2f}, {wall_s:.0f}s)" if wall_s
          else f"manifest += {a.cell_id}  (${cost:.2f})")


if __name__ == "__main__":
    main()
