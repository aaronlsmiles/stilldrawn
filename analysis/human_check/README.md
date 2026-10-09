# Human check

The pre-registered human check behind the paper's human-check section: six
raters, 20 clips drawn from the manifest by a fixed seed, two questions per
clip, and a per-panel baseline question asked before any clip.

| File | Contents |
|---|---|
| `instrument/R2.html`…`R6.html` | The hosted instrument as the five recruited raters used it: one rating page per rater slot, with the questions, scale labels and guidance (clip order differs per rater, by a fixed seed). The authentication gate and submission endpoint they posted to are not included. The question wording is also frozen verbatim in `docs/PREREGISTRATION.md` (amendments A6 and A8). The author rated earlier, on the offline kit (A6): its question wording is identical, but the register question's bottom label and its guidance note were revised after the author's pass (A6 addendum 4 and A8), before any recruited rating. The author gave the A8 baseline through a separate offline page. |
| `mapping.json` | Opaque clip code (`c01`…`c20`) → cell id |
| `baseline_mapping.json` | Opaque panel code (`p01`…`p14`) → panel id, clip → panel, and each rater's baseline order |
| `ratings/ratings-<code>.json` | Each rater's scores: the register and sameness score for each clip, and the baseline score for each panel. Rater codes are opaque slots (`AARON` is the author's own). |
| `ratings_aggregate.csv` | Per clip: number of raters, mean, SD and median for the *register* and *sameness* questions |
| `baseline_aggregate.csv` | Per panel: baseline "does this still image look hand-drawn?" mean and SD, over all raters and excluding the author |
| `human_check_results.json` | Krippendorff's ordinal α per question and the Spearman correlation of each metric with the mean rating, with bootstrap CIs |
| `collect.py` | The script that produced `human_check_results.json` from `ratings/`. Run it from the repository root; it reproduces the shipped file exactly (the build verifies this). |
| `build_harness.py` | The script that built the instrument pages from the frozen question text |

**Privacy.** Raters took part knowing the results would be published, through
opaque rater slots: no names or contact details were collected at any point
(amendment A7). The scores are released under those slots. The original rating
files also recorded the time of each answer, how long each clip was watched
and optional free-text comments; those are not needed to check the paper's
claims and are withheld, since exact times of day are the one thing that could
point to an individual rater.
