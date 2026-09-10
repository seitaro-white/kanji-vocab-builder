"""Domain models for pending vocabulary and batch commit outcomes."""

from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kanji_vocab_miner.jisho import JishoWord


@dataclass
class PendingVocabItem:
    """Store a selected word and its user-controlled commit preferences."""

    word: JishoWord
    add_enabled: bool = True
    recall_enabled: bool = False
    last_error: Optional[str] = None


@dataclass
class AddFailure:
    """Describe one vocabulary item that could not be committed."""

    item: PendingVocabItem
    stage: Literal["definition", "furigana", "anki"]
    message: str


@dataclass
class BatchAddResult:
    """Separate committed, failed, and already-existing vocabulary items."""

    added: List[PendingVocabItem] = field(default_factory=list)
    failed: List[AddFailure] = field(default_factory=list)
    skipped_duplicates: List[PendingVocabItem] = field(default_factory=list)
