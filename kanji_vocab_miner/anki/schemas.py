"""Typed Anki card responses and stored vocabulary-note projections."""

from dataclasses import dataclass
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

FieldType = TypeVar("FieldType", bound=BaseModel)


class AnkiCard(BaseModel, Generic[FieldType]):
    """An AnkiConnect card response with validated, model-specific note fields.

    A card is a reviewable template instance; several cards can share one note.
    The wire names ``ord`` and ``type`` use aliases to avoid builtin names.

    Attributes:
        cardId: Card identity used for reads and scheduling changes.
        fields: Typed fields from the card's owning note.
        fieldOrder: Field ordinal reported by Anki, when present.
        question: Rendered question HTML, when present.
        answer: Rendered answer HTML, when present.
        modelName: Owning note's model name.
        ord_val: Card-template ordinal, parsed from ``ord``.
        deckName: Deck containing this card.
        css: Model stylesheet, when present.
        factor: Scheduling ease factor reported by Anki.
        interval: Scheduling interval reported by Anki.
        note: Owning note ID; distinct from cardId and used for field updates.
        type_val: Scheduling card type, parsed from ``type``.
        queue: Scheduling queue reported by Anki.
        due: Queue position or due value, depending on card state.
        reps: Recorded review count.
        lapses: Recorded lapse count.
        left: Remaining learning-step state reported by Anki.
        mod: Card modification timestamp.
        nextReviews: Upcoming review descriptions, when supplied.
        flags: Card flag value reported by Anki.
    """

    cardId: int
    fields: FieldType
    fieldOrder: Optional[int] = None
    question: Optional[str] = None
    answer: Optional[str] = None
    modelName: str
    ord_val: int = Field(alias="ord")
    deckName: str
    css: Optional[str] = None
    factor: Optional[int] = Field(default=0)
    interval: Optional[int] = Field(default=0)
    note: int
    type_val: int = Field(alias="type")
    queue: Optional[int] = None
    due: Optional[int] = None
    reps: Optional[int] = Field(default=0)
    lapses: Optional[int] = Field(default=0)
    left: Optional[int] = None
    mod: int
    nextReviews: Optional[List[str]] = Field(default_factory=list)
    flags: Optional[int] = Field(default=0)


class KanjiFieldDetail(BaseModel):
    """One stored note field returned by AnkiConnect.

    Attributes:
        value: Stored field content, without rendering or normalization.
        order: Field's ordinal within its note type.
    """

    value: str
    order: int


class KanjiFields(BaseModel):
    """The supported All In One Kanji note's fields.

    Attributes:
        Kanji: Target kanji field.
        Onyomi: On-reading content.
        Kunyomi: Kun-reading content.
        Nanori: Name-reading content.
        English: English meanings.
        Examples: Usage or vocabulary examples.
        JLPT_Level: JLPT metadata, parsed from ``JLPT Level``.
        Jouyou_Grade: School-grade metadata, parsed from ``Jouyou Grade``.
        Frequency: Frequency metadata.
        Components: Component descriptions.
        Number_of_Strokes: Stroke count, parsed from ``Number of Strokes``.
        Kanji_Radical: Radical content, parsed from ``Kanji Radical``.
        Radical_Number: Radical identifier, parsed from ``Radical Number``.
        Radical_Strokes: Radical stroke count, parsed from ``Radical Strokes``.
        Radical_Reading: Radical reading, parsed from ``Radical Reading``.
        Traditional_Form: Traditional form, parsed from ``Traditional Form``.
        Classification: Character classification.
        Keyword: Mnemonic keyword.
        Koohii_Story_1: First mnemonic story, parsed from ``Koohii Story 1``.
        Koohii_Story_2: Second mnemonic story, parsed from ``Koohii Story 2``.
    """

    Kanji: KanjiFieldDetail
    Onyomi: KanjiFieldDetail
    Kunyomi: KanjiFieldDetail
    Nanori: KanjiFieldDetail
    English: KanjiFieldDetail
    Examples: KanjiFieldDetail
    JLPT_Level: KanjiFieldDetail = Field(alias="JLPT Level")
    Jouyou_Grade: KanjiFieldDetail = Field(alias="Jouyou Grade")
    Frequency: KanjiFieldDetail
    Components: KanjiFieldDetail
    Number_of_Strokes: KanjiFieldDetail = Field(alias="Number of Strokes")
    Kanji_Radical: KanjiFieldDetail = Field(alias="Kanji Radical")
    Radical_Number: KanjiFieldDetail = Field(alias="Radical Number")
    Radical_Strokes: KanjiFieldDetail = Field(alias="Radical Strokes")
    Radical_Reading: KanjiFieldDetail = Field(alias="Radical Reading")
    Traditional_Form: KanjiFieldDetail = Field(alias="Traditional Form")
    Classification: KanjiFieldDetail
    Keyword: KanjiFieldDetail
    Koohii_Story_1: KanjiFieldDetail = Field(alias="Koohii Story 1")
    Koohii_Story_2: KanjiFieldDetail = Field(alias="Koohii Story 2")


KanjiCard = AnkiCard[KanjiFields]


@dataclass(frozen=True)
class VocabNoteFurigana:
    """A stored note's identity and the content eligible for furigana maintenance.

    This is a projection, not a full note or a new validation layer. Compatible
    notes are identified by fields, independently of model name or card count.

    Attributes:
        note_id: Note ID used for updates, never a card ID. A missing ID remains
            None so the existing write path retains responsibility for errors.
        front_html: Stored Front content, possibly still in legacy notation.
        japanese_cue_html: Stored JapaneseCue content, or blank when absent.
    """

    note_id: int | None
    front_html: str
    japanese_cue_html: str

    @classmethod
    def from_anki_note(cls, note: dict[str, Any]) -> "VocabNoteFurigana":
        """Project a notesInfo record without coercing IDs or stored content.

        Args:
            note: Raw AnkiConnect note record; legacy ``note`` IDs are accepted
                when ``noteId`` is absent or false-valued.

        Returns:
            An immutable view of the note ID and editable furigana fields.
            Missing fields become blank strings; malformed records are not
            repaired or validated here.
        """
        fields = note.get("fields", {})
        return cls(
            note_id=note.get("noteId") or note.get("note"),
            front_html=fields.get("Front", {}).get("value", ""),
            japanese_cue_html=fields.get("JapaneseCue", {}).get("value", ""),
        )