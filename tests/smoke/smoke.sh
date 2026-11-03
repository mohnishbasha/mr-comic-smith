#!/usr/bin/env bash
# CLI smoke test with fakes (TEST_PLAN section 1). Grows with each sprint.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
export COMIC_SMITH_DATA_DIR="$(mktemp -d)"
export COMIC_SMITH_LLM=fake COMIC_SMITH_VISION=fake COMIC_SMITH_EMBEDDINGS=fake COMIC_SMITH_IMAGE_BACKEND=mock
trap 'rm -rf "$COMIC_SMITH_DATA_DIR"' EXIT
cs() { uv run mr-comic-smith "$@"; }

echo "smoke_cli_version_exits_zero"
cs --version | grep -q "mr-comic-smith"

echo "smoke_doctor_json_parses"
cs doctor --json | uv run python -c "import json,sys; d=json.load(sys.stdin); assert 'results' in d"

echo "smoke_cli_new_auto_finalize_scripted_story"
cs new duck --narrative "$(cat tests/fixtures/narratives/duck.txt)" --audience kids-5-8 --strips 8 > /dev/null
cs auto duck --until-target > /dev/null
cs finalize duck --title Puddle --json > "$COMIC_SMITH_DATA_DIR/story.json"
cs strips duck --json > "$COMIC_SMITH_DATA_DIR/strips.json"
uv run python - "$COMIC_SMITH_DATA_DIR" <<'PY'
import json, sys
root = sys.argv[1]
strips = json.load(open(f"{root}/strips.json"))
story = json.load(open(f"{root}/story.json"))
assert len(strips) == 8, len(strips)
assert all(s["status"] == "approved" and s["panel_count"] >= 1 for s in strips)
assert story["title"] == "Puddle" and story["finalized_at"], story
PY

echo "smoke OK"
