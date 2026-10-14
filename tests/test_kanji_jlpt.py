"""Tests for the JLPT kanji-level index and hardest-kanji lookup."""

from kanji_vocab_miner import kanji_jlpt


def test_hardest_kanji_returns_an_n3_kanji_when_both_are_n3():
    kanji, level = kanji_jlpt.hardest_kanji("経済")

    assert kanji in ("経", "済")
    assert level == 3


def test_hardest_kanji_prefers_n3_to_n5(monkeypatch):
    monkeypatch.setattr(
        kanji_jlpt, "get_kanji_level_index", lambda: {"学": 5, "問": 3}
    )

    assert kanji_jlpt.hardest_kanji("学問") == ("問", 3)


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


def test_level_totals_count_each_level_including_empty_levels(monkeypatch):
    monkeypatch.setattr(kanji_jlpt, "LEVELS", {"一": 5, "二": 5, "勝": 3})
    kanji_jlpt.kanji_level_totals.cache_clear()
    try:
        totals = kanji_jlpt.kanji_level_totals()
    finally:
        # Keep the miniature dataset out of later dashboard tests.
        kanji_jlpt.kanji_level_totals.cache_clear()

    assert totals == {1: 0, 2: 0, 3: 1, 4: 0, 5: 2}
