"""Tests for the pending-word review screen."""

from unittest.mock import MagicMock

from kanji_vocab_miner import review
from kanji_vocab_miner.jisho import JishoWord


def _word(expression: str, kana: str = "") -> JishoWord:
    return JishoWord(expression=expression, kana=kana, jlpt=5, definitions=["dummy"])


def test_review_empty_pending_returns_empty_list():
    """An empty pending list should short-circuit without prompting."""
    result = review.review_pending_words([])
    assert result == []


def test_review_returns_selected_words():
    """When the user confirms a subset, return exactly those words."""
    words = [_word("学校", "がっこう"), _word("大学", "だいがく")]
    mock_prompt = MagicMock()
    mock_prompt.execute.return_value = [words[0]]

    result = review.review_pending_words(
        words, prompt_func=lambda **kwargs: mock_prompt
    )

    assert result == [words[0]]
    assert mock_prompt.execute.called


def test_review_returns_none_on_abort():
    """When the user aborts, return None to signal cancellation."""
    words = [_word("学校", "がっこう")]
    mock_prompt = MagicMock()
    mock_prompt.execute.side_effect = KeyboardInterrupt

    result = review.review_pending_words(
        words, prompt_func=lambda **kwargs: mock_prompt
    )

    assert result is None


def test_format_choice_includes_expression_and_reading():
    """Choice text should display the word and its kana reading."""
    word = _word("学校", "がっこう")
    assert review._format_choice(word) == "学校 (がっこう) — dummy"


def test_format_choice_includes_definition():
    """Choice text should include the first definition for context."""
    word = JishoWord(
        expression="学校",
        kana="がっこう",
        jlpt=5,
        definitions=["school", "educational institution"],
    )
    assert review._format_choice(word) == "学校 (がっこう) — school"


def test_review_defaults_to_inquirerpy_checkbox(monkeypatch):
    """When no prompt_func is injected, InquirerPy checkbox is used with all choices enabled."""
    words = [_word("学校", "がっこう")]
    mock_prompt = MagicMock()
    mock_prompt.execute.return_value = words

    captured: dict = {}

    def fake_checkbox(**kwargs):
        captured.update(kwargs)
        return mock_prompt

    monkeypatch.setattr(review, "inquirer", type("FakeInquirer", (), {"checkbox": staticmethod(fake_checkbox)})())

    result = review.review_pending_words(words)

    assert result == words
    assert len(captured["choices"]) == 1
    assert captured["choices"][0].name == "学校 (がっこう) — dummy"
    assert captured["choices"][0].enabled is True
