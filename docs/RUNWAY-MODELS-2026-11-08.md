# Runway API, image_to_video, as read from the public OpenAPI file on 8 Nov 2026

Source: https://docs.dev.runwayml.com/openapi.json, fetched on 8 Nov 2026; the rendered reference at
docs.dev.runwayml.com/api shows the same schema under its model selector. Read for amendments A10, A12,
A14 and A15. Prices are not in the file.

| model | required | ratio | duration | seed | audio |
|---|---|---|---|---|---|
| `gen4.5` | promptText, promptImage, ratio, duration, model | 1280:720, 720:1280, 1104:832, 960:960, 832:1104, 1584:672 | integer 2–10 | integer 0–4294967295, optional | none |
| `gen4_turbo` | promptImage, ratio, model | the same six | integer 2–10 | integer 0–4294967295, optional | none |
| `seedance2` | promptImage, model | 24 values incl. 1280:720 and 1920:1080 | seconds, or `auto` (billed at the variant maximum, then refunded) | integer 0–4294967295, optional | `audio` boolean, default true |
| `seedance2_5` | promptImage, model | 18 values incl. 1280:720 (480p, 720p, 1080p) | seconds or `auto` | integer, optional | `audio` boolean, default true |
| `kling_4` | promptImage, model | `auto_720p`, `auto_1080p` (both keep the framing of the input image) | integer 3–30 | none | none (audio is always generated) |
| `kling_4_flash` | promptImage, model | string | integer 3–20 | none | none |

Seed. Where a model takes one, the field is optional: leave it out and Runway picks a random number. The
file says only that the same seed on an otherwise identical request gives "similar results"; a seed on
Runway therefore fixes the request, not the bytes.

Images. For `seedance2`, `promptImage` takes one image or an array. Each image can carry a position
(`first` or `last`) for keyframe mode, or none, for reference images; the two modes cannot be mixed in one
request. For `kling_4`, `promptImage` is the first frame, or an array holding a first frame and optionally
middle and last frames.

Consequences for the study: A10.3.3 and A12.3.1 therefore say that Runway accepts a seed; A14 sends
`audio: false` rather than stripping a track afterwards; A15 records `auto_720p` and no seed; first-frame
and last-frame pairs are possible on both engines.
