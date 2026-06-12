"""Tests for the pure progress-calculation logic."""

from kanji_vocab_miner import progress
from kanji_vocab_miner.jouyou_data import BY_GRADE


def test_kanji_coverage_counts_only_jouyou():
    # Two real jouyou kanji plus a non-jouyou character that must be ignored.
    reviewed = {"一", "二", "ヲ"}
    result = progress.kanji_coverage(reviewed_kanji=reviewed, all_deck_kanji=reviewed)

    assert result.total == 2136
    assert result.known_total == 2  # 一 and 二 only


def test_kanji_coverage_per_grade_bars():
    # Pick one real kanji from grade 1 and one from grade 3.
    g1_kanji = BY_GRADE[1][0]
    g3_kanji = BY_GRADE[3][0]
    reviewed = {g1_kanji, g3_kanji}

    result = progress.kanji_coverage(reviewed_kanji=reviewed, all_deck_kanji=reviewed)
    bars = {bar.grade: bar for bar in result.grades}

    # One bar per grade, in canonical order.
    assert [bar.grade for bar in result.grades] == [1, 2, 3, 4, 5, 6, "secondary"]
    # Totals match the embedded data.
    assert bars[1].total == len(BY_GRADE[1])
    assert bars["secondary"].total == len(BY_GRADE["secondary"])
    # Known counts land in the right grade.
    assert bars[1].known == 1
    assert bars[3].known == 1
    assert bars[2].known == 0


def test_kanji_coverage_missing_from_deck():
    # Deck contains only two jouyou kanji, so the rest are "missing from deck".
    deck = {"一", "二"}
    result = progress.kanji_coverage(reviewed_kanji=set(), all_deck_kanji=deck)
    assert result.missing_from_deck == 2136 - 2


def test_vocab_coverage_per_band():
    # freq_map maps a surface form -> its nf band (1-48).
    freq_map = {"の": 1, "日本": 25, "学校": 25}
    result = progress.vocab_coverage(["の", "日本", "学校"], freq_map)

    # 48 bands of 500 words each, covering the top 24k.
    assert len(result.bands) == 48
    assert [b.band for b in result.bands] == list(range(1, 49))
    by = {b.band: b for b in result.bands}
    assert by[1].size == 500
    assert by[1].known == 1  # の
    assert by[25].known == 2  # 日本 + 学校
    assert by[2].known == 0
    assert result.placed == 3
    assert result.total_ranked == 24000


def test_binned_vocab_variable_widths():
    # 1 known in every band, so each bin's known == its band count.
    bands = [progress.BandCell(band=i + 1, known=1, size=500) for i in range(48)]
    bins = progress.binned_vocab(bands)

    labels = [b[0] for b in bins]
    assert labels == [
        "0-500", "500-1k", "1-1.5k", "1.5-2k", "2-2.5k",
        "2.5-3.5k", "3.5-4.5k", "4.5-5.5k", "5.5k+",
    ]
    # 500-wide single-band bins up front.
    assert bins[0] == ("0-500", 1, 500)
    assert bins[4] == ("2-2.5k", 1, 500)
    # 1000-wide bins (two bands) in the middle.
    assert bins[5] == ("2.5-3.5k", 2, 1000)
    # Wide tail bin: bands 12-48 == 37 bands == 18,500 words.
    assert bins[-1] == ("5.5k+", 37, 18500)


def test_vocab_coverage_unranked_and_dedup():
    freq_map = {"の": 1}  # 謎語 and 鬱 absent -> unranked
    # Duplicate "の" must not be double-counted.
    result = progress.vocab_coverage(["の", "の", "謎語", "鬱"], freq_map)

    assert result.total_deck == 3  # distinct words
    assert result.placed == 1  # only の has a band
    assert result.unranked == 2  # 謎語 + 鬱
