# A14 route check: `seedance2` through Runway's API (A14.3.3)

The operator's own record of the check A14.3.3 registers. It was made on 2026-11-10 (UTC), after
registration and before the first A14 submission.

## Pages checked

Runway's public developer documentation, captured on 2026-11-10. The captured pages are
third-party text and are kept privately; only their hashes are given here.

| Page | URL | sha256 of the captured file |
|---|---|---|
| Models guide | `https://docs.dev.runwayml.com/guides/models/` | `e9e7eb90b8740040f906c4ca4ba7074eee6cc85b3ce63207a73953e3ae866e36` |
| Pricing guide | `https://docs.dev.runwayml.com/guides/pricing/` | `48a6e8dea102496030c50687e0db3396580abf17245a8fd8d675a4d4c99d8f2d` |
| API schema | `https://docs.dev.runwayml.com/openapi.json` | `9be166e96b075256fab17998dc14ab0e07c6a2c233c1bf7dc9231f710b4e63e6` |

## Fields read

- Models guide, the table of models: for the row whose model id is `seedance2`, its name, its
  provider and its release date; and the ids and names of the neighbouring Seedance rows.
- Pricing guide: the credit rate listed for `seedance2` at 720p.
- API schema: the model ids offered on `/v1/image_to_video`.

## What the documentation names

- The model id `seedance2` is listed as Seedance 2.0, provider ByteDance, released 2026-05-28.
- It is listed apart from three other Seedance entries, each with its own model id: Seedance 2.0
  Fast (`seedance2_fast`), Seedance 2.0 Mini (`seedance2_mini`, which the guide calls the most
  cost-efficient Seedance 2.0 tier) and Seedance 2.5 (`seedance2_5`). The schema offers all four
  ids on `/v1/image_to_video`.
- So `seedance2` is version 2.0 at its standard tier: not the fast tier, not the mini tier, and
  not a later version.
- Credit rate read the same day: `seedance2` at 720p, 30 credits a second, the rate A14.8 states.

## Verdict

**match.** The documentation names ByteDance's Seedance 2.0 at its standard tier (A14.3.3). A
match means only that no difference is documented: it does not show that Runway's route and the
route used in August 2026 (fal, `bytedance/seedance-2.0/image-to-video`, standard tier, 720p)
serve the same model.
