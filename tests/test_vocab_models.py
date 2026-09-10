"""Tests for vocabulary commit state and outcomes."""

from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.vocab_models import (
    AddFailure,
    CommitProgressEvent,
    PendingVocabItem,
)


def test_pending_vocab_item_defaults_to_recognition_only() -> None:
    """New pending vocabulary is included without enabling recall."""
    word = JishoWord(
        expression="学校",
        kana="がっこう",
        jlpt=5,
        definitions=["school"],
    )

    item = PendingVocabItem(word=word)

    assert item.add_enabled is True
    assert item.recall_enabled is False
    assert item.last_error is None


def test_enrichment_failure_and_progress_event_are_typed_domain_state() -> None:
    item = PendingVocabItem(
        word=JishoWord(
            expression="学校", kana="がっこう", jlpt=5, definitions=["school"]
        ),
        recall_enabled=True,
    )

    failure = AddFailure(item, "enrichment", "provider unavailable")
    event = CommitProgressEvent(
        phase="enrichment",
        completed=1,
        total=1,
        item=item,
        outcome="failed",
    )

    assert failure.stage == "enrichment"
    assert failure.item.recall_enabled is True
    assert event.is_terminal is True
    assert event.completed == event.total == 1
