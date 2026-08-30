"""Tests for the pure progress-calculation logic."""

from kanji_vocab_miner import jlpt, kanji_jlpt, progress


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

    # Detail bars still show every level, including N1.
    assert [bar.level for bar in result.levels] == [5, 4, 3, 2, 1]
    # Totals match the embedded data.
    totals = kanji_jlpt.kanji_level_totals()
    assert bars[5].total == totals[5]
    assert bars[2].total == totals[2]
    assert bars[1].total == totals[1]
    # Known counts land in the right level.
    assert bars[5].known == 1
    assert bars[3].known == 1
    assert bars[4].known == 0


def test_kanji_coverage_excludes_n1_from_target():
    # 丁 is N1, while 一 is N5.
    reviewed = {"丁", "一"}
    result = progress.kanji_coverage(reviewed_kanji=reviewed, all_deck_kanji=reviewed)

    assert result.known_total == 1
    n1_bar = next(bar for bar in result.levels if bar.level == 1)
    assert n1_bar.known == 1


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


def test_vocab_coverage_per_level():
    # 猫 is N5, 一定 is N2 in the vendored JLPT index.
    result = progress.vocab_coverage(["猫", "一定"])

    # One bar per N-level, N5 first through N1 last.
    assert len(result.levels) == 5
    assert [lb.level for lb in result.levels] == [5, 4, 3, 2, 1]
    by = {lb.level: lb for lb in result.levels}
    assert by[5].known == 1  # 猫
    assert by[2].known == 1  # 一定
    assert by[4].known == 0
    assert result.placed == 2
    assert result.total_ranked == sum(jlpt.level_totals().values())


def test_vocab_coverage_unranked_and_dedup():
    # でたらめ123 isn't a real word -> unranked.
    # Duplicate "猫" must not be double-counted.
    result = progress.vocab_coverage(["猫", "猫", "でたらめ123"])

    assert result.total_deck == 2  # distinct words
    assert result.placed == 1  # only 猫 has a level
    assert result.unranked == 1  # でたらめ123
