#!/usr/bin/env python3
"""One-shot RunPod job: the Wan 2.2 half of the A3 ground series (5 cells).

A3 clause 2 permits pod execution for the local engines with hardware recorded
per clip (A2). Wan at 704p exceeds the harness's 2 h local timeout on the
study Mac (verified 2026-08-14), so the five ground cells run on a rented
CUDA GPU with the pinned Wan weights, identical settings to the matrix.

SAFETY: the pod is terminated in a finally: block on every exit path —
success, exception, or Ctrl-C. It also carries a hard wall-clock budget; if
the job overruns, the pod is killed regardless of progress. Losing the run
costs pennies; leaking a running pod costs the balance.

Invoke via `op run --env-file harness/runpod.env -- python harness/pod_run_wan_ground.py`.
"""
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://api.runpod.io/graphql"
KEY = os.environ["RUNPOD_API_KEY"]
SSH_KEY = pathlib.Path.home() / ".ssh/stilldrawn_runpod"
# 48GB cards first: the matrix ran on a 32GB RTX 5090, and Wan at 704p may not
# fit 24GB. Community pricing for A6000/A40 is comparable to a 4090 anyway.
GPUS = ["NVIDIA RTX A6000", "NVIDIA A40", "NVIDIA GeForce RTX 4090",
        "NVIDIA GeForce RTX 3090 Ti", "NVIDIA GeForce RTX 3090"]
# torch 2.4 cannot parse the list[int] annotations in current comfy_kitchen
# (a pip dependency of ComfyUI, so pinning ComfyUI does not avoid it).
# torch >=2.5 fixes it; this image is torch 2.8 / CUDA 12.8 (diagnosed 2026-08-14).
IMAGE = "runpod/pytorch:1.1.0-rc.154-cu1281-torch280-ubuntu2204-cluster"
MAX_MINUTES = 90          # hard wall-clock budget for the whole job
SSH_WAIT_MINUTES = 12     # a pod that is not reachable by then is abandoned
MAX_DEPLOYS = 3           # ...and we try this many pods before giving up
KS = [100, 90, 80, 65, 52]


def gql(query):
    req = urllib.request.Request(
        API, data=json.dumps({"query": query}).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {KEY}",
                 # RunPod 403s the default Python-urllib UA (diagnosed 2026-08-14)
                 "User-Agent": "curl/8.7.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.loads(r.read())
    if "errors" in out:
        raise RuntimeError(json.dumps(out["errors"])[:400])
    return out["data"]


def deploy():
    """Try GPUs cheapest-capable-first; community capacity comes and goes.

    PUBLIC_KEY must be passed as a pod env var — RunPod images install it into
    authorized_keys and start sshd from it. Omitting it deploys a pod you can
    never reach (diagnosed 2026-08-14: exposed port, connection refused)."""
    pub = (pathlib.Path.home() / ".ssh/stilldrawn_runpod.pub").read_text().strip()
    last = None
    for gpu in GPUS:
        q = (f'mutation {{ podFindAndDeployOnDemand(input: {{'
             f'cloudType: SECURE, gpuCount: 1, gpuTypeId: "{gpu}", '
             f'name: "stilldrawn-a3-wan", imageName: "{IMAGE}", '
             f'containerDiskInGb: 20, volumeInGb: 30, '
             f'volumeMountPath: "/workspace", ports: "22/tcp", '
             f'env: [{{key: "PUBLIC_KEY", value: "{pub}"}}]}}) {{ id }} }}')
        try:
            pid = gql(q)["podFindAndDeployOnDemand"]["id"]
            print(f"deployed on {gpu}", flush=True)
            return pid
        except Exception as e:                                # noqa: BLE001
            last = f"{gpu}: {e}"
            print(f"  no capacity: {gpu}", flush=True)
    raise RuntimeError(f"no GPU available; last error {last}")


def terminate(pod_id):
    for _ in range(5):
        try:
            gql(f'mutation {{ podTerminate(input:{{podId:"{pod_id}"}}) }}')
            print(f"POD {pod_id} TERMINATED", flush=True)
            return True
        except Exception as e:                                # noqa: BLE001
            print(f"terminate retry: {e}", flush=True)
            time.sleep(10)
    print(f"!!! COULD NOT TERMINATE {pod_id} — kill it at runpod.io/console/pods",
          flush=True)
    return False


def ssh_endpoint(pod_id, deadline):
    while time.time() < deadline:
        d = gql(f'query {{ pod(input:{{podId:"{pod_id}"}}) '
                f'{{ runtime {{ ports {{ ip publicPort privatePort type isIpPublic }} }} }} }}')
        rt = d["pod"].get("runtime")
        for p in (rt or {}).get("ports") or []:
            if p["privatePort"] == 22 and p["isIpPublic"]:
                return p["ip"], p["publicPort"]
        print("  … waiting for pod", flush=True)
        time.sleep(15)
    raise TimeoutError("pod never exposed SSH")


def sh(ip, port, cmd, timeout=3600):
    full = ["ssh", "-tt", "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=20",
            "-i", str(SSH_KEY), "-p", str(port), f"root@{ip}", cmd]
    return subprocess.run(full, timeout=timeout).returncode


def scp(ip, port, src, dst, from_pod=False):
    a, b = (f"root@{ip}:{src}", dst) if from_pod else (src, f"root@{ip}:{dst}")
    return subprocess.run(
        ["scp", "-r", "-o", "StrictHostKeyChecking=no",
         "-o", "UserKnownHostsFile=/dev/null", "-i", str(SSH_KEY),
         "-P", str(port), a, b], timeout=1800).returncode


SETUP = r'''set -e
cd /workspace
pip install -q -U "huggingface_hub[cli]" hf_transfer && export HF_HUB_ENABLE_HF_TRANSFER=1
# PIN the ComfyUI version to the one the matrix ran on (manifest: 0.31.0).
# Required for comparability, and it also avoids the master-branch crash:
# newer ComfyUI's comfy_kitchen calls torch.library.custom_op with list[int]
# annotations that torch 2.4 (this image) cannot parse (diagnosed 2026-08-14).
[ -d ComfyUI ] || git clone -q https://github.com/comfyanonymous/ComfyUI
cd ComfyUI && git checkout -q v0.31.0 && echo "ComfyUI pinned: $(git describe --tags)"
pip install -q -r requirements.txt
[ -d custom_nodes/ComfyUI-GGUF ] || git -C custom_nodes clone -q https://github.com/city96/ComfyUI-GGUF
pip install -q gguf sentencepiece protobuf imageio imageio-ffmpeg av
M=/workspace/ComfyUI/models
hf download QuantStack/Wan2.2-TI2V-5B-GGUF Wan2.2-TI2V-5B-Q5_K_M.gguf --local-dir $M/diffusion_models/
hf download QuantStack/Wan2.2-TI2V-5B-GGUF VAE/Wan2.2_VAE.safetensors --local-dir /tmp/v
mv -f /tmp/v/VAE/Wan2.2_VAE.safetensors $M/vae/
hf download city96/umt5-xxl-encoder-gguf umt5-xxl-encoder-Q5_K_M.gguf --local-dir $M/text_encoders/
echo SETUP-OK'''

JOB = r'''
# NOTE: deliberately no `set -e` — we want the comfy log dumped on failure
# rather than a silent exit (attempts 3-4 died blind, 2026-08-14).
cd /workspace/ComfyUI
setsid nohup python main.py --listen 127.0.0.1 --port 8188 < /dev/null > /workspace/comfy.log 2>&1 &
echo "waiting for comfy…"
for i in $(seq 1 90); do
  if curl -s -m 3 http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
    echo "COMFY-UP after ${i} polls"; break
  fi
  sleep 5
done
if ! curl -s -m 3 http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
  echo "=== COMFY FAILED TO START — last 60 lines of /workspace/comfy.log ==="
  tail -60 /workspace/comfy.log
  echo "=== end comfy log ==="
  exit 1
fi
cd /workspace/stilldrawn
export STILLDRAWN_HW="$(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | head -1) (RunPod, A3 clause 2)"
python harness/ground_series.py run --engine wan22 || {
  echo "=== GENERATION FAILED — last 40 lines of comfy.log ==="; tail -40 /workspace/comfy.log; }
ls -la runs/wan22/ 2>/dev/null | tail -8
echo JOB-DONE'''


def main():
    t0 = time.time()
    deadline = t0 + MAX_MINUTES * 60
    pod_id = None
    try:
        ip = port = None
        for attempt in range(MAX_DEPLOYS):
            pod_id = os.environ.get("STILLDRAWN_POD_ID") if attempt == 0 else None
            if pod_id:
                print(f"adopting existing pod {pod_id}", flush=True)
            else:
                print(f"deploying pod (try {attempt + 1}/{MAX_DEPLOYS})…", flush=True)
                pod_id = deploy()
            print(f"pod {pod_id}", flush=True)
            try:
                ip, port = ssh_endpoint(
                    pod_id, min(deadline, time.time() + SSH_WAIT_MINUTES * 60))
                break
            except TimeoutError:
                # a pod that never opens SSH is a provisioning dud: bin it and
                # take another rather than burning the whole budget waiting
                # (cost 90 min / $1.39 on 2026-08-14 before this was added)
                print("pod never opened SSH — abandoning it", flush=True)
                terminate(pod_id)
                pod_id = None
        if not ip:
            raise RuntimeError(f"no reachable pod after {MAX_DEPLOYS} tries")
        print(f"ssh root@{ip}:{port}", flush=True)
        for _ in range(20):                       # sshd may lag the port
            if sh(ip, port, "echo ready", timeout=60) == 0:
                break
            time.sleep(10)

        print("setup…", flush=True)
        assert sh(ip, port, SETUP, timeout=2400) == 0, "setup failed"

        print("payload…", flush=True)
        sh(ip, port, "mkdir -p /workspace/stilldrawn/{harness,dataset/panels,dataset/lineart,runs/wan22}")
        for k in KS:
            pid = f"ground-cu-line-1-v{k:03d}"
            scp(ip, port, str(ROOT / f"dataset/panels/{pid}.png"),
                "/workspace/stilldrawn/dataset/panels/")
        for f in ("gen_video.py", "ground_series.py", "pack_parser.py",
                  "motion-prompts.md"):
            scp(ip, port, str(ROOT / "harness" / f), "/workspace/stilldrawn/harness/")
        scp(ip, port, str(ROOT / "harness/graphs"), "/workspace/stilldrawn/harness/")

        print("generating…", flush=True)
        rc = sh(ip, port, JOB, timeout=int(max(600, deadline - time.time())))
        print(f"job rc={rc}", flush=True)

        print("retrieving…", flush=True)
        scp(ip, port, "/workspace/stilldrawn/runs/wan22/ground-*.mp4",
            str(ROOT / "runs/wan22/"), from_pod=True)
        scp(ip, port, "/workspace/stilldrawn/runs/manifest.jsonl",
            "/tmp/pod-manifest.jsonl", from_pod=True)
        print("retrieved", flush=True)
    finally:
        if pod_id:
            for attempt in range(5):
                try:
                    gql(f'mutation {{ podTerminate(input:{{podId:"{pod_id}"}}) }}')
                    print(f"POD {pod_id} TERMINATED", flush=True)
                    break
                except Exception as e:                       # noqa: BLE001
                    print(f"terminate attempt {attempt+1} failed: {e}", flush=True)
                    time.sleep(10)
            else:
                print(f"!!! COULD NOT TERMINATE {pod_id} — KILL IT MANUALLY "
                      f"at runpod.io/console/pods", flush=True)
        print(f"elapsed {(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    sys.exit(main())
