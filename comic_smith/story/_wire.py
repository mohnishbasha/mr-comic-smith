"""Wire format between story services and their prompts.

User messages carry one compact JSON line (`CONTEXT: {...}`) for facts the service computed, plus
fenced blocks for untrusted user text. Fake responders parse the same format, so the offline flow
sees exactly what a real model sees.
"""

import json
import re
from typing import Any

CONTEXT_PREFIX = "CONTEXT: "


def context_block(data: dict[str, Any]) -> str:
    """One line of compact JSON the model (or a fake responder) reads as trusted facts."""
    return CONTEXT_PREFIX + json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def parse_context(user: str) -> dict[str, Any]:
    """Inverse of `context_block`; an empty dict when the message has none."""
    for line in user.splitlines():
        if line.startswith(CONTEXT_PREFIX):
            value = json.loads(line[len(CONTEXT_PREFIX) :])
            return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}
    return {}


def parse_untrusted(user: str, label: str) -> str:
    """Text between the `wrap_untrusted(label, ...)` fences, or an empty string."""
    match = re.search(rf"<<<BEGIN {re.escape(label)}>>>\n(.*?)\n<<<END {re.escape(label)}>>>", user, re.S)
    return match.group(1) if match else ""
