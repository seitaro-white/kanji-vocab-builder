"""Specifications for visible CLI tables and progress dashboards."""

import re

import pytest
from rich.console import Console

from kanji_vocab_miner import render
from kanji_vocab_miner.jisho import JishoWord, KanjiSummary
from kanji_vocab_miner.progress import (
    KanjiProgress,
    LevelBar,
    ManualProgress,
    ManualProgressBar,
    VocabProgress,
)
from kanji_vocab_miner.review_status import KanjiReviewStatus


@pytest.fixture
def console(monkeypatch) -> Console:
    console = Console(width=140, record=True)
    monkeypatch.setattr(render, "console", console)
    return console


@pytest.fixture
def dashboard_data() -> tuple[KanjiProgress, ManualProgress, VocabProgress]:
    return (
        KanjiProgress(
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
        ),
        ManualProgress(
            reading=(
                ManualProgressBar("Total", 6, 81),
                ManualProgressBar("I", 1, 41),
                ManualProgressBar("II", 2, 29),
                ManualProgressBar("III", 3, 11),
            ),
            grammar=(
                ManualProgressBar("Total", 10, 48),
                ManualProgressBar("I", 4, 10),
                ManualProgressBar("II", 5, 11),
                ManualProgressBar("III", 1, 5),
                ManualProgressBar("IV", 0, 7),
                ManualProgressBar("V", 0, 3),
                ManualProgressBar("VI", 0, 12),
            ),
        ),
        VocabProgress(known=4425, total=6000),
    )


def test_welcome_message_shows_jlpt_countdown(monkeypatch, console):
    countdown = "JLPT N2 exam countdown: 259 days (37 weeks)"
    monkeypatch.setattr(render.countdown, "format_jlpt_countdown", lambda: countdown)

    with console.capture() as capture:
        render.welcome_message()

    assert countdown in capture.get()


@pytest.mark.parametrize(
    ("status", "label"),
    [
        (KanjiReviewStatus.REVIEWED, "Reviewed"),
        (KanjiReviewStatus.NOT_REVIEWED, "Not reviewed"),
        (KanjiReviewStatus.NOT_IN_DECK, "Not in deck"),
        (KanjiReviewStatus.UNKNOWN, "Unknown"),
    ],
)
def test_kanji_summary_shows_review_status(status, label, console):
    summary = KanjiSummary(
        kanji="学", meanings=["study"], kun_readings=["まな.ぶ"],
        on_readings=["ガク"], jlpt=5,
    )

    with console.capture() as capture:
        render.kanji_summary(summary, status)

    output = capture.get()
    assert "Review status" in output
    assert label in output


def test_words_table_shows_frequency_band(console):
    word = JishoWord(
        expression="日本", kana="にほん", jlpt=5,
        definitions=["Japan"], parts_of_speech=["n"],
    )

    with console.capture() as capture:
        render.words_table([(word, False)], [], {"日本": 2})

    assert "top 1k" in capture.get()


def test_words_table_prefers_vendored_jlpt_level_to_jisho_tag(console):
    word = JishoWord(
        expression="日本", kana="にほん", jlpt=5,
        definitions=["Japan"], parts_of_speech=["n"],
    )

    with console.capture() as capture:
        render.words_table([(word, False)], [])

    assert "N3" in capture.get()


@pytest.mark.parametrize(
    ("label", "expected_colour"),
    [
        ("Kanji", "#d47728"),
        ("Vocab", "#528bc0"),
        ("Grammar", "#5a9b66"),
        ("Reading", "#b47d59"),
    ],
)
def test_dashboard_summary_bars_use_subject_colours(
    label, expected_colour, dashboard_data, console
):
    render.progress_dashboard(*dashboard_data)
    output = console.export_text(styles=True)
    line = next(line for line in output.splitlines() if label in line)

    assert _coloured_fill(expected_colour) in line


@pytest.mark.parametrize("known", [1, 9])
def test_kanji_bar_colour_is_independent_of_completion(
    known, dashboard_data, console
):
    _, manual, vocab = dashboard_data
    kanji = KanjiProgress([LevelBar(5, known, 10)], known, 10, 0, 0)

    render.progress_dashboard(kanji, manual, vocab)
    line = next(
        line for line in console.export_text(styles=True).splitlines()
        if "Kanji" in line
    )

    assert _coloured_fill("#d47728") in line


def test_dashboard_detail_tracks_scale_with_section_totals(dashboard_data, console):
    kanji, _, vocab = dashboard_data
    manual = ManualProgress(
        reading=(
            ManualProgressBar("Total", 3, 70),
            ManualProgressBar("I", 1, 40),
            ManualProgressBar("II", 1, 20),
            ManualProgressBar("III", 1, 10),
        ),
        grammar=(
            ManualProgressBar("Total", 1, 26),
            ManualProgressBar("I", 1, 26),
        ),
    )

    with console.capture() as capture:
        render.progress_dashboard(kanji, manual, vocab)
    tracks = _track_lengths(capture.get())

    assert tracks["1/40"] == 2 * tracks["1/20"]
    assert tracks["1/40"] == 4 * tracks["1/10"]


def test_dashboard_summary_tracks_have_equal_lengths(dashboard_data, console):
    with console.capture() as capture:
        render.progress_dashboard(*dashboard_data)
    tracks = _track_lengths(capture.get())

    assert (
        tracks["180/979"] == tracks["6/81"]
        == tracks["10/48"] == tracks["4425/6000"]
    )


def test_progress_dashboard_shows_jlpt_countdown_first(
    monkeypatch, dashboard_data, console
):
    countdown = "JLPT N2 exam countdown: 259 days (37 weeks)"
    monkeypatch.setattr(render.countdown, "format_jlpt_countdown", lambda: countdown)

    with console.capture() as capture:
        render.progress_dashboard(*dashboard_data)

    assert capture.get().startswith(countdown)


def test_progress_dashboard_renders_key_figures(dashboard_data, console):
    with console.capture() as capture:
        render.progress_dashboard(*dashboard_data)
    output = capture.get()

    assert "N2 target coverage" in output
    assert "180/979" in output
    assert "12 reviewed kanji with no JLPT level" in output
    assert "N1" not in output
    assert "4425/6000" in output
    assert "Vocab — JLPT coverage" not in output


def test_progress_dashboard_renders_summary_before_detail_panels(
    dashboard_data, console
):
    with console.capture() as capture:
        render.progress_dashboard(*dashboard_data)
    output = capture.get()
    panel_order = [
        output.index("Kanji — N2 target coverage"),
        output.index("Reading — textbook coverage"),
        output.index("Grammar — textbook coverage"),
    ]

    assert panel_order == sorted(panel_order)
    for total in ["180/979", "6/81", "10/48", "4425/6000"]:
        assert output.index(total) < panel_order[0]
        assert output.count(total) == 1
    assert output.index("1/41") > panel_order[1]
    for total in ["2/29", "3/11", "4/10", "5/11", "1/5", "0/7", "0/3", "0/12"]:
        assert total in output


def _track_lengths(output: str) -> dict[str, int]:
    return {
        count: len(track)
        for track, count in re.findall(r"([█░]+)\s+(\d+/\d+)", output)
    }


def _coloured_fill(colour: str) -> str:
    rgb = [str(int(colour[index : index + 2], 16)) for index in (1, 3, 5)]
    return "\x1b[38;2;" + ";".join(rgb) + "m█"
