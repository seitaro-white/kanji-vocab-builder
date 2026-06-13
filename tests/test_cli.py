"""Tests for CLI commands that don't require a live Anki."""

from click.testing import CliRunner

from kanji_vocab_miner import cli
from kanji_vocab_miner.frequency import BandWord
from kanji_vocab_miner.jisho import JishoWord


def _word(expression: str, kana: str = "") -> JishoWord:
    return JishoWord(expression=expression, kana=kana, jlpt=5, definitions=["dummy"])


def test_review_band_rejects_out_of_range():
    result = CliRunner().invoke(cli.jisho_anki, ["review-band", "99"])
    assert result.exit_code == 1
    assert "between 1 and 48" in result.output


def test_review_band_marks_known_words(monkeypatch):
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_vocab", lambda **k: [])
    monkeypatch.setattr(
        cli.frequency,
        "words_in_band",
        lambda band: [BandWord("猫", "ねこ", "cat"), BandWord("犬", "いぬ", "dog")],
    )
    monkeypatch.setattr(cli.known_words, "load_known_words", lambda *a, **k: set())

    added: list[str] = []
    monkeypatch.setattr(
        cli.known_words,
        "add_known_word",
        lambda word, *a, **k: (added.append(word) or True),
    )

    # Know the first word, skip the second.
    answers = iter(["y", "n"])
    monkeypatch.setattr(cli, "normalized_input", lambda prompt: next(answers))

    result = CliRunner().invoke(cli.jisho_anki, ["review-band", "1"])
    assert result.exit_code == 0, result.output
    assert added == ["猫"]
    assert "Marked 1 word" in result.output


def test_review_band_quits_early(monkeypatch):
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_vocab", lambda **k: [])
    monkeypatch.setattr(
        cli.frequency,
        "words_in_band",
        lambda band: [BandWord("猫", "ねこ", "cat"), BandWord("犬", "いぬ", "dog")],
    )
    monkeypatch.setattr(cli.known_words, "load_known_words", lambda *a, **k: set())
    added: list[str] = []
    monkeypatch.setattr(
        cli.known_words, "add_known_word", lambda word, *a, **k: (added.append(word) or True)
    )
    monkeypatch.setattr(cli, "normalized_input", lambda prompt: "q")

    result = CliRunner().invoke(cli.jisho_anki, ["review-band", "1"])
    assert result.exit_code == 0, result.output
    assert added == []  # quit before marking anything


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
