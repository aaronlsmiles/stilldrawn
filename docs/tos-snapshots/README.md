# ToS snapshots — 2026-08-12

Best-effort headless captures of the governing documents cited in `../TOS-REVIEW.md`,
with SHA-256 hashes in `SHA256SUMS`. HTML files are page source as served that day
(some are JS-rendered apps; the served payload still hashes the state of record).

**Captured:** Runway ToU · Wan 2.2 LICENSE.txt (verbatim Apache-2.0) · LTX-2.3
in-repo LICENSE · LTX AUP PDF · FAIPL 1.0-SD · Google Gemini API Additional Terms.

**fal.ai documents** (terms, api-services, AUP): fal serves a Vercel bot-challenge to
headless fetchers, so these three were captured from a real browser (Aaron,
2026-08-12 11:23, webpage-complete save; bundled `_files` asset directories trimmed —
the saved DOM carries the full terms text, verified by keyword check). All snapshot
files hashed in `SHA256SUMS`.

**Re-check, 2026-10-01** (files named `*_captured-2026-10-01.html`, fetched as served,
hashes in `SHA256SUMS`): Runway Terms of Use (last updated 2026-09-15; the version above
was last updated 2026-05-11), Runway Usage Policy (effective 2026-03-06), fal Terms of
Service (last updated 2026-09-08; the version above, 2026-07-31) and fal API Services
supplemental terms. The Runway §4.4 and §5(viii) texts and fal §14.3 are identical across
the two captures of each provider.

**Re-check, 2026-10-09** (`runway-terms-of-use_captured-2026-10-09.pdf`, saved by Aaron
from the browser while logged in): still the 2026-09-15 version. §4.4 and §5(viii) are
word-for-word identical to the 2026-10-01 capture (differences are site navigation and a
print footer only). The Terms of Use name no specific Supplemental Terms.

**Not redistributed.** The captured pages are third-party material, so this release ships only their hashes (`SHA256SUMS`), which let anyone check a copy of the same page against the state of record.
