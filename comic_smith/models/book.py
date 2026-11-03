"""Layout template, lettering document, and book manifest (ARCHITECTURE 5.5, 5.8, 5.9)."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from comic_smith.models._base import (
    DialogueType,
    HexColor,
    Id,
    PageKind,
    PageSize,
    Str20,
    Str30,
    Str60,
    Str80,
    Str120,
    Str160,
    Str200,
    Strict,
    Unit,
    schema_field,
)

LAYOUT_SCHEMA = "comic-smith/layout@1"
LETTERING_SCHEMA = "comic-smith/lettering@1"
BOOK_SCHEMA = "comic-smith/book@1"


class SlotAccepts(StrEnum):
    """What a layout slot can hold."""

    PANEL = "panel"
    STRIP = "strip"


class BorderStyle(StrEnum):
    """Slot border styles."""

    SOLID = "solid"
    NONE = "none"
    DASHED = "dashed"


class Border(Strict):
    """Slot border."""

    style: BorderStyle = BorderStyle.SOLID
    width_pt: float = Field(default=2.0, ge=0)


class Margins(Strict):
    """Page margins in the template's units (inches by default)."""

    top: float = Field(ge=0)
    right: float = Field(ge=0)
    bottom: float = Field(ge=0)
    left: float = Field(ge=0)


class CustomPageSize(Strict):
    """Override for custom page sizes."""

    w: float = Field(gt=0)
    h: float = Field(gt=0)
    unit: Literal["in"] = "in"


class Slot(Strict):
    """A rectangle on the page."""

    id: Id
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    w: float = Field(gt=0)
    h: float = Field(gt=0)
    accepts: SlotAccepts
    border: Border | None = None


class LayoutTemplate(Strict):
    """Page layout template (`comic-smith/layout@1`)."""

    schema_id: Literal["comic-smith/layout@1"] = schema_field(LAYOUT_SCHEMA)
    id: Id
    name: Str60
    sizes: list[PageSize] = Field(min_length=1)
    page_size: CustomPageSize | None = None
    margins: Margins
    gutter: float = Field(ge=0)
    bleed: float = Field(ge=0)
    slots: list[Slot] = Field(min_length=1, max_length=12)
    reading_order: list[Id]

    @model_validator(mode="after")
    def _order_is_permutation(self) -> Self:
        """Slot ids are unique and `reading_order` lists each exactly once."""
        ids = [s.id for s in self.slots]
        if len(ids) != len(set(ids)):
            raise ValueError("slot ids must be unique")
        if sorted(self.reading_order) != sorted(ids):
            raise ValueError("reading_order must be a permutation of the slot ids")
        return self


class Box(Strict):
    """Rectangle as fractions of the panel, origin top-left (ADR-019)."""

    x: Unit
    y: Unit
    w: Unit
    h: Unit

    @model_validator(mode="after")
    def _inside_panel(self) -> Self:
        """A box must stay inside the panel."""
        if self.x + self.w > 1.0 + 1e-9 or self.y + self.h > 1.0 + 1e-9:
            raise ValueError("box must stay inside the panel (x+w <= 1, y+h <= 1)")
        return self


class Tail(Strict):
    """Balloon tail target."""

    tip_x: Unit
    tip_y: Unit
    speaker: Id | None = None


class Balloon(Box):
    """A speech, thought, shout, or whisper balloon."""

    id: Id
    type: DialogueType
    text: Str200
    tail: Tail | None
    font: Str30
    size: float = Field(gt=0, le=1)
    order: int = Field(ge=0)
    locked: bool = False


class CaptionBox(Box):
    """A narration box."""

    id: Id
    text: Str160
    font: Str30
    size: float = Field(gt=0, le=1)
    order: int = Field(ge=0)


class SfxItem(Box):
    """A placed sound effect."""

    id: Id
    text: Str20
    rotation: float = Field(ge=-45, le=45)
    font: Str30
    size: float = Field(gt=0, le=1)
    fill: HexColor
    outline: HexColor
    near: Id | None = None
    order: int = Field(ge=0)


class CharacterBox(Box):
    """Located character body and head boxes, used to avoid occlusion and aim tails."""

    character_id: Id
    head: Box | None = None


class LetteringDoc(Strict):
    """All lettering of one panel (`comic-smith/lettering@1`)."""

    schema_id: Literal["comic-smith/lettering@1"] = schema_field(LETTERING_SCHEMA)
    panel_id: Id
    balloons: list[Balloon] = Field(default_factory=list)
    captions: list[CaptionBox] = Field(default_factory=list)
    sfx: list[SfxItem] = Field(default_factory=list)
    character_boxes: list[CharacterBox] = Field(default_factory=list)


class BookMetadata(Strict):
    """Bibliographic data, also written into export file metadata."""

    title: Str120
    subtitle: Str120 | None = None
    author: Str120 | None = None
    year: int | None = Field(default=None, ge=1900, le=2200)
    language: Str30 = "en"
    noncommercial_models_used: bool = False


class BookPage(Strict):
    """A page entry in the manifest."""

    id: Id
    idx: int = Field(ge=1)
    kind: PageKind
    layout_id: Id
    story_id: Id | None = None


class Chapter(Strict):
    """A story included in the book."""

    story_id: Id
    title: Str80
    start_page: int = Field(ge=1)


class ExportDefaults(Strict):
    """Default export options, also stored in `book.settings_json`."""

    dpi: Literal[72, 150, 300] = 300
    pdf_mode: Literal["screen", "print"] = "print"
    bleed_in: float = Field(default=0.125, ge=0)
    trim_marks: bool = False
    single_file_web: bool = True


class BookManifest(Strict):
    """The book (`comic-smith/book@1`)."""

    schema_id: Literal["comic-smith/book@1"] = schema_field(BOOK_SCHEMA)
    id: Id = Field(pattern=r"^bk_")
    metadata: BookMetadata
    page_size: PageSize
    pages: list[BookPage]
    chapters: list[Chapter] = Field(default_factory=list)
    export_defaults: ExportDefaults = Field(default_factory=ExportDefaults)

    @model_validator(mode="after")
    def _pages_consecutive(self) -> Self:
        """Page `idx` values run 1..n in order."""
        if [p.idx for p in self.pages] != list(range(1, len(self.pages) + 1)):
            raise ValueError("page idx values must be consecutive from 1")
        return self
