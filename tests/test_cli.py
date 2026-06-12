"""Tests for CLI commands that don't require a live Anki."""

from click.testing import CliRunner

from kanji_vocab_miner import cli
from kanji_vocab_miner.frequency import BandWord


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
