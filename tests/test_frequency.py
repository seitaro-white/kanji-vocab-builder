"""Frequency labels, dictionary reduction, and band lookup specifications."""

import sqlite3

import pytest

from kanji_vocab_miner import frequency
from kanji_vocab_miner.frequency import BandWord


@pytest.fixture
def dictionary_db(tmp_path, monkeypatch) -> None:
    """Use a tiny dictionary containing duplicate priorities and alternate forms."""
    path = tmp_path / "dictionary.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE Kanji (ID INTEGER, idseq INTEGER, text TEXT);
            CREATE TABLE KJP (kid INTEGER, text TEXT);
            CREATE TABLE Kana (ID INTEGER, idseq INTEGER, text TEXT);
            CREATE TABLE KNP (kid INTEGER, text TEXT);
            CREATE TABLE Sense (ID INTEGER, idseq INTEGER);
            CREATE TABLE SenseGloss (sid INTEGER, text TEXT, lang TEXT);

            INSERT INTO Kanji VALUES (1, 1, '国'), (2, 2, '学校'), (3, 2, '學校');
            INSERT INTO KJP VALUES
                (1, 'nf20'), (1, 'nf03'), (1, 'nf10'), (3, 'nf01');
            INSERT INTO Kana VALUES
                (10, 1, 'くに'), (20, 2, 'がっこう'), (30, 3, 'すごい');
            INSERT INTO KNP VALUES (30, 'nf01');
            INSERT INTO Sense VALUES (100, 1), (200, 2), (300, 3);
            INSERT INTO SenseGloss VALUES
                (100, 'country', 'eng'), (200, 'school', 'eng'),
                (300, 'amazing', 'eng');
        """)
    monkeypatch.setattr(frequency, "database_path", lambda: path)


def test_bundled_dictionary_contains_ranked_forms():
    index = frequency.build_frequency_index()

    assert len(index) > 10000
    assert index["日本"] == 25
    assert all(isinstance(band, int) and 1 <= band <= 48 for band in index.values())


def test_repeated_surface_keeps_smallest_frequency_band(dictionary_db):
    index = frequency.build_frequency_index()

    assert index["国"] == 3


@pytest.mark.parametrize(
    ("band", "label"),
    [(None, ""), (1, "top 500"), (2, "top 1k"),
     (5, "top 2.5k"), (48, "top 24k")],
)
def test_band_label_describes_rank_range(band, label):
    assert frequency.band_label(band) == label


def test_band_lookup_includes_alternate_forms_and_kana_only_entries(dictionary_db):
    words = frequency.words_in_band(1)

    assert sorted(words, key=lambda word: word.expression) == [
        BandWord(expression="すごい", kana="すごい", definition="amazing"),
        BandWord(expression="学校", kana="がっこう", definition="school"),
    ]


@pytest.mark.parametrize("band", [0, 99])
def test_words_in_band_empty_for_out_of_range(band):
    assert frequency.words_in_band(band) == []
