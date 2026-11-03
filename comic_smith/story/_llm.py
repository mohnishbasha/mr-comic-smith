"""One helper for every story LLM call: render the template, call, validate, return the model."""

from pydantic import BaseModel, ValidationError

from comic_smith.backends.llm.base import TEMPERATURE_DETERMINISTIC
from comic_smith.context import Ctx
from comic_smith.errors import SchemaValidationError
from comic_smith.models import llm_schema
from comic_smith.story.audience import audience_rules
from comic_smith.story.prompts import load_prompt


def call_model[M: BaseModel](
    ctx: Ctx,
    template: str,
    model: type[M],
    *,
    audience: str,
    user: str,
    temperature: float = TEMPERATURE_DETERMINISTIC,
) -> M:
    """Render `template` with the audience rules, ask the LLM for JSON, validate into `model`.

    Why validate again after the provider: the provider checks the inlined JSON Schema, while the
    pydantic model also enforces cross-field rules (for example the suggestion intent order).

    Raises:
        SchemaValidationError: The reply parsed but broke a model rule.
    """
    system = load_prompt(template).system(audience_rules=audience_rules(audience))
    reply = ctx.require_llm().complete_json(
        system, user, llm_schema(model), temperature=temperature, seed=None
    )
    try:
        return model.model_validate(reply)
    except ValidationError as e:
        raise SchemaValidationError(
            "The language model's answer did not fit the expected shape.",
            hint="Try again.",
            detail=str(e)[:500],
        ) from e
