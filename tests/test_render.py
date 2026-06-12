"""Smoke tests for the progress dashboard rendering."""

from kanji_vocab_miner import render
from kanji_vocab_miner.jisho import JishoWord
from kanji_vocab_miner.progress import BandCell, GradeBar, KanjiProgress, VocabProgress


def test_words_table_shows_frequency_band():
    word = JishoWord(
        expression="日本", kana="にほん", jlpt=5,
        definitions=["Japan"], parts_of_speech=["n"],
    )
    with render.console.capture() as cap:
        render.words_table([(word, False)], [], {"日本": 2})  # band 2 -> top 1k
    assert "top 1k" in cap.get()


def _sample():
    kanji = KanjiProgress(
        grades=[
            GradeBar(1, 80, 80),
            GradeBar(2, 100, 160),
            GradeBar(3, 0, 200),
            GradeBar(4, 0, 220),
            GradeBar(5, 0, 185),
            GradeBar(6, 0, 181),
            GradeBar("secondary", 0, 1110),
        ],
        known_total=180,
        total=2136,
        missing_from_deck=500,
    )
    # 48 bands with coverage tapering off toward rarer words.
    bands = [BandCell(band=i + 1, known=max(0, 50 - i), size=500) for i in range(48)]
    placed = sum(b.known for b in bands)
    vocab = VocabProgress(
        bands=bands,
        placed=placed,
        total_ranked=24000,
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
    # Per-grade label present.
    assert "secondary" in out.lower()
    # Vocab bins: a variable-width bin label, denominator, and honesty footer.
    assert "2.5-3.5k" in out
    assert "24000" in out or "24,000" in out
    assert "30" in out  # unranked
