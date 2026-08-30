"""Smoke tests for the progress dashboard rendering."""

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
            LevelBar(1, 20, 985),
        ],
        known_total=180,
        total=979,
        missing_from_deck=500,
        unranked=12,
    )
    # Coverage tapering off toward harder levels.
    levels = [
        LevelBar(5, 400, 710),
        LevelBar(4, 200, 663),
        LevelBar(3, 50, 2077),
        LevelBar(2, 0, 1731),
        LevelBar(1, 0, 2655),
    ]
    placed = sum(lb.known for lb in levels)
    vocab = VocabProgress(
        levels=levels,
        placed=placed,
        total_ranked=7836,
        unranked=30,
        total_deck=placed + 30,
    )
    return kanji, vocab


def test_progress_dashboard_renders_key_figures():
    kanji, vocab = _sample()
    manual = manual_coverage(ManualProgressCounts())
    with render.console.capture() as cap:
        render.progress_dashboard(kanji, manual, vocab)
    out = cap.get()

    # Kanji headline and N2-target denominator.
    assert "N2 target coverage" in out
    assert "979" in out
    assert "180" in out
    assert "12" in out  # kanji with no JLPT level
    # Level labels, denominator, and honesty footer.
    assert "N5" in out
    assert "N1" in out
    assert "7836" in out
    assert "30" in out  # unranked vocab


def test_progress_dashboard_renders_summary_before_detail_panels():
    kanji, vocab = _sample()
    manual = manual_coverage(
        ManualProgressCounts(
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
        out.index("Vocab — JLPT coverage"),
    ]
    assert panel_order == sorted(panel_order)

    for total in ["180/979", "6/81", "10/26", "650/7836"]:
        assert out.index(total) < panel_order[0]
        assert out.count(total) == 1

    assert out.index("1/41") > panel_order[1]
    assert "2/29" in out
    assert "3/11" in out
    assert "10/26" in out
    assert "4/10" in out
    assert "5/11" in out
    assert "1/5" in out
