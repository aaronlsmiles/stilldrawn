#!/usr/bin/env python3
"""One Runway image_to_video task: submit, poll, download. The harness's own client, for the
requests gen_video.py sends through Runway with fields the older client does not carry: a seed
(gen4.5 and gen4_turbo, amendments A10 and A12; seedance2, A14), first and last frames by
position (seedance2 and kling_4, A14 and A15) and the audio switch (seedance2).

    op run --env-file <runway.env> -- python3 harness/runway_task.py --request JSON --out CLIP

--request is the request body, with each image given as a file path: "promptImage" is a path,
or a list of {"uri": <path>, "position": "first" | "last"}. Each path is inlined here as a data
URI, byte for byte; a panel too large to inline is refused before anything is sent, never
resampled. The key is read from RUNWAY_API_KEY in this process only (op run puts it there).

Right after the submission is accepted, `submitted <model> as task <id>` goes to stderr, so a
task Runway has taken (and may charge for) is on record whatever happens next. On success the
clip is written to --out and one JSON line is printed on stdout:
{"task_id": ..., "task": <the final task record's scalar fields>}. The output URLs are signed
and short-lived, so they are left out. Progress goes to stderr. A task that ends FAILED,
CANCELLED or ERROR exits with `task <id> <STATUS>: <record>`, the line harness/ladder.py's
refusal rule reads (only FAILED can become a refusal there). An API error, a network error, a
timeout or a success without an output exits with its own message, which is never a refusal.

Fields per model: docs/RUNWAY-MODELS-2026-11-08.md (Runway's OpenAPI file, 8 Nov 2026).
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.dev.runwayml.com/v1"
API_VERSION = "2024-11-06"            # X-Runway-Version, as gen_video.RUNWAY_API_VERSION
POLL_SECONDS = 5
POLL_TIMEOUT = 1800                   # a timeout is a harness fault; the task may still finish
MAX_INLINE_BYTES = 4_500_000          # the older client's inline cap; every benchmark panel is under it
TERMINAL_FAIL = ("FAILED", "CANCELLED", "ERROR")


def api_key():
    k = os.environ.get("RUNWAY_API_KEY", "").strip()
    if not k:
        sys.exit("RUNWAY_API_KEY not set in this process: run through op run --env-file <runway.env> -- ...")
    return k


def _req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {api_key()}")
    req.add_header("X-Runway-Version", API_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"API {e.code} on {method} {path}: {e.read().decode(errors='replace')[:800]}")
    except urllib.error.URLError as e:
        sys.exit(f"network error on {method} {path}: {e.reason}")


def inline(path):
    """A PNG panel as a data URI, byte for byte."""
    raw = Path(path).read_bytes()
    if len(raw) > MAX_INLINE_BYTES:
        sys.exit(f"{path}: {len(raw)} bytes, too large to inline (cap {MAX_INLINE_BYTES}); a "
                 "benchmark panel is never resampled, so nothing was sent")
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def inline_request(body):
    """The body with every image path inlined; every other field unchanged."""
    out = dict(body)
    img = body.get("promptImage")
    if isinstance(img, str):
        out["promptImage"] = inline(img)
    elif isinstance(img, list):
        out["promptImage"] = [{**f, "uri": inline(f["uri"])} for f in img]
    return out


def submit_and_wait(body, req=None, sleep=None, log=None):
    """(task id, final task record) of a SUCCEEDED task; any other end exits."""
    req = req or _req
    sleep = sleep or time.sleep
    log = log or (lambda s: print(s, file=sys.stderr, flush=True))
    log(f"submit {body.get('model')} (/image_to_video)")
    task = req("POST", "/image_to_video", body)
    tid = task.get("id") or task.get("taskId")
    if not tid:
        sys.exit(f"no task id in response: {task}")
    log(f"submitted {body.get('model')} as task {tid}")   # on record before any poll; never a refusal line
    waited = 0
    while waited < POLL_TIMEOUT:
        sleep(POLL_SECONDS)
        waited += POLL_SECONDS
        st = req("GET", f"/tasks/{tid}")
        status = (st.get("status") or "").upper()
        log(f"   {status} ({waited}s)")
        if status == "SUCCEEDED":
            return tid, st
        if status in TERMINAL_FAIL:
            sys.exit(f"task {tid} {status}: {st}")
    sys.exit(f"task {tid} timed out after {POLL_TIMEOUT}s (it may still finish: check before resubmitting)")


def task_summary(record):
    """The task record's scalar fields (id, status, createdAt, and any seed or version field the
    API reports); the signed output URLs and any nested value are left out."""
    return {k: v for k, v in record.items()
            if k != "output" and (v is None or isinstance(v, (str, int, float, bool)))}


def download(url, out):
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, out)


def main(argv=None):
    p = argparse.ArgumentParser(description="one Runway image_to_video task (harness client)")
    p.add_argument("--request", required=True, help="the request body as JSON, images as file paths")
    p.add_argument("--out", required=True, help="where the clip is written")
    a = p.parse_args(argv)
    body = inline_request(json.loads(a.request))
    tid, rec = submit_and_wait(body)
    outputs = rec.get("output") or []
    if not isinstance(outputs, list):
        outputs = [outputs]
    if not outputs:
        sys.exit(f"task {tid} succeeded with no output: {task_summary(rec)}")
    download(outputs[0], a.out)
    print(json.dumps({"task_id": tid, "task": task_summary(rec)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
