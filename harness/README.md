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
| `ground_series.py` | Builds the ground-value variants and runs amendment A3; with `--draw`, amendment A12's repeat draws |
| `ladder.py` | Amendment A10's motion ladder: builds the cell list, runs the clips, runs the metrics |
| `motion-ladder.md` | Amendment A10's prompt pack (four motion levels) |
| `registration.py` | The registration tripwire: A10–A12 tools refuse to make or read new data until the amendment is in the public pre-registration |
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
API key. `STILLDRAWN_HW` names the machine and is appended to each local clip's
`model_version` in the manifest; it is **required** for local runs of `ladder.py`
and of `ground_series.py --draw` (Wan 2.2, LTX-2.3), which refuse without it, and
optional elsewhere. `STILLDRAWN_PUBLIC_PREREG` names the public
`docs/PREREGISTRATION.md` that `registration.py` checks (default:
`../stilldrawn/docs/PREREGISTRATION.md` from this tree's folder, which is this
tree's own file when the folder is named `stilldrawn`; a copy inside a private
working tree never counts). Optional: `STILLDRAWN_POD_ID`, `STILLDRAWN_FAL_SEEDANCE_MODEL`.

**Amendments A10–A12.** `ladder.py` and `ground_series.py --draw` generate the
clips; their analyses are `analysis/a10_ladder.py` and
`analysis/a12_ground_repeats.py`. Amendment A11's human check (40 clips, new
raters) is analysed by `analysis/human_check2/collect.py`; its ratings ship as
scores only, in `analysis/human_check2/`. The tests are the `test_*.py` files in
`harness/` and `analysis/`.
