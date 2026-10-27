"""Tests for pure Japanese article analysis and rendering."""

import re
from html import unescape

import pytest
from bs4 import BeautifulSoup

from kanji_vocab_miner.article_reader import (
    ArticleToken,
    JlptVocabularyGroup,
    VocabularyCount,
    analyze_article,
    build_unknown_vocabulary_summary,
)
from kanji_vocab_miner.article_render import render_article_html


def _visible_text(rendered: str) -> str:
    without_readings = re.sub(r"<rt[^>]*>.*?</rt>", "", rendered)
    return unescape(re.sub(r"<[^>]+>", "", without_readings))


def test_sudachi_c_mode_keeps_native_compounds_as_single_tokens() -> None:
    """Use native coarse segmentation rather than a custom compound matcher."""
    tokens = analyze_article("国家公務員 情報処理 人工知能", set())

    assert [token.surface for token in tokens] == [
        "国家公務員", "情報処理", "人工知能"
    ]


def test_part_of_speech_has_named_native_fields() -> None:
    """Expose native POS meanings without positional tuple access in application code."""
    person = analyze_article("山田", set())[0].part_of_speech
    assert person is not None
    assert person.category == "名詞"
    assert person.subcategory == "固有名詞"
    assert person.subclass == "人名"
    assert person.detail == "姓"

    verb = analyze_article("食べました", set())[0].part_of_speech
    assert verb is not None
    assert verb.category == "動詞"
    assert verb.conjugation_type == "下一段-バ行"
    assert verb.conjugation_form == "連用形-一般"


def test_plain_non_kanji_text_passes_through_safely() -> None:
    """Kana, punctuation, Latin text, and numbers remain readable."""
    tokens = analyze_article("すごい cat! 123", set())

    rendered = render_article_html(tokens)

    assert _visible_text(rendered) == "すごい cat! 123"


@pytest.mark.parametrize("character", ["あ", "㍻", "㌖", "😀"])
def test_long_normalized_input_remains_within_parser_limits(character: str) -> None:
    """The reader's character limit must also respect Sudachi's byte limits."""
    source = character * 16_000
    tokens = analyze_article(source, set())
    reconstructed = "".join(t.leading_whitespace + t.surface for t in tokens)
    assert reconstructed == source
    assert _visible_text(render_article_html(tokens)) == source


def test_html_like_input_is_escaped() -> None:
    """Pasted markup is displayed as text rather than injected."""
    rendered = render_article_html(analyze_article('<script>alert("x")</script>', set()))

    parsed = BeautifulSoup(rendered, "html.parser")
    assert parsed.find("script") is None
    assert parsed.get_text() == '<script>alert("x")</script>'


def test_whitespace_blank_lines_and_trailing_space_are_preserved() -> None:
    """Article layout survives tokenization and rendering exactly."""
    source = "  猫\n\n犬  "

    rendered = render_article_html(analyze_article(source, set()))

    assert _visible_text(rendered) == source


def test_repeated_blank_lines_collapse_to_one_between_paragraphs() -> None:
    """Runs of blank lines render as one consistent paragraph gap."""
    source = "猫\n\n\n\n犬"
    rendered = render_article_html(analyze_article(source, set()))

    assert _visible_text(rendered) == "猫\n\n犬"


def test_inflected_verb_exposes_dictionary_identity() -> None:
    """A content token includes its lemma before its inflected surface."""
    tokens = analyze_article("食べました", set())

    assert tokens[0].identities[0] == "食べる"
    assert tokens[0].surface == "食べ"


def test_dictionary_identity_matches_a_known_inflected_word() -> None:
    """Known vocabulary is compared against normalized token candidates."""
    tokens = analyze_article("食べました", {"食べる"})

    assert tokens[0].is_known is True


def test_kana_identity_matches_across_kana_scripts() -> None:
    """An actual kana spelling matches across scripts, without kanji homophones."""
    token = analyze_article("ネコ", {"ねこ"})[0]

    assert "ねこ" in token.identities
    assert token.is_known is True


def test_kanji_homophones_do_not_match_through_their_readings() -> None:
    """A stored kanji spelling is not converted to kana to force a match."""
    token = analyze_article("橋", {"箸"})[0]

    assert token.is_known is False


def test_known_components_do_not_make_a_compound_known() -> None:
    """Matching remains token-based rather than compositional."""
    token = analyze_article("学校", {"学", "校"})[0]

    assert token.is_known is False


def test_jlpt_level_uses_word_identities_without_kanji_fallback() -> None:
    """Listed words get their level while unlisted words stay neutral."""
    listed = analyze_article("猫", set())[0]
    unlisted = analyze_article("電脳", set())[0]

    assert listed.jlpt_level == 5
    assert unlisted.jlpt_level is None


def test_known_and_unknown_tokens_receive_semantic_classes() -> None:
    """Rendered token wrappers expose known status and JLPT level to CSS."""
    rendered = render_article_html(analyze_article("猫 犬", {"猫"}))

    assert '<span class="token known jlpt-n5"><ruby>猫' in rendered
    assert '<span class="token unknown jlpt-n5" data-reading-level="5"><ruby>犬' in rendered


def test_vocabulary_summary_filters_then_counts_dictionary_forms_by_level() -> None:
    analyzed_tokens = analyze_article(
        "猫 食べた 食べます 犬 電脳 山田さん きょう", {"猫"}
    )
    original_tokens = tuple(analyzed_tokens)

    summary = build_unknown_vocabulary_summary(analyzed_tokens)

    assert summary == [
        JlptVocabularyGroup(
            jlpt_level=5,
            word_counts=(VocabularyCount("食べる", 2), VocabularyCount("犬", 1)),
        ),
        JlptVocabularyGroup(
            jlpt_level=None,
            word_counts=(VocabularyCount("電脳", 1),),
        ),
    ]
    # The article-rendering branch still receives every original token.
    assert tuple(analyzed_tokens) == original_tokens
    assert any(token.surface == "猫" for token in analyzed_tokens)


def test_kana_grammar_and_standalone_affixes_are_not_vocabulary() -> None:
    """The display and unknown dictionary share the kanji/POS eligibility rule."""
    tokens = analyze_article("きょう とても ゆっくり 一般的 子供っぽい", set())
    kana = [token for token in tokens if token.surface in {"きょう", "とても", "ゆっくり", "っぽい"}]
    suffixes = [
        token for token in tokens
        if token.part_of_speech and token.part_of_speech.category == "接尾辞"
    ]

    assert all(token.jlpt_level is None for token in kana + suffixes)
    dictionary_forms = [
        word.dictionary_form
        for group in build_unknown_vocabulary_summary(tokens)
        for word in group.word_counts
    ]
    assert dictionary_forms == ["子供", "一般的"]


def test_particles_do_not_receive_jlpt_highlighting() -> None:
    """JLPT-list homonyms do not cause grammatical particles to be highlighted."""
    tokens = analyze_article("猫の家で食べる", set())
    particles = [
        token for token in tokens
        if token.part_of_speech and token.part_of_speech.category == "助詞"
    ]

    assert [token.surface for token in particles] == ["の", "で"]
    assert all(token.jlpt_level is None for token in particles)
    rendered = render_article_html(particles)
    assert "jlpt-n" not in rendered


def test_auxiliary_verbs_do_not_receive_jlpt_highlighting() -> None:
    """Grammar markers such as past-tense た remain visually neutral."""
    tokens = analyze_article("採択されたが、至っていない", set())
    auxiliaries = [
        token for token in tokens
        if token.part_of_speech and token.part_of_speech.category == "助動詞"
    ]

    assert [token.surface for token in auxiliaries] == ["れ", "た", "ない"]
    assert all(token.jlpt_level is None for token in auxiliaries)
    assert "jlpt-n" not in render_article_html(auxiliaries)


def test_furigana_uses_kanji_knowledge_independently_of_vocabulary() -> None:
    """Known vocab can need ruby, and unknown vocab can have all-known kanji."""
    tokens = analyze_article("図書館 学生 日本語 生き物", {"図書館"})
    rendered = render_article_html(tokens, known_kanji=set("学生日本"))
    parsed = BeautifulSoup(rendered, "html.parser")
    words = parsed.find_all("span", class_="token")

    assert "known" in words[0]["class"]
    assert words[0].rt.get("class", []) == []
    assert "unknown" in words[1]["class"]
    assert words[1].rt["class"] == ["known-kanji"]
    assert words[2].rt.get("class", []) == []  # 語 remains unknown.
    assert [rt.get("class", []) for rt in words[3].find_all("rt")] == [
        ["known-kanji"], []
    ]
    assert render_article_html(analyze_article("学生", {"学生"}), set("学生")) == (
        render_article_html(analyze_article("学生", set()), set("学生"))
        .replace('token unknown', 'token known')
        .replace(' data-reading-level="5"', '')
    )


@pytest.mark.parametrize("is_known_vocab", [False, True])
@pytest.mark.parametrize(
    ("known_kanji", "expected_classes"),
    [(set(), []), (set("日本"), []), (set("日本語"), ["known-kanji"])],
)
def test_grouped_ruby_knowledge_matrix(
    is_known_vocab: bool, known_kanji: set[str], expected_classes: list[str]
) -> None:
    vocabulary = {"日本語"} if is_known_vocab else set()
    rendered = render_article_html(analyze_article("日本語", vocabulary), known_kanji)
    parsed = BeautifulSoup(rendered, "html.parser")
    assert parsed.rt.get("class", []) == expected_classes
    assert ("known" in parsed.span["class"]) is is_known_vocab


def test_native_person_and_place_tags_receive_name_styling_only() -> None:
    """Names need just parser tags and styling, not a separate name recognizer."""
    tokens = analyze_article("山田さんは東京都で研究。株式会社", set())
    rendered = render_article_html(tokens)
    parsed = BeautifulSoup(rendered, "html.parser")
    names = parsed.select(".name")

    assert [name["title"] for name in names] == ["Person name", "Place name"]
    assert [token.surface for token in tokens if token.name_kind] == ["山田", "東京都"]
    assert all("jlpt-n" not in str(name.get("class")) for name in names)
    dictionary_forms = [
        word.dictionary_form
        for group in build_unknown_vocabulary_summary(tokens)
        for word in group.word_counts
    ]
    assert "山田" not in dictionary_forms
    assert "東京都" not in dictionary_forms
    assert "研究" in dictionary_forms
    assert "name" not in parsed.find_all("span", class_="token")[-1]["class"]


def test_okurigana_receives_kanji_chunk_ruby() -> None:
    """Kana anchors keep okurigana outside the ruby element."""
    rendered = render_article_html(analyze_article("食べる", set()))

    assert "<ruby>食<rt>た</rt></ruby>べる" in rendered


def test_irregular_reading_uses_whole_token_ruby() -> None:
    """An unanchored irregular reading remains legible as grouped ruby."""
    rendered = render_article_html(analyze_article("大人", set()))

    assert "<ruby>大人<rt>おとな</rt></ruby>" in rendered


def test_missing_reading_preserves_surface_without_ruby() -> None:
    """Unknown kanji are not assigned a guessed reading."""
    token = ArticleToken("未知", "", None, ("未知",), False, None)

    assert render_article_html([token]) == (
        '<span class="token unknown" data-reading-level="0">未知</span>'
    )


def test_surface_and_reading_are_escaped_before_markup() -> None:
    """Application markup never interpolates unescaped analyzed strings."""
    token = ArticleToken(
        "猫<script>", "", "ねこ</rt><script>", ("猫",), False, None
    )
    rendered = render_article_html([token])

    assert "<script>" not in rendered
    assert "猫&lt;script&gt;" in rendered
    assert "ねこ&lt;/rt&gt;&lt;script&gt;" in rendered
