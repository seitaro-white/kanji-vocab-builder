"""Tests for Japanese cue furigana rendering."""

from kanji_vocab_miner.furigana import (
    render_japanese_cue,
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
    assert "</div><div" in rendered


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
