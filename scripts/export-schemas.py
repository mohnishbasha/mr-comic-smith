#!/usr/bin/env python3
"""Write (or with --check, verify) the published JSON Schemas under schemas/.

The schemas are generated from the pydantic models in `comic_smith.models` (ARCHITECTURE 5.10), so
the files can never be edited by hand without CI noticing.
"""

import argparse
import sys
from pathlib import Path

from comic_smith.models import PUBLISHED, render_schema

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"


def main(argv: list[str] | None = None) -> int:
    """Export or check; returns the process exit code (1 when `--check` finds stale files)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if any file is missing or stale")
    args = parser.parse_args(argv)
    stale: list[str] = []
    for name in PUBLISHED:
        path = SCHEMAS_DIR / f"{name}.schema.json"
        text = render_schema(name)
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        stale.append(path.name)
        if not args.check:
            SCHEMAS_DIR.mkdir(exist_ok=True)
            path.write_text(text, encoding="utf-8")
    if args.check and stale:
        print(f"stale schemas: {', '.join(stale)}; run scripts/export-schemas.py", file=sys.stderr)
        return 1
    if stale:
        print(f"wrote {len(stale)} schema file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
