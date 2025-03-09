import pytest
from jisho_anki_tool import card_processor


@pytest.fixture
def unordered_words():
    """Fixture providing sample words with varying JLPT levels and Kanji combinations."""
    return [
        # Word with no JLPT level (should be 4th)
        {
            "word": "学問",
            "reading": "がくもん",
            "jlpt": None,
            "other_kanji": ["学", "問"],
            "meaning": "learning",
        },
        # Reviewed and JLPT 5 (should be 1st)
        {
            "word": "学校",
            "reading": "がっこう",
            "jlpt": 5,
            "other_kanji": ["学", "校"],
            "meaning": "school",
        },
        # Unreviewed and JLPT 2 (should be 3rd)
        {
            "word": "言語",
            "reading": "げんご",
            "jlpt": 2,
            "other_kanji": ["言", "語"],
            "meaning": "language",
        },
        # Unreviewed and JLPT 5 (should be 2nd)
        {
            "word": "大学",
            "reading": "だいがく",
            "jlpt": 5,
            "other_kanji": ["大", "学"],
            "meaning": "university",
        },
    ]


def test_sort_and_limit_words(unordered_words):
    """
    Test that words are properly sorted based on reviewed Kanji and JLPT level.

    The sorting priority should be:
    1. Words where all other Kanji have been reviewed (Priority 1)
    2. Words where some Kanji have not been reviewed (Priority 0)

    Within each priority group, words are further sorted by JLPT level (N5 > N4 > N3 > N2 > N1 > none).
    """
    # Call the function
    result = card_processor.sort_and_limit_words(unordered_words, limit=10)

    # Check that the words are sorted correctly
    result_kanji = [word["word"] for word in result]
    assert result_kanji == ["学校", "大学", "言語", "学問"]


def test_sort_and_limit_words_empty_list():
    """Test that sort_and_limit_words handles an empty list gracefully."""
    result = card_processor.sort_and_limit_words([], limit=10)
    assert result == [], "Empty input should return empty output"
