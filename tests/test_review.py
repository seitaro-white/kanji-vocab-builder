"""Tests for the pending-word review screen."""

from io import StringIO
from unittest.mock import MagicMock

from prompt_toolkit.application import create_app_session
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.output.vt100 import Vt100_Output

from kanji_vocab_miner import review
from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.jlpt import LevelWord
from kanji_vocab_miner.vocab_models import PendingVocabItem


def _word(expression: str, kana: str = "") -> JishoWord:
    return JishoWord(expression=expression, kana=kana, jlpt=5, definitions=["dummy"])


def _pending(expression: str, kana: str = "") -> PendingVocabItem:
    return PendingVocabItem(word=_word(expression, kana))


def test_review_empty_pending_returns_submitted_result() -> None:
    """An empty pending list short-circuits as a confirmed empty review."""
    result = review.review_pending_words([])

    assert result.submitted is True
    assert result.items == []


def test_space_toggles_only_add() -> None:
    """Space changes inclusion without changing the stored recall preference."""
    items = [PendingVocabItem(word=_word("学校"), recall_enabled=True)]

    updated, focus = review.reduce_review_state(items, 0, "toggle_add")

    assert updated[0].add_enabled is False
    assert updated[0].recall_enabled is True
    assert focus == 0


def test_recall_toggle_enables_add() -> None:
    """Enabling recall also includes the item in the commit."""
    items = [PendingVocabItem(word=_word("学校"), add_enabled=False)]

    updated, _ = review.reduce_review_state(items, 0, "toggle_recall")

    assert updated[0].recall_enabled is True
    assert updated[0].add_enabled is True


def test_bulk_add_actions_preserve_recall() -> None:
    """Bulk add controls never erase per-row recall preferences."""
    items = [PendingVocabItem(word=_word("学校"), recall_enabled=True)]

    disabled, _ = review.reduce_review_state(items, 0, "disable_all")
    enabled, _ = review.reduce_review_state(disabled, 0, "enable_all")

    assert disabled[0].add_enabled is False
    assert disabled[0].recall_enabled is True
    assert enabled[0].add_enabled is True
    assert enabled[0].recall_enabled is True


def test_focus_stays_within_rows() -> None:
    """Navigation clamps focus at the first and last review rows."""
    items = [_pending("学校"), _pending("大学")]

    _, top = review.reduce_review_state(items, 0, "up")
    _, bottom = review.reduce_review_state(items, 1, "down")

    assert top == 0
    assert bottom == 1


def test_review_adapter_returns_abort_with_edited_items() -> None:
    """The adapter returns edited state explicitly when review is aborted."""
    items = [_pending("学校")]

    result = review.review_pending_words(
        items,
        run_application=lambda application: review.ReviewResult(False, items),
    )

    assert result.submitted is False
    assert result.items == items


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


def test_level_review_choice_shows_word_definition_and_reviewed_kanji():
    items = review.build_level_review_items(
        [LevelWord(expression="猫", kana="ねこ", definition="cat")], reviewed_kanji={"猫"}
    )
    prompt = MagicMock()
    choices = []

    def capture_prompt(**kwargs):
        choices.extend(kwargs["choices"])
        return prompt

    review.review_level_words(items, prompt_func=capture_prompt)
    text = choices[0].name

    assert "猫" in text
    assert "(ねこ)" in text
    assert "cat" in text
    assert "N3" in text
    assert "reviewed" in text


def test_level_review_displays_coloured_kanji_and_returns_space_selected_word():
    """Exercise the real prompt with in-memory terminal input and output."""
    word = LevelWord(expression="猫", kana="ねこ", definition="cat")
    items = review.build_level_review_items([word], reviewed_kanji=set())
    terminal = StringIO()
    output = Vt100_Output(
        terminal,
        lambda: Size(rows=24, columns=120),
        default_color_depth=ColorDepth.TRUE_COLOR,
    )

    with create_pipe_input() as pipe, create_app_session(input=pipe, output=output):
        pipe.send_text(" \r")
        result = review.review_level_words(items)

    assert result == [word]
    # The N3 segment is yellow, independently of the rest of the row.
    assert "\x1b[0;38;2;235;255;10;1m猫 (N3)" in terminal.getvalue()
    assert "NOT reviewed" in terminal.getvalue()


def test_level_review_choice_shows_no_kanji_for_kana_only_words():
    items = review.build_level_review_items(
        [LevelWord(expression="すごい", kana="すごい", definition="amazing")], reviewed_kanji=set()
    )
    prompt = MagicMock()
    choices = []

    def capture_prompt(**kwargs):
        choices.extend(kwargs["choices"])
        return prompt

    review.review_level_words(items, prompt_func=capture_prompt)

    assert "no kanji" in choices[0].name
