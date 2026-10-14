from unittest.mock import MagicMock, patch

import pytest

from kanji_vocab_miner import jisho


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


def test_word_search_encodes_query_and_returns_response_json() -> None:
    payload = {"meta": {"status": 200}, "data": []}
    response = MagicMock()
    response.json.return_value = payload

    with patch("kanji_vocab_miner.jisho.requests.get", return_value=response) as get:
        result = jisho.fetch_jisho_word_search("山")

    assert result == payload
    get.assert_called_once_with(
        "https://jisho.org/api/v1/search/words?keyword=*%E5%B1%B1*"
    )


def test_search_returns_matching_words_with_at_most_three_senses() -> None:
    payload = {
        "data": [
            {"japanese": [{"word": "猫", "reading": "ねこ"}]},
            {
                "japanese": [{"word": "山", "reading": "やま"}],
                "jlpt": ["jlpt-n5"],
                "senses": [
                    {"english_definitions": ["mountain", "hill"],
                     "parts_of_speech": ["Noun", "Counter"]},
                    {"english_definitions": ["mine"], "parts_of_speech": ["Noun"]},
                    {"english_definitions": ["forest"], "parts_of_speech": ["Noun"]},
                    {"english_definitions": ["extra sense"]},
                ],
            },
        ]
    }
    response = MagicMock()
    response.json.return_value = payload

    with patch("kanji_vocab_miner.jisho.requests.get", return_value=response):
        words = jisho.search_words_containing_kanji("山")

    assert words == [
        jisho.JishoWord(
            expression="山",
            kana="やま",
            jlpt=5,
            definitions=["mountain; hill", "mine", "forest"],
            parts_of_speech=["Noun; Counter", "Noun", "Noun"],
        )
    ]


@pytest.mark.parametrize(
    "characters, furigana, reviewed_kanji, expected",
    [
        (
            "お風呂",
            ["ふ", "ろ"],
            set(),
            "お<ruby>風<rt>ふ</rt></ruby><ruby>呂<rt>ろ</rt></ruby>",
        ),
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


def test_fetch_kanji_summary_returns_meanings_readings_and_jlpt() -> None:
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

    response = MagicMock()
    response.text = html

    with patch("kanji_vocab_miner.jisho.requests.get", return_value=response):
        summary = jisho.fetch_kanji_summary("山")

    assert summary == jisho.KanjiSummary(
        kanji="山",
        meanings=["mountain", "hill"],
        kun_readings=["やま"],
        on_readings=["サン", "セン"],
        jlpt=5,
    )
