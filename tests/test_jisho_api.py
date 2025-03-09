import pytest
import requests
import json
import jsonschema
import os
from jisho_anki_tool import jisho_api


def test_fetch_jisho_data():
    """Test that fetch_jisho_data returns a valid response for a simple kanji query."""
    # Test with the kanji for "mountain" (山)
    kanji = "山"

    # Call the function
    try:
        result = jisho_api.fetch_jisho_data(kanji)

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
    words = jisho_api.search_words(kanji)

    # Check that we got a list
    assert isinstance(words, list)

    # Check we get results
    assert len(words) > 0

    # Check the structure of the first item
    first_word = words[0]
    assert "word" in first_word
    assert "reading" in first_word
    assert "definitions" in first_word
    assert "other_kanji" in first_word
    assert "meaning" in first_word

    # The target kanji should appear in the word
    assert kanji in first_word["word"]


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
