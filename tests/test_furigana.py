"""Tests for Japanese cue furigana rendering."""

import re
from html import unescape

import pytest

from kanji_vocab_miner.furigana import (
    render_japanese_cue,
    render_token_furigana,
    update_furigana_visibility,
)


def test_render_japanese_cue_preserves_kana_punctuation_and_latin_text() -> None:
    """Text without kanji passes through without ruby markup."""
    assert render_japanese_cue(["すごい cat! 123"], set()) == (
        '<div class="sense">すごい cat! 123</div>'
    )


def test_render_japanese_cue_preserves_leading_and_trailing_whitespace() -> None:
    """Tokenizer gaps at sense boundaries are retained safely."""
    assert render_japanese_cue(["  猫  "], set()) == (
        '<div class="sense">  <ruby>猫<rt>ねこ</rt></ruby>  </div>'
    )


def test_render_japanese_cue_aligns_single_kanji() -> None:
    """A single-kanji token receives its hiragana reading."""
    assert render_japanese_cue(["猫"], set()) == (
        '<div class="sense"><ruby>猫<rt>ねこ</rt></ruby></div>'
    )


def test_render_japanese_cue_aligns_okurigana() -> None:
    """Ruby covers only the kanji when a kana suffix anchors the reading."""
    assert render_japanese_cue(["食べる"], set()) == (
        '<div class="sense"><ruby>食<rt>た</rt></ruby>べる</div>'
    )


def test_render_japanese_cue_aligns_kana_anchored_kanji_chunks() -> None:
    """Kana anchors allow separate ruby for multiple kanji chunks."""
    assert render_japanese_cue(["取り扱う"], set()) == (
        '<div class="sense"><ruby>取<rt>と</rt></ruby>り'
        '<ruby>扱<rt>あつか</rt></ruby>う</div>'
    )


def test_multi_kanji_chunk_leaves_kana_outside_ruby() -> None:
    assert render_token_furigana("勉強する", "べんきょうする", {"勉", "強"}) == (
        '<ruby>勉強<rt class="known">べんきょう</rt></ruby>する'
    )


def test_grouped_ruby_does_not_ignore_supplementary_kanji() -> None:
    assert render_token_furigana("𠮷田", "よしだ", {"田"}) == (
        "<ruby>𠮷田<rt>よしだ</rt></ruby>"
    )
    assert render_token_furigana("𠮷田", "よしだ", {"𠮷", "田"}) == (
        '<ruby>𠮷田<rt class="known">よしだ</rt></ruby>'
    )


def test_repeated_kana_anchor_falls_back_to_grouped_ruby() -> None:
    """The first の in もののけ belongs to 物, not to the literal anchor."""
    assert render_token_furigana("物の怪", "もののけ") == (
        "<ruby>物の怪<rt>もののけ</rt></ruby>"
    )


def test_render_japanese_cue_groups_ambiguous_compound() -> None:
    """A compound without kana anchors uses one whole-token ruby."""
    assert render_japanese_cue(["学校"], set()) == (
        '<div class="sense"><ruby>学校<rt>がっこう</rt></ruby></div>'
    )


def test_render_japanese_cue_groups_irregular_reading() -> None:
    """An irregular compound remains legible through whole-token ruby."""
    assert render_japanese_cue(["大人"], set()) == (
        '<div class="sense"><ruby>大人<rt>おとな</rt></ruby></div>'
    )


def test_grouped_ruby_is_known_only_when_every_kanji_is_reviewed() -> None:
    """A grouped reading stays visible until all represented kanji are known."""
    unreviewed = render_japanese_cue(["学校"], {"学"})
    reviewed = render_japanese_cue(["学校"], {"学", "校"})

    assert '<rt class="known">' not in unreviewed
    assert '<rt class="known">がっこう</rt>' in reviewed


def test_render_japanese_cue_escapes_source_html() -> None:
    """Dictionary text cannot inject markup into generated card HTML."""
    rendered = render_japanese_cue(["<b>猫 & 犬</b>"], set())

    assert "<b>" not in rendered
    assert "&lt;b&gt;" in rendered
    assert "&amp;" in rendered
    assert "&lt;/b&gt;" in rendered


def test_render_japanese_cue_preserves_multiple_sense_boundaries() -> None:
    """Each definition sense is emitted in its own controlled block."""
    rendered = render_japanese_cue(["猫。", "犬。"], set())

    assert rendered.count('<div class="sense">') == 2
    assert "</div><br><div" in rendered


def test_cue_uses_native_c_mode_compounds_and_contextual_reading() -> None:
    """Snapshot native compound grouping and a contextual reading."""
    assert render_japanese_cue(["国家公務員 今日"], set("国家公務員")) == (
        '<div class="sense"><ruby>国家公務員<rt class="known">'
        'こっかこうむいん</rt></ruby> <ruby>今日<rt>きょう</rt></ruby></div>'
    )


def test_cue_preserves_raw_whitespace_empty_senses_and_unknown_kanji() -> None:
    assert render_japanese_cue(["\t 猫\r\n\n\n　𠮷𠮷\r  ", "", "  "], {"猫"}) == (
        '<div class="sense">\t <ruby>猫<rt class="known">ねこ</rt></ruby>'
        '\r\n\n\n　𠮷𠮷\r  </div><br><div class="sense"></div>'
        '<br><div class="sense">  </div>'
    )


@pytest.mark.parametrize("character", ["あ", "㌖", "😀"])
def test_long_cue_preserves_source_without_reader_normalization(character: str) -> None:
    source = "\t猫。\r\n" + character * 50_000 + "\n\n\n犬  "
    rendered = render_japanese_cue([source], set())
    without_readings = re.sub(r"<rt[^>]*>.*?</rt>", "", rendered, flags=re.DOTALL)
    assert unescape(re.sub(r"<[^>]+>", "", without_readings)) == source


@pytest.mark.parametrize("reading", [None, "", "*"])
def test_missing_token_reading_is_plain_escaped_text(reading: str | None) -> None:
    assert render_token_furigana("未知<&", reading) == "未知&lt;&amp;"


def test_token_reading_cannot_inject_html() -> None:
    assert render_token_furigana("猫", "</rt><script>") == (
        '<ruby>猫<rt>&lt;/rt&gt;&lt;script&gt;</rt></ruby>'
    )


def test_cue_names_use_card_ruby_without_reader_styling() -> None:
    assert render_japanese_cue(["山田さんは東京都。"], {"山", "田", "東"}) == (
        '<div class="sense"><ruby>山田<rt class="known">やまだ</rt></ruby>'
        'さんは<ruby>東京都<rt>とうきょうと</rt></ruby>。</div>'
    )


def test_update_furigana_visibility_updates_single_kanji_ruby() -> None:
    """Existing single-kanji ruby responds to the current reviewed set."""
    html = "<ruby>猫<rt>ねこ</rt></ruby>"

    assert update_furigana_visibility(html, {"猫"}) == (
        '<ruby>猫<rt class="known">ねこ</rt></ruby>',
        True,
    )


def test_update_furigana_visibility_updates_grouped_ruby() -> None:
    """Grouped ruby is hidden only while every represented kanji is reviewed."""
    visible = "<ruby>学校<rt>がっこう</rt></ruby>"
    hidden = '<ruby>学校<rt class="known">がっこう</rt></ruby>'

    assert update_furigana_visibility(visible, {"学", "校"}) == (hidden, True)
    assert update_furigana_visibility(hidden, {"学"}) == (visible, True)
