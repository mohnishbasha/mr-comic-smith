"""Record LLM fixtures by running a named scenario against a real provider (`make record-fixtures`).

Replies are saved as `{prompt_hash}.json` in tests/fixtures/llm so the fake provider can replay
them offline. Scenarios are small functions; later tasks add their own to SCENARIOS.

    uv run python scripts/record-fixtures.py --provider ollama:qwen3:14b --scenario selftest
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from comic_smith.backends.llm.base import TEMPERATURE_DETERMINISTIC, LLMProvider
from comic_smith.backends.llm.fake import RecordingLLMProvider
from comic_smith.backends.llm.providers import build_llm, parse_provider_string
from comic_smith.config import load_settings
from comic_smith.story.prompts import load_prompt, wrap_untrusted

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "llm"
SELFTEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"echo": {"type": "string"}},
    "required": ["echo"],
    "additionalProperties": False,
}


def scenario_selftest(llm: LLMProvider) -> None:
    system = load_prompt("_selftest").system(who="the reader")
    user = wrap_untrusted("name", "Ada")
    llm.complete_json(system, user, SELFTEST_SCHEMA, temperature=TEMPERATURE_DETERMINISTIC, seed=1)


SCENARIOS: dict[str, Callable[[LLMProvider], None]] = {"selftest": scenario_selftest}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", help="provider string, e.g. ollama:qwen3:14b")
    parser.add_argument("--scenario", action="append", help="scenario name (repeatable; default all)")
    parser.add_argument("--out", type=Path, default=DEFAULT_DIR, help="fixtures directory")
    parser.add_argument("--list", action="store_true", help="list scenarios and exit")
    args = parser.parse_args(argv)
    if args.list:
        print("\n".join(sorted(SCENARIOS)))
        return 0
    if not args.provider:
        parser.error("--provider is required")
    names: list[str] = args.scenario or sorted(SCENARIOS)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        parser.error(f"unknown scenario: {', '.join(unknown)}")
    settings = load_settings()
    llm = RecordingLLMProvider(build_llm(parse_provider_string(args.provider), settings), args.out)
    for name in names:
        SCENARIOS[name](llm)
        print(f"recorded scenario {name} into {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
