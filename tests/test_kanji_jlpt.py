"""Tests for the JLPT kanji-level index and hardest-kanji lookup."""

from kanji_vocab_miner import kanji_jlpt


def test_hardest_kanji_picks_lowest_n_number():
    # 経 and 済 are both N3 in the vendored kanji index.
    kanji, level = kanji_jlpt.hardest_kanji("経済")
    assert kanji in ("経", "済")
    assert level == 3


def test_hardest_kanji_ignores_unranked_kanji_if_others_are_ranked():
    # 鬱 has no JLPT level in the source data; 陶 is N1.
    kanji, level = kanji_jlpt.hardest_kanji("鬱陶しい")
    assert kanji == "陶"
    assert level == 1


def test_hardest_kanji_none_for_kana_only_word():
    assert kanji_jlpt.hardest_kanji("すごい") == (None, None)


def test_hardest_kanji_returns_first_kanji_when_all_unranked():
    # Both 鬱 and its jouyou pair here (using 鬱 twice) have no JLPT level.
    kanji, level = kanji_jlpt.hardest_kanji("鬱鬱")
    assert kanji == "鬱"
    assert level is None


def test_kanji_level_totals_sum_matches_index_size():
    totals = kanji_jlpt.kanji_level_totals()
    index = kanji_jlpt.get_kanji_level_index()
    assert sum(totals.values()) == len(index)
