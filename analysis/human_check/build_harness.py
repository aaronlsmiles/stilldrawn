#!/usr/bin/env python3
"""Build the blinded human-check rating kit (frozen §6, revised by A6).

Produces analysis/human_check/kit/ containing:
  clips/c01.mp4 … c20.mp4      opaque copies of the subset clips (engine names
                               stripped — the originals' filenames would leak)
  panels/c01.png … c20.png     display copies of each clip's source panel
                               (true PNGs, max 900px long edge; display only,
                               measurement never touches these)
  rating-AARON.html, rating-R1.html … rating-R5.html
                               one page per rater slot; clip order randomised
                               per rater by a string-seeded RNG
  README-FIRST.txt             one-paragraph rater instructions

and, OUTSIDE the kit (never shipped): analysis/human_check/mapping.json —
opaque id ↔ cell_id, per-rater orders, and the seeds.

Instrument (amendment A6, 2026-08-15): TWO questions per clip, each a 5-point
scale with every point labelled and the direction stated. Q1 is the register
axis (§6's original construct, re-worded); Q2 is the content/framing axis,
added because most catalogued failures leave the register intact and would
otherwise score a perfect 5. Both must be answered before advancing.
"""
import json
import random
import shutil
import zipfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = ROOT / "analysis" / "out"
KIT = HERE / "kit"
SEED = 20260813
# R6 added by A8: enables the pre-registered sensitivity analysis that repeats
# the §6 result excluding rater 1, so pooling the author is demonstrated not to
# carry the finding rather than merely caveated.
RATERS = ["AARON", "R1", "R2", "R3", "R4", "R5", "R6"]
ENGINE_DIR = {"gen4t": "gen4_turbo", "h3": "h3-fal", "gen45": "gen4.5",
              "wan22": "wan22", "ltx23": "ltx23"}

# ---- A6 instrument (frozen 2026-08-15) ------------------------------------
Q1 = ("Does this clip still look like a hand-drawn black-and-white ink "
      "picture, all the way through?")
Q1_LABELS = ["No: it stops looking hand-drawn — photographic, painted, or "
             "mechanically rendered",
             "Mostly not",
             "Half and half",
             "Mostly: a few frames slip",
             "Yes: every frame could be a drawn panel"]
Q2 = ("Apart from the movement itself, is this the same original image throughout?")
# A6 addendum (2026-08-15): both clarifications came from the author's pilot
# pass, which nearly scored an inserted-cyclist clip 5 by judging its final
# frame. Neither steers the answer; both remove ways of misreading the ask.
Q2_NOTE = ("Anything <b>added, removed or replaced</b> counts as a change, even if "
           "the setting looks identical — a clip that adds a person to an empty "
           "landscape is not the same image.")
# A6 addendum 3: the continuation/invention distinction. The motion prompts ask
# that "the action implied by the drawing continues", so a shattering pane
# throwing more shards is the animation working, not an addition.
Q2_CONT = ("<b>Action already in the drawing doesn't count.</b> If the original "
           "shows glass shattering, a figure mid-leap, or cloth blowing, then that "
           "action carrying on is the animation working — not a change. Count only "
           "things the original never contained: a new person, vehicle, object or "
           "lettering.")
# A6 addendum 4: the written instrument now states what rater 1 effectively
# had (three passes plus a discussion of tone shifts). Naming the failure kinds
# does not steer the score; withholding them made rater 1 the odd one out.
Q1_TONE = ("A slight overall shift in paper tone or brightness belongs here, mildly "
           "— a 4 rather than a 5. It is not a question-2 change.")
# A8 (2026-08-17): addendum 4's wording REPLACED. It named "flat, even fills",
# "perfectly uniform screentone", "no variation in line weight, no wobble" as
# evidence of not being hand-drawn. Those describe ordinary modern manga —
# screentone has been mechanical since the 1960s, and digital inking is
# routinely even-weighted. The reference page checked against it (Dragon Ball
# Super, art/refs/IMG_2321.JPG) has uniform tone, flat solid blacks and smooth
# even contours, and is unmistakably hand-drawn; the old text would have scored
# it a departure. It was an over-generalisation of rater 1's reasoning — he
# marked down two clips that genuinely looked machine-made, and the addendum
# turned that into a far broader rule. The replacement points at machine
# artefacts rather than at cleanliness, and rules the normal properties in.
Q1_MECH = ("Ink can stop looking hand-drawn <b>without</b> becoming photographic. "
           "Look for marks that no one drawing by hand would make: contours gone "
           "soft or blurred, edges that fade instead of ending crisply, lines that "
           "smear, warp or run together in ways a pen or brush would not, or "
           "shading that has turned into a smooth gradient instead of line or "
           "tone. <b>Clean, even linework, flat solid blacks and regular "
           "screentone are normal in manga and are not, by themselves, a "
           "departure.</b>")

# ---- A8 baseline instrument (2026-08-17) ----------------------------------
# Q1 is an ABSOLUTE judgement ("does this look hand-drawn") while Q2 is
# relative to the original shown alongside. Q1 therefore has no baseline: if a
# source panel already reads as mechanical, a low Q1 is charged to the engine
# when it is a property of the corpus. Q3 supplies that baseline, asked once
# per distinct source panel (14, not 20 — several clips share a panel) and
# asked FIRST, before any clip is seen. Deliberately mirrors Q1's construct so
# that clip_Q1 − panel_Q3 isolates the engine's contribution.
Q3 = ("Does this original still image look like a hand-drawn black-and-white "
      "ink picture?")
Q3_LABELS = ["No: it doesn't look hand-drawn — photographic, painted, or "
             "mechanically rendered",
             "Mostly not",
             "Half and half",
             "Mostly",
             "Yes: it could be a drawn panel"]
WATCH_NOTE = ("Watch the whole five seconds before answering. Things that appear "
              "briefly and then leave still count.")
# A6 addendum 2 (2026-08-15): "moving" removed from the question and the top
# label. It implied motion was required for a 5, but a near-static clip that
# preserves its content is a 5 — how much a clip moves is a separate axis we
# deliberately do not ask about here.
Q2_LABELS = ["No: it became a different picture",
             "Mostly not: much of it is different",
             "Half and half",
             "Mostly: small things change",
             "Yes: nothing has been added, removed or replaced"]


def panel_for(cell_id: str) -> Path:
    return ROOT / "dataset" / "panels" / (cell_id.rsplit("_", 2)[0] + ".png")


def page_html(rater: str, order: list) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ink clip rating — {rater}</title>
<style>
 :root {{ --paper:#fbfaf8; --ink:#131311; --line:#ddd; --accent:#2a78d6;
   --muted:#6b6b68; }}
 body {{ margin:0; background:var(--paper); color:var(--ink);
   font:17px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
 .wrap {{ max-width:1080px; margin:0 auto; padding:1.4rem; }}
 .card {{ background:#fff; border:1px solid var(--line); padding:1.2rem 1.4rem;
   border-radius:10px; }}
 .media {{ display:flex; gap:14px; flex-wrap:wrap; align-items:flex-start;
   justify-content:center; margin:.8rem 0; }}
 .media > div {{ flex:1 1 380px; max-width:500px; }}
 .media img, .media video {{ width:100%; height:auto; border:1px solid var(--line);
   background:#fff; display:block; border-radius:4px; }}
 .medialabel {{ font-size:.8rem; color:var(--muted); text-transform:uppercase;
   letter-spacing:.05em; margin-bottom:4px; }}
 .qblock {{ border-top:1px solid var(--line); padding-top:.9rem; margin-top:.9rem; }}
 .q {{ font-size:1.06rem; font-weight:650; text-align:center; margin:0 0 .1rem; }}
 .dir {{ text-align:center; font-size:.85rem; color:var(--muted); margin:0 0 .5rem; }}
 .scale {{ display:flex; gap:8px; justify-content:center; margin:.4rem 0 .3rem;
   flex-wrap:wrap; }}
 .scale button {{ font:inherit; font-weight:650; width:56px; height:52px;
   border:2px solid var(--line); background:#fff; cursor:pointer;
   border-radius:8px; }}
 .scale button:hover {{ border-color:var(--accent); }}
 .scale button.sel {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
 .picked {{ text-align:center; font-size:.9rem; color:var(--muted);
   min-height:1.4em; margin:0; }}
 .picked b {{ color:var(--ink); font-weight:600; }}
 .nav {{ display:flex; justify-content:space-between; align-items:center;
   margin-top:1rem; }}
 .nav button {{ font:inherit; padding:.55rem 1.1rem; cursor:pointer;
   border:1px solid var(--line); background:#fff; border-radius:6px; }}
 .nav button.primary {{ background:var(--ink); color:#fff; border-color:var(--ink); }}
 .nav button:disabled {{ opacity:.4; cursor:default; }}
 .prog {{ color:var(--muted); font-size:.9rem; }}
 ol.key {{ font-size:.9rem; color:var(--muted); margin:.3rem 0 0; padding-left:1.4rem; }}
 #done textarea {{ width:100%; min-height:70px; font:inherit; margin:.5rem 0; }}
 .hint {{ font-size:.85rem; color:var(--muted); }}
 .note {{ font-size:.9rem; color:var(--ink); background:#f4f6f9;
   border-left:3px solid var(--accent); padding:.5rem .7rem; border-radius:4px; }}
 .note2 {{ font-size:.85rem; color:var(--muted); text-align:center;
   max-width:62ch; margin:.1rem auto .4rem; }}
 .watch {{ font-size:.8rem; color:var(--muted); margin:.35rem 0 0; }}
 #seen {{ color:#15803d; font-weight:700; }}
</style></head><body><div class="wrap">

<div class="card" id="intro">
 <h2 style="margin-top:0">Rating 20 short clips — about 20 minutes</h2>
 <p>Each screen shows an <b>original still image</b> (left) and a <b>5-second
 animated clip</b> made from it (right, plays on loop). You answer
 <b>two questions</b> about each clip.</p>

 <div class="qblock">
  <p class="q">1. “{Q1}”</p>
  <p class="dir">5 = yes, completely · 1 = no, not at all</p>
  <ol class="key">{''.join(f'<li>{l}</li>' for l in Q1_LABELS)}</ol>
  <p class="note">{Q1_MECH}</p>
  <p class="note2">{Q1_TONE}</p>
 </div>
 <div class="qblock">
  <p class="q">2. “{Q2}”</p>
  <p class="dir">5 = yes, it is unchanged · 1 = no, it became a different picture</p>
  <ol class="key">{''.join(f'<li>{l}</li>' for l in Q2_LABELS)}</ol>
  <p class="note">{Q2_NOTE}</p>
  <p class="note">{Q2_CONT}</p>
 </div>

 <p class="note" style="margin-top:1rem"><b>{WATCH_NOTE}</b></p>
 <p style="margin-top:1rem">The two are different questions and often have
 different answers. A clip can still look perfectly hand-drawn (a high answer
 to&nbsp;1) while having turned into a completely different picture (a low
 answer to&nbsp;2). How <i>much</i> a clip moves is not being asked about —
 a clip that barely moves but keeps everything intact is still a 5 on
 question&nbsp;2.</p>
 <p>Go with your eye — there are no right answers, and other people's answers
 will differ. Please do it in one sitting, without discussing it with anyone
 first. You can change an answer with Back before finishing.</p>
 <p class="hint">If a video doesn't play, keep this file in the same folder as
 the <code>clips</code> and <code>panels</code> folders from the zip.</p>
 <div class="nav"><span></span><button class="primary" onclick="start()">Start</button></div>
</div>

<div class="card" id="rate" style="display:none">
 <div class="media">
  <div><div class="medialabel">Original image</div><img id="panel" alt="original image"></div>
  <div><div class="medialabel">Clip (loops) <span id="seen"></span></div>
   <video id="clip" loop autoplay muted playsinline controls></video>
   <p class="watch">{WATCH_NOTE}</p></div>
 </div>

 <div class="qblock">
  <p class="q">1. “{Q1}”</p>
  <p class="dir">5 = yes, completely · 1 = no, not at all</p>
  <p class="note2">{Q1_MECH}</p>
  <div class="scale" id="scale1"></div>
  <p class="picked" id="picked1"></p>
 </div>
 <div class="qblock">
  <p class="q">2. “{Q2}”</p>
  <p class="dir">5 = yes, unchanged at every point · 1 = no, it became a different picture</p>
  <p class="note2">{Q2_NOTE}</p>
  <p class="note2">{Q2_CONT}</p>
  <div class="scale" id="scale2"></div>
  <p class="picked" id="picked2"></p>
 </div>

 <div class="nav">
  <button id="back" onclick="nav(-1)">◀ Back</button>
  <span class="prog" id="prog"></span>
  <button id="next" class="primary" onclick="nav(1)" disabled>Next ▶</button>
 </div>
</div>

<div class="card" id="done" style="display:none">
 <h2 style="margin-top:0">Done — thank you!</h2>
 <p>Anything that stood out, or was hard to judge? (optional)</p>
 <textarea id="comment" placeholder="optional"></textarea>
 <div class="nav">
  <button onclick="show('rate');paint()">◀ Back to the clips</button>
  <button class="primary" onclick="save()">Download my answers</button>
 </div>
 <p class="hint">This saves a small file called
 <code>ratings-{rater}.json</code> — please send it back to Aaron. Nothing is
 uploaded anywhere by this page.</p>
</div>

</div><script>
const RATER = {json.dumps(rater)};
const ITEMS = {json.dumps(order)};
const L1 = {json.dumps(Q1_LABELS)}, L2 = {json.dumps(Q2_LABELS)};
let i = 0;
const t0 = new Date().toISOString();
const a1 = {{}}, a2 = {{}};

function mkScale(elId, store, labels, pickedId) {{
  const el = document.getElementById(elId);
  for (let v = 1; v <= 5; v++) {{
    const b = document.createElement('button');
    b.textContent = v;
    b.onclick = () => {{ store[ITEMS[i]] = v; paint(); }};
    el.appendChild(b);
  }}
}}
mkScale('scale1', a1, L1, 'picked1');
mkScale('scale2', a2, L2, 'picked2');

function show(id) {{ for (const s of ['intro','rate','done'])
  document.getElementById(s).style.display = (s === id ? '' : 'none'); }}

function paint() {{
  const item = ITEMS[i];
  document.getElementById('panel').src = 'panels/' + item + '.png';
  const v = document.getElementById('clip');
  const src = 'clips/' + item + '.mp4';
  if (!v.src.endsWith(src)) {{ v.src = src; v.play().catch(()=>{{}}); }}
  document.getElementById('prog').textContent = (i + 1) + ' / ' + ITEMS.length;
  document.getElementById('back').disabled = (i === 0);
  document.getElementById('next').disabled = !(item in a1 && item in a2);
  const s1 = document.getElementById('scale1').children;
  const s2 = document.getElementById('scale2').children;
  [...s1].forEach((b, k) => b.classList.toggle('sel', a1[item] === k + 1));
  [...s2].forEach((b, k) => b.classList.toggle('sel', a2[item] === k + 1));
  document.getElementById('picked1').innerHTML =
    a1[item] ? '<b>' + a1[item] + '</b> — ' + L1[a1[item]-1] : '';
  document.getElementById('picked2').innerHTML =
    a2[item] ? '<b>' + a2[item] + '</b> — ' + L2[a2[item]-1] : '';
  paintSeen();
}}
document.getElementById('clip').addEventListener('ended', markSeen);
document.getElementById('clip').addEventListener('timeupdate', function () {{
  // loop:true fires 'seeking' rather than 'ended' in some browsers
  if (this.duration && this.currentTime > this.duration - 0.15) markSeen();
}});
const seenOnce = {{}};
function markSeen() {{ seenOnce[ITEMS[i]] = true; paintSeen(); }}
function paintSeen() {{
  document.getElementById('seen').textContent =
    seenOnce[ITEMS[i]] ? '· played through ✓' : '';
}}
function start() {{ show('rate'); paint(); }}
function nav(d) {{
  if (d > 0 && i === ITEMS.length - 1) {{ show('done'); return; }}
  i = Math.max(0, Math.min(ITEMS.length - 1, i + d)); paint();
}}
function save() {{
  const out = {{ rater: RATER, started: t0, finished: new Date().toISOString(),
    instrument: "A6",
    questions: {{ register: {json.dumps(Q1)}, sameness: {json.dumps(Q2)} }},
    ratings: ITEMS.map(id => ({{ clip: id,
      register: a1[id] ?? null, sameness: a2[id] ?? null }})),
    comment: document.getElementById('comment').value || null }};
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)],
    {{type: 'application/json'}}));
  a.download = 'ratings-' + RATER + '.json'; a.click();
}}
</script></body></html>
"""


def main():
    # A8 (2026-08-17): the standalone offline CLIP kit is SUPERSEDED. The
    # protocol now opens with the 14-panel baseline (Q3), and this builder does
    # not produce it — a kit built here would silently administer a different
    # protocol from the hosted study, which is the exact failure this project
    # has hit twice (addendum 4; the answers/ directory). The superseded pages
    # and zip are archived under
    # [private archive path]
    #
    # This function is retained because page_html() is the single source of
    # truth that the hosted build transforms — but running it to ship a kit
    # requires a decision, so it refuses unless explicitly overridden.
    import os
    if os.environ.get("STILLDRAWN_ALLOW_OFFLINE_KIT") != "1":
        raise SystemExit(
            "REFUSING: the offline clip kit is superseded by the hosted study "
            "(amendment A8) and omits the mandatory 14-panel baseline.\n"
            "The hosted app is the instrument; page_html() here remains its "
            "source of truth.\n"
            "If an offline fallback is genuinely needed, it must include the "
            "baseline first — then re-run with STILLDRAWN_ALLOW_OFFLINE_KIT=1 "
            "and record the decision as an amendment.")

    sub = json.loads((OUT / "human_subset.json").read_text())
    cells = sub["cells"]
    assert len(cells) == 20

    if KIT.exists():
        shutil.rmtree(KIT)
    (KIT / "clips").mkdir(parents=True)
    (KIT / "panels").mkdir()

    rng = random.Random(SEED)
    shuffled = cells[:]
    rng.shuffle(shuffled)
    opaque = {cell: f"c{k+1:02d}" for k, cell in enumerate(shuffled)}

    for cell, oid in opaque.items():
        suffix = cell.rsplit("_", 1)[1]
        shutil.copy(ROOT / "runs" / ENGINE_DIR[suffix] / f"{cell}.mp4",
                    KIT / "clips" / f"{oid}.mp4")
        im = Image.open(panel_for(cell)).convert("RGB")
        im.thumbnail((900, 900))
        im.save(KIT / "panels" / f"{oid}.png", optimize=True)

    orders = {}
    for rater in RATERS:
        rr = random.Random(f"{SEED}:{rater}")
        order = sorted(opaque.values())
        rr.shuffle(order)
        orders[rater] = order
        (KIT / f"rating-{rater}.html").write_text(page_html(rater, order))

    (KIT / "README-FIRST.txt").write_text(
        "Open YOUR rating-<name>.html in any browser (keep it in this folder,\n"
        "next to clips/ and panels/). About 20 minutes, one sitting. Two\n"
        "questions per clip. At the end it saves a small ratings-<name>.json -\n"
        "please send that file back.\n")

    (HERE / "mapping.json").write_text(json.dumps({
        "built": "2026-08-15", "instrument": "A6", "seed": SEED,
        "subset": "analysis/out/human_subset.json (frozen §6 draw)",
        "opaque_to_cell": {v: k for k, v in opaque.items()},
        "rater_orders": orders,
        "order_seed_scheme": "random.Random(f'{SEED}:{rater}')",
    }, indent=1))

    zip_path = HERE / "stilldrawn-rating-kit.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(KIT.rglob("*")):
            if f.is_file():
                z.write(f, f"stilldrawn-rating-kit/{f.relative_to(KIT)}")
    print(f"kit  -> {KIT}")
    print(f"zip  -> {zip_path} ({zip_path.stat().st_size/1e6:.1f} MB)")
    print(f"private mapping -> {HERE/'mapping.json'} (do NOT ship)")


if __name__ == "__main__":
    main()
