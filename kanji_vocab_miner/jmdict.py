"""Find alternate spellings in the bundled JMdict without loading full entries."""

import sqlite3
from pathlib import Path

import jamdict_data


def database_path() -> Path:
    """Return the bundled JMdict database path."""
    return Path(jamdict_data.__file__).parent / "jamdict.db"


def sibling_spellings(expression: str, reading: str) -> list[str]:
    """Return sibling kanji forms of entries containing this spelling and reading."""
    connection = sqlite3.connect(database_path().as_uri() + "?mode=ro", uri=True)
    try:
        rows = connection.execute(
            """
            SELECT DISTINCT sibling.text
            FROM Kanji original
            JOIN Kana reading ON reading.idseq = original.idseq
            JOIN Kanji sibling ON sibling.idseq = original.idseq
            WHERE original.text = ? AND reading.text = ?
                AND sibling.text != original.text
            ORDER BY sibling.ID
            """,
            (expression, reading),
        ).fetchall()
    finally:
        connection.close()
    return [row[0] for row in rows]
