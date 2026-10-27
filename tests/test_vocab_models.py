"""Tests for vocabulary commit state and outcomes."""

from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.vocab_models import (
    AddFailure,
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


def test_enrichment_failure_keeps_pending_recall_choice() -> None:
    item = PendingVocabItem(
        word=JishoWord(
            expression="学校", kana="がっこう", jlpt=5, definitions=["school"]
        ),
        recall_enabled=True,
    )

    failure = AddFailure(item, "enrichment", "provider unavailable")
    assert failure.stage == "enrichment"
    assert failure.item.recall_enabled is True
    assert failure.message == "provider unavailable"
