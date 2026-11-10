# StillDrawn motion ladder — prompt pack v2 (amendment A10)

**Contract:** same parser as the frozen pack (`harness/pack_parser.py`): a `**<SHOT> — title**`
heading ending the line, then a `>` blockquote. `harness/ladder.py` resolves every ladder cell
from THIS file only, through `gen_video.py --pack harness/motion-ladder.md`. Frozen by amendment
A10, whose manifest hashes this file; after registration it changes only by a dated amendment,
never by an edit.

Design notes (written before registration, before any ladder clip):
- Four intensity levels of one manipulation: how much the subject is asked to move.
- STILL is the frozen IDLE prompt of `harness/motion-prompts.md`, word for word, so the ladder's
  lowest step is a bridge to the frozen corpus.
- LOW, MID and HIGH share one template and differ only in the words before "Camera locked off.":
  one fixed list of what moves, scaled on three slots only (amount, distance, pace). The camera
  sentence and the style-lock sentence are identical on all four levels and identical to the
  frozen pack's.
- The STILL to LOW step also changes the sentence template (STILL's "Subtle idle motion only: ..."
  against the shared ladder template), so monotone-trend claims rest mainly on LOW, MID and HIGH,
  with STILL as the bridge to the frozen corpus.
- Wording is engine-agnostic (Runway, Wan, LTX) and moderation-safe: no contact, no impact, no
  named subject, because the twelve panels vary.

---

**STILL — the frozen IDLE prompt, verbatim**
> Subtle idle motion only: gentle breathing, faint sway of cloth or foliage, slight ambient drift. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

**LOW — small, slow subject motion**
> Small, slow subject motion: the drawn subject and any loose elements (hair, cloth, foliage, water, smoke) move a little from where they are drawn, slowly. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

**MID — moderate, steady subject motion**
> Moderate, steady subject motion: the drawn subject and any loose elements (hair, cloth, foliage, water, smoke) move a clear distance from where they are drawn, at a steady pace. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

**HIGH — large, fast subject motion**
> Large, fast subject motion: the drawn subject and any loose elements (hair, cloth, foliage, water, smoke) move a long way from where they are drawn, quickly. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

---

## Changelog

- **v2 (drafted 2026-11-04; frozen when A10 is registered):** new pack beside v1, which is unchanged (harness/motion-prompts.md; sha256 4978eb9c… as frozen, 43a02298… in the release, whose title line carries the released name). STILL copies v1's IDLE verbatim; LOW, MID and HIGH are new, share one template and differ only before "Camera locked off."; the camera and style-lock sentences are v1's. BURST, CAMPUSH and FLINT are not carried. Wording revised at review on 4 Nov 2026: one fixed list of what moves, scaled on amount, distance and pace only.
