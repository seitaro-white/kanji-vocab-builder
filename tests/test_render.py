"""Smoke tests for the progress dashboard rendering."""

from datetime import date

import pytest

from kanji_vocab_miner import render
from kanji_vocab_miner.review_status import KanjiReviewStatus
from kanji_vocab_miner.jisho import JishoWord, KanjiSummary
from kanji_vocab_miner.progress import (
    KanjiProgress,
    LevelBar,
    ManualProgressCounts,
    VocabProgress,
    manual_coverage,
)


def test_welcome_message_shows_jlpt_countdown(monkeypatch):
    monkeypatch.setattr(
        render.countdown,
        "format_jlpt_countdown",
        lambda: "JLPT N2 exam countdown: 259 days (37 weeks)",
    )

    with render.console.capture() as cap:
        render.welcome_message()

    assert "JLPT N2 exam countdown: 259 days (37 weeks)" in cap.get()


@pytest.mark.parametrize(
    ("status", "label"),
    [
        (KanjiReviewStatus.REVIEWED, "Reviewed"),
        (KanjiReviewStatus.NOT_REVIEWED, "Not reviewed"),
        (KanjiReviewStatus.NOT_IN_DECK, "Not in deck"),
        (KanjiReviewStatus.UNKNOWN, "Unknown"),
    ],
)
def test_kanji_summary_shows_review_status(status, label):
    summary = KanjiSummary(
        kanji="学",
        meanings=["study"],
        kun_readings=["まな.ぶ"],
        on_readings=["ガク"],
        jlpt=5,
    )

    with render.console.capture() as cap:
        render.kanji_summary(summary, status)

    output = cap.get()
    assert "Review status" in output
    assert label in output


def test_words_table_shows_frequency_band():
    word = JishoWord(
        expression="日本", kana="にほん", jlpt=5,
        definitions=["Japan"], parts_of_speech=["n"],
    )
    with render.console.capture() as cap:
        render.words_table([(word, False)], [], {"日本": 2})  # band 2 -> top 1k
    assert "top 1k" in cap.get()


def test_words_table_shows_jlpt_level():
    # 日本 is N3 in the vendored JLPT index, which wins over the word's own
    # (live-scraped) jlpt=5 tag.
    word = JishoWord(
        expression="日本", kana="にほん", jlpt=5,
        definitions=["Japan"], parts_of_speech=["n"],
    )
    with render.console.capture() as cap:
        render.words_table([(word, False)], [])
    assert "N3" in cap.get()


def _sample():
    kanji = KanjiProgress(
        levels=[
            LevelBar(5, 70, 79),
            LevelBar(4, 60, 166),
            LevelBar(3, 40, 367),
            LevelBar(2, 10, 367),
        ],
        known_total=180,
        total=979,
        missing_from_deck=500,
        unranked=12,
    )
    vocab = VocabProgress(known=4425, total=6000)
    return kanji, vocab


@pytest.mark.parametrize(
    ("category", "expected_colour"),
    [
        ("kanji", "#d47728"),
        ("vocab", "#528bc0"),
        ("grammar", "#5a9b66"),
        ("reading", "#b47d59"),
    ],
)
def test_progress_bars_use_fixed_category_colours(category, expected_colour):
    bar = render._bar(1, 2, render.PROGRESS_COLORS[category])

    assert bar.spans[0].style == expected_colour


def test_progress_bar_colour_does_not_change_with_completion():
    colour = render.PROGRESS_COLORS["kanji"]

    assert render._bar(1, 10, colour).spans[0].style == colour
    assert render._bar(9, 10, colour).spans[0].style == colour


def test_detail_grid_scales_tracks_to_largest_total(monkeypatch):
    widths = []

    def capture_bar(known, total, colour, width=24):
        widths.append(width)
        return render.Text()

    monkeypatch.setattr(render, "_bar", capture_bar)
    render._progress_grid(
        [("I", 1, 40, "red"), ("II", 1, 20, "red"), ("III", 1, 10, "red")],
        scale_totals=True,
    )

    assert widths == [24, 12, 6]


def test_summary_grid_keeps_independent_bars_full_width(monkeypatch):
    widths = []

    def capture_bar(known, total, colour, width=24):
        widths.append(width)
        return render.Text()

    monkeypatch.setattr(render, "_bar", capture_bar)
    render._progress_grid(
        [("Grammar", 1, 26, "green"), ("Vocab", 1, 6000, "blue")]
    )

    assert widths == [24, 24]


def test_progress_dashboard_shows_jlpt_countdown_first(monkeypatch):
    kanji, vocab = _sample()
    manual = manual_coverage(
        ManualProgressCounts(
            vocab_baseline=4400,
            vocab_tracking_start=date(2026, 9, 3),
        )
    )
    countdown_text = "JLPT N2 exam countdown: 259 days (37 weeks)"
    monkeypatch.setattr(
        render.countdown, "format_jlpt_countdown", lambda: countdown_text
    )

    with render.console.capture() as cap:
        render.progress_dashboard(kanji, manual, vocab)
    out = cap.get()

    assert out.startswith(countdown_text)
    assert out.index(countdown_text) < out.index("Kanji")


def test_progress_dashboard_renders_key_figures():
    kanji, vocab = _sample()
    manual = manual_coverage(
        ManualProgressCounts(
            vocab_baseline=4400,
            vocab_tracking_start=date(2026, 9, 3),
        )
    )
    with render.console.capture() as cap:
        render.progress_dashboard(kanji, manual, vocab)
    out = cap.get()

    # Kanji headline and N2-target denominator.
    assert "N2 target coverage" in out
    assert "979" in out
    assert "180" in out
    assert "12" in out  # kanji with no JLPT level
    assert "N1" not in out
    # Vocabulary is one core-6k bar, with no JLPT breakdown panel.
    assert "4425/6000" in out
    assert "Vocab — JLPT coverage" not in out


def test_progress_dashboard_renders_summary_before_detail_panels():
    kanji, vocab = _sample()
    manual = manual_coverage(
        ManualProgressCounts(
            vocab_baseline=4400,
            vocab_tracking_start=date(2026, 9, 3),
            reading_i=1,
            reading_ii=2,
            reading_iii=3,
            grammar_i=4,
            grammar_ii=5,
            grammar_iii=1,
        )
    )

    with render.console.capture() as cap:
        render.progress_dashboard(kanji, manual, vocab)
    out = cap.get()

    panel_order = [
        out.index("Kanji — N2 target coverage"),
        out.index("Reading — textbook coverage"),
        out.index("Grammar — textbook coverage"),
    ]
    assert panel_order == sorted(panel_order)

    for total in ["180/979", "6/81", "10/26", "4425/6000"]:
        assert out.index(total) < panel_order[0]
        assert out.count(total) == 1

    assert out.index("1/41") > panel_order[1]
    assert "2/29" in out
    assert "3/11" in out
    assert "10/26" in out
    assert "4/10" in out
    assert "5/11" in out
    assert "1/5" in out
