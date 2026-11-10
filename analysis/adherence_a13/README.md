# Adherence at power (amendment A13)

A9's two blind rating studies ask whether each clip did the motion its prompt asked for (`analysis/adherence/`). A13 asks the same question of new, paid raters, enough of them to test the clip-level claim A9 found without a verdict: on the same drawing, the clips that drift more are the ones that do the motion more. Amendment A13 in `docs/PREREGISTRATION.md` registers the design and the analysis (`analysis/a13_adherence.py`).

| File | What it is |
|---|---|
| `build_a13.py` | Writes the two studies from A9's frozen instrument, links A9's rating copies, writes `mapping.json`, checks the builds |
| `test_build_a13.py` | Its tests |
| `burst/`, `push/` | `study.yaml` (A9's study with new seeds and two repeats), `study.lock.json` (must equal A9's), `banned-terms.txt`, `media-sources.json` (A9's, unchanged) |
| `mapping.json` | Each study's codes, its two repeats and the attention rule |
| `build-trees.json` | The hash of each built study; the rating app serves exactly these builds |
| `instrument.sha256` | Hashes of the rating app's A13 pages, orders and vendored kit |
| `served.sha256` | Hashes of every study file the rating app serves (its copy of the two builds, less the kit's own `index.html` and `reveal.json`) |
| `ratings/ratings-R<n>.json` | One rater's scores per study, under an opaque slot. The release ships the scores and the attention answers only, sorted by code |

The wording is A9's: the question, the labels, the notes, the intro and the titles are imported from `analysis/adherence/prepare.py`, and each study's wording hash equals A9's. What changes: new blinding seeds, so every code is new; two clips per study shown a second time at positions 30 and 52 of 57, as attention checks; one sitting on Prolific with a break between the studies, through the hosted study, not at the author's computer.

Not released: the rating copies (`burst/media/`, `push/media/`, links to A9's) and the builds (`.build/`).
