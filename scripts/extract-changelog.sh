#!/usr/bin/env bash
# Print the CHANGELOG.md section for one version (used as the GitHub Release body).
set -euo pipefail
VERSION="${1:?Usage: $0 <version>}"
FILE="${2:-CHANGELOG.md}"
grep -q "^## \[${VERSION}\]" "$FILE" || { echo "No section for ${VERSION} in ${FILE}" >&2; exit 1; }
awk -v v="$VERSION" 'index($0, "## [" v "]") == 1 {found=1; next} found && /^## \[/ {exit} found {print}' "$FILE"
