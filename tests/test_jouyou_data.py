"""Tests for the embedded Jouyou kanji list."""

from kanji_vocab_miner import jouyou_data


# Per-grade counts as recorded in KanjiDic2 (the authoritative source we
# generate from): grades 1-6 are the 1026 kyouiku kanji, "secondary" is
# KanjiDic2 grade 8 (jouyou kanji taught in junior high). Sum == 2136.
EXPECTED_GRADE_COUNTS = {
    1: 80,
    2: 160,
    3: 200,
    4: 220,
    5: 185,
    6: 181,
    "secondary": 1110,
}


def test_total_count_is_2136():
    assert len(jouyou_data.JOUYOU) == 2136


def test_per_grade_counts():
    for grade, expected in EXPECTED_GRADE_COUNTS.items():
        assert len(jouyou_data.BY_GRADE[grade]) == expected, grade


def test_jouyou_is_union_of_grades():
    union = set().union(*(jouyou_data.BY_GRADE[g] for g in EXPECTED_GRADE_COUNTS))
    assert union == set(jouyou_data.JOUYOU)


def test_no_duplicates_across_grades():
    total = sum(len(jouyou_data.BY_GRADE[g]) for g in EXPECTED_GRADE_COUNTS)
    assert total == 2136
