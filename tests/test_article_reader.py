"""Tests for pure Japanese article analysis and rendering."""

from html import unescape
import re

from bs4 import BeautifulSoup

from kanji_vocab_miner.article_reader import (
    ArticleToken,
    analyze_article,
    render_article_html,
)


def _visible_text(rendered: str) -> str:
    without_readings = re.sub(r"<rt[^>]*>.*?</rt>", "", rendered)
    return unescape(re.sub(r"<[^>]+>", "", without_readings))


def test_plain_non_kanji_text_passes_through_safely() -> None:
    """Kana, punctuation, Latin text, and numbers remain readable."""
    tokens = analyze_article("すごい cat! 123", set())

    rendered = render_article_html(tokens)

    assert _visible_text(rendered) == "すごい cat! 123"


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
    """A stored kana spelling matches UniDic's normalized reading candidate."""
    token = analyze_article("猫", {"ネコ"})[0]

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
    assert '<span class="token unknown jlpt-n5"><ruby>犬' in rendered


def test_particles_do_not_receive_jlpt_highlighting() -> None:
    """JLPT-list homonyms do not cause grammatical particles to be highlighted."""
    tokens = analyze_article("猫の家で食べる", set())
    particles = [token for token in tokens if token.part_of_speech == "助詞"]

    assert [token.surface for token in particles] == ["の", "で"]
    assert all(token.jlpt_level is None for token in particles)
    rendered = render_article_html(particles)
    assert "jlpt-n" not in rendered


def test_auxiliary_verbs_do_not_receive_jlpt_highlighting() -> None:
    """Grammar markers such as past-tense た remain visually neutral."""
    tokens = analyze_article("採択されたが、至っていない", set())
    auxiliaries = [token for token in tokens if token.part_of_speech == "助動詞"]

    assert [token.surface for token in auxiliaries] == ["れ", "た", "ない"]
    assert all(token.jlpt_level is None for token in auxiliaries)
    assert "jlpt-n" not in render_article_html(auxiliaries)


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
        '<span class="token unknown">未知</span>'
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
