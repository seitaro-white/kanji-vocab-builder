"""Tests for the manual Reading and Grammar progress file."""

from kanji_vocab_miner import manual_progress
from kanji_vocab_miner.progress import ManualProgressCounts


def test_manual_progress_path_uses_current_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    assert manual_progress.manual_progress_path() == tmp_path / "manual_progress.toml"


def test_load_manual_progress(tmp_path):
    path = tmp_path / "manual_progress.toml"
    path.write_text(
        """\
reading_i = 1
reading_ii = 2
reading_iii = 3
grammar_i = 4
grammar_ii = 5
grammar_iii = 0
""",
        encoding="utf-8",
    )

    assert manual_progress.load_manual_progress(path) == ManualProgressCounts(
        reading_i=1,
        reading_ii=2,
        reading_iii=3,
        grammar_i=4,
        grammar_ii=5,
        grammar_iii=0,
    )
