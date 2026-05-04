import pytest
import requests
import json
import jsonschema
import os
from unittest.mock import patch, MagicMock
from kanji_vocab_miner import jisho

from typing import List


def _make_furigana_response(characters: str, furigana: list[str]) -> MagicMock:
    """Build a mock requests.Response whose HTML looks like a Jisho word page."""
    kanji_spans = "".join(f'<span class="kanji">{f}</span>' for f in furigana)
    html = f"""
    <div class="concept_light-representation">
        <span class="text">{characters}</span>
        {kanji_spans}
    </div>
    """
    mock_response = MagicMock()
    mock_response.text = html
    return mock_response


def test_fetch_jisho_data():
    """Test that fetch_jisho_data returns a valid response for a simple kanji query."""
    # Test with the kanji for "mountain" (山)
    kanji = "山"

    # Call the function
    try:
        result = jisho.fetch_jisho_word_search(kanji)

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
    words: List[jisho.JishoWord] = jisho.search_words_containing_kanji(kanji)

    # Check we get results
    assert len(words) > 0

    # The target kanji should appear in the word
    assert words[0] == jisho.JishoWord(
        expression="山",
        kana="やま",
        jlpt=5,
        definitions=["mountain; hill", "mine", "(mountain) forest"],
        parts_of_speech=["Noun; Counter", "Noun; Counter", "Noun; Counter"],
    )


@pytest.mark.parametrize(
    "word, expected",
    [
        ("学校", "<ruby>学<rt>がっ</rt></ruby><ruby>校<rt>こう</rt></ruby>"),
        ("お風呂", "お<ruby>風<rt>ふ</rt></ruby><ruby>呂<rt>ろ</rt></ruby>"),
        ("走る", "<ruby>走<rt>はし</rt></ruby>る"),
        ("借金", "<ruby>借金<rt>しゃっきん</rt></ruby>"),
    ],
)
def test_fetch_jisho_word_furigana(word, expected):
    """Test that fetch_jisho_word_furigana returns a valid furigana string."""
    furigana_html = jisho.fetch_jisho_word_furigana(word, set())

    # Check that the result is a string
    assert isinstance(furigana_html, str)

    # Check for basic ruby HTML structure
    assert furigana_html == expected


@pytest.mark.parametrize(
    "characters, furigana, reviewed_kanji, expected",
    [
        # Per-kanji path — no kanji reviewed
        (
            "学校",
            ["がっ", "こう"],
            set(),
            "<ruby>学<rt>がっ</rt></ruby><ruby>校<rt>こう</rt></ruby>",
        ),
        # Per-kanji path — one kanji reviewed
        (
            "学校",
            ["がっ", "こう"],
            {"学"},
            '<ruby>学<rt class="known">がっ</rt></ruby><ruby>校<rt>こう</rt></ruby>',
        ),
        # Per-kanji path — all kanji reviewed
        (
            "学校",
            ["がっ", "こう"],
            {"学", "校"},
            '<ruby>学<rt class="known">がっ</rt></ruby><ruby>校<rt class="known">こう</rt></ruby>',
        ),
        # Per-kanji path — hiragana suffix passes through; reviewed kanji gets class
        (
            "走る",
            ["はし"],
            {"走"},
            '<ruby>走<rt class="known">はし</rt></ruby>る',
        ),
        # Fallback path (one furigana for two kanji) — no kanji reviewed
        (
            "借金",
            ["しゃっきん"],
            set(),
            "<ruby>借金<rt>しゃっきん</rt></ruby>",
        ),
        # Fallback path — partially reviewed (not all kanji known → no class)
        (
            "借金",
            ["しゃっきん"],
            {"借"},
            "<ruby>借金<rt>しゃっきん</rt></ruby>",
        ),
        # Fallback path — all kanji reviewed → class="known" on the group rt
        (
            "借金",
            ["しゃっきん"],
            {"借", "金"},
            '<ruby>借金<rt class="known">しゃっきん</rt></ruby>',
        ),
    ],
)
def test_furigana_known_kanji_markup(characters, furigana, reviewed_kanji, expected):
    """Test that fetch_jisho_word_furigana applies class="known" exactly to reviewed kanji."""
    with patch("kanji_vocab_miner.jisho.requests.get", return_value=_make_furigana_response(characters, furigana)):
        result = jisho.fetch_jisho_word_furigana(characters, reviewed_kanji)
    assert result == expected


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
    assert jisho.is_kanji(character) == expected


def test_parse_kanji_summary_from_html():
    html = """
    <div class="kanji details">
        <div class="kanji-details__main-meanings">mountain, hill</div>
        <div class="kanji-details__main-readings">
            <dl class="dictionary_entry kun_yomi">
                <dt>Kun:</dt>
                <dd class="kanji-details__main-readings-list" lang="ja">
                    <a href="//jisho.org/search/%E5%B1%B1%20%E3%82%84%E3%81%BE">やま</a>
                </dd>
            </dl>
            <dl class="dictionary_entry on_yomi">
                <dt>On:</dt>
                <dd class="kanji-details__main-readings-list" lang="ja">
                    <a href="//jisho.org/search/%E5%B1%B1%20%E3%81%95%E3%82%93">サン</a>
                    、
                    <a href="//jisho.org/search/%E5%B1%B1%20%E3%81%9B%E3%82%93">セン</a>
                </dd>
            </dl>
        </div>
        <div class="kanji_stats">
            <div class="stat jlpt">
                <strong>N5</strong>
            </div>
        </div>
    </div>
    """

    summary = jisho._parse_kanji_summary_from_html("山", html)
    assert summary is not None
    assert summary.kanji == "山"
    assert summary.meanings == ["mountain", "hill"]
    assert summary.kun_readings == ["やま"]
    assert summary.on_readings == ["サン", "セン"]
    assert summary.jlpt == 5
