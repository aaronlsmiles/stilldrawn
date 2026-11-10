#!/usr/bin/env python3
"""I2V run wrapper — every benchmark clip is born through this script.

Same provenance contract as gen_panel.py: motion prompts are resolved here
(from the frozen harness/motion-prompts.md via pack_parser by default; --pack,
amendment A10, can name another pack in the repository) and passed to the
engine client as explicit strings; every clip appends one line to
runs/manifest.jsonl BEFORE the next run submits.

Usage
  gen_video.py --engine gen4_turbo --panel dataset/panels/cu-line-1.png \
      --motion IDLE --cell-id cu-line-1_idle_gen4t

Engines
  gen4_turbo / gen4.5   Runway dev API image_to_video (wired; key via `op run`
                        inside the child call). $0.05/s and $0.12/s respectively.
                        Without --seed: the original client, no seed sent (every
                        clip before A10). With --seed (A10's ladder, A12's draws):
                        harness/runway_task.py sends it, and the line records it.
  seedance2             Seedance 2.0 through Runway (A14; refused until A14 is in the
                        public pre-registration): harness/runway_task.py,
                        1280:720, 5 s, `audio: false`, --seed sent when given;
                        first frame, or first and last (--last-panel, FLINT).
  kling_4               Kling 4 through Runway (A15; refused until A15 is public):
                        --ratio auto_720p (keeps the panel's framing; the
                        delivered size is the line's ratio), 5 s, no seed; first frame, or first and last. Audio is
                        always generated: it is stripped by stream copy (video
                        packets md5-checked) and the delivered file is kept
                        privately in runs/delivered/ (never released).
  wan22 / ltx23         Local ComfyUI (127.0.0.1:8188), GGUF quants; graphs in
                        harness/graphs/. £0; wall-clock recorded in the manifest.
                        Latent grids are step-32, so 1280:720 runs 1280x704 and
                        720:1280 runs 704x1280 — prereg amendment A1, recorded
                        per clip.
  h3-fal                MiniMax H3 via fal.ai queue API; key via
                        `op run --env-file harness/fal.env`. Supports --last-panel
                        for FLINT (first→last) cells. Endpoint id comes from
                        $STILLDRAWN_FAL_H3_MODEL (verified at batch time).

A route through harness/runway_task.py logs `submitted <model> as task <id>` (the child) and then
`runway route record: <json>` (model, request, task id, seed, clip path) to stderr before the
audio check, so a paid clip whose run stops before its line is written keeps its record; adopt()
(the drivers' `adopt` subcommand) then writes that clip's line from the delivered file, the task id and,
if kept, that record, with the checks below. It
appends, after the frozen keys: route, model_id, runway_api_version, the request as sent
(images by path), Runway's task id and the task record's scalar fields (any seed or version field the API reports among them), and on
seedance2 and kling_4 the audio record. Runway's word for a seed is "similar results": a
seed fixes the request, not the bytes.
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import pathlib
import shutil
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
SEED_DEFAULT = 20260812   # prereg §5: local engines run at it unless --seed says otherwise
# Amendments A14 and A15: third-party models through Runway's API, by harness/runway_task.py.
# Fields per docs/RUNWAY-MODELS-2026-11-08.md (Runway's OpenAPI file, 8 Nov 2026). Ratio and
# duration are the amendments' own; anything else is refused before anything is sent.
RUNWAY_ROUTED = {
    "seedance2": {"ratio": "1280:720", "duration": 5, "seed": True, "audio": False},
    "kling_4": {"ratio": "auto_720p", "duration": 5, "seed": False, "audio": None},  # no switch
}
# A second guard until A14's and A15's drivers exist (ruled 8 Nov 2026): a routed model runs only
# once its amendment is in the PUBLIC pre-registration (harness/registration.py).
ROUTED_AMENDMENT = {"seedance2": "A14", "kling_4": "A15"}
SEEDANCE2_USD_PER_S = 0.30                     # 30 credits a second at 720p (catalogue, 31 Oct 2026)
KLING4_USD_PER_S = (0.1256, 0.157)             # 720p: the 20 % promotion, then the list price
KLING4_PROMO_LAST_DAY = _dt.date(2026, 11, 30)  # UTC
DELIVERED = "runs/delivered"   # a delivered clip whose audio was stripped, kept privately; never released
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
    graph[node]["inputs"][key] = effective_seed(a)
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


def build_parser():
    p = argparse.ArgumentParser(description="StillDrawn I2V run (provenance-recording wrapper)")
    p.add_argument("--engine", required=True)
    p.add_argument("--panel", required=True, help="source still (dataset/panels/*.png)")
    p.add_argument("--motion", required=True,
                   help="shot id in the prompt pack (IDLE / BURST / CAMPUSH / FLINT in the frozen "
                        "pack; STILL / LOW / MID / HIGH in A10's ladder pack)")
    p.add_argument("--cell-id", required=True, help="runs/<engine>/<cell-id>.mp4")
    p.add_argument("--duration", type=int, default=5)
    p.add_argument("--ratio", default="1280:720")
    p.add_argument("--seed", type=int, default=None,
                   help=f"local engines run at it ({SEED_DEFAULT}, prereg §5, when not given); gen4.5, "
                        "gen4_turbo and seedance2 send it to Runway when given (none sent otherwise); "
                        "kling_4 refuses it (no seed); fal ignores it. Recorded in the line")
    p.add_argument("--last-panel", default=None,
                   help="FLINT cells: the last-frame panel (h3-fal, seedance, seedance2, kling_4)")
    p.add_argument("--pack", default=str(MOTION_PACK),
                   help="prompt pack --motion resolves from (default: the frozen harness/motion-prompts.md; "
                        "amendment A10's ladder passes harness/motion-ladder.md). A non-default pack is "
                        "recorded in the manifest line as prompt_pack")
    return p


def resolve_prompt(motion, pack=MOTION_PACK):
    """The prompt for `motion` from `pack`, through the frozen parser."""
    return _prompt_from_file(str(pack), motion)


def pack_field(pack):
    """None for the frozen pack, whose manifest lines stay exactly as before; otherwise the
    pack's repo-relative path. A missing pack, or one outside the repository (it could not be
    registered), is refused."""
    if not pathlib.Path(pack).is_file():
        sys.exit(f"--pack {pack}: no such prompt pack file")
    p = pathlib.Path(pack).resolve()
    if p == MOTION_PACK.resolve():
        return None
    try:
        return str(p.relative_to(ROOT.resolve()))
    except ValueError:
        sys.exit(f"--pack {pack}: a prompt pack must live inside the repository")


def effective_seed(a):
    """The seed a clip runs at and its line records: local engines --seed or SEED_DEFAULT;
    gen4.5, gen4_turbo and seedance2 --seed when given, else None (nothing sent); kling_4 and fal
    None (they take none here)."""
    if a.engine in LOCAL_MODELS:
        return SEED_DEFAULT if a.seed is None else a.seed
    if a.engine in RUNWAY_MODELS or RUNWAY_ROUTED.get(a.engine, {}).get("seed"):
        return a.seed
    return None


def uses_runway_task(a):
    """True for the routes through harness/runway_task.py: a routed model, or gen4 with a seed.
    gen4 without a seed keeps the original client and its lines, byte for byte."""
    return a.engine in RUNWAY_ROUTED or (a.engine in RUNWAY_MODELS and a.seed is not None)


def check_runway_task(a):
    """Refuse, before anything is sent, a request outside the registered settings."""
    if a.seed is not None and not 0 <= a.seed <= 4294967295:
        sys.exit(f"--seed {a.seed}: Runway takes 0-4294967295")
    if a.engine in RUNWAY_MODELS:
        if a.last_panel:
            sys.exit(f"{a.engine} with a seed is sent a first frame only here: drop --last-panel")
        return
    cfg = RUNWAY_ROUTED[a.engine]
    if a.seed is not None and not cfg["seed"]:
        sys.exit(f"{a.engine} takes no seed: drop --seed (the line records seed null)")
    if a.ratio != cfg["ratio"]:
        sys.exit(f"{a.engine} runs at --ratio {cfg['ratio']} only (got {a.ratio})")
    if a.duration != cfg["duration"]:
        sys.exit(f"{a.engine} runs at {cfg['duration']} s only (got --duration {a.duration})")


def runway_body(a, prompt):
    """The request body, images by path (harness/runway_task.py inlines them). Pure."""
    body = {"model": a.engine, "promptText": prompt, "ratio": a.ratio, "duration": a.duration}
    if a.engine in RUNWAY_MODELS:
        body["promptImage"] = a.panel
    else:
        frames = [{"uri": a.panel, "position": "first"}]
        if a.last_panel:
            frames.append({"uri": a.last_panel, "position": "last"})
        body["promptImage"] = frames
        if RUNWAY_ROUTED[a.engine]["audio"] is False:
            body["audio"] = False
    seed = effective_seed(a)
    if seed is not None:
        body["seed"] = seed
    return body


def runway_cost(engine, duration, day):
    """Estimated $ for one clip; `day` (UTC) decides kling_4's promotional or list price."""
    if engine in RUNWAY_MODELS:
        rate = RUNWAY_MODELS[engine]
    elif engine == "seedance2":
        rate = SEEDANCE2_USD_PER_S
    else:
        rate = KLING4_USD_PER_S[0] if day <= KLING4_PROMO_LAST_DAY else KLING4_USD_PER_S[1]
    return round(rate * duration, 2)


def runway_model_version(engine):
    return f"{engine} (Runway dev API, X-Runway-Version {RUNWAY_API_VERSION})"


def _probe(path, entries, select=None):
    cmd = ["ffprobe", "-v", "error"] + (["-select_streams", select] if select else []) + [
        "-show_entries", entries, "-of", "json", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ffprobe could not read {path}: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout).get("streams", [])


def audio_streams(path):
    return len(_probe(path, "stream=index", "a"))


def frame_size(path):
    s = _probe(path, "stream=width,height", "v:0")
    return f"{s[0]['width']}x{s[0]['height']}" if s else None


def video_md5(path):
    """MD5 of the first video stream's packets (as the A11 build checks its re-mux); exits rather
    than return something two failures could share."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-c", "copy",
                        "-f", "md5", "-"], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip().startswith("MD5="):
        sys.exit(f"ffmpeg could not hash the video of {path}: {r.stderr.strip()[:200]}")
    return r.stdout.strip()


def settle_audio(a, out):
    """seedance2 and kling_4: the audio record. A delivered audio track is removed by copying the
    first video stream alone, without re-encoding (as the A11 build does); the copy's video-packet
    md5 must equal the delivered file's and it must carry no audio, or the run stops with the
    delivered file left at `out` (harness/ladder.py then stops on a clip left behind). The
    delivered file is kept privately under runs/delivered/ and recorded by sha256."""
    delivered_sha = hashlib.sha256(out.read_bytes()).hexdigest()
    n = audio_streams(out)
    rec = {"sent": RUNWAY_ROUTED[a.engine]["audio"], "delivered_audio_streams": n,
           "delivered_sha256": delivered_sha, "stripped": n > 0}
    if not n:
        return rec
    tmp = out.with_name(out.stem + ".tmp.mp4")
    kept = ROOT / DELIVERED / a.engine / out.name
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-map", "0:v:0", "-c", "copy",
                            str(tmp)], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"ffmpeg could not strip the audio of {out}: {r.stderr.strip()[:200]}; the delivered "
                     "clip is left in place")
        md5 = video_md5(tmp)
        if md5 != video_md5(out):
            sys.exit(f"{out}: the stripped copy's video packets differ from the delivered file's; the "
                     "delivered clip is left in place")
        if audio_streams(tmp):
            sys.exit(f"{out}: audio survived the strip; the delivered clip is left in place")
        kept.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, kept)   # copied, not moved: `out` is never absent, even mid-swap
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)
    rec.update(video_packet_md5=md5, delivered_kept=str(kept.relative_to(ROOT)))
    return rec


def _run_runway_task(a, prompt, out):
    """(wall_s, ratio for the line, route record) for a route through harness/runway_task.py."""
    routed = a.engine in RUNWAY_ROUTED
    if routed:
        for tool in ("ffmpeg", "ffprobe"):   # checked before anything is paid for
            if not shutil.which(tool):
                sys.exit(f"{tool} not found: {a.engine}'s audio check needs it; nothing was sent")
    body = runway_body(a, prompt)
    cmd = ["op", "run", "--env-file", str(BACKEND_SCRIPTS / "runway.env"), "--",
           "python3", str(HERE / "runway_task.py"), "--request", json.dumps(body), "--out", str(out)]
    t_start = time.time()
    r = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True)
    wall_s = time.time() - t_start
    lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    try:
        res = json.loads(lines[-1])
    except (IndexError, ValueError):
        sys.exit(f"runway_task.py printed no task record for {out} (the clip, if any, is left in place)")
    route = {"route": "Runway", "model_id": a.engine, "runway_api_version": RUNWAY_API_VERSION,
             "request": body, "task_id": res.get("task_id"), "task": res.get("task")}
    # Runway has made (and charged for) the clip: its record goes to stderr before anything below
    # can stop the run, so a stop that writes no manifest line never loses it.
    print("runway route record: " + json.dumps({"model": a.engine, "request": body, "task_id": res.get("task_id"),
                                                "seed": effective_seed(a), "out": str(out),
                                                "task": res.get("task")}), file=sys.stderr, flush=True)
    if not routed:
        return wall_s, a.ratio, route
    route["audio"] = settle_audio(a, out)
    return wall_s, frame_size(out), route


def size_ok(ratio, size):
    """Whether a delivered frame size is the one requested: W:H exactly; auto_<N>p keeps the input's
    framing at N pixels on its shorter side."""
    if not size:
        return False
    w, h = (int(x) for x in size.split("x"))
    if ratio.startswith("auto_") and ratio.endswith("p"):
        return min(w, h) == int(ratio[len("auto_"):-1])
    rw, rh = (int(x) for x in ratio.split(":"))
    return (w, h) == (rw, rh)


ROUTE_RECORD_PREFIX = "runway route record: "


def read_record_file(path):
    """The route record from a file (`--record-file`): its `runway route record:` lines if it has any (a saved
    stderr; an appended batch log has one per cell, so all of them come back, newline-joined, and
    parse_record(record, task_id) takes the one carrying the adopted task id, the last when none does), else
    the whole text (the line itself, or its JSON). Shell-quoting a long JSON line is the mistake this avoids."""
    p = pathlib.Path(path)
    if not p.is_file():
        sys.exit(f"--record-file {path}: no such file")
    text = p.read_text()
    hits = [ln for ln in text.splitlines() if ln.startswith(ROUTE_RECORD_PREFIX)]
    return "\n".join(hits) if hits else text


def record_from_args(record, record_file):
    """The `record` adopt() takes, from a driver's --record and --record-file (one of them, or neither)."""
    if record and record_file:
        sys.exit("give --record or --record-file, not both")
    return read_record_file(record_file) if record_file else record


def parse_record(record, task_id=None):
    """The route record as a dict: a dict as it is, a string (the stderr line or its JSON) parsed. Anything
    else is refused, naming why. Of several `runway route record:` lines the one whose task id is `task_id`
    is taken, the last when none is (adopt's match check then refuses a wrong one)."""
    if isinstance(record, str):
        text = record.strip()
        hits = [ln for ln in text.splitlines() if ln.startswith(ROUTE_RECORD_PREFIX)]
        if len(hits) > 1:
            def carries(ln):
                try:
                    return json.loads(ln[len(ROUTE_RECORD_PREFIX):]).get("task_id") == task_id
                except (ValueError, AttributeError):
                    return False
            text = next((ln for ln in hits if carries(ln)), hits[-1])
        try:
            record = json.loads(text[len(ROUTE_RECORD_PREFIX):] if text.startswith(ROUTE_RECORD_PREFIX) else text)
        except ValueError as e:
            sys.exit(f"REFUSING: --record is not a 'runway route record:' line ({e}); not adopted")
    if not isinstance(record, dict):
        sys.exit(f"REFUSING: --record is not a 'runway route record:' line (its JSON is a "
                 f"{type(record).__name__}, not an object); not adopted")
    return record


def _created_at(task):
    """The task record's creation time as an aware datetime, or None (absent or not an ISO time)."""
    raw = (task or {}).get("createdAt")
    if not isinstance(raw, str):
        return None
    try:
        t = _dt.datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)


def adopt(a, file, task_id, today=None, record=None):
    """Record a paid clip whose run stopped with it left behind ("left a clip behind"), from the file
    Runway delivered (the dashboard keeps it) and the task id the run printed. Adopt makes the checks the
    normal path makes: the settings check and the amendment's tripwire, the frame size (which adopt checks
    itself; the normal path only records it), and on seedance2 and kling_4 the audio strip with its
    packet-md5 check. When a clip was left at the cell's path, the delivered file's video packets must equal
    it (a clip whose packets differ is refused; a partial download is kept as it is); the left clip is
    kept privately (runs/delivered/), and an earlier adopt's kept copy stops a second one. The file may
    be the clip left in place (the audio check stopped the run, A15.3.4): it is then recorded from
    there. A file already recorded for another cell (its sha256 as `adopted.file_sha256` or
    `audio.delivered_sha256` on any line) is refused. `record` is the route record the run printed on stderr
    (`runway route record: {...}`, the line or its JSON, or the parsed dict; `--record-file` reads it from a
    file): when given, its task id, model and request must be this cell's, and its Runway task record becomes
    the line's `task`; the line's date and kling_4's day-based cost then follow the task's `createdAt`
    when it has one, the adopt day otherwise. Without it the line's task is {"id": task_id}. Refuses a cell
    that already has a manifest line, and takes the per-cell lock the normal path takes. Returns the line
    written."""
    if not uses_runway_task(a):
        sys.exit(f"adopt: {a.engine} without a seed is not a route this tool adopts")
    check_runway_task(a)
    if a.engine in ROUTED_AMENDMENT:
        from registration import require_public
        require_public(ROUTED_AMENDMENT[a.engine], f"adopt a {a.engine} clip")
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found: adopt checks the file with it")
    out = ROOT / "runs" / a.engine / f"{a.cell_id}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    lock = out.with_suffix(".lock")
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        sys.exit(f"{lock} held — another driver is working on this cell; not adopting over it")
    try:
        return _adopt_locked(a, file, task_id, out, today, record)
    finally:
        os.close(lock_fd)
        lock.unlink(missing_ok=True)


def _adopt_locked(a, file, task_id, out, today, record):
    manifest = ROOT / "runs" / "manifest.jsonl"
    lines = [json.loads(x) for x in manifest.read_text().splitlines() if x.strip()] if manifest.exists() else []
    if any(x.get("cell_id") == a.cell_id for x in lines):
        sys.exit(f"{a.cell_id} already has a manifest line: nothing to adopt")
    src = pathlib.Path(file)
    if not src.is_file():
        sys.exit(f"{src}: no such file")
    file_sha = hashlib.sha256(src.read_bytes()).hexdigest()
    for x in lines:
        if file_sha in ((x.get("adopted") or {}).get("file_sha256"), (x.get("audio") or {}).get("delivered_sha256")):
            sys.exit(f"REFUSING: {src} is the file already recorded for {x.get('cell_id')} (sha256 {file_sha[:12]}…): "
                     f"one delivered file is one cell's clip; not adopted for {a.cell_id}")
    size = frame_size(src)
    if not size_ok(a.ratio, size):
        sys.exit(f"{src}: frame size {size}, not the {a.ratio} requested; not adopted")
    prompt = resolve_prompt(a.motion, a.pack)
    body = runway_body(a, prompt)
    task, task_from = {"id": task_id}, None
    if record is not None:
        record = parse_record(record, task_id)
        if record.get("task_id") != task_id or record.get("model") != a.engine or record.get("request") != body:
            sys.exit(f"the route record given is not {a.cell_id}'s request and task {task_id} (its task id, model "
                     "and request must match); not adopted")
        task, task_from = record.get("task") or task, "the route record the run printed"
    kept = ROOT / DELIVERED / a.engine / f"{a.cell_id}.left-behind.mp4"
    if kept.exists():
        sys.exit(f"REFUSING: an earlier adopt stopped part-way for {a.cell_id}; inspect {kept} before adopting")
    left = None
    if out.exists() and out.resolve() == src.resolve():
        left = {"in_place": True}                 # the clip the run left is the delivered file (A15.3.4's stop)
    elif out.exists():
        if hashlib.sha256(out.read_bytes()).hexdigest() == file_sha:
            sys.exit(f"REFUSING: {out} already holds this clip for {a.cell_id}; adopt it in place with "
                     f"--file {out}; not adopted")
        try:
            left_md5 = video_md5(out)
        except SystemExit:
            left_md5 = None                       # a partial download: nothing to compare
        if left_md5 is not None and left_md5 != video_md5(src):
            sys.exit(f"{src}: its video packets differ from the clip left at {out}: another video; not adopted")
        kept.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out, kept)
        left = {"kept": str(kept.relative_to(ROOT)), "video_packet_md5": left_md5}
    if not (left or {}).get("in_place"):
        shutil.copyfile(src, out)
    adopt_day = today or _dt.datetime.now(_dt.timezone.utc).date()
    created = _created_at(task) if task_from else None
    route = {"route": "Runway", "model_id": a.engine, "runway_api_version": RUNWAY_API_VERSION, "request": body,
             "task_id": task_id, "task": task,
             "adopted": {"file_sha256": file_sha, "left_behind": left, "task_record": task_from,
                         "date": adopt_day.isoformat()}}
    if a.engine in RUNWAY_ROUTED:
        route["audio"] = settle_audio(a, out)
        actual_ratio = frame_size(out)
    else:
        actual_ratio = a.ratio
    t0 = created.astimezone().replace(tzinfo=None) if created else _dt.datetime.now()
    cost_day = created.astimezone(_dt.timezone.utc).date() if created else adopt_day
    line = manifest_line(a, prompt, runway_model_version(a.engine), effective_seed(a), None,
                         runway_cost(a.engine, a.duration, cost_day),
                         actual_ratio, t0, out, prompt_pack=pack_field(a.pack), route=route)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("a") as f:
        f.write(json.dumps(line) + "\n")
    return line


def manifest_line(a, prompt, model_version, seed, wall_s, cost, actual_ratio, t0, out,
                  prompt_pack=None, route=None):
    """One clip's manifest record, keys in the frozen order; prompt_pack (pack_field's value,
    computed before the run) last, and only for a non-default pack; then, for a route through
    harness/runway_task.py, its record. Pure: it never exits, so nothing can stop a paid clip's
    line from being written."""
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
    if prompt_pack:
        line["prompt_pack"] = prompt_pack
    if route:
        line.update(route)
    return line


def main():
    a = build_parser().parse_args()

    known = set(RUNWAY_MODELS) | set(RUNWAY_ROUTED) | set(LOCAL_MODELS) | {"h3-fal", "seedance"}
    if a.engine not in known:
        sys.exit(f"unknown engine {a.engine} (wired: {', '.join(sorted(known))})")
    if uses_runway_task(a):
        check_runway_task(a)   # a request outside the registered settings is refused here
    if a.engine in ROUTED_AMENDMENT:
        from registration import require_public
        require_public(ROUTED_AMENDMENT[a.engine], f"generate {a.engine} clips",
                       hint="Nothing was sent.")

    prompt_pack = pack_field(a.pack)   # a missing or outside pack is refused before anything runs
    prompt = resolve_prompt(a.motion, a.pack)
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
    seed = effective_seed(a)
    cost = 0.0
    route = None

    if uses_runway_task(a):   # a seeded gen4, seedance2 or kling_4
        wall_s, actual_ratio, route = _run_runway_task(a, prompt, out)
        model_version = runway_model_version(a.engine)
        cost = runway_cost(a.engine, a.duration, _dt.datetime.now(_dt.timezone.utc).date())
    elif a.engine in RUNWAY_MODELS:   # no seed: the original client, unchanged
        cmd = ["op", "run", "--env-file", str(BACKEND_SCRIPTS / "runway.env"), "--",
               "python3", str(BACKEND_SCRIPTS / "runway_gen.py"), "video",
               "--model", a.engine, "--image", a.panel, "--prompt", prompt,
               "--ratio", a.ratio, "--duration", str(a.duration), "--out", str(out)]
        t_start = time.time()
        subprocess.run(cmd, check=True)
        wall_s = time.time() - t_start
        model_version = f"{a.engine} (Runway dev API, X-Runway-Version {RUNWAY_API_VERSION})"
        seed = None   # this route sends no seed (a seed goes through runway_task.py)
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

    line = manifest_line(a, prompt, model_version, seed, wall_s, cost, actual_ratio, t0, out,
                         prompt_pack=prompt_pack, route=route)
    manifest = ROOT / "runs/manifest.jsonl"
    with manifest.open("a") as f:
        f.write(json.dumps(line) + "\n")
    print(f"manifest += {a.cell_id}  (${cost:.2f}, {wall_s:.0f}s)" if wall_s
          else f"manifest += {a.cell_id}  (${cost:.2f})")


if __name__ == "__main__":
    main()
