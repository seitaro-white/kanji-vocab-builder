"""Tests for CLI commands that don't require a live Anki."""

import pytest
from click.testing import CliRunner

from kanji_vocab_miner import cli, setup
from kanji_vocab_miner.review_status import KanjiReviewStatus
from kanji_vocab_miner.jisho import KanjiSummary
from kanji_vocab_miner.jlpt import LevelWord
from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.progress import ManualProgressCounts


def _word(expression: str, kana: str = "") -> JishoWord:
    return JishoWord(expression=expression, kana=kana, jlpt=5, definitions=["dummy"])


def test_stats_loads_manual_progress_and_passes_all_dashboard_data(monkeypatch):
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_kanji", lambda: {"一"})
    monkeypatch.setattr(cli.ankiconnect, "get_all_kanji", lambda: {"一"})
    monkeypatch.setattr(
        cli.ankiconnect, "get_reviewed_vocab", lambda **kwargs: ["猫"]
    )
    counts = ManualProgressCounts(reading_i=1, grammar_i=2)
    monkeypatch.setattr(cli.manual_progress, "load_manual_progress", lambda: counts)
    monkeypatch.setattr(cli.known_words, "load_known_words", lambda: set())

    rendered = []
    monkeypatch.setattr(
        cli.render,
        "progress_dashboard",
        lambda kanji, manual, vocab: rendered.append((kanji, manual, vocab)),
    )

    result = CliRunner().invoke(cli.jisho_anki, ["stats"])

    assert result.exit_code == 0, result.output
    assert len(rendered) == 1
    assert rendered[0][1].reading[1].known == 1
    assert rendered[0][1].grammar[1].known == 2


def test_review_level_rejects_invalid_level():
    result = CliRunner().invoke(cli.jisho_anki, ["review-level", "N99"])
    assert result.exit_code == 1
    assert "N5, N4, N3, N2, N1" in result.output


def test_review_level_marks_known_words(monkeypatch):
    words = [LevelWord(expression="猫", kana="ねこ", definition="cat"), LevelWord(expression="犬", kana="いぬ", definition="dog")]
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_vocab", lambda **k: [])
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(cli.jlpt, "words_in_level", lambda level: words)
    monkeypatch.setattr(cli.known_words, "load_known_words", lambda *a, **k: set())

    added: list[str] = []
    monkeypatch.setattr(
        cli.known_words,
        "add_known_word",
        lambda word, *a, **k: (added.append(word) or True),
    )

    # User checks 猫 (known), leaves 犬 unchecked.
    monkeypatch.setattr(cli.review, "review_level_words", lambda items: [words[0]])

    result = CliRunner().invoke(cli.jisho_anki, ["review-level", "N5"])
    assert result.exit_code == 0, result.output
    assert added == ["猫"]
    assert "Marked 1 word" in result.output


def test_review_level_aborts_without_marking(monkeypatch):
    words = [LevelWord(expression="猫", kana="ねこ", definition="cat"), LevelWord(expression="犬", kana="いぬ", definition="dog")]
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_vocab", lambda **k: [])
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(cli.jlpt, "words_in_level", lambda level: words)
    monkeypatch.setattr(cli.known_words, "load_known_words", lambda *a, **k: set())
    added: list[str] = []
    monkeypatch.setattr(
        cli.known_words, "add_known_word", lambda word, *a, **k: (added.append(word) or True)
    )
    monkeypatch.setattr(cli.review, "review_level_words", lambda items: None)

    result = CliRunner().invoke(cli.jisho_anki, ["review-level", "N5"])
    assert result.exit_code == 0, result.output
    assert added == []  # aborted before marking anything


def test_handle_review_and_commit_aborts_keep_pending(monkeypatch):
    """Aborting review leaves pending words untouched and continues the loop."""
    words = [_word("学校", "がっこう")]
    monkeypatch.setattr(cli.review, "review_pending_words", lambda pending: None)
    committed: list = []
    monkeypatch.setattr(
        cli, "add_pending_words_to_anki", lambda words, **k: committed.extend(words)
    )

    pending, continue_loop = cli.handle_review_and_commit(words, [], is_quitting=False)

    assert pending == words
    assert continue_loop is True
    assert committed == []


def test_handle_review_and_commit_commits_selected_and_exits_on_quit(monkeypatch):
    """On quit, committing selected words clears pending and exits the loop."""
    words = [_word("学校", "がっこう"), _word("大学", "だいがく")]
    monkeypatch.setattr(cli.review, "review_pending_words", lambda pending: [words[0]])
    committed: list = []
    monkeypatch.setattr(
        cli, "add_pending_words_to_anki", lambda words, rk: committed.extend(words)
    )

    pending, continue_loop = cli.handle_review_and_commit(words, set(), is_quitting=True)

    assert pending == []
    assert continue_loop is False
    assert committed == [words[0]]


def test_fetch_words_from_kanji_renders_unknown_status_on_anki_error(monkeypatch):
    summary = KanjiSummary(
        kanji="学",
        meanings=["study"],
        kun_readings=[],
        on_readings=["ガク"],
        jlpt=5,
    )
    rendered_statuses = []
    monkeypatch.setattr(cli.jisho, "fetch_kanji_summary", lambda kanji: summary)
    monkeypatch.setattr(cli.jisho, "search_words_containing_kanji", lambda kanji: [])
    monkeypatch.setattr(
        cli.ankiconnect,
        "get_kanji_review_status",
        lambda kanji: (_ for _ in ()).throw(RuntimeError("Anki unavailable")),
    )
    monkeypatch.setattr(
        cli.render,
        "kanji_summary",
        lambda kanji_summary, status: rendered_statuses.append(status),
    )

    assert cli.fetch_words_from_kanji("学") == []
    assert rendered_statuses == [KanjiReviewStatus.UNKNOWN]


def test_reposition_kanji_moves_first_matching_card_without_prompt(monkeypatch):
    moved = []
    monkeypatch.setattr(cli.ankiconnect, "find_kanji_card_id", lambda kanji: 42)
    monkeypatch.setattr(
        cli.ankiconnect, "reposition_card_to_top", lambda card_id: moved.append(card_id)
    )

    assert cli.reposition_kanji("学") is True
    assert moved == [42]


@pytest.mark.parametrize(("inputs", "expected_kanji"), [(["学", "a", "q"], "学"), (["n", "a", "q"], "校")])
def test_interactive_a_targets_latest_direct_or_anki_kanji(
    monkeypatch, inputs, expected_kanji
):
    commands = iter(inputs)
    moved = []
    monkeypatch.setattr(cli.render, "welcome_message", lambda: None)
    monkeypatch.setattr(setup, "validate_prerequisites", lambda: (True, []))
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(cli, "get_user_input", lambda pending_count: next(commands))
    monkeypatch.setattr(cli, "handle_next_card", lambda: "校")
    monkeypatch.setattr(cli, "fetch_words_from_kanji", lambda kanji: [])
    monkeypatch.setattr(cli, "reposition_kanji", lambda kanji: moved.append(kanji))
    monkeypatch.setattr(
        cli, "_sync_furigana_and_exit", lambda: (_ for _ in ()).throw(SystemExit())
    )

    with pytest.raises(SystemExit):
        cli.run_interactive()

    assert moved == [expected_kanji]


def test_failed_lookup_disables_a(monkeypatch):
    commands = iter(["学", "校", "a", "q"])
    moved = []
    monkeypatch.setattr(cli.render, "welcome_message", lambda: None)
    monkeypatch.setattr(setup, "validate_prerequisites", lambda: (True, []))
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(cli, "get_user_input", lambda pending_count: next(commands))
    monkeypatch.setattr(
        cli,
        "fetch_words_from_kanji",
        lambda kanji: [] if kanji == "学" else (_ for _ in ()).throw(RuntimeError()),
    )
    monkeypatch.setattr(cli, "reposition_kanji", lambda kanji: moved.append(kanji))
    monkeypatch.setattr(
        cli, "_sync_furigana_and_exit", lambda: (_ for _ in ()).throw(SystemExit())
    )

    with pytest.raises(SystemExit):
        cli.run_interactive()

    assert moved == []


def test_handle_review_and_commit_commits_selected_and_continues_on_commit(monkeypatch):
    """On commit command, committing selected words clears pending and continues."""
    words = [_word("学校", "がっこう")]
    monkeypatch.setattr(cli.review, "review_pending_words", lambda pending: words)
    committed: list = []
    monkeypatch.setattr(
        cli, "add_pending_words_to_anki", lambda words, rk: committed.extend(words)
    )

    pending, continue_loop = cli.handle_review_and_commit(words, set(), is_quitting=False)

    assert pending == []
    assert continue_loop is True
    assert committed == words
