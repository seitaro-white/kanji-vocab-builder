"""Tests for the pending-word review screen."""

from unittest.mock import MagicMock

from kanji_vocab_miner import review
from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.jlpt import LevelWord


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
    assert captured["enabled_symbol"] == review.COMMIT_SYMBOL
    assert captured["disabled_symbol"] == review.DISCARD_SYMBOL
    assert captured["style"].dict["checkbox"] == "bold #98c379"


def test_build_level_review_items_finds_hardest_kanji():
    # 猫 and 経済 both have N3 kanji, despite being simpler N5/N4 vocab.
    words = [
        LevelWord(expression="猫", kana="ねこ", definition="cat"),
        LevelWord(expression="経済", kana="けいざい", definition="economy"),
        LevelWord(expression="すごい", kana="すごい", definition="amazing"),
    ]
    items = review.build_level_review_items(words, reviewed_kanji={"猫"})

    by_expression = {item.word.expression: item for item in items}

    cat = by_expression["猫"]
    assert cat.hardest_kanji == "猫"
    assert cat.hardest_kanji_level == 3
    assert cat.hardest_kanji_known is True  # in reviewed_kanji

    economy = by_expression["経済"]
    assert economy.hardest_kanji in ("経", "済")  # tied at N3
    assert economy.hardest_kanji_level == 3
    assert economy.hardest_kanji_known is False  # not in reviewed_kanji

    kana_only = by_expression["すごい"]
    assert kana_only.hardest_kanji is None
    assert kana_only.hardest_kanji_level is None
    assert kana_only.hardest_kanji_known is True  # no kanji, no barrier


def test_review_level_words_empty_returns_empty_list():
    assert review.review_level_words([]) == []


def test_review_level_words_returns_checked_words():
    items = review.build_level_review_items(
        [LevelWord(expression="猫", kana="ねこ", definition="cat"), LevelWord(expression="犬", kana="いぬ", definition="dog")],
        reviewed_kanji=set(),
    )
    mock_prompt = MagicMock()
    mock_prompt.execute.return_value = [items[0].word]

    result = review.review_level_words(items, prompt_func=lambda **kwargs: mock_prompt)

    assert result == [items[0].word]


def test_review_level_words_defaults_choices_to_unchecked():
    """Unlike the commit screen, words start unchecked -- most won't be known."""
    items = review.build_level_review_items(
        [LevelWord(expression="猫", kana="ねこ", definition="cat")], reviewed_kanji=set()
    )
    mock_prompt = MagicMock()
    mock_prompt.execute.return_value = []

    captured: dict = {}

    def fake_checkbox(**kwargs):
        captured.update(kwargs)
        return mock_prompt

    review.review_level_words(items, prompt_func=fake_checkbox)

    assert captured["choices"][0].enabled is False


def test_review_level_words_returns_none_on_abort():
    items = review.build_level_review_items(
        [LevelWord(expression="猫", kana="ねこ", definition="cat")], reviewed_kanji=set()
    )
    mock_prompt = MagicMock()
    mock_prompt.execute.side_effect = KeyboardInterrupt

    result = review.review_level_words(items, prompt_func=lambda **kwargs: mock_prompt)

    assert result is None


def test_format_level_choice_shows_hardest_kanji_and_known_status():
    items = review.build_level_review_items(
        [LevelWord(expression="猫", kana="ねこ", definition="cat")], reviewed_kanji={"猫"}
    )
    text = review._format_level_choice(items[0])

    assert "猫" in text
    assert "(ねこ)" in text
    assert "cat" in text
    assert "N3" in text
    assert "reviewed" in text


def test_review_level_words_colorizes_default_prompt(monkeypatch):
    """When no prompt_func is injected, the live control's row rendering is
    patched to emit coloured, per-column fragments instead of one flat name."""
    items = review.build_level_review_items(
        [LevelWord(expression="猫", kana="ねこ", definition="cat")], reviewed_kanji=set()
    )

    class FakeControl:
        _pointer = "❯"
        _enabled_symbol = review.COMMIT_SYMBOL
        _disabled_symbol = review.DISCARD_SYMBOL

    class FakePrompt:
        def __init__(self):
            self.content_control = FakeControl()

        def execute(self):
            return []

    fake_prompt = FakePrompt()
    monkeypatch.setattr(review, "inquirer", type("FakeInquirer", (), {"checkbox": staticmethod(lambda **k: fake_prompt)})())

    result = review.review_level_words(items)
    assert result == []

    choice = {"enabled": True, "value": items[0].word}
    fragments = fake_prompt.content_control._get_normal_text(choice)
    styles_and_text = "".join(text for _, text in fragments)

    assert "猫" in styles_and_text
    assert "N3" in styles_and_text
    # The hardest-kanji level segment carries its own colour class.
    assert any(style == "class:n3" for style, _ in fragments)


def test_format_level_choice_shows_no_kanji_for_kana_only_words():
    items = review.build_level_review_items(
        [LevelWord(expression="すごい", kana="すごい", definition="amazing")], reviewed_kanji=set()
    )
    text = review._format_level_choice(items[0])

    assert "no kanji" in text
