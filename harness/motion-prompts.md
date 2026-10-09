# StillDrawn motion prompts — the four frozen motion classes

**Contract:** same parser as the panel pack (`harness/pack_parser.py`). One entry per
motion class; `gen_video.py --motion <SHOT>` resolves from THIS file only. These
prompts are part of the pre-registration (`docs/PREREGISTRATION.md`) — after the
freeze they change only by dated amendment, never edit. No per-run editing.

Design notes (recorded before freeze):
- Wording is engine-agnostic (works as the text prompt for Runway, Wan, LTX, and the
  hosted H3 API) and moderation-safe.
- Every entry carries the same style-lock sentence — the pilot study's establishing-shot
  failure suggested weak in-prompt style anchoring contributes to photoreal drift, so
  the lock rides on every class identically; the benchmark then measures what survives.
- Subject language is generic because panels vary; the motion class, not the subject,
  is the experimental variable.

---

**IDLE — idle / subtle motion**
> Subtle idle motion only: gentle breathing, faint sway of cloth or foliage, slight ambient drift. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

**BURST — action burst**
> The action implied by the drawing continues in one fast, committed burst of motion, then settles. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

**CAMPUSH — camera push-in**
> Slow, steady camera push-in toward the focal point of the drawing. No subject motion beyond minimal ambient drift. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

**FLINT — first-to-last interpolation** *(engines with first/last-frame conditioning only; recorded n/a elsewhere)*
> Animate the natural motion that carries the first drawing into the last drawing, as one continuous drawn movement. Camera locked off unless the two drawings imply a camera move. Both drawings are black-and-white inked artwork and every intermediate frame must remain one — line weight, screentone dots, and flat black ink shapes stay as drawn; no repainting, no photorealistic rendering, no colour.

---

## Changelog

- **v1 (2026-08-12):** four classes authored ahead of the pre-registration freeze.
