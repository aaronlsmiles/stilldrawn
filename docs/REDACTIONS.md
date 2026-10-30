# Redactions in the public release

Frozen and historical documents ship verbatim except for the changes below.
Each removes private operational detail (hosting accounts, project
identifiers, an unreleased project's name or private paths) or brings a
checklist up to date; none alters protocol content.

## Commitments to the originals

Each changed file's unchanged original is committed to with HMAC-SHA256 under
a key the author holds privately. Revealing the key and the original later
proves the original was fixed at release; the value on its own cannot be
used to test a guess about the removed text. The same scheme covers the
original panel and clip files in `dataset/PANEL-HASHES.csv` and
`runs/CLIP-HASHES.csv`.

- `dataset/recipes/chain-est-cosmic-1.json` — `d0375adcf9067755b7be32cc8d6a4f682a5d47afe78c647697ef73fd66046d77`
- `dataset/recipes/cip-act-tank-1.json` — `543c57fe468f9b34f3c52bc722590c5e3c7526dc05c04d89ab6ed857a2ee313f`
- `docs/PREREGISTRATION.md` — `9ae7c5817e4c833257ca50e94410cb9a458252870d7b3a45c181ff151040ab29`
- `docs/TAXONOMY.md` — `ec5899a4039a25c0dc94ec859150f5f1e4801b33852db727d4fff66576934003`
- `docs/TOS-REVIEW.md` — `67e55da4906ad25b20739f042d95ce623c3a28584dbb9d3178547b141987d795`

## Changes

| File | Kind | What |
|---|---|---|
| `dataset/recipes/chain-est-cosmic-1.json` | wording | private-project phrasing replaced with neutral wording |
| `dataset/recipes/cip-act-tank-1.json` | wording | private-project phrasing replaced with neutral wording |
| `docs/PREREGISTRATION.md` | inline | a private name, path or pointer replaced with a neutral phrase |
| `docs/PREREGISTRATION.md` | inline | a private name, path or pointer replaced with a neutral phrase |
| `docs/PREREGISTRATION.md` | inline | a private name, path or pointer replaced with a neutral phrase |
| `docs/PREREGISTRATION.md` | block | 70 lines (A7 hosting-account passage) |
| `docs/TAXONOMY.md` | inline | a private name, path or pointer replaced with a neutral phrase |
| `docs/TAXONOMY.md` | wording | private-project phrasing replaced with neutral wording |
| `docs/TOS-REVIEW.md` | status | open-items checklist updated to its status at release |
| `docs/TOS-REVIEW.md` | status | open-items checklist updated to its status at release |
| `docs/TOS-REVIEW.md` | status | open-items checklist updated to its status at release |
| `docs/TOS-REVIEW.md` | status | open-items checklist updated to its status at release |
| `docs/TOS-REVIEW.md` | inline | a private name, path or pointer replaced with a neutral phrase |

Identifier change (all files): the creator-IP panel's id now reads `cip-act-tank-1` (`cip` = creator-IP).

## Referenced but not released

The released records refer in places to the author's private working files,
which are not part of the release: the findings log (`FINDINGS.md`, rounds
R1–R14, also named in the frozen metric definitions), the session kickoff
notes (`NEXT-KICKOFF.md`), the draft of amendment A5, the hosted-rating
handoff document and the rating-fetch script, the raw per-rater rating files
(only the pseudonymised scores in `analysis/human_check/ratings/` ship)
and the pilot pass (`pilot/`), the recruitment
message, and the session log. Their substance is summarised in the
pre-registration, its amendments and the paper.
