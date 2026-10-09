# Provider-terms notice

**This notice is informational. It does not add conditions to, or otherwise
modify, the CC BY 4.0 licence that covers the data in this release.**

Some items in StillDrawn were generated through commercial services. Their
providers' terms apply to the author's use of those services, and some of them
restrict using the services' outputs to build competing products. The author
releases these items for evaluation and research on image-to-video stability.
If you reuse them, it is your responsibility to check whether any provider's
terms bear on what you intend to do.

**Please do not use the items below to train, fine-tune or improve generative
image or video models.**

| Items | Service | Where to find them |
|---|---|---|
| 9 panels, plus the 5 ground-series variants derived from one of them (`cu-line-1`) | Google Gemini 2.5 Flash Image via the Runway API | `dataset/recipes/*.json` with `"engine": "hosted"`; `dataset/panels/ground-*` |
| 140 clips | Runway Gen-4 Turbo (69) and Gen-4.5 (71) | `runs/gen4_turbo/`, `runs/gen4.5/` |
| 148 clips | MiniMax H3 via fal.ai | `runs/h3-fal/` |
| 9 clips | Seedance 2.0 (ByteDance) via fal.ai | `runs/seedance/` |

The remaining 76 clips (`runs/wan22/`, `runs/ltx23/`) were generated locally
from open-weights models (Wan 2.2 under Apache-2.0; LTX-2.3 under the LTX-2
Community License). Of the remaining panels, 18 were generated locally with
Illustrious-XL v0.1 and 2 through the author's private production chain.

## Runway (panels and Runway clips)

Runway's Terms of Use §5 *User Conduct* say: "You shall not (and shall not
permit any third party to) either (a) take any action or (b) Make Available any
Content on or through the Services that: … (viii) directly or indirectly uses
the Services (including, but not limited to, Outputs) to create, train,
develop, or improve similar or competitive products or services." Runway does
not claim ownership of outputs (§4.4). The text of §4.4 and §5(viii) is identical in the version in
force when the items were generated (last updated 11 May 2026) and the current
version (last updated 15 September 2026). Both captures, with hashes, are in
`docs/tos-snapshots/SHA256SUMS`.

## fal.ai (MiniMax H3 and Seedance 2.0 items)

fal's Terms of Service §14.3 (last updated 8 September 2026; unchanged from the
31 July 2026 version in force at generation) say that a customer may not: "use
or access any Third-Party Materials or any outputs derived from such materials
to develop, modify, fine-tune, or improve any products or services that compete
with those Third Party Materials, including to develop, fine-tune, or train any
artificial intelligence or machine learning algorithms or models". Third-party
materials include machine-learning models hosted by third parties, such as these
two. fal does not assign ownership of outputs to the customer. The author
accessed both models through fal, under fal's terms. ByteDance's developer
terms (BytePlus Terms of Service, last updated 18 March 2024) do not address AI
outputs.

Neither provider's terms contain a clause on publishing evaluations or
benchmarks.

## Provenance marks, kept intact

- The 288 Runway and MiniMax clips carry C2PA Content Credentials signed by the
  service. They ship byte-exact: re-encoding or remuxing a clip breaks the
  signature's hash binding. Hashes are in `runs/CLIP-HASHES.csv`.
- The 9 Gemini panels carry a Google-signed C2PA manifest, Google's SynthID
  watermark and XMP/IPTC "AI-generated" metadata, all left in place (the files
  ship byte-exact).
- The 9 Seedance clips carry no embedded provenance metadata.
- Every item in this release is machine-generated and is labelled as such.

See `docs/TOS-REVIEW.md` for the full terms review.
