"""Doctor checks for the configured LLM and embeddings providers."""

from comic_smith.backends.llm.base import PreflightIssue
from comic_smith.backends.llm.providers import get_embeddings, get_llm, parse_provider_string
from comic_smith.config import Settings
from comic_smith.doctor import Check, CheckResult
from comic_smith.errors import ComicSmithError


def _result(name: str, provider_string: str, issues: list[PreflightIssue], required: bool) -> CheckResult:
    if issues:
        return CheckResult(
            name=name,
            ok=False,
            required=required,
            detail="; ".join(i.message for i in issues),
            hint=" ".join(i.hint for i in issues if i.hint) or None,
        )
    return CheckResult(name=name, ok=True, required=required, detail=provider_string)


def _check(name: str, provider_string: str, settings: Settings) -> CheckResult:
    required = parse_provider_string_kind(provider_string) != "fake"
    try:
        provider = get_llm(settings) if name == "llm" else get_embeddings(settings)
        issues = provider.preflight()
    except ComicSmithError as e:
        return CheckResult(name=name, ok=False, required=required, detail=e.message, hint=e.hint)
    return _result(name, provider_string, issues, required)


def parse_provider_string_kind(provider_string: str) -> str:
    try:
        return parse_provider_string(provider_string).kind
    except ComicSmithError:
        return "invalid"


def llm_check(settings: Settings) -> CheckResult:
    return _check("llm", settings.llm, settings)


def embeddings_check(settings: Settings) -> CheckResult:
    return _check("embeddings", settings.embeddings, settings)


def llm_checks() -> list[Check]:
    return [Check(name="llm", run=llm_check), Check(name="embeddings", run=embeddings_check)]
