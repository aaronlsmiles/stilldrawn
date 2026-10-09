#!/usr/bin/env bash
# Build the arXiv upload from paper/ and check that it compiles on its own.
#   tools/make_arxiv_bundle.sh               -> paper/arxiv/stilldrawn-arxiv.tar.gz
#   ALLOW_TODO=1 tools/make_arxiv_bundle.sh  -> preview build with the DOI still open
set -euo pipefail
cd "$(dirname "$0")/.."
B="$(mktemp -d)"
OUT="paper/arxiv"
mkdir -p "$OUT" "$B/figures"

cp paper/main.tex paper/refs.bib "$B/"
cp analysis/out/figures/panel_grid.png analysis/out/figures/fig6_motion.png "$B/figures/"
# The repo layout keeps figures in analysis/; arXiv wants them beside main.tex.
sed -i.bak 's#\.\./analysis/out/figures/#figures/#g' "$B/main.tex" && rm "$B/main.tex.bak"

# arXiv serves source: no comment lines may remain.
if grep -nE '^[[:space:]]*%' "$B/main.tex"; then
  echo "comment lines remain in main.tex" >&2; exit 1
fi
# Every \todo must be resolved (the only one expected is the Zenodo DOI).
if grep -n '\\todo{' "$B/main.tex" | grep -v 'newcommand{\\todo}'; then
  if [ "${ALLOW_TODO:-0}" != 1 ]; then
    echo "unresolved \\todo above; set ALLOW_TODO=1 for a preview build" >&2; exit 1
  fi
fi

(cd "$B" && tectonic --keep-intermediates --keep-logs main.tex >/dev/null)
[ -f "$B/main.bbl" ] || { echo "no main.bbl produced" >&2; exit 1; }
overfull=$(grep -c "Overfull" "$B/main.log" || true)
undefined=$(grep -ci "undefined" "$B/main.log" || true)

tar -C "$B" -czf "$OUT/stilldrawn-arxiv.tar.gz" main.tex main.bbl refs.bib figures
# Every graphic the manuscript includes must be inside the tarball.
for f in $(grep -o '\\includegraphics\[[^]]*\]{[^}]*}' "$B/main.tex" | sed 's/.*{\(.*\)}/\1/'); do
  tar -tzf "$OUT/stilldrawn-arxiv.tar.gz" | grep -qx "$f" || { echo "missing from bundle: $f" >&2; exit 1; }
done
cp "$B/main.pdf" "$OUT/preview.pdf"
echo "bundle: $OUT/stilldrawn-arxiv.tar.gz  (overfull: $overfull, undefined: $undefined)"
tar -tzf "$OUT/stilldrawn-arxiv.tar.gz"
rm -rf "$B"
