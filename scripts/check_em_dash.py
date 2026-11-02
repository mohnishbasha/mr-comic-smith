#!/usr/bin/env python3
"""Fail when any given file contains an em dash (U+2014) or en dash (U+2013).

Used by pre-commit and `make lint`. With no arguments it scans tracked md, py, ts, tsx, json,
and yaml files. The characters are built with chr() so no formatter can rewrite this file into
containing them.
"""

import subprocess
import sys
from pathlib import Path

FORBIDDEN = {chr(0x2014): "em dash", chr(0x2013): "en dash"}
PATTERNS = ("*.md", "*.py", "*.ts", "*.tsx", "*.json", "*.yaml", "*.yml")
EXCLUDE = ("docs/BUILD_PROMPT.md",)
EXCLUDE_PARTS = ("node_modules", "package-lock.json")
ROOT = Path(__file__).resolve().parent.parent


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", *PATTERNS], cwd=ROOT, check=True, capture_output=True, text=True, timeout=30
    )
    return [
        str(ROOT / f)
        for f in out.stdout.splitlines()
        if f not in EXCLUDE and not any(p in f for p in EXCLUDE_PARTS)
    ]


def find_dashes(paths: list[str]) -> list[str]:
    problems: list[str] = []
    for name in paths:
        path = Path(name)
        if not path.is_file() or any(name.endswith(e) for e in EXCLUDE):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for char, label in FORBIDDEN.items():
                if char in line:
                    problems.append(f"{name}:{lineno}: {label} found; use a comma, colon, or parentheses")
    return problems


def main(argv: list[str]) -> int:
    problems = find_dashes(argv or tracked_files())
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
