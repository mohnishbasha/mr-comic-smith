#!/usr/bin/env bash
# Set a new version in pyproject.toml and every synced file, then verify with check-versions.sh.
set -euo pipefail
NEW="${1:?Usage: $0 <new-version>}"
[[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$ ]] || { echo "Invalid semver: $NEW"; exit 2; }
cd "${COMIC_SMITH_REPO_ROOT:-$(git rev-parse --show-toplevel)}"
python3 - "$NEW" <<'PY'
import re, sys
from pathlib import Path
p = Path("pyproject.toml")
text = p.read_text(encoding="utf-8")
new = re.sub(r'(?m)^version = "[^"]+"', f'version = "{sys.argv[1]}"', text, count=1)
p.write_text(new, encoding="utf-8")
PY
for f in web/studio/package.json reader/package.json integrations/pi/package.json; do
  [[ -f "$f" ]] || continue
  python3 - "$f" "$NEW" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))
data["version"] = sys.argv[2]
p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
done
CHART=charts/mr-comic-smith/Chart.yaml
if [[ -f "$CHART" ]]; then
  sed -i.bak -E "s/^version: .*/version: $NEW/; s/^appVersion: .*/appVersion: \"$NEW\"/" "$CHART" && rm -f "$CHART.bak"
fi
./scripts/check-versions.sh
