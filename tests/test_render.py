"""Smoke tests for the progress dashboard rendering."""

from kanji_vocab_miner import render
from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.progress import KanjiProgress, LevelBar, VocabProgress


def test_welcome_message_shows_jlpt_countdown(monkeypatch):
    monkeypatch.setattr(
        render.countdown,
        "format_jlpt_countdown",
        lambda: "JLPT N2 exam countdown: 259 days (37 weeks)",
    )

    with render.console.capture() as cap:
        render.welcome_message()

    assert "JLPT N2 exam countdown: 259 days (37 weeks)" in cap.get()


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
            LevelBar(5, 80, 300),
            LevelBar(4, 60, 300),
            LevelBar(3, 40, 400),
            LevelBar(2, 0, 500),
            LevelBar(1, 0, 464),
        ],
        known_total=180,
        total=2136,
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
    with render.console.capture() as cap:
        render.progress_dashboard(kanji, vocab)
    out = cap.get()

    # Kanji headline and denominator.
    assert "2136" in out
    assert "180" in out
    assert "12" in out  # kanji with no JLPT level
    # Level labels, denominator, and honesty footer.
    assert "N5" in out
    assert "N1" in out
    assert "7836" in out
    assert "30" in out  # unranked vocab
