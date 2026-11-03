"""Versioned prompt templates (ARCHITECTURE 9.2, 11.5).

Templates are `{name}.md` files with YAML front matter (`name`, `version`, `description`) and a
body using `{{var}}` placeholders. `system()` renders the template-marker first line that the
fake provider uses to pick a responder, so story code never builds system prompts by hand.
"""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from comic_smith.backends.llm.base import TEMPLATE_MARKER_PREFIX
from comic_smith.errors import ConfigError

PROMPTS_DIR = Path(__file__).resolve().parent
NAME_RE = re.compile(r"[A-Za-z0-9_-]+")
VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)
DELIMITER_RE = re.compile(r"<<<\s*(?:BEGIN|END)\b[^<>\n]*>>>")
AUDIENCE_HEADING = "## Audience rules"


class _FrontMatter(BaseModel):
    name: str
    version: int
    description: str = ""


class PromptTemplate(BaseModel):
    name: str
    version: int
    body: str

    @property
    def key(self) -> str:
        """Cache-key component: changing a template changes its version and so its keys."""
        return f"{self.name}@{self.version}"

    def system(self, audience_rules: str | None = None, **variables: object) -> str:
        """Render the system prompt: marker line, substituted body, optional audience rules."""

        def substitute(match: re.Match[str]) -> str:
            var = match.group(1)
            if var not in variables:
                raise ConfigError(
                    f"The prompt template {self.key} needs a value for '{var}'.",
                    hint="Pass it as a keyword argument to system().",
                )
            return str(variables[var])

        body = VAR_RE.sub(substitute, self.body).strip("\n")
        parts = [f"{TEMPLATE_MARKER_PREFIX}{self.key} -->", body]
        if audience_rules:
            parts.append(f"{AUDIENCE_HEADING}\n{audience_rules.strip()}")
        return "\n\n".join(parts) + "\n"


def load_prompt(name: str) -> PromptTemplate:
    if not NAME_RE.fullmatch(name):
        raise ConfigError(f"'{name}' is not a valid prompt template name.")
    path = PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise ConfigError(f"The prompt template '{name}' does not exist.", hint=f"Expected {path.name}.")
    match = FRONT_MATTER_RE.match(path.read_text(encoding="utf-8"))
    if match is None:
        raise ConfigError(f"The prompt template {path.name} has no front matter.")
    try:
        meta = _FrontMatter.model_validate(yaml.safe_load(match.group(1)))
    except (ValidationError, yaml.YAMLError) as e:
        raise ConfigError(f"The prompt template {path.name} has invalid front matter.", detail=str(e)) from e
    if meta.name != name:
        raise ConfigError(f"The prompt template {path.name} declares the name '{meta.name}'.")
    return PromptTemplate(name=meta.name, version=meta.version, body=match.group(2))


def wrap_untrusted(label: str, text: str) -> str:
    """Fence user-supplied text so the model treats it as data; strips fence-like tokens inside."""
    cleaned = text
    while True:
        stripped = DELIMITER_RE.sub("", cleaned)
        if stripped == cleaned:
            break
        cleaned = stripped
    return f"<<<BEGIN {label}>>>\n{cleaned.strip()}\n<<<END {label}>>>"
