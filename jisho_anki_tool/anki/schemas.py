""" Schemas for Anki Cards and Decks"""

from pydantic import BaseModel, Field, ValidationError
from pydantic.generics import GenericModel
from typing import TypeVar, List, Generic, Dict, Optional # Added Generic, TypeVar

FieldType = TypeVar('FieldType', bound=BaseModel)

class AnkiCard(GenericModel, Generic[FieldType]):
    # --- Standard Anki Fields ---
    cardId: int
    fields: FieldType
    fieldOrder: Optional[int] = None # Making optional if sometimes absent
    question: Optional[str] = None # Making optional if sometimes absent
    answer: Optional[str] = None   # Making optional if sometimes absent
    modelName: str
    ord_val: int = Field(alias="ord") # 'ord' is a built-in, aliasing
    deckName: str
    css: Optional[str] = None      # Making optional if sometimes absent
    factor: Optional[int] = Field(default=0) # Using Optional with default
    interval: Optional[int] = Field(default=0)
    note: int # Usually the note ID, seems important
    type_val: int = Field(alias="type") # 'type' is a built-in, aliasing
    queue: Optional[int] = None
    due: Optional[int] = None
    reps: Optional[int] = Field(default=0)
    lapses: Optional[int] = Field(default=0)
    left: Optional[int] = None
    mod: int # Modification timestamp, usually important
    nextReviews: Optional[List[str]] = Field(default_factory=list) # Use factory for mutable default
    flags: Optional[int] = Field(default=0)



# Inner model for each field's value and order (e.g., Kanji, Onyomi)
class KanjiFieldDetail(BaseModel):
    value: str
    order: int

# Model for the 'fields' dictionary
class KanjiFields(BaseModel):
    """
    The fields of the Kanji card that are made available in the
    All In One Kanji Deck (https://ankiweb.net/shared/info/798002504)"""

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

# Define the specific type for Kanji cards
KanjiCard = AnkiCard[KanjiFields]