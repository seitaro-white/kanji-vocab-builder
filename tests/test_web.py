"""Tests for the localhost article reader web boundary."""

from bs4 import BeautifulSoup

from kanji_vocab_miner.web import create_app


def test_get_root_shows_editor_and_submit_control() -> None:
    app = create_app(expression_loader=set, known_loader=set)

    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b'<textarea name="text"' in response.data
    assert b'type="submit"' in response.data


def test_empty_text_returns_inline_validation_error() -> None:
    app = create_app(expression_loader=set, known_loader=set)

    response = app.test_client().post("/", data={"text": "   \n"})

    assert response.status_code == 400
    assert b"Paste some Japanese text" in response.data
    assert b'<textarea name="text"' in response.data


def test_fifty_thousand_characters_are_accepted() -> None:
    app = create_app(expression_loader=set, known_loader=set)

    response = app.test_client().post("/", data={"text": "あ" * 50_000})

    assert response.status_code == 200
    assert b"50,000-character limit" not in response.data


def test_over_limit_is_rejected_before_loading_anki() -> None:
    calls: list[None] = []

    def load_expressions() -> set[str]:
        calls.append(None)
        return set()

    app = create_app(expression_loader=load_expressions, known_loader=set)
    response = app.test_client().post("/", data={"text": "あ" * 50_001})

    assert response.status_code == 400
    assert b"50,000-character limit" in response.data
    assert calls == []


def test_anki_and_manual_known_vocabulary_are_unioned() -> None:
    app = create_app(
        expression_loader=lambda: {"猫"},
        known_loader=lambda: {"犬"},
    )

    response = app.test_client().post("/", data={"text": "猫 犬 鳥"})

    assert response.status_code == 200
    assert response.data.count(b'class="token known ') == 2
    assert b'class="token unknown ' in response.data


def test_anki_loader_runs_once_per_valid_submission() -> None:
    calls = 0

    def load_expressions() -> set[str]:
        nonlocal calls
        calls += 1
        return set()

    app = create_app(expression_loader=load_expressions, known_loader=set)

    response = app.test_client().post("/", data={"text": "猫"})

    assert response.status_code == 200
    assert calls == 1


def test_anki_failure_blocks_output_and_preserves_source() -> None:
    def unavailable() -> set[str]:
        raise RuntimeError("private connector details")

    app = create_app(expression_loader=unavailable, known_loader=set)
    response = app.test_client().post("/", data={"text": "猫 & 犬"})

    assert response.status_code == 503
    assert b"Start Anki and make sure AnkiConnect is enabled" in response.data
    assert b"private connector details" not in response.data
    assert "猫 &amp; 犬".encode() in response.data
    assert b'<textarea name="text"' in response.data


def test_success_replaces_editor_with_controls_and_start_over() -> None:
    app = create_app(expression_loader=set, known_loader=set)

    response = app.test_client().post("/", data={"text": "猫"})

    assert response.status_code == 200
    assert b'<textarea name="text"' not in response.data
    assert b"Unknown only" in response.data
    assert b"All furigana" in response.data
    assert b"No furigana" in response.data
    assert b"Start Over" in response.data


def test_pasted_markup_is_displayed_as_text() -> None:
    app = create_app(expression_loader=set, known_loader=set)

    response = app.test_client().post(
        "/", data={"text": '<script>alert("x")</script>'}
    )

    parsed = BeautifulSoup(response.data, "html.parser")
    assert parsed.find("article").find("script") is None
    assert '<script>alert("x")</script>' in parsed.get_text()


def test_default_result_mode_is_unknown_only() -> None:
    app = create_app(expression_loader=set, known_loader=set)

    response = app.test_client().post("/", data={"text": "猫"})

    assert b"furigana-mode-unknown" in response.data
    assert b'data-furigana-mode="unknown" aria-pressed="true"' in response.data


def test_unexpected_processing_failure_returns_safe_message() -> None:
    def broken_known_loader() -> set[str]:
        raise RuntimeError("sensitive processing details")

    app = create_app(expression_loader=set, known_loader=broken_known_loader)
    response = app.test_client().post("/", data={"text": "猫"})

    assert response.status_code == 500
    assert b"Could not process this article" in response.data
    assert b"sensitive processing details" not in response.data
    assert "猫".encode() in response.data


def test_known_jlpt_highlighting_defaults_off_with_toggle() -> None:
    app = create_app(expression_loader=lambda: {"猫"}, known_loader=set)

    response = app.test_client().post("/", data={"text": "猫 犬"})

    assert b'class="article furigana-mode-unknown jlpt-highlight-unknown"' in response.data
    assert b'data-jlpt-toggle aria-pressed="false"' in response.data
    assert b"Highlight known words" in response.data


def test_jlpt_toggle_has_client_side_style_and_script_hooks() -> None:
    app = create_app(expression_loader=set, known_loader=set)
    client = app.test_client()

    css = client.get("/static/article_reader.css").data
    javascript = client.get("/static/article_reader.js").data

    assert b".jlpt-highlight-unknown .known.jlpt-n5" in css
    assert b'querySelector("[data-jlpt-toggle]")' in javascript
    assert b'"jlpt-highlight-all"' in javascript


def test_result_dictionary_lists_unknown_words_but_not_known_words() -> None:
    app = create_app(expression_loader=lambda: {"猫"}, known_loader=set)

    response = app.test_client().post("/", data={"text": "猫 犬"})

    parsed = BeautifulSoup(response.data, "html.parser")
    dictionary = parsed.find(id="unknown-dictionary")
    assert dictionary is not None
    assert "犬 × 1" in dictionary.get_text(" ", strip=True)
    assert "猫" not in dictionary.get_text(" ", strip=True)


def test_dictionary_combines_inflections_and_sorts_by_frequency() -> None:
    app = create_app(expression_loader=set, known_loader=set)

    response = app.test_client().post(
        "/", data={"text": "猫 食べた 食べます 猫 食べる"}
    )

    parsed = BeautifulSoup(response.data, "html.parser")
    n5_section = parsed.find("h3", string="N5").parent
    assert [item.get_text(" ", strip=True) for item in n5_section.find_all("li")] == [
        "食べる × 3",
        "猫 × 2",
    ]


def test_dictionary_groups_run_from_n5_to_n1_then_unlisted() -> None:
    app = create_app(expression_loader=set, known_loader=set)

    response = app.test_client().post(
        "/", data={"text": "取り扱う 電脳 一流 政府 経済 犬"}
    )

    parsed = BeautifulSoup(response.data, "html.parser")
    dictionary = parsed.find(id="unknown-dictionary")
    assert [heading.get_text(strip=True) for heading in dictionary.find_all("h3")] == [
        "N5",
        "N4",
        "N3",
        "N2",
        "N1",
        "Unlisted",
    ]


def test_equal_frequency_words_keep_first_appearance_order() -> None:
    app = create_app(expression_loader=set, known_loader=set)

    response = app.test_client().post("/", data={"text": "犬 猫 犬 猫"})

    parsed = BeautifulSoup(response.data, "html.parser")
    n5_section = parsed.find("h3", string="N5").parent
    assert [item.get_text(" ", strip=True) for item in n5_section.find_all("li")] == [
        "犬 × 2",
        "猫 × 2",
    ]


def test_dictionary_omits_non_vocabulary_tokens() -> None:
    app = create_app(expression_loader=set, known_loader=set)

    response = app.test_client().post("/", data={"text": "食べた cat 123。"})

    parsed = BeautifulSoup(response.data, "html.parser")
    entries = [
        item.get_text(" ", strip=True)
        for item in parsed.find(id="unknown-dictionary").find_all("li")
    ]
    assert entries == ["食べる × 1"]


def test_page_includes_local_assets_and_jlpt_legend() -> None:
    app = create_app(expression_loader=set, known_loader=set)

    response = app.test_client().post("/", data={"text": "猫"})

    assert b'article_reader.css' in response.data
    assert b'article_reader.js' in response.data
    for level in range(1, 6):
        assert f"N{level}".encode() in response.data
