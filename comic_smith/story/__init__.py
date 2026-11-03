"""Story engine: bible, suggestions, writer, arc, finalize."""

from comic_smith.story import fake_responses as fake_responses  # registers the offline LLM answers
from comic_smith.story import (
    fake_responses_writer as fake_responses_writer,  # registers strip writer, continuity, titles
)
