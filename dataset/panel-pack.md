# StillDrawn panel pack — the 27 neutral dataset panels

**Contract:** `**<SHOT> — title**` heading ending the line → `>` blockquote positive →
optional `**Negative:**` + `>` blockquote. Parsed by `harness/pack_parser.py`. Each panel
has TWO entries: `-H` (hosted prose dialect) and `-L` (local booru-tag dialect); the
recipe JSON records which one actually ran. These 27 prompts are the dataset's own
one-off recipes — they are authored for this benchmark and ship with it.

**Design (goes into the pre-registration):**
- Grid: 3 content classes (`cu` character close-up · `act` action/foreshortened ·
  `est` establishing environment) × 3 ink treatments (`line` line-only · `tone`
  screentone · `black` heavy blacks + one reserved white) × 3 panels.
- **Uniform frame 1344×768 landscape** (hosted `1344:768`), video later at `1280:720` —
  one geometry for every panel so I2V cropping never differs across cells.
- Engine mix: panel `-1` of each cell = hosted `gemini_2.5_flash` (prose); panels
  `-2`/`-3` = local Illustrious-XL (tags). No cell is single-engine.
- Subjects are original and neutral: no named properties, no franchise content, no
  real people. Character panels lock subject sex explicitly (known local-model drift).
- 1 reroll allowance per panel (seed+1000, `--force`, counted in the ledger row).

**Batch plan** (seed recorded here and in each recipe):

| panel id | engine | seed | subject |
|---|---|---|---|
| cu-line-1 | hosted | 1101 | elderly violinist backstage |
| cu-line-2 | local | 1102 | young welder, goggles up |
| cu-line-3 | local | 1103 | beekeeper in veil |
| cu-tone-1 | hosted | 1104 | night-shift nurse |
| cu-tone-2 | local | 1105 | boxer between rounds |
| cu-tone-3 | local | 1106 | elderly radio operator |
| cu-black-1 | hosted | 1107 | miner with headlamp |
| cu-black-2 | local | 1108 | actor in a single spotlight |
| cu-black-3 | local | 1109 | fishmonger under a hanging bulb |
| act-line-1 | hosted | 1110 | BMX rider jumping at camera |
| act-line-2 | local | 1111 | parkour vault, palm at camera |
| act-line-3 | local | 1112 | goalkeeper full-stretch dive |
| act-tone-1 | hosted | 1113 | skateboarder mid-ollie, low angle |
| act-tone-2 | local | 1114 | sprinter out of the blocks |
| act-tone-3 | local | 1115 | climber mid-dyno from below |
| act-black-1 | hosted | 1116 | firefighter in a backlit doorway |
| act-black-2 | local | 1117 | pitcher mid-throw, ball at camera |
| act-black-3 | local | 1118 | woodcutter's swing against low sun |
| est-line-1 | hosted | 1119 | lighthouse spiral stair |
| est-line-2 | local | 1120 | railway yard at dawn |
| est-line-3 | local | 1121 | Victorian glasshouse interior |
| est-tone-1 | hosted | 1122 | subway platform at night |
| est-tone-2 | local | 1123 | harbour at low tide |
| est-tone-3 | local | 1124 | terraced hillside village in rain |
| est-black-1 | hosted | 1125 | turbine hall, one light shaft |
| est-black-2 | local | 1126 | aircraft boneyard at dusk |
| est-black-3 | local | 1127 | night alley, one lit window |

---

## Character close-up × line-only

**CU-LINE-1H — elderly violinist, line-only (hosted prose)**
> Black-and-white inked comic panel, landscape frame. Close-up of an elderly violinist backstage, chin resting on her instrument, eyes closed, deep laugh lines. Drawn in clean unbroken pen contour only: every outline closed, uniform fine line weight, interiors left as bare white paper, no tone fields, no grey wash, no dot shading anywhere. Wide white negative space on the right of the frame. Monochrome ink on white. No lettering, no sound-effect marks.

**CU-LINE-1L — elderly violinist, line-only (local tags)**
> masterpiece, best quality, monochrome, greyscale, lineart, clean line art, (white background:1.3), 1girl, old woman, elderly, wrinkles, closed eyes, violin, holding instrument, close-up, portrait, backstage, simple background, negative space

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, halftone, gradient, grey wash, grey background, gradient background, ink drips, ink splatter, stains, 1boy, male

**CU-LINE-2H — young welder, line-only (hosted prose)**
> Inked black-and-white comic panel, landscape frame. Close-up of a young male welder, safety goggles pushed up into his hair, sweat-damp forehead, half-smile, workshop behind him suggested by a few contour strokes. Pure line drawing: wiry confident outlines, all contours closed, zero tone or shading — the modelling lives entirely in the drawing of the line, paper left white. Monochrome. No lettering.

**CU-LINE-2L — young welder, line-only (local tags)**
> masterpiece, best quality, monochrome, greyscale, lineart, clean line art, (white background:1.3), 1boy, male focus, adult, stubble, goggles on head, welder, work clothes, sweat, smile, close-up, portrait, workshop, simple background

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, halftone, gradient, grey wash, grey background, gradient background, ink drips, ink splatter, stains, 1girl, female, child

**CU-LINE-3H — beekeeper in veil, line-only (hosted prose)**
> Black-and-white inked comic panel, landscape frame. Close-up of a beekeeper, a woman seen through the fine mesh of her veil hat, calm direct gaze, one gloved hand raised with a single bee resting on the fingertip. Line-only ink drawing: the veil mesh rendered as delicate open crosshatch of single-weight lines, every contour closed, no tone fields, white paper ground. Monochrome. No lettering.

**CU-LINE-3L — beekeeper in veil, line-only (local tags)**
> masterpiece, best quality, monochrome, greyscale, lineart, clean line art, (white background:1.3), 1girl, female focus, beekeeper, veil, mesh, hat, gloves, bee on finger, looking at viewer, face visible, close-up, portrait, simple background

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, halftone, gradient, grey wash, grey background, gradient background, ink drips, ink splatter, stains, 1boy, male, covering face

## Character close-up × screentone

**CU-TONE-1H — night-shift nurse, screentone (hosted prose)**
> Black-and-white manga-style panel, landscape frame. Close-up of a night-shift nurse at a ward desk, tired eyes over a paper cup of coffee, fluorescent light from above. All shading carried by mechanical halftone dot fields: fine dots on the face's shadow side, coarser dots in the room behind, crisp ink line holding every edge above the tone. No grey wash — dots and line only. Monochrome. No lettering, no sound-effect marks.

**CU-TONE-1L — night-shift nurse, screentone (local tags)**
> masterpiece, best quality, monochrome, greyscale, screentone, halftone, manga style, ink, 1girl, female focus, nurse, tired, coffee cup, desk, fluorescent light, close-up, portrait, night

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, ink drips, ink splatter, stains on skin, 1boy, male

**CU-TONE-2H — boxer between rounds, screentone (hosted prose)**
> Inked manga-style panel, black and white, landscape frame. Close-up of a heavyweight boxer slumped on his corner stool between rounds, towel over his head, steam rising, one eye swelling. Screentone sheets do the modelling — dense dot tone in the towel's shadow, mid-grey dot fields on the skin, the crowd behind dissolved into a coarse tone texture. Line stays sharp over the dots. Monochrome. No lettering.

**CU-TONE-2L — boxer between rounds, screentone (local tags)**
> masterpiece, best quality, monochrome, greyscale, screentone, halftone, manga style, ink, 1boy, male focus, boxer, facing viewer, sitting on stool, boxing gloves, towel on head, sweat, bruise, exhausted, close-up, upper body

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, ink drips, ink splatter, blood, 1girl, female, from behind, back view

**CU-TONE-3H — elderly radio operator, screentone (hosted prose)**
> Black-and-white manga-style panel, landscape frame. Close-up of an elderly woman at a shortwave radio set, headphones on, hand on the tuning dial, dial-light glow suggested by an absence of tone around her glasses. Printed dot tone carries every value: fine tone on the face, medium tone on the cardigan, coarse tone in the dark room behind; the equipment's edges held by precise ink line. Monochrome, dots and line only. No lettering.

**CU-TONE-3L — elderly radio operator, screentone (local tags)**
> masterpiece, best quality, monochrome, greyscale, screentone, halftone, manga style, ink, 1girl, old woman, elderly, glasses, headphones, radio, tuning dial, cardigan, close-up, portrait, dark room

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, ink drips, ink splatter, stains, 1boy, male, young

## Character close-up × heavy blacks + reserved white

**CU-BLACK-1H — miner with headlamp, heavy blacks (hosted prose)**
> Black-and-white inked comic panel, landscape frame. Close-up of a coal miner underground, face turned toward the viewer. Pooled solid blacks swallow the tunnel and half his face in flat ink masses; the single pure-white region in the whole frame is the cone of his headlamp beam and the lit crescent of his cheek — every other surface carries black or deep tone. Confident heavy contour lines, no grey gradients. Monochrome. No lettering.

**CU-BLACK-1L — miner with headlamp, heavy blacks (local tags)**
> masterpiece, best quality, monochrome, greyscale, high contrast, ink, manga style, chiaroscuro, black background, 1boy, male focus, miner, hard hat, headlamp, light beam, coal dust, close-up, portrait, dramatic lighting, limited palette

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, gradient, grey wash, ink drips on skin, 1girl, female

**CU-BLACK-2H — actor in a spotlight, heavy blacks (hosted prose)**
> Inked black-and-white comic panel, landscape frame. Close-up of a stage actor mid-soliloquy, one arm raised. The theatre is flat solid black — a poured ink field with no detail in it; the only white in the frame is her spotlit face and raised hand, cut out of the dark by one hard-edged beam. Everything else that isn't black carries heavy tone. Bold closed contours, no soft gradients, no grey mist. Monochrome. No lettering.

**CU-BLACK-2L — actor in a spotlight, heavy blacks (local tags)**
> masterpiece, best quality, monochrome, greyscale, high contrast, ink, manga style, chiaroscuro, black background, spotlight, 1girl, female focus, actor, stage, raised arm, dramatic pose, close-up, upper body, dramatic lighting

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, gradient, grey wash, ink drips, stains, 1boy, male

**CU-BLACK-3H — fishmonger under a bulb, heavy blacks (hosted prose)**
> Black-and-white inked comic panel, landscape frame. Close-up of a fishmonger at his dawn market stall under a single hanging bulb. The market behind him is massed solid black, his apron and cap heavy flat ink; the one reserved white is the wet slab of fish under the bulb, gleaming. Black dominates the frame in hard-edged inked shapes; line weight thick and certain; no grey gradients anywhere. Monochrome. No lettering.

**CU-BLACK-3L — fishmonger under a bulb, heavy blacks (local tags)**
> masterpiece, best quality, monochrome, greyscale, high contrast, ink, manga style, chiaroscuro, dark background, 1boy, male focus, mature man, fishmonger, apron, flat cap, hanging light bulb, fish, market stall, close-up, upper body, dramatic lighting

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, gradient, grey wash, ink drips on skin, 1girl, female

## Action / foreshortened × line-only

**ACT-LINE-1H — BMX rider at camera, line-only (hosted prose)**
> Black-and-white inked comic panel, landscape frame. A BMX rider mid-jump coming straight at the viewer, front wheel huge in extreme foreshortening, body compressed behind the handlebars, dirt kicked loose below. Pure contour line drawing: speed lines as single strokes, all outlines closed, no tone, no dots, no wash — white paper carries all the light. Monochrome. No lettering, no sound-effect marks.

**ACT-LINE-1L — BMX rider at camera, line-only (local tags)**
> masterpiece, best quality, monochrome, greyscale, lineart, clean line art, (white background:1.3), 1boy, male focus, bmx, bicycle, jumping, foreshortening, perspective, front wheel, incoming attack, speed lines, dynamic pose, action, motion lines

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, halftone, gradient, grey wash, grey background, gradient background, ink drips, 1girl, female

**ACT-LINE-2H — parkour vault, line-only (hosted prose)**
> Inked black-and-white comic panel, landscape frame. A traceur vaulting a concrete barrier toward the viewer, leading palm slammed flat toward the camera in hard foreshortening, fingers spread and enormous, body whipping sideways behind it. Line-only ink: wiry single-weight contours, closed shapes, motion described by a handful of long clean stroke lines, nothing filled, nothing toned, white ground. Monochrome. No lettering.

**ACT-LINE-2L — parkour vault, line-only (local tags)**
> masterpiece, best quality, monochrome, greyscale, lineart, clean line art, (white background:1.3), 1boy, male focus, short hair, parkour, vault, outstretched arm, palm, foreshortening, perspective, spread fingers, dynamic pose, action, motion lines, concrete wall

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, halftone, gradient, grey wash, grey background, gradient background, ink drips, 1girl, female, long hair

**ACT-LINE-3H — goalkeeper dive, line-only (hosted prose)**
> Black-and-white inked comic panel, landscape frame. A goalkeeper at full horizontal stretch across the frame, gloved fingertips just reaching a ball in the top corner, boots leaving the ground, net drawn as a sparse open grid of single lines. Clean pen line only: every contour closed, uniform weight, no tone fields, no shading, white paper everywhere the line isn't. Monochrome. No lettering.

**ACT-LINE-3L — goalkeeper dive, line-only (local tags)**
> masterpiece, best quality, monochrome, greyscale, lineart, clean line art, (white background:1.3), 1boy, male focus, goalkeeper, diving, full stretch, gloves, soccer ball, soccer goal, grass field, horizontal, dynamic pose, action, motion lines, foreshortening

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, halftone, gradient, grey wash, grey background, gradient background, ink drips, 1girl, female, spider web

## Action / foreshortened × screentone

**ACT-TONE-1H — skateboarder ollie, screentone (hosted prose)**
> Black-and-white manga-style panel, landscape frame. A skateboarder mid-ollie shot from ground level, deck's grip-tape underside dominating the foreground in steep foreshortening, rider folded above it against the sky. Halftone dot fields carry all value: coarse tone on the deck's underside, fine tone in the sky gradient, dot-textured shadow pooling below; crisp ink line above the dots throughout. Monochrome, dots and line only. No lettering.

**ACT-TONE-1L — skateboarder ollie, screentone (local tags)**
> masterpiece, best quality, monochrome, greyscale, screentone, halftone, manga style, ink, 1boy, male focus, skateboard, ollie, from below, worm's eye view, foreshortening, perspective, jumping, dynamic pose, action, sky

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, ink drips, 1girl, female

**ACT-TONE-2H — sprinter from the blocks, screentone (hosted prose)**
> Inked manga-style panel, black and white, landscape frame. A sprinter exploding out of the starting blocks straight at the viewer, lead fist foreshortened huge, face tucked low behind it, track lanes converging behind her. Screentone does the modelling: dense dots in the deep shadow under her body, mid-tone on the track surface, a coarse tone band for the stadium blur; sharp closed ink contours over everything. Monochrome. No lettering.

**ACT-TONE-2L — sprinter from the blocks, screentone (local tags)**
> masterpiece, best quality, monochrome, greyscale, screentone, halftone, manga style, ink, 1girl, female focus, sprinter, starting blocks, running, clenched fist, foreshortening, perspective, incoming punch, track and field, dynamic pose, action, motion lines

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, ink drips, 1boy, male

**ACT-TONE-3H — climber mid-dyno, screentone (hosted prose)**
> Black-and-white manga-style panel, landscape frame. A rock climber mid-dyno seen from directly below: both hands leaving one hold, body arched across the frame toward the next, chalk dust hanging. The rock face is built from layered halftone: coarse dots in the overhang's shadow, fine dots across sunlit stone, the climber's silhouette held by hard ink line over the tone. Monochrome, dots and line only. No lettering.

**ACT-TONE-3L — climber mid-dyno, screentone (local tags)**
> masterpiece, best quality, monochrome, greyscale, screentone, halftone, manga style, ink, 1boy, male focus, full body, rock climbing, dyno, jumping, from below, worm's eye view, foreshortening, reaching, chalk dust, cliff, overhang, dynamic pose, action

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, ink drips, 1girl, female, close-up, abstract

## Action / foreshortened × heavy blacks + reserved white

**ACT-BLACK-1H — firefighter in the doorway, heavy blacks (hosted prose)**
> Black-and-white inked comic panel, landscape frame. A firefighter swinging an axe through a door, seen from inside the dark room: his silhouette and the room are massed solid black ink, flat and hard-edged; the single reserved white is the blinding glare of the doorway bursting around him. Foreshortened axe-head leading. No gradients, no grey — black shapes, white shape, heavy closed line. Full-bleed composition: the drawing fills the entire frame edge to edge, no borders, no margins, no panel frame. Monochrome. No lettering.

**ACT-BLACK-1L — firefighter in the doorway, heavy blacks (local tags)**
> masterpiece, best quality, monochrome, greyscale, high contrast, ink, manga style, silhouette, backlighting, 1boy, male focus, firefighter, axe, swinging, doorway, breaking door, foreshortening, dynamic pose, action, dramatic lighting, black background

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, gradient, grey wash, 1girl, female

**ACT-BLACK-2H — pitcher mid-throw, heavy blacks (hosted prose)**
> Inked black-and-white comic panel, landscape frame. A baseball pitcher at full release under night-game lights, ball foreshortened huge an instant from the camera. The stadium night is flat poured black; the pitcher is carved from it in heavy ink masses; the one pure-white shape in the frame is the ball and the streak of its seam-spin. Hard closed contours, no gradients, no dots. Monochrome. No lettering.

**ACT-BLACK-2L — pitcher mid-throw, heavy blacks (local tags)**
> masterpiece, best quality, monochrome, greyscale, high contrast, ink, manga style, chiaroscuro, black background, 1boy, male focus, baseball, pitcher, throwing, ball, foreshortening, incoming attack, perspective, night, dynamic pose, action, dramatic lighting

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, gradient, grey wash, 1girl, female

**ACT-BLACK-3H — woodcutter's swing, heavy blacks (hosted prose)**
> Black-and-white inked comic panel, landscape frame. A woodcutter mid-swing at dusk, axe arcing over his shoulder, seen low and close so the blade foreshortens across the frame. The treeline and his body are flat solid black masses; the reserved white is the low sun's disc on the horizon and the bright edge it puts on the axe blade. Everything else carries black or heavy tone. Bold certain line, no gradients. Monochrome. No lettering.

**ACT-BLACK-3L — woodcutter's swing, heavy blacks (local tags)**
> masterpiece, best quality, monochrome, greyscale, high contrast, ink, manga style, silhouette, backlighting, 1boy, male focus, lumberjack, axe, swinging, overhead swing, foreshortening, sunset, sun, treeline, dynamic pose, action, dramatic lighting

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, gradient, grey wash, 1girl, female

## Establishing environment × line-only

**EST-LINE-1H — lighthouse spiral stair, line-only (hosted prose)**
> Black-and-white inked comic panel, landscape frame. Interior of a lighthouse: the spiral stair winding up and away from the viewer, iron railings, stone courses, a small window throwing a parallelogram of light on the steps. Pure line drawing — architecture described entirely by closed single-weight contours and sparse open hatching, no tone fields, no wash, white paper ground. Empty of people. Monochrome. No lettering.

**EST-LINE-1L — lighthouse spiral stair, line-only (local tags)**
> masterpiece, best quality, monochrome, greyscale, lineart, clean line art, (white background:1.3), no humans, scenery, indoors, lighthouse, spiral staircase, stone wall, iron railing, window, architecture, perspective, vanishing point

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, halftone, gradient, grey wash, grey background, gradient background, 1boy, 1girl, people, crowd

**EST-LINE-2H — railway yard at dawn, line-only (hosted prose)**
> Inked black-and-white comic panel, landscape frame. A railway marshalling yard at dawn: rails converging to the horizon, points and signal gantries, a line of idle freight wagons, catenary wires ruling the sky. Line-only ink drawing — every rail a clean unbroken stroke, wagons in closed contour, no tone anywhere, the dawn sky left as bare white paper. Empty of people. Monochrome. No lettering.

**EST-LINE-2L — railway yard at dawn, line-only (local tags)**
> masterpiece, best quality, monochrome, greyscale, lineart, clean line art, (white background:1.3), no humans, scenery, outdoors, railroad tracks, train yard, freight car, power lines, signal, vanishing point, perspective, dawn, wide shot

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, halftone, gradient, grey wash, grey background, gradient background, 1boy, 1girl, people, crowd

**EST-LINE-3H — Victorian glasshouse, line-only (hosted prose)**
> Black-and-white inked comic panel, landscape frame. Interior of a Victorian glasshouse: curved iron ribs and glazing bars arching overhead, palms and ferns crowding a central path, condensation traced on a few panes. Drawn in line only — the iron structure in confident closed contours, foliage as layered open linework, no tone fields, no grey, white ground throughout. Empty of people. Monochrome. No lettering.

**EST-LINE-3L — Victorian glasshouse, line-only (local tags)**
> masterpiece, best quality, monochrome, greyscale, lineart, clean line art, (white background:1.3), no humans, scenery, indoors, greenhouse, glass ceiling, iron framework, arches, palm tree, ferns, path, architecture, perspective

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, halftone, gradient, grey wash, grey background, gradient background, 1boy, 1girl, people, crowd

## Establishing environment × screentone

**EST-TONE-1H — subway platform at night, screentone (hosted prose)**
> Black-and-white manga-style panel, landscape frame. An empty subway platform at night: tiled walls, a bench, the tunnel mouth swallowing the tracks, strip lights overhead. Every value carried by halftone dot tone — fine dots on lit tile, mid dots across the platform floor, coarse heavy dots deepening into the tunnel; edges held crisp by ink line above the tone. No people. Monochrome, dots and line only. No lettering.

**EST-TONE-1L — subway platform at night, screentone (local tags)**
> masterpiece, best quality, monochrome, greyscale, screentone, halftone, manga style, ink, no humans, scenery, indoors, subway station, train platform, tiles, bench, tunnel, fluorescent lights, night, perspective, empty

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, 1boy, 1girl, people, crowd, train

**EST-TONE-2H — harbour at low tide, screentone (hosted prose)**
> Inked manga-style panel, black and white, landscape frame. A small fishing harbour at low tide: trawlers heeled over on wet mud, mooring chains slack, a stone quay running out of frame, gulls as sparse marks. Screentone builds the scene — coarse dot fields for the mud flats, finer tone banding the overcast sky, dense dots under each hull's shadow; hard ink line over every edge. No people. Monochrome. No lettering.

**EST-TONE-2L — harbour at low tide, screentone (local tags)**
> masterpiece, best quality, monochrome, greyscale, screentone, halftone, manga style, ink, no humans, scenery, outdoors, harbor, fishing boat, low tide, mudflat, mooring chain, stone quay, seagulls, overcast, wide shot

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, 1boy, 1girl, people, crowd

**EST-TONE-3H — terraced village in rain, screentone (hosted prose)**
> Black-and-white manga-style panel, landscape frame. A terraced hillside village in steady rain: stacked tiled roofs stepping down the slope, narrow stairs between houses, rain ruled as fine parallel strokes across everything. Halftone dot tone carries the values — layered tone fields separating each terrace plane, coarse dots in the ravine below, pale tone in the rain-white sky; ink line stays sharp beneath the rain strokes. No people. Monochrome. No lettering.

**EST-TONE-3L — terraced village in rain, screentone (local tags)**
> masterpiece, best quality, monochrome, greyscale, screentone, halftone, manga style, ink, no humans, scenery, outdoors, village, hillside, terraced, tiled roofs, stairs, rain, rain streaks, mist, wide shot, depth

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, 1boy, 1girl, people, crowd, umbrella

## Establishing environment × heavy blacks + reserved white

**EST-BLACK-1H — turbine hall light shaft, heavy blacks (hosted prose)**
> Black-and-white inked comic panel, landscape frame. A vast disused turbine hall: the great machines and the roof trusses massed in flat solid black ink, floor grime in heavy tone; one tall shaft of light from a broken roof panel is the single pure-white region in the frame, cutting down onto the floor. Hard-edged ink shapes, no gradients, no mist. Empty of people. Monochrome. No lettering.

**EST-BLACK-1L — turbine hall light shaft, heavy blacks (local tags)**
> masterpiece, best quality, monochrome, greyscale, high contrast, ink, manga style, chiaroscuro, black background, no humans, scenery, indoors, industrial, turbine, machinery, abandoned, roof truss, light shaft, light beam, dust, dramatic lighting

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, gradient, grey wash, 1boy, 1girl, people

**EST-BLACK-2H — aircraft boneyard at dusk, heavy blacks (hosted prose)**
> Inked black-and-white comic panel, landscape frame. An aircraft boneyard at dusk: rows of retired airliners nose-to-tail, engines cowled, all of it silhouetted in flat solid black against the last of the light. The reserved white is the thin bright band of sky along the horizon; everything above it carries deep tone, everything below is black mass and heavy line. No gradients. Empty of people. Monochrome. No lettering.

**EST-BLACK-2L — aircraft boneyard at dusk, heavy blacks (local tags)**
> masterpiece, best quality, monochrome, greyscale, high contrast, ink, manga style, silhouette, backlighting, no humans, scenery, outdoors, airplane, aircraft graveyard, rows, dusk, horizon, sky band, dramatic lighting, wide shot

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, gradient, grey wash, 1boy, 1girl, people

**EST-BLACK-3H — night alley, one window, heavy blacks (hosted prose)**
> Black-and-white inked comic panel, landscape frame. A narrow brick alley at night, walls leaning close, fire escapes overhead, puddles in the cobbles. The alley is flooded with flat black ink — buildings, stairs, sky, all one poured dark mass with heavy contour holding the shapes; the single reserved white is one lit window high on the right wall and its broken reflection in a puddle. No grey gradients. Empty of people. Monochrome. No lettering.

**EST-BLACK-3L — night alley, one window, heavy blacks (local tags)**
> masterpiece, best quality, monochrome, greyscale, high contrast, ink, manga style, chiaroscuro, black background, no humans, scenery, outdoors, alley, brick wall, fire escape, night, lit window, puddle, reflection, cobblestone, dramatic lighting

**Negative:**
> color, blurry, worst quality, lowres, text, watermark, signature, speech bubble, sound effects, screentone, gradient, grey wash, 1boy, 1girl, people

---

## Changelog

- **v2 (2026-08-12, applies FINDINGS R2):** value-ceiling fix on all local line-only
  entries (`(white background:1.3)` + `grey background, gradient background` negatives);
  subject anchors: cu-line-2 `adult, stubble`/−`child`; cu-line-3 `face visible`/−`covering
  face`; cu-tone-2 `facing viewer, sitting on stool`/−`from behind, back view`; act-line-2
  `short hair`/−`long hair`; act-line-3 `soccer goal, grass field` replaces `goal net`,
  −`spider web`; act-tone-3 `full body`/−`close-up, abstract`; ACT-BLACK-1H gains the
  explicit full-bleed sentence. Reroll round: seeds +1000, one reroll per affected panel.
- **v1 (2026-08-12):** 27 panels authored, two dialects each. Anti-leak negatives on all
  local character entries (`ink drips` family — the bare `ink` tag is known to leak as
  subject matter); explicit sex locks on all character entries; `no humans` + people
  negatives on all establishing entries. Uniform 1344×768 frame decision recorded above.
