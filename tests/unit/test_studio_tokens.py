"""Design tokens (DESIGN section 5) must exist for light, system-dark, and forced dark."""

import re
from pathlib import Path

TOKENS = Path(__file__).resolve().parents[2] / "web" / "studio" / "src" / "styles" / "tokens.css"
LIGHT_ONLY = ("--cs-balloon-fill", "--cs-balloon-ink", "--cs-caption")


def _block(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{(.*?)\}", css, re.DOTALL)
    assert match, f"missing block {selector}"
    return match.group(1)


def test_studio_tokens_light_and_dark_css_variables_defined() -> None:
    css = TOKENS.read_text(encoding="utf-8")
    root = _block(css, ":root")
    for token in ("--cs-bg", "--cs-surface", "--cs-text", "--cs-accent", "--cs-focus", "--cs-space-4"):
        assert token in root
    assert "@media (prefers-color-scheme: dark)" in css
    system_dark = _block(css, ':root:not([data-theme="light"])')
    forced_dark = _block(css, ':root[data-theme="dark"]')
    for block in (system_dark, forced_dark):
        for token in ("--cs-bg", "--cs-surface", "--cs-text", "--cs-accent", "--cs-border"):
            assert token in block
        for token in LIGHT_ONLY:
            assert token not in block, "lettering colors never follow the UI theme"
    assert "gradient" not in css
