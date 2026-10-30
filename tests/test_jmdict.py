"""Check sibling discovery against a small, isolated JMdict schema."""

import sqlite3
from pathlib import Path

import pytest

from kanji_vocab_miner import jmdict


@pytest.fixture
def dictionary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    database = tmp_path / "jamdict.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE Kanji (ID INTEGER, idseq INTEGER, text TEXT);
        CREATE TABLE Kana (ID INTEGER, idseq INTEGER, text TEXT);
        INSERT INTO Kanji VALUES (1, 100, '択ぶ'), (2, 100, '選ぶ'),
            (3, 100, '撰ぶ'), (4, 200, '択ぶ'), (5, 200, '別語'),
            (6, 300, '択ぶ'), (7, 300, '選ぶ');
        INSERT INTO Kana VALUES (1, 100, 'えらぶ'), (2, 200, 'べつご'),
            (3, 300, 'えらぶ');
        """
    )
    connection.close()
    monkeypatch.setattr(jmdict, "database_path", lambda: database)
    return database


def test_siblings_require_exact_expression_and_reading_and_exclude_duplicates(
    dictionary: Path,
) -> None:
    assert jmdict.sibling_spellings("択ぶ", "えらぶ") == ["選ぶ", "撰ぶ"]
    assert jmdict.sibling_spellings("択ぶ", "エラブ") == []
    assert jmdict.sibling_spellings("択", "えらぶ") == []
    assert jmdict.sibling_spellings("択ぶ", "") == []
