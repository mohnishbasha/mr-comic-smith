"""Per-audience rule blocks (FR-028), loaded from `prompts/audience_rules.yaml`."""

from functools import lru_cache
from pathlib import Path

import yaml

from comic_smith.errors import ConfigError, UsageError

RULES_FILE = Path(__file__).resolve().parent / "prompts" / "audience_rules.yaml"


@lru_cache(maxsize=1)
def _load() -> dict[str, list[str]]:
    data = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    audiences = data.get("audiences") if isinstance(data, dict) else None
    if not isinstance(audiences, dict) or not audiences:
        raise ConfigError(f"{RULES_FILE.name} has no audiences.")
    return {str(k): [str(line) for line in v] for k, v in audiences.items()}


def audience_rules(audience: str) -> str:
    """The rule block appended to every system prompt for this audience.

    Raises:
        UsageError: `audience` is not one of the five audience values.
    """
    rules = _load().get(str(audience))
    if rules is None:
        raise UsageError(
            f"'{audience}' is not a known audience.",
            hint="Use all-ages, kids-5-8, kids-9-12, teen, or adult.",
        )
    return "\n".join(f"- {line}" for line in rules)
