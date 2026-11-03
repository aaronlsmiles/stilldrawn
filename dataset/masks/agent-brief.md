# Brief: where may each drawing move?

You have been given one folder. It holds this brief, 20 drawings named `<panel>.png`, and for each drawing a copy with a coordinate grid drawn over it, named `<panel>.grid.png`. Read only these files, and nothing outside the folder.

Below are 22 rows. Each row pairs one drawing with a motion prompt written for it. For every row, outline the regions of the drawing that the marking rule allows to move for the row's kind of motion.

## The marking rule

Idle marks bodies (breathing), hair, cloth, foliage, smoke, water, cloud and particles. Burst marks the actor, its plausible path, whatever it strikes or sheds, and anything attached to it. Never rigid structure, ground, lettering or the camera. When unsure, leave it unmarked.

The rule decides what may be marked. The motion prompt only tells you which kind of motion the row asks for (idle or burst); its wording does not widen the rule.

Each row's motion is `idle` or `burst`. The rule's sentence for that motion applies to the row; its last two sentences ("Never rigid structure…" and "When unsure…") apply to every row. If nothing in a drawing may move under the rule, give the row the status `nothing-allowed` and no polygons.

## Coordinates

Give every point as `[x, y]` in fractions of the drawing's width and height: `[0, 0]` is the top-left corner and `[1, 1]` the bottom-right; x grows to the right and y downwards. The grid copy has a thin line every 0.05 and a thicker, labelled line every 0.1 in both directions; no line is drawn along the edges at 0 and 1. The labels 0.1 to 0.9 sit on small white boxes: those for x run along the top edge, each just right of its own line, and those for y run down the left edge, each just below its own line; a single "0" marks the top-left corner. Read positions off the grid. The grid is only a ruler; the plain copy shows the drawing unobstructed.

Each polygon is a closed outline of at least 3 points that does not cross itself: list the points in order around the outline; do not repeat the first point at the end. Use as many polygons in a row as its regions need; they may overlap. Every coordinate lies between 0 and 1 inclusive; up to 4 decimal places is enough.

## Output

Reply with exactly one JSON document and nothing else: no text before or after it and no code fence. It has exactly two top-level keys, `notes` and `rows`, and `rows` holds all 22 rows, each keyed by its row id: the text of the row's heading exactly, such as `act-black-2_idle`. The example below shows the shape only; `<row id>`, `x` and `y` are placeholders, so it is not literal JSON to copy:

{
 "notes": "<anything a reader should know, such as an image you could not read; an empty string if nothing>",
 "rows": {
  "<row id>": {"status": "drawn", "allowed": [[[x, y], [x, y], [x, y]], [[x, y], [x, y], [x, y], [x, y]]]},
  "<row id>": {"status": "nothing-allowed", "allowed": []}
 }
}

Each row has exactly two keys. `status` is `drawn` when `allowed` holds at least one polygon, and `nothing-allowed` when `allowed` is empty. If you cannot read a drawing, still include its row with status `nothing-allowed` and an empty `allowed`, and say which in `notes`.

## The 22 rows

### act-black-2_idle

- drawing: `act-black-2.png`, grid copy `act-black-2.grid.png`; 1344 × 768 px
- motion: idle
- prompt: Subtle idle motion only: gentle breathing, faint sway of cloth or foliage, slight ambient drift. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### act-black-3_burst

- drawing: `act-black-3.png`, grid copy `act-black-3.grid.png`; 1344 × 768 px
- motion: burst
- prompt: The action implied by the drawing continues in one fast, committed burst of motion, then settles. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### act-line-1_idle

- drawing: `act-line-1.png`, grid copy `act-line-1.grid.png`; 1344 × 768 px
- motion: idle
- prompt: Subtle idle motion only: gentle breathing, faint sway of cloth or foliage, slight ambient drift. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### act-line-2_burst

- drawing: `act-line-2.png`, grid copy `act-line-2.grid.png`; 1344 × 768 px
- motion: burst
- prompt: The action implied by the drawing continues in one fast, committed burst of motion, then settles. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### act-tone-1_burst

- drawing: `act-tone-1.png`, grid copy `act-tone-1.grid.png`; 1344 × 768 px
- motion: burst
- prompt: The action implied by the drawing continues in one fast, committed burst of motion, then settles. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### act-tone-3_idle

- drawing: `act-tone-3.png`, grid copy `act-tone-3.grid.png`; 1344 × 768 px
- motion: idle
- prompt: Subtle idle motion only: gentle breathing, faint sway of cloth or foliage, slight ambient drift. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### chain-est-cosmic-1_burst

- drawing: `chain-est-cosmic-1.png`, grid copy `chain-est-cosmic-1.grid.png`; 1344 × 768 px
- motion: burst
- prompt: The action implied by the drawing continues in one fast, committed burst of motion, then settles. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### chain-est-cosmic-1_idle

- drawing: `chain-est-cosmic-1.png`, grid copy `chain-est-cosmic-1.grid.png`; 1344 × 768 px
- motion: idle
- prompt: Subtle idle motion only: gentle breathing, faint sway of cloth or foliage, slight ambient drift. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### cip-act-tank-1_burst

- drawing: `cip-act-tank-1.png`, grid copy `cip-act-tank-1.grid.png`; 1024 × 1792 px
- motion: burst
- prompt: The action implied by the drawing continues in one fast, committed burst of motion, then settles. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### cip-act-tank-1_idle

- drawing: `cip-act-tank-1.png`, grid copy `cip-act-tank-1.grid.png`; 1024 × 1792 px
- motion: idle
- prompt: Subtle idle motion only: gentle breathing, faint sway of cloth or foliage, slight ambient drift. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### cu-black-2_idle

- drawing: `cu-black-2.png`, grid copy `cu-black-2.grid.png`; 1344 × 768 px
- motion: idle
- prompt: Subtle idle motion only: gentle breathing, faint sway of cloth or foliage, slight ambient drift. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### cu-black-3_burst

- drawing: `cu-black-3.png`, grid copy `cu-black-3.grid.png`; 1344 × 768 px
- motion: burst
- prompt: The action implied by the drawing continues in one fast, committed burst of motion, then settles. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### cu-line-1_idle

- drawing: `cu-line-1.png`, grid copy `cu-line-1.grid.png`; 1344 × 768 px
- motion: idle
- prompt: Subtle idle motion only: gentle breathing, faint sway of cloth or foliage, slight ambient drift. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### cu-line-2_burst

- drawing: `cu-line-2.png`, grid copy `cu-line-2.grid.png`; 1344 × 768 px
- motion: burst
- prompt: The action implied by the drawing continues in one fast, committed burst of motion, then settles. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### cu-tone-1_burst

- drawing: `cu-tone-1.png`, grid copy `cu-tone-1.grid.png`; 1344 × 768 px
- motion: burst
- prompt: The action implied by the drawing continues in one fast, committed burst of motion, then settles. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### cu-tone-3_idle

- drawing: `cu-tone-3.png`, grid copy `cu-tone-3.grid.png`; 1344 × 768 px
- motion: idle
- prompt: Subtle idle motion only: gentle breathing, faint sway of cloth or foliage, slight ambient drift. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### est-black-2_idle

- drawing: `est-black-2.png`, grid copy `est-black-2.grid.png`; 1344 × 768 px
- motion: idle
- prompt: Subtle idle motion only: gentle breathing, faint sway of cloth or foliage, slight ambient drift. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### est-black-3_burst

- drawing: `est-black-3.png`, grid copy `est-black-3.grid.png`; 1344 × 768 px
- motion: burst
- prompt: The action implied by the drawing continues in one fast, committed burst of motion, then settles. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### est-line-1_idle

- drawing: `est-line-1.png`, grid copy `est-line-1.grid.png`; 1344 × 768 px
- motion: idle
- prompt: Subtle idle motion only: gentle breathing, faint sway of cloth or foliage, slight ambient drift. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### est-line-2_burst

- drawing: `est-line-2.png`, grid copy `est-line-2.grid.png`; 1344 × 768 px
- motion: burst
- prompt: The action implied by the drawing continues in one fast, committed burst of motion, then settles. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### est-tone-1_burst

- drawing: `est-tone-1.png`, grid copy `est-tone-1.grid.png`; 1344 × 768 px
- motion: burst
- prompt: The action implied by the drawing continues in one fast, committed burst of motion, then settles. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.

### est-tone-3_idle

- drawing: `est-tone-3.png`, grid copy `est-tone-3.grid.png`; 1344 × 768 px
- motion: idle
- prompt: Subtle idle motion only: gentle breathing, faint sway of cloth or foliage, slight ambient drift. Camera locked off. The image is a black-and-white inked drawing and must remain one in every frame — line weight, screentone dots, and flat black ink shapes stay exactly as drawn; no repainting, no photorealistic rendering, no colour, no added lighting effects.
