"""Tests for the known-words store."""

from kanji_vocab_miner import known_words


def test_load_missing_file_returns_empty(tmp_path):
    assert known_words.load_known_words(tmp_path / "nope.txt") == set()


def test_add_then_load_roundtrips(tmp_path):
    path = tmp_path / "known.txt"
    assert known_words.add_known_word("日本", path) is True
    assert known_words.add_known_word("学校", path) is True
    assert known_words.load_known_words(path) == {"日本", "学校"}


def test_add_duplicate_is_noop(tmp_path):
    path = tmp_path / "known.txt"
    known_words.add_known_word("日本", path)

    added = known_words.add_known_word("日本", path)

    assert added is False
    assert path.read_text(encoding="utf-8").splitlines() == ["日本"]
