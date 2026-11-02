#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
export COMIC_SMITH_DATA_DIR="$(mktemp -d)"
export COMIC_SMITH_LLM=fake COMIC_SMITH_VISION=fake COMIC_SMITH_EMBEDDINGS=fake COMIC_SMITH_IMAGE_BACKEND=mock
cs() { uv run mr-comic-smith "$@"; }
if ! cs --help | grep -q ' new '; then
  echo "fixture comic: pipeline commands not implemented yet (Sprint 0); doctor only"
  cs doctor --json > /dev/null || true
  exit 0
fi
cs new duck --image tests/fixtures/images/duck.jpg \
  --narrative "$(cat tests/fixtures/narratives/duck.txt)" --strips 4
cs cast approve duck --all
cs auto duck --until-target
cs finalize duck --title "Puddle"
cs pages duck --layout strip-stack --size us-comic
cs book duck cover --generate
cs export duck --target book --format pdf,web --out "$COMIC_SMITH_DATA_DIR/out"
uv run python -c "import sys,pypdf; r=pypdf.PdfReader(sys.argv[1]); assert len(r.pages)>=3, len(r.pages)" \
  "$COMIC_SMITH_DATA_DIR/out/duck/book.pdf"
grep -q 'data-narrate' "$COMIC_SMITH_DATA_DIR/out/duck/web/index.html"
echo "fixture comic OK"
