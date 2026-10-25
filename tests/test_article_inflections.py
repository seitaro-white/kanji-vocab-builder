"""Reader-only display grouping must not change native morphology or inventories."""

import re
from html import unescape

import pytest
from bs4 import BeautifulSoup

from kanji_vocab_miner.article_reader import (
    JlptVocabularyGroup,
    VocabularyCount,
    analyze_article,
    build_unknown_vocabulary_summary,
)
from kanji_vocab_miner.article_render import render_article_html
from kanji_vocab_miner.furigana import render_japanese_cue


@pytest.mark.parametrize(
    ("source", "native_surfaces"),
    [
        ("乗った", ["乗っ", "た"]),
        ("食べました", ["食べ", "まし", "た"]),
        ("降って", ["降っ", "て"]),
        ("読んで", ["読ん", "で"]),
    ],
)
def test_inflection_shares_one_highlight_without_changing_native_tokens(
    source: str, native_surfaces: list[str]
) -> None:
    tokens = analyze_article(source, set())
    assert [token.surface for token in tokens] == native_surfaces
    parsed = BeautifulSoup(render_article_html(tokens), "html.parser")
    for reading in parsed.find_all("rt"):
        reading.decompose()

    highlighted = parsed.select(".token.jlpt-n5")
    assert [word.get_text() for word in highlighted] == [source]
    assert len(parsed.select(".token")) == 1
    assert [token.surface for token in tokens] == native_surfaces


@pytest.mark.parametrize(
    "source",
    [
        "食べませんでした", "忘れなかった", "高かった", "難しくない",
        "食べられた", "食べさせられました", "食べたい", "乗ったら",
    ],
)
def test_common_auxiliary_chains_share_the_lexical_highlight(source: str) -> None:
    parsed = BeautifulSoup(
        render_article_html(analyze_article(source, set())), "html.parser"
    )
    for reading in parsed.find_all("rt"):
        reading.decompose()
    assert [word.get_text() for word in parsed.select(".token")] == [source]
    assert any(name.startswith("jlpt-n") for name in parsed.span["class"])


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("降ってきた", ["降って", "き", "た"]),
        ("見ている", ["見て", "いる"]),
        ("乗ったので", ["乗った", "の", "で"]),
        ("乗った。犬", ["乗った", "。", "犬"]),
        ("乗っ た", ["乗っ", "た"]),
        ("乗っ\nた", ["乗っ", "た"]),
        ("猫だった", ["猫", "だっ", "た"]),
        ("一般的な", ["一般的", "な"]),
        ("子供っぽい", ["子供", "っぽい"]),
        ("山田さん", ["山田", "さん"]),
        ("食べるだけ", ["食べる", "だけ"]),
    ],
)
def test_display_grouping_stops_at_non_endings_and_source_gaps(
    source: str, expected: list[str]
) -> None:
    rendered = render_article_html(analyze_article(source, set()))
    without_readings = re.sub(r"<rt[^>]*>.*?</rt>", "", rendered)
    assert unescape(re.sub(r"<[^>]+>", "", without_readings)) == source
    parsed = BeautifulSoup(without_readings, "html.parser")
    assert [word.get_text() for word in parsed.select(".token")] == expected


@pytest.mark.parametrize("known_vocab", [False, True])
@pytest.mark.parametrize("known_kanji", [False, True])
def test_group_knowledge_and_summary_remain_independent(
    known_vocab: bool, known_kanji: bool
) -> None:
    tokens = analyze_article("乗った", {"乗る"} if known_vocab else set())
    original = tuple(tokens)
    before = build_unknown_vocabulary_summary(tokens)
    parsed = BeautifulSoup(
        render_article_html(tokens, {"乗"} if known_kanji else set()), "html.parser"
    )

    assert ("known" in parsed.span["class"]) is known_vocab
    assert ("known-kanji" in parsed.rt.get("class", [])) is known_kanji
    assert tuple(tokens) == original
    assert build_unknown_vocabulary_summary(tokens) == before
    assert before == (
        [] if known_vocab else [JlptVocabularyGroup(5, (VocabularyCount("乗る", 1),))]
    )


def test_grouped_source_and_token_readings_remain_escaped() -> None:
    source = '<b>乗った & 食べました</b>\n\n'
    rendered = render_article_html(analyze_article(source, set()))
    without_readings = re.sub(r"<rt[^>]*>.*?</rt>", "", rendered)
    assert unescape(re.sub(r"<[^>]+>", "", without_readings)) == source
    assert "<b>" not in rendered
    assert "&lt;" in rendered
    assert "&amp;" in rendered


@pytest.mark.parametrize("source", ["蠢いた", "きた"])
def test_display_grouping_does_not_invent_jlpt_levels(source: str) -> None:
    rendered = render_article_html(analyze_article(source, set()))
    assert "jlpt-n" not in rendered
    without_readings = re.sub(r"<rt[^>]*>.*?</rt>", "", rendered)
    assert unescape(re.sub(r"<[^>]+>", "", without_readings)) == source


def test_grouping_keeps_ruby_alignment_and_anki_cues_unchanged() -> None:
    tokens = analyze_article("食べました", {"食べる"})
    assert render_article_html(tokens, {"食"}) == (
        '<span class="token known jlpt-n5"><ruby>食<rt class="known-kanji">'
        'た</rt></ruby>べました</span>'
    )
    assert render_japanese_cue(["食べました"], {"食"}) == (
        '<div class="sense"><ruby>食<rt class="known">た</rt></ruby>べました</div>'
    )
