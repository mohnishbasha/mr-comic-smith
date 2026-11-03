"""Sortable prefixed ids: `{prefix}_{ULID}` (ARCHITECTURE section 4 general rules).

A ULID body is 48 bits of millisecond time then 80 bits of randomness in 26 Crockford base32
characters, so ids sort by creation time and are safe in filenames and URLs. Within one
millisecond the default generator increments the random part, so ids from one process still sort
in creation order.
"""

import os
import re
import time
from collections.abc import Callable

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ULID_LEN = 26
RANDOM_BITS = 80
TIME_BITS = 48
PREFIX_RE = re.compile(r"^[a-z]{1,4}$")

# Follows ARCHITECTURE 4.1 (the comment next to each id column), not shorthand used elsewhere.
PREFIXES: dict[str, str] = {
    "project": "prj",
    "bible": "bib",
    "character": "ch",
    "style": "st",
    "branch": "br",
    "strip": "sp",
    "panel": "pn",
    "take": "tk",
    "suggestion_set": "ss",
    "story": "sy",
    "book": "bk",
    "page": "pg",
    "export": "ex",
    "job": "jb",
    "workspace": "ws",
}

Clock = Callable[[], int]
RandomBytes = Callable[[int], bytes]


def _now_ms() -> int:
    """Wall clock in milliseconds."""
    return time.time_ns() // 1_000_000


def encode_ulid(time_ms: int, randomness: int) -> str:
    """Encode a timestamp and 80 random bits as 26 Crockford base32 characters."""
    value = ((time_ms & ((1 << TIME_BITS) - 1)) << RANDOM_BITS) | (randomness & ((1 << RANDOM_BITS) - 1))
    chars = []
    for _ in range(ULID_LEN):
        chars.append(ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(chars))


class UlidFactory:
    """Generates monotonic ULIDs; the clock and randomness are injectable for tests."""

    def __init__(self, clock: Clock = _now_ms, rand: RandomBytes = os.urandom) -> None:
        """Create a factory.

        Args:
            clock: Returns milliseconds since the epoch.
            rand: Returns n random bytes.
        """
        self._clock = clock
        self._rand = rand
        self._last_ms = -1
        self._last_rand = 0

    def new(self) -> str:
        """Next ULID; bumps the previous random part when the millisecond has not advanced."""
        now = self._clock()
        if now <= self._last_ms:
            now = self._last_ms
            self._last_rand = (self._last_rand + 1) & ((1 << RANDOM_BITS) - 1)
        else:
            self._last_rand = int.from_bytes(self._rand(RANDOM_BITS // 8), "big")
        self._last_ms = now
        return encode_ulid(now, self._last_rand)


_DEFAULT = UlidFactory()


def new_id(prefix: str, *, clock: Clock | None = None, rand: RandomBytes | None = None) -> str:
    """Return `{prefix}_{ulid}`.

    Args:
        prefix: 1 to 4 lowercase letters, usually a value of `PREFIXES`.
        clock: Test hook: milliseconds clock; builds a one-off non-monotonic generator.
        rand: Test hook: random bytes source.

    Raises:
        ValueError: The prefix is not 1 to 4 lowercase letters.
    """
    if not PREFIX_RE.match(prefix):
        raise ValueError(f"id prefix must be 1 to 4 lowercase letters, got {prefix!r}")
    if clock is None and rand is None:
        return f"{prefix}_{_DEFAULT.new()}"
    factory = UlidFactory(clock or _now_ms, rand or os.urandom)
    return f"{prefix}_{factory.new()}"
