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

echo "smoke OK"
