import pytest
import requests
import json
import jsonschema
import os
from jisho_anki_tool import jisho_api

from typing import List


def test_fetch_jisho_data():
    """Test that fetch_jisho_data returns a valid response for a simple kanji query."""
    # Test with the kanji for "mountain" (山)
    kanji = "山"

    # Call the function
    try:
        result = jisho_api.fetch_jisho_word_search(kanji)

        # Check if the result is a dictionary (JSON)
        assert isinstance(result, dict)

        # Check if the expected keys are in the response
        assert "meta" in result
        assert "data" in result

        # Verify status code is 200
        assert result["meta"]["status"] == 200

        # Check that data is a list
        assert isinstance(result["data"], list)

        # Validate against schema
        schema_path = os.path.join(os.path.dirname(__file__), "jisho_words_schema.json")
        with open(schema_path, "r") as schema_file:
            schema = json.load(schema_file)
            jsonschema.validate(instance=result, schema=schema)

    except Exception as e:
        pytest.fail(f"fetch_jisho_data raised an exception: {e}")


def test_search_words():
    """Test that search_words correctly processes the Jisho API response."""
    kanji = "山"

    # Call the function
    words: List[jisho_api.JishoWord] = jisho_api.search_words_containing_kanji(kanji)

    # Check we get results
    assert len(words) > 0

    # The target kanji should appear in the word
    assert kanji in words[0].expression


def test_fetch_jisho_word_furigana():
    """Test that fetch_jisho_word_furigana returns a valid furigana string."""
    word = "学校"  # A common word with kanji
    furigana_html = jisho_api.fetch_jisho_word_furigana(word)

    # Check that the result is a string
    assert isinstance(furigana_html, str)

    # Check for basic ruby HTML structure
    assert "<ruby>" in furigana_html
    assert "</ruby>" in furigana_html
    assert "<rt>" in furigana_html
    assert "</rt>" in furigana_html
    assert "学" in furigana_html # Check for original kanji
    assert "校" in furigana_html # Check for original kanji
    assert furigana_html == '<ruby>学<rt>がっ</rt>校<rt>こう</rt></ruby>'



@pytest.mark.parametrize(
    "character, expected",
    [
        # Kanji
        ("山", True),
        ("木", True),
        # Hiragana
        ("あ", False),
        # Katakana
        ("ア", False),
        # Latin characters
        ("a", False),
        ("A", False),
        # Numbers
        ("1", False),
        # Multiple characters
        ("山水", False),
    ],
)
def test_is_kanji(character, expected):
    """Test that is_kanji correctly identifies kanji characters."""
    assert jisho_api.is_kanji(character) == expected
