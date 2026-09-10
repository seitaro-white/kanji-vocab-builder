"""Tests for vocabulary commit state and outcomes."""

from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.vocab_models import PendingVocabItem


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
