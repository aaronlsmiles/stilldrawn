#!/usr/bin/env python3
"""Panel generation wrapper — every dataset panel is born through this script.

Thin subprocess wrapper around the wired generation clients (local ComfyUI
driver / hosted Runway dev-API client); its job is provenance: every call's
full resolved arguments land in dataset/recipes/<panel-id>.json BEFORE the
image is accepted into dataset/panels/. Prompts are resolved here (via
pack_parser) and passed to the child as explicit strings, so the recipe
records exactly what ran.

Subcommands
  gen      make a panel        gen_panel.py gen --engine local --prompt-file dataset/panel-pack.md \
                                   --shot CU-LINE-1 --panel-id cu-line-1 --seed 20260812
  lineart  extraction pass     gen_panel.py lineart --panel dataset/panels/cu-line-1.png
                               (AnimeLineArt extract via ComfyUI, then inversion →
                                dataset/lineart/<id>-lines.png; run with the ComfyUI
                                venv python — inversion needs PIL)

Engines
  local   → ComfyUI txt2img (Illustrious-XL-v0.1), £0, --ratio WxH (SDXL buckets
            832x1216 / 1024x1024 / 1536x640)
  hosted  → Runway dev API text_to_image (default model gemini_2.5_flash),
            --ratio W:H (e.g. 768:1344, 1344:768, 1024:1024), key injected by
            `op run` inside this wrapper's child call — never in this process's env.
"""
import argparse
import datetime as _dt
import json
import pathlib
import subprocess
import sys

from pack_parser import _prompt_from_file, _negative_from_file

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
# Thin engine clients (ComfyUI / hosted-API wrappers) are not part of the
# release; point STILLDRAWN_BACKEND at your own. See harness/README.md.
BACKEND_SCRIPTS = pathlib.Path(__import__("os").environ.get(
    "STILLDRAWN_BACKEND", "backend"))
VENV_PY = pathlib.Path(__import__("os").environ.get("STILLDRAWN_PY", __import__("sys").executable))

COMFY_DEFAULT_NEG = "color, blurry, worst quality, lowres, text, watermark, signature"
LOCAL_MODEL = "Illustrious-XL-v0.1.safetensors (ComfyUI txt2img workflow)"
HOSTED_COST_USD = {"gemini_2.5_flash": 0.04}   # per image; re-verify on dashboard


def _resolve(a):
    if a.prompt:
        return a.prompt, a.negative
    pos = _prompt_from_file(a.prompt_file, a.shot)
    # hosted engines take no negative parameter — never resolve one for them,
    # so the recipe records exactly what the engine saw
    neg = None if a.engine == "hosted" else (a.negative or _negative_from_file(a.prompt_file, a.shot))
    return pos, neg


def cmd_gen(a):
    pos, neg = _resolve(a)
    out = ROOT / "dataset/panels" / f"{a.panel_id}.png"
    recipe_path = ROOT / "dataset/recipes" / f"{a.panel_id}.json"
    if out.exists() and not a.force:
        sys.exit(f"{out} exists — pass --force to reroll (and count it in the ledger row)")

    if a.engine == "local":
        ratio = a.ratio or "832x1216"
        cmd = ["python3", str(BACKEND_SCRIPTS / "comfy_gen.py"), "gen",
               "--prompt", pos, "--seed", str(a.seed), "--ratio", ratio,
               "--steps", str(a.steps), "--cfg", str(a.cfg), "--out", str(out)]
        if neg:
            cmd += ["--negative", neg]
        model, cost = LOCAL_MODEL, 0.0
        neg_recorded = neg or COMFY_DEFAULT_NEG
    elif a.engine == "hosted":
        ratio = a.ratio or "768:1344"
        cmd = ["op", "run", "--env-file", str(BACKEND_SCRIPTS / "runway.env"), "--",
               "python3", str(BACKEND_SCRIPTS / "runway_gen.py"), "image",
               "--model", a.model, "--prompt", pos, "--ratio", ratio,
               "--seed", str(a.seed), "--out", str(out)]
        model = a.model
        cost = HOSTED_COST_USD.get(a.model)
        neg_recorded = neg  # hosted models take no negative; any avoidance language lives in the prompt
    else:
        sys.exit(f"unknown engine {a.engine}")

    t0 = _dt.datetime.now()
    subprocess.run(cmd, check=True)

    recipe = {
        "panel_id": a.panel_id,
        "engine": a.engine,
        "model": model,
        "prompt": pos,
        "negative": neg_recorded,
        "seed": a.seed,
        "settings": {"ratio": ratio,
                     **({"steps": a.steps, "cfg": a.cfg} if a.engine == "local" else {})},
        "prompt_file": a.prompt_file, "shot": a.shot,
        "cost_usd": cost,
        "date": t0.strftime("%Y-%m-%d"),
        "reroll": bool(a.force),
    }
    recipe_path.parent.mkdir(parents=True, exist_ok=True)
    recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
    print(f"recipe -> {recipe_path}")


def cmd_lineart(a):
    """Extraction pass: AnimeLineArt (white-on-black) → invert → black-on-white layer."""
    panel = pathlib.Path(a.panel)
    out = ROOT / "dataset/lineart" / f"{panel.stem}-lines.png"
    raw = out.with_suffix(".raw.png")
    subprocess.run(["python3", str(BACKEND_SCRIPTS / "comfy_gen.py"), "extract",
                    "--control", str(panel), "--out", str(raw)], check=True)
    try:
        from PIL import Image, ImageOps
    except ImportError:
        sys.exit(f"PIL unavailable — rerun with the ComfyUI venv python: {VENV_PY}")
    ImageOps.invert(Image.open(raw).convert("L")).save(out)
    raw.unlink()
    print(f"lineart -> {out}")


def main():
    p = argparse.ArgumentParser(description="StillDrawn panel generation (provenance-recording wrapper)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pg = sub.add_parser("gen", help="generate a dataset panel + its recipe JSON")
    pg.add_argument("--engine", required=True, choices=["local", "hosted"])
    pg.add_argument("--panel-id", required=True, help="dataset id, e.g. cu-line-1")
    pg.add_argument("--prompt")
    pg.add_argument("--prompt-file")
    pg.add_argument("--shot")
    pg.add_argument("--negative")
    pg.add_argument("--seed", type=int, required=True, help="always explicit — recipes must reproduce")
    pg.add_argument("--ratio", help="local: WxH bucket; hosted: W:H")
    pg.add_argument("--steps", type=int, default=28)
    pg.add_argument("--cfg", type=float, default=5.5)
    pg.add_argument("--model", default="gemini_2.5_flash", help="hosted only")
    pg.add_argument("--force", action="store_true", help="overwrite an existing panel (reroll)")
    pg.set_defaults(fn=cmd_gen)

    pl = sub.add_parser("lineart", help="extraction pass → dataset/lineart/<id>-lines.png")
    pl.add_argument("--panel", required=True)
    pl.set_defaults(fn=cmd_lineart)

    a = p.parse_args()
    if a.cmd == "gen" and not (a.prompt or (a.prompt_file and a.shot)):
        sys.exit("need --prompt or --prompt-file + --shot")
    a.fn(a)


if __name__ == "__main__":
    main()
