"""Domain models for pending vocabulary and batch commit outcomes."""

from dataclasses import dataclass, field
from typing import Callable, List, Literal, Optional

from kanji_vocab_miner.jisho import JishoWord

CommitPhase = Literal["duplicate", "definition", "furigana", "enrichment", "anki"]
CommitTerminalOutcome = Literal["added", "duplicate", "failed"]


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
    stage: Literal["definition", "furigana", "enrichment", "anki"]
    message: str


@dataclass(frozen=True)
class CommitProgressEvent:
    """Report a commit phase and, when terminal, one completed item."""

    phase: CommitPhase
    completed: int
    total: int
    item: Optional[PendingVocabItem] = None
    outcome: Optional[CommitTerminalOutcome] = None

    @property
    def is_terminal(self) -> bool:
        """Return whether this event advances the completed item count."""
        return self.outcome is not None


CommitProgressCallback = Callable[[CommitProgressEvent], None]


@dataclass
class BatchAddResult:
    """Separate committed, failed, and already-existing vocabulary items."""

    added: List[PendingVocabItem] = field(default_factory=list)
    failed: List[AddFailure] = field(default_factory=list)
    skipped_duplicates: List[PendingVocabItem] = field(default_factory=list)
