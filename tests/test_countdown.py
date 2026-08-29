"""Tests for the JLPT N2 exam countdown."""

from datetime import date

from kanji_vocab_miner.countdown import format_jlpt_countdown


def test_countdown_formats_weeks_and_remaining_days():
    assert format_jlpt_countdown(date(2026, 11, 28)) == (
        "JLPT N2 exam countdown: 8 days (1 week, 1 day)"
    )


def test_countdown_uses_singular_day():
    assert format_jlpt_countdown(date(2026, 12, 5)) == (
        "JLPT N2 exam countdown: 1 day (0 weeks, 1 day)"
    )


def test_countdown_is_zero_on_exam_day():
    assert format_jlpt_countdown(date(2026, 12, 6)) == (
        "JLPT N2 exam countdown: 0 days (0 weeks)"
    )


def test_countdown_stays_signed_after_exam():
    assert format_jlpt_countdown(date(2026, 12, 14)) == (
        "JLPT N2 exam countdown: -8 days (-1 week, -1 day)"
    )
