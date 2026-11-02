#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
if [[ -x ./scripts/gen-api-types.sh ]]; then
  ./scripts/gen-api-types.sh
  git diff --exit-code web/studio/src/api/ || { echo "API types changed: commit them"; exit 1; }
fi
make typecheck
