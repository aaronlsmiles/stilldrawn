# harness/

The code that generated the panels and clips. It documents exactly how every
item was produced; it is not a turnkey installer.

| File | Role |
|---|---|
| `gen_panel.py` | Panel generation and line-art extraction, recipe written before acceptance |
| `gen_video.py` | One clip per call, for any engine; writes the manifest line |
| `matrix.py` | Drives the frozen run matrix (cells × engines) |
| `motion-prompts.md` | The three motion prompts, frozen verbatim |
| `graphs/wan22-i2v.json`, `graphs/ltx23-i2v.json` | The ComfyUI graphs used for the two local engines |
| `ground_series.py` | Builds the ground-value variants and runs amendment A3 |
| `hazard_probe.py`, `seedance_scout.py` | Amendments A4 and A5 |
| `pod-setup.sh`, `pod_run_wan_ground.py`, `run_local_ground.sh` | Rented-GPU and local runs |
| `pack_parser.py` | Reads prompts out of `dataset/panel-pack.md` |

**Not included: the engine clients.** `gen_panel.py` and `gen_video.py` call two
thin client scripts, a ComfyUI API wrapper and a hosted-API wrapper, from the
directory named by the `STILLDRAWN_BACKEND` environment variable. Those clients
belong to the author's wider tooling and are not part of this release. Anyone
reproducing a run needs their own client for each engine; the request
parameters are fully specified by the recipes, the graphs and
`runs/manifest.jsonl`.

**Credentials** were never stored in files. The harness passes them to the
clients at run time through 1Password's `op run` with environment files that
held secret references only; those files are not included. The harness itself
reads `FAL_KEY` and `RUNPOD_API_KEY`; your Runway client will need your Runway
API key. Optional: `STILLDRAWN_HW` (hardware label written to the manifest),
`STILLDRAWN_POD_ID`, `STILLDRAWN_FAL_SEEDANCE_MODEL`.
