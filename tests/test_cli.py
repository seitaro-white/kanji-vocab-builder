"""Tests for CLI commands that don't require a live Anki."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Literal

import pytest
from click.testing import CliRunner

from kanji_vocab_miner import cli, setup
from kanji_vocab_miner.jisho import JishoWord, KanjiSummary
from kanji_vocab_miner.jlpt import LevelWord
from kanji_vocab_miner.progress import ManualProgressCounts
from kanji_vocab_miner.review import ReviewResult
from kanji_vocab_miner.vocab_models import (
    AddFailure,
    BatchAddResult,
    PendingVocabItem,
)


def _word(expression: str, kana: str = "") -> JishoWord:
    return JishoWord(expression=expression, kana=kana, jlpt=5, definitions=["dummy"])


def test_stats_shows_manual_section_counts_and_vocab_since_baseline(monkeypatch):
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_kanji", lambda: {"一"})
    monkeypatch.setattr(cli.ankiconnect, "get_all_kanji", lambda: {"一"})
    monkeypatch.setattr(
        cli.ankiconnect, "count_vocab_notes_added_since", lambda start_date: 25
    )
    counts = ManualProgressCounts(
        vocab_baseline=4400,
        vocab_tracking_start=date(2026, 9, 3),
        reading_i_total=41,
        reading_ii_total=29,
        reading_iii_total=11,
        grammar_i_total=10,
        grammar_ii_total=11,
        grammar_iii_total=5,
        grammar_iv_total=7,
        grammar_v_total=3,
        grammar_vi_total=12,
        reading_i=1,
        grammar_i=2,
    )
    monkeypatch.setattr(cli.manual_progress, "load_manual_progress", lambda: counts)

    result = CliRunner().invoke(cli.jisho_anki, ["stats"])

    assert result.exit_code == 0, result.output
    assert "1/41" in result.output
    assert "2/10" in result.output
    assert "4425/6000" in result.output


def test_web_command_binds_localhost_without_debug(monkeypatch):
    """The reader never exposes Flask to the LAN or enables debug mode."""
    from kanji_vocab_miner import web

    run_options = []
    monkeypatch.setattr(
        web.Flask,
        "run",
        lambda self, **kwargs: run_options.append(kwargs),
    )

    result = CliRunner().invoke(cli.jisho_anki, ["web"])

    assert result.exit_code == 0, result.output
    assert run_options == [{"host": "127.0.0.1", "port": 8766, "debug": False}]


def test_review_level_rejects_invalid_level():
    result = CliRunner().invoke(cli.jisho_anki, ["review-level", "N99"])
    assert result.exit_code == 1
    assert "N5, N4, N3, N2, N1" in result.output


def test_review_level_persists_checked_words(monkeypatch, tmp_path):
    words = [LevelWord(expression="猫", kana="ねこ", definition="cat"), LevelWord(expression="犬", kana="いぬ", definition="dog")]
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_vocab", lambda **k: [])
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(cli.jlpt, "words_in_level", lambda level: words)
    path = tmp_path / "known.txt"
    monkeypatch.setattr(cli.known_words, "known_words_path", lambda: path)

    # User checks 猫 (known), leaves 犬 unchecked.
    monkeypatch.setattr(cli.review, "review_level_words", lambda items: [words[0]])

    result = CliRunner().invoke(cli.jisho_anki, ["review-level", "N5"])
    assert result.exit_code == 0, result.output
    assert cli.known_words.load_known_words(path) == {"猫"}
    assert "Marked 1 word" in result.output


def test_review_level_aborts_without_marking(monkeypatch, tmp_path):
    words = [LevelWord(expression="猫", kana="ねこ", definition="cat"), LevelWord(expression="犬", kana="いぬ", definition="dog")]
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_vocab", lambda **k: [])
    monkeypatch.setattr(cli.ankiconnect, "get_reviewed_kanji", lambda: set())
    monkeypatch.setattr(cli.jlpt, "words_in_level", lambda level: words)
    path = tmp_path / "known.txt"
    monkeypatch.setattr(cli.known_words, "known_words_path", lambda: path)
    monkeypatch.setattr(cli.review, "review_level_words", lambda items: None)

    result = CliRunner().invoke(cli.jisho_anki, ["review-level", "N5"])
    assert result.exit_code == 0, result.output
    assert not path.exists()


def test_process_word_selection_deduplicates_pending_expressions() -> None:
    """Selecting the same expression twice creates one pending item."""
    word = _word("学校", "がっこう")

    pending = cli.process_word_selection([word], [], "1 1")

    assert len(pending) == 1
    assert pending[0].word is word


def test_handle_review_and_commit_aborts_keep_edited_pending(monkeypatch):
    """Aborting review keeps every row and its edited recall preference."""
    item = PendingVocabItem(word=_word("学校", "がっこう"))
    edited = PendingVocabItem(word=item.word, recall_enabled=True)
    monkeypatch.setattr(
        cli.review,
        "review_pending_words",
        lambda pending: ReviewResult(submitted=False, items=[edited]),
    )

    pending, continue_loop = cli.handle_review_and_commit([item], is_quitting=False)

    assert pending == [edited]
    assert continue_loop is True


def test_handle_review_and_commit_partitions_outcomes(monkeypatch):
    """Confirmed discards and successes leave while failures retain their choices."""
    discarded = PendingVocabItem(word=_word("大学", "だいがく"), add_enabled=False)
    added = PendingVocabItem(word=_word("学校", "がっこう"))
    failed = PendingVocabItem(word=_word("覚える", "おぼえる"), recall_enabled=True)
    monkeypatch.setattr(
        cli.review,
        "review_pending_words",
        lambda pending: ReviewResult(True, [discarded, added, failed]),
    )
    monkeypatch.setattr(
        cli,
        "add_pending_words_to_anki",
        lambda items: BatchAddResult(
            added=[added],
            failed=[AddFailure(failed, "definition", "definition missing")],
        ),
    )

    pending, continue_loop = cli.handle_review_and_commit(
        [discarded, added, failed], is_quitting=True
    )

    assert pending == [failed]
    assert pending[0].recall_enabled is True
    assert pending[0].last_error == "definition missing"
    assert continue_loop is True


def test_fetch_words_from_kanji_shows_unknown_status_on_anki_error(
    monkeypatch, capsys
):
    summary = KanjiSummary(
        kanji="学",
        meanings=["study"],
        kun_readings=[],
        on_readings=["ガク"],
        jlpt=5,
    )
    monkeypatch.setattr(cli.jisho, "fetch_kanji_summary", lambda kanji: summary)
    monkeypatch.setattr(cli.jisho, "search_words_containing_kanji", lambda kanji: [])
    monkeypatch.setattr(
        cli.ankiconnect,
        "get_kanji_review_status",
        lambda kanji: (_ for _ in ()).throw(RuntimeError("Anki unavailable")),
    )
    words = cli.fetch_words_from_kanji("学")

    assert words == []
    output = capsys.readouterr().out
    assert "Review status" in output
    assert "Unknown" in output


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


def test_handle_review_and_commit_reports_actual_outcome_counts(monkeypatch, capsys):
    """Commit messaging is derived from structured workflow outcomes."""
    added = PendingVocabItem(word=_word("学校", "がっこう"))
    duplicate = PendingVocabItem(word=_word("大学", "だいがく"))
    monkeypatch.setattr(
        cli.review,
        "review_pending_words",
        lambda pending: ReviewResult(True, [added, duplicate]),
    )
    monkeypatch.setattr(
        cli,
        "add_pending_words_to_anki",
        lambda items: BatchAddResult(
            added=[added], skipped_duplicates=[duplicate]
        ),
    )

    pending, continue_loop = cli.handle_review_and_commit(
        [added, duplicate], is_quitting=False
    )

    output = capsys.readouterr().out
    assert pending == []
    assert continue_loop is True
    assert "Added 1" in output
    assert "already existed 1" in output
    assert "failed 0" in output


@pytest.mark.parametrize("should_fail", [False, True])
def test_add_pending_words_uses_one_spinner_until_commit_finishes(
    monkeypatch: pytest.MonkeyPatch, should_fail: bool
) -> None:
    items = [
        PendingVocabItem(word=_word("学校", "がっこう")),
        PendingVocabItem(word=_word("大学", "だいがく")),
    ]
    status_events = []
    expected = BatchAddResult(added=[items[1]], skipped_duplicates=[items[0]])

    @contextmanager
    def fake_status(message: str, *, spinner: str) -> Iterator[None]:
        status_events.append((message, spinner))
        try:
            yield
        finally:
            status_events.append("stopped")

    def fake_add(pending: list[PendingVocabItem]) -> BatchAddResult:
        assert pending is items
        assert status_events == [("Pushing to Anki…", "dots")]
        if should_fail:
            raise RuntimeError("Anki unavailable")
        return expected

    monkeypatch.setattr(cli.console, "status", fake_status)
    monkeypatch.setattr(cli.vocab_commit, "add_vocab_items", fake_add)

    if should_fail:
        with pytest.raises(RuntimeError, match="Anki unavailable"):
            cli.add_pending_words_to_anki(items)
    else:
        assert cli.add_pending_words_to_anki(items) is expected
    assert status_events == [("Pushing to Anki…", "dots"), "stopped"]


@pytest.mark.parametrize("failure_stage", ["enrichment", "serialization"])
def test_commit_failures_are_reported_and_retained_in_reviewed_order(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure_stage: Literal["enrichment", "serialization"],
) -> None:
    first = PendingVocabItem(word=_word("最初"), recall_enabled=True)
    second = PendingVocabItem(word=_word("次"))
    monkeypatch.setattr(
        cli.review,
        "review_pending_words",
        lambda pending: ReviewResult(True, [first, second]),
    )
    monkeypatch.setattr(
        cli,
        "add_pending_words_to_anki",
        lambda items: BatchAddResult(
            failed=[
                AddFailure(first, failure_stage, "preparation failed"),
                AddFailure(second, "anki", "Anki unavailable"),
            ]
        ),
    )

    pending, continue_loop = cli.handle_review_and_commit(
        [first, second], is_quitting=True
    )

    output = capsys.readouterr().out
    assert pending == [first, second]
    assert pending[0].recall_enabled is True
    assert pending[0].last_error == "preparation failed"
    assert f"最初: {failure_stage} failed" in output
    assert "Added 0; already existed 0; failed 2." in output
    assert continue_loop is True
