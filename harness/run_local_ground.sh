#!/bin/zsh
# A3 clause 2 — local-engine ground cells (wan22 + ltx23), Mac/MPS overnight run.
# Detached by design: nohup this so it survives any session ending.
#   nohup harness/run_local_ground.sh > runs/local-ground.log 2>&1 &
# LTX first (faster ≈26 min/clip), then Wan (≈90 min/clip at 704p), then metrics
# for both into runs/metrics-ground/. Resumable: existing clips/metrics are skipped.
set -u
cd "$(dirname "$0")/.." || exit 1
PY=${STILLDRAWN_PY:-python3}

echo "=== $(date '+%F %T') local ground series start (A3 clause 2)"
for ENGINE in ltx23 wan22; do
  echo "--- $(date '+%F %T') generate: $ENGINE"
  $PY harness/ground_series.py run --engine "$ENGINE" || echo "!! $ENGINE generation returned $?"
  echo "--- $(date '+%F %T') metrics: $ENGINE"
  $PY harness/ground_series.py metrics --engine "$ENGINE" || echo "!! $ENGINE metrics returned $?"
done

echo "--- $(date '+%F %T') refresh analyses"
$PY analysis/ground_response.py || true
echo "=== $(date '+%F %T') DONE. Clips: $(ls runs/wan22 runs/ltx23 2>/dev/null | grep -c ground) | metrics: $(ls runs/metrics-ground 2>/dev/null | wc -l)"
