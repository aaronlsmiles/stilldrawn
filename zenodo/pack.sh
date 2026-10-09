#!/usr/bin/env bash
# Pack the release tree into Zenodo upload files.
# Zenodo allows 50 GB and 100 files per record; this makes 11 files (~1.7 GB).
#   zenodo/pack.sh [version]      -> zenodo/dist/
set -euo pipefail
cd "$(dirname "$0")/.."
V="${1:-1.0.0}"
OUT="zenodo/dist"
rm -rf "$OUT"; mkdir -p "$OUT"

# Clips are STORED (-0), never recompressed: the C2PA-signed clips must stay
# byte-exact or their signatures' hash binding breaks.
for e in gen4_turbo gen4.5 h3-fal wan22 ltx23 seedance; do
  zip -q -r -0 -X "$OUT/stilldrawn-clips-$e-v$V.zip" "runs/$e"
done

zip -q -r -9 -X "$OUT/stilldrawn-dataset-v$V.zip" \
  dataset README.md NOTICE-PROVIDERS.md CITATION.cff LICENSE-DATA \
  -x "*/.DS_Store" ".DS_Store"

zip -q -r -9 -X "$OUT/stilldrawn-results-v$V.zip" \
  runs/manifest.jsonl runs/manifest-supplement.jsonl runs/CLIP-HASHES.csv \
  runs/README.md runs/RECONCILIATION-2026-08-12-h3.md runs/metrics* \
  analysis/out analysis/human_check docs LEDGER.md LICENSE-DATA \
  -x "analysis/human_check/*.py" "*/__pycache__/*" "*/.DS_Store" ".DS_Store"

zip -q -r -9 -X "$OUT/stilldrawn-code-v$V.zip" \
  metrics harness analysis/*.py analysis/human_check/collect.py \
  analysis/human_check/build_harness.py zenodo/pack.sh paper tools \
  README.md LICENSE-CODE -x "paper/arxiv/*" "*/__pycache__/*" "*/.DS_Store" ".DS_Store"

cp README.md "$OUT/README.md"
(cd "$OUT" && shasum -a 256 ./*.zip README.md > SHA256SUMS)

# Verify every clip inside the archives against runs/CLIP-HASHES.csv.
python3 - "$OUT" <<'PY'
import csv, hashlib, sys, zipfile, pathlib
want = {r["file"]: r["sha256"] for r in csv.DictReader(open("runs/CLIP-HASHES.csv"))}
seen = 0
for z in sorted(pathlib.Path(sys.argv[1]).glob("stilldrawn-clips-*.zip")):
    with zipfile.ZipFile(z) as zf:
        for i in zf.infolist():
            if i.filename.endswith(".mp4"):
                if i.compress_type != zipfile.ZIP_STORED:
                    sys.exit(f"{i.filename}: compressed, expected stored")
                h = hashlib.sha256(zf.read(i)).hexdigest()
                if want.get(i.filename) != h:
                    sys.exit(f"{i.filename}: hash mismatch")
                seen += 1
if seen != len(want):
    sys.exit(f"clips in archives {seen} != clips in CLIP-HASHES.csv {len(want)}")
print(f"verified {seen} clips byte-exact inside the archives")
PY
ls -lh "$OUT"
