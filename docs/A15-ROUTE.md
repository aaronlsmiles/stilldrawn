# A15 route check: `kling_4` through Runway's API (A15.3.5)

The operator's own record of the check A15.3.5 registers. It was made on 2026-11-11 (UTC), after
registration and before the scout's first submission.

## Pages checked

Runway's public developer documentation, captured on 2026-11-11 (UTC). The captured pages are
third-party text and are kept privately; only their hashes are given here.

| Page | URL | sha256 of the captured file |
|---|---|---|
| Models guide | `https://docs.dev.runwayml.com/guides/models/` | `f2cc65c1b71929d65ca091703877c81d1e4e4e663679651748a1602c721e33a2` |
| Pricing guide | `https://docs.dev.runwayml.com/guides/pricing/` | `2d0882507b4397cde69979b32b6e85f58ccb15f95e55450724d59fc3f03a691c` |
| API schema | `https://docs.dev.runwayml.com/openapi.json` | `9be166e96b075256fab17998dc14ab0e07c6a2c233c1bf7dc9231f710b4e63e6` |

The API schema is byte-identical to the copy captured on 2026-11-10 for A14's route check. The
two guides differ from that day's copies only in rows for image models this study does not use.

## Fields read

- API schema, the request body of `/v1/image_to_video` for the model id `kling_4`: the list of
  its fields, the values `ratio` accepts, the type and range of `duration`, and what
  `promptImage` accepts.
- Models guide, the table of models: for the row whose model id is `kling_4`, its name, its
  provider, its release date and its one-line summary; and the neighbouring Kling 4 row.
- Pricing guide: the credit rate listed for `kling_4` at 720p without an input video, the end
  date of the promotion, the list price, and the rounding rule with its worked example.

## What the documentation names

- The model id `kling_4` is listed as Kling 4.0, provider Kling, released 2026-10-23, and the
  schema offers it on `/v1/image_to_video`.
- `ratio` accepts `auto_720p` and `auto_1080p`, and no other value.
- `duration` is a whole number of seconds from 3 to 30, so 5 s is within it.
- `promptImage` takes a first frame, or a list holding a first frame with an optional middle
  and last frame. The scout's FLINT cells send a first and a last frame, and its BURST cells a
  first frame only (A15.3.1).
- The request has no seed field and no audio field. The pricing guide says the model's output
  always carries audio, with no switch (A15.3.3, A15.3.4).
- It is listed apart from Kling 4.0 Flash (`kling_4_flash`), which has its own model id. No
  other Kling model is sent at any point (A15.3.5).
- Credit rate read the same day: `kling_4` at 720p without an input video, 12.56 credits a
  second under a promotion that runs to 2026-11-30 UTC, and 15.7 credits a second at list: the
  rates A15.9 states.
- The pricing guide rounds each charge up to a whole credit, and gives 64 credits for a 5 s
  clip at 720p under the promotion. A15.9's estimate multiplies the unrounded rate (62.8 credits
  a clip), so the scout's six clips are expected to cost 384 credits, not 377. The ledger row
  carries the rounded figure.

## Verdict

**offered.** 5 s at `auto_720p` is offered for `kling_4` on `/v1/image_to_video` (A15.3.5). The
verdict is about what the documentation offers on the day: it does not show which model weights
Runway's route serves.
