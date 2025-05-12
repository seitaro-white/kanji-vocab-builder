import pytest
from jisho_anki_tool import card_processor
from jisho_anki_tool.jisho_api import JishoWord


@pytest.fixture
def unordered_words():
    """Fixture providing sample words with varying JLPT levels and Kanji combinations."""
    return [
        # Word with no JLPT level (should be 4th)
        JishoWord(
            expression="学問",
            kana="がくもん",
            jlpt=0,  # None converted to 0
            definitions=["learning"],
        ),
        # Reviewed and JLPT 5 (should be 1st)
        JishoWord(
            expression="学校",
            kana="がっこう",
            jlpt=5,
            definitions=["school"],
        ),
        # Unreviewed and JLPT 2 (should be 3rd)
        JishoWord(
            expression="言語",
            kana="げんご",
            jlpt=2,
            definitions=["language"],
        ),
        # Unreviewed and JLPT 5 (should be 2nd)
        JishoWord(
            expression="大学",
            kana="だいがく",
            jlpt=5,
            definitions=["university"],
        ),
    ]


# TODO: Uncomment this test after implementing mock data I think
# Also it needs to be decoupled from the anki search functionality


def test_sort_and_limit_words(unordered_words):
    """
    Test that words are properly sorted based on reviewed Kanji and JLPT level.

    The sorting priority should be:
    1. Words where all other Kanji have been reviewed (Priority 1)
    2. Words where some Kanji have not been reviewed (Priority 0)

    Within each priority group, words are further sorted by JLPT level (N5 > N4 > N3 > N2 > N1 > none).
    """
    # Call the function
    result = card_processor.sort_and_limit_words(
        unordered_words, original_kanji="学", limit=10
    )

    # Check that the words are sorted correctly
    result_kanji = [word.expression for word in result]
    assert result_kanji == ["学校", "大学", "言語", "学問"]


def test_sort_and_limit_words_empty_list():
    """Test that sort_and_limit_words handles an empty list gracefully."""
    result = card_processor.sort_and_limit_words([], original_kanji="学", limit=10)
    assert result == [], "Empty input should return empty output"
