from html import escape
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from kanji_vocab_miner import jisho


def _make_furigana_response(characters: str, furigana: list[str]) -> MagicMock:
    """Build a mock requests.Response whose HTML looks like a Jisho word page."""
    kanji_spans = "".join(f'<span class="kanji">{escape(f)}</span>' for f in furigana)
    html = f"""
    <div class="concept_light-representation">
        <span class="text">{escape(characters)}</span>
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


def test_search_finds_kanji_spelling_after_kana_only_form() -> None:
    """Keep 眼鏡 even when Jisho lists メガネ as the first form."""
    response = MagicMock()
    response.json.return_value = {
        "data": [
            {
                "japanese": [
                    {"reading": "メガネ"},
                    {"word": "眼鏡", "reading": "めがね"},
                ],
                "jlpt": ["jlpt-n5"],
                "senses": [
                    {
                        "english_definitions": ["glasses", "spectacles"],
                        "parts_of_speech": ["Noun"],
                    }
                ],
            }
        ]
    }

    with patch("kanji_vocab_miner.jisho.requests.get", return_value=response):
        words = jisho.search_words_containing_kanji("眼")

    assert words == [
        jisho.JishoWord(
            expression="眼鏡",
            kana="めがね",
            jlpt=5,
            definitions=["glasses; spectacles"],
            parts_of_speech=["Noun"],
        )
    ]


@pytest.mark.parametrize(
    "kanji, forms, expected",
    [
        pytest.param(
            "飲",
            [
                {"word": "湯のみ", "reading": "ゆのみ"},
                {"word": "湯飲み", "reading": "ゆのみ"},
            ],
            ("湯飲み", "ゆのみ"),
            id="alternate-kanji-spelling",
        ),
        pytest.param(
            "眼",
            [
                {"reading": "メグスリ"},
                {"word": "目薬", "reading": "めぐすり"},
                {"word": "眼薬", "reading": "がんやく"},
            ],
            ("眼薬", "がんやく"),
            id="later-match-keeps-its-own-reading",
        ),
        pytest.param(
            "眼",
            [
                {"word": "眼差し", "reading": "まなざし"},
                {"word": "眼指", "reading": "まなざし"},
            ],
            ("眼差し", "まなざし"),
            id="preserve-first-matching-form",
        ),
        pytest.param(
            "眼",
            [
                {"word": "目やに", "reading": "めやに"},
                {"word": "眼脂", "reading": "めやに"},
                {"word": "眼脂", "reading": "がんし"},
            ],
            ("眼脂", "めやに"),
            id="one-result-for-multiple-later-matches",
        ),
    ],
)
def test_search_selects_first_matching_form_per_entry(
    kanji: str, forms: list[dict[str, str]], expected: tuple[str, str]
) -> None:
    response = MagicMock()
    response.json.return_value = {"data": [{"japanese": forms}]}

    with patch("kanji_vocab_miner.jisho.requests.get", return_value=response):
        words = jisho.search_words_containing_kanji(kanji)

    assert [(word.expression, word.kana) for word in words] == [expected]


@pytest.mark.parametrize(
    "item",
    [
        {},
        {"japanese": []},
        {"japanese": [{"reading": "メガネ"}]},
        {
            "slug": "眼鏡",
            "japanese": [
                {"word": "目", "reading": "め"},
                {"word": "芽", "reading": "め"},
            ],
        },
    ],
    ids=["missing-forms", "empty-forms", "kana-only", "no-matching-spelling"],
)
def test_search_skips_entries_without_matching_forms(item: dict[str, object]) -> None:
    response = MagicMock()
    response.json.return_value = {"data": [item]}

    with patch("kanji_vocab_miner.jisho.requests.get", return_value=response):
        words = jisho.search_words_containing_kanji("眼")

    assert words == []


@pytest.mark.parametrize(
    "reviewed_kanji, expected",
    [
        (set(), "<ruby>眼鏡<rt>めがね</rt></ruby>"),
        ({"眼"}, "<ruby>眼鏡<rt>めがね</rt></ruby>"),
        ({"眼", "鏡"}, '<ruby>眼鏡<rt class="known">めがね</rt></ruby>'),
    ],
)
def test_furigana_preserves_requested_spelling_from_other_forms(
    reviewed_kanji: set[str], expected: str
) -> None:
    """Jisho's 眼鏡 page displays メガネ first, without any ruby spans."""
    response = MagicMock()
    response.text = (
        Path(__file__).parent / "fixtures" / "jisho_megane.html"
    ).read_text(encoding="utf-8")

    with patch("kanji_vocab_miner.jisho.requests.get", return_value=response):
        result = jisho.fetch_jisho_word_furigana("眼鏡", reviewed_kanji)

    assert result == expected


@pytest.mark.parametrize(
    "word, fixture, suffix",
    [("善い", "jisho_yoi_search.html", "い"), ("善く", "jisho_yoku_search.html", "く")],
)
@pytest.mark.parametrize("reviewed", [set(), {"善"}])
def test_missing_word_page_uses_exact_search_other_form(
    word: str, fixture: str, suffix: str, reviewed: set[str]
) -> None:
    missing = MagicMock(status_code=404, text="<html>Not found</html>")
    search = MagicMock(
        status_code=200,
        text=(Path(__file__).parent / "fixtures" / fixture).read_text(encoding="utf-8"),
    )
    with patch("kanji_vocab_miner.jisho.requests.get", side_effect=[missing, search]) as get:
        front = jisho.fetch_jisho_word_furigana(word, reviewed)

    css = ' class="known"' if reviewed else ""
    assert front == f"<ruby>善<rt{css}>よ</rt></ruby>{suffix}"
    assert get.call_args_list == [
        call("https://jisho.org/word/" + word),
        call("https://jisho.org/search/" + jisho.urllib.parse.quote(word)),
    ]


def _search_concept(spelling: str, reading: str) -> str:
    return f'''<div class="concept_light">
        <div class="concept_light-representation"><span class="text">別</span></div>
        <span class="meaning-meaning"><span class="break-unit">
        {spelling} 【{reading}】</span></span></div>'''


@pytest.mark.parametrize("second_reading", ["よく", "ぜんく"])
def test_search_checks_readings_across_all_matching_concepts(second_reading: str) -> None:
    missing = MagicMock(status_code=404)
    search = MagicMock(
        status_code=200,
        text=_search_concept("善く", "よく") + _search_concept("善く", second_reading),
    )
    with patch("kanji_vocab_miner.jisho.requests.get", side_effect=[missing, search]):
        if second_reading == "よく":
            assert jisho.fetch_jisho_word_furigana("善く", set()) == (
                "<ruby>善<rt>よ</rt></ruby>く"
            )
        else:
            with pytest.raises(ValueError, match="conflicting readings for '善く'"):
                jisho.fetch_jisho_word_furigana("善く", set())


def test_search_http_failure_reports_requested_word() -> None:
    missing = MagicMock(status_code=404)
    search = MagicMock(status_code=503)
    search.raise_for_status.side_effect = jisho.requests.HTTPError("503 Unavailable")
    with (
        patch("kanji_vocab_miner.jisho.requests.get", side_effect=[missing, search]),
        pytest.raises(jisho.requests.RequestException, match="善く.*503"),
    ):
        jisho.fetch_jisho_word_furigana("善く", set())


def test_word_page_does_not_borrow_other_forms_from_another_concept() -> None:
    response = MagicMock(
        status_code=200,
        text=_search_concept("別物", "べつもの") + _search_concept("善く", "よく"),
    )
    with (
        patch("kanji_vocab_miner.jisho.requests.get", return_value=response),
        pytest.raises(ValueError, match="lists no reading for the requested spelling"),
    ):
        jisho.fetch_jisho_word_furigana("善く", set())


def test_search_skips_unrelated_results_and_requires_exact_spelling() -> None:
    missing = MagicMock(status_code=404)
    search = MagicMock(status_code=200, text=_search_concept("善くする", "よくする"))
    with (
        patch("kanji_vocab_miner.jisho.requests.get", side_effect=[missing, search]),
        pytest.raises(ValueError, match="no reading for the exact spelling '善く'"),
    ):
        jisho.fetch_jisho_word_furigana("善く", set())


@pytest.mark.parametrize("status", [403, 429, 500])
def test_furigana_does_not_search_after_other_http_errors(status: int) -> None:
    response = MagicMock(status_code=status)
    response.raise_for_status.side_effect = jisho.requests.HTTPError(str(status))
    with (
        patch("kanji_vocab_miner.jisho.requests.get", return_value=response) as get,
        pytest.raises(jisho.requests.RequestException, match="善く"),
    ):
        jisho.fetch_jisho_word_furigana("善く", set())
    get.assert_called_once_with("https://jisho.org/word/善く")


def test_furigana_reports_http_failure_with_requested_word() -> None:
    response = _make_furigana_response("メガネ", [])
    response.raise_for_status.side_effect = jisho.requests.HTTPError("404 Not Found")

    with (
        patch("kanji_vocab_miner.jisho.requests.get", return_value=response),
        pytest.raises(
            jisho.requests.RequestException,
            match="Failed to fetch furigana for '眼鏡'",
        ),
    ):
        jisho.fetch_jisho_word_furigana("眼鏡", set())


@pytest.mark.parametrize(
    "html", ["<html></html>", '<div class="concept_light-representation"></div>']
)
def test_furigana_reports_missing_word_representation(html: str) -> None:
    response = MagicMock(text=html)

    with (
        patch("kanji_vocab_miner.jisho.requests.get", return_value=response),
        pytest.raises(ValueError, match="no word representation for '眼鏡'"),
    ):
        jisho.fetch_jisho_word_furigana("眼鏡", set())


def test_furigana_does_not_substitute_an_unrelated_spelling() -> None:
    response = _make_furigana_response("メガネ", [])
    response.text += """
    <span class="meaning-meaning">
        <span class="break-unit">眼鏡違い 【めがねちがい】</span>
    </span>
    """

    with (
        patch("kanji_vocab_miner.jisho.requests.get", return_value=response),
        pytest.raises(ValueError, match="lists no reading for the requested spelling"),
    ):
        jisho.fetch_jisho_word_furigana("眼鏡", set())


@pytest.mark.parametrize(
    "characters, furigana, reviewed_kanji, expected",
    [
        ("メガネ", [], set(), "メガネ"),
        (
            "缶コーヒー",
            ["かん"],
            {"缶"},
            '<ruby>缶<rt class="known">かん</rt></ruby>コーヒー',
        ),
        (
            "<学校&>",
            ["がっ", "こう"],
            set(),
            "&lt;<ruby>学<rt>がっ</rt></ruby><ruby>校<rt>こう</rt></ruby>&amp;&gt;",
        ),
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
        # Preserve the existing grouped fallback for mixed kana/kanji spellings.
        (
            "お土産",
            ["みやげ"],
            set(),
            "<ruby>お土産<rt>みやげ</rt></ruby>",
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
