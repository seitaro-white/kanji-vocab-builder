"""Tests for the pure progress-calculation logic."""

from datetime import date

from kanji_vocab_miner import kanji_jlpt, progress
from kanji_vocab_miner.progress import ManualProgressCounts


def test_kanji_coverage_counts_only_jouyou():
    # Two real jouyou kanji plus a non-jouyou character that must be ignored.
    reviewed = {"一", "二", "ヲ"}
    result = progress.kanji_coverage(reviewed_kanji=reviewed, all_deck_kanji=reviewed)

    expected_total = sum(
        kanji_jlpt.kanji_level_totals()[level]
        for level in progress.KANJI_TARGET_LEVELS
    )
    assert result.total == expected_total
    assert result.known_total == 2  # 一 and 二 only


def test_kanji_coverage_per_level_bars():
    # 一 is N5, 勝 is N3 in the vendored JLPT kanji index.
    reviewed = {"一", "勝"}

    result = progress.kanji_coverage(reviewed_kanji=reviewed, all_deck_kanji=reviewed)
    bars = {bar.level: bar for bar in result.levels}

    # Detail bars show only the current N2-and-below study target.
    assert [bar.level for bar in result.levels] == [5, 4, 3, 2]
    # Totals match the embedded data.
    totals = kanji_jlpt.kanji_level_totals()
    assert bars[5].total == totals[5]
    assert bars[2].total == totals[2]
    assert 1 not in bars
    # Known counts land in the right level.
    assert bars[5].known == 1
    assert bars[3].known == 1
    assert bars[4].known == 0


def test_kanji_coverage_excludes_n1_from_target():
    # 丁 is N1, while 一 is N5.
    reviewed = {"丁", "一"}
    result = progress.kanji_coverage(reviewed_kanji=reviewed, all_deck_kanji=reviewed)

    assert result.known_total == 1
    assert all(bar.level != 1 for bar in result.levels)


def test_kanji_coverage_unranked():
    # 鬱 is a jouyou kanji the source data couldn't place on the N5-N1 scale.
    result = progress.kanji_coverage(reviewed_kanji={"鬱"}, all_deck_kanji={"鬱"})
    assert result.unranked == 1
    assert result.known_total == 0


def test_kanji_coverage_missing_from_deck():
    # Only target kanji absent from the deck count as missing.
    deck = {"一", "二"}
    result = progress.kanji_coverage(reviewed_kanji=set(), all_deck_kanji=deck)
    assert result.missing_from_deck == result.total - 2


def test_manual_coverage_aggregates_independent_section_counts():
    counts = ManualProgressCounts(
        vocab_baseline=4400,
        vocab_tracking_start=date(2026, 9, 3),
        reading_i=10,
        reading_ii=20,
        reading_iii=5,
        grammar_i=4,
        grammar_ii=6,
        grammar_iii=2,
    )

    result = progress.manual_coverage(counts)

    assert [bar.label for bar in result.reading] == ["Total", "I", "II", "III"]
    assert [bar.label for bar in result.grammar] == ["Total", "I", "II", "III"]
    assert (result.reading[0].known, result.reading[0].total) == (35, 81)
    assert [(bar.known, bar.total) for bar in result.reading[1:]] == [
        (10, 41),
        (20, 29),
        (5, 11),
    ]
    assert (result.grammar[0].known, result.grammar[0].total) == (12, 26)
    assert [(bar.known, bar.total) for bar in result.grammar[1:]] == [
        (4, 10),
        (6, 11),
        (2, 5),
    ]


def test_vocab_progress_adds_new_notes_to_manual_baseline():
    result = progress.vocab_progress(baseline=4400, added_since_baseline=25)

    assert result.known == 4425
    assert result.total == 6000
