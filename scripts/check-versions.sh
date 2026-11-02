#!/usr/bin/env bash
# Verify every versioned file matches pyproject.toml [project].version (the only human-edited version).
# Files that do not exist yet (packages created in later sprints) are skipped.
set -euo pipefail
cd "${COMIC_SMITH_REPO_ROOT:-$(git rev-parse --show-toplevel)}"

CANONICAL=$(python3 - <<'PY'
import tomllib
with open("pyproject.toml", "rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)

check() {
  local actual=$1 file=$2
  if [[ "$actual" != "$CANONICAL" ]]; then
    echo "✗ Version mismatch in $file: expected $CANONICAL, got $actual"
    exit 1
  fi
  echo "✓ $file: $CANONICAL"
}

json_version() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$1"; }
yaml_field() { python3 -c 'import sys,yaml; print(yaml.safe_load(open(sys.argv[1]))[sys.argv[2]])' "$1" "$2"; }

for f in web/studio/package.json reader/package.json integrations/pi/package.json; do
  [[ -f "$f" ]] && check "$(json_version "$f")" "$f"
done
CHART=charts/mr-comic-smith/Chart.yaml
if [[ -f "$CHART" ]]; then
  check "$(yaml_field "$CHART" version)" "$CHART (version)"
  check "$(yaml_field "$CHART" appVersion)" "$CHART (appVersion)"
fi

echo "── All versions consistent: $CANONICAL ──"
