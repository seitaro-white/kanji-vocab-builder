"""Build a {surface form -> nf frequency band} index from JMdict.

jamdict ships JMdict in a bundled SQLite database. Rather than calling
``jam.lookup()`` once per word (which materialises full entries and is slow),
we read every kanji/kana form's ``nfXX`` priority code in a single query and
collapse it to the smallest (most frequent) band per surface form.
"""

import functools
import os
import re
import sqlite3
from dataclasses import dataclass

import jamdict_data

_NF_RE = re.compile(r"^nf(\d+)$")

NUM_BANDS = 48
BAND_SIZE = 500


def band_label(band: int | None) -> str:
    """Human-readable rank label for an nf band, e.g. 5 -> 'top 2.5k'.

    Returns an empty string for None (a word with no frequency band).
    """
    if not band:
        return ""
    upper = band * BAND_SIZE
    if upper < 1000:
        return f"top {upper}"
    return f"top {upper / 1000:g}k"


@dataclass
class BandWord:
    expression: str  # primary kanji surface form (or kana if no kanji form)
    kana: str  # reading
    definition: str  # first English gloss

# Pull all kanji- and kana-form priority codes that are nf bands in one shot.
_QUERY = """
    SELECT k.text, p.text FROM Kanji k JOIN KJP p ON k.ID = p.kid
        WHERE p.text LIKE 'nf%'
    UNION ALL
    SELECT n.text, p.text FROM Kana n JOIN KNP p ON n.ID = p.kid
        WHERE p.text LIKE 'nf%'
"""


def _db_path() -> str:
    return os.path.join(os.path.dirname(jamdict_data.__file__), "jamdict.db")


@functools.lru_cache(maxsize=1)
def get_frequency_index() -> dict[str, int]:
    """Cached frequency index, built once per process (read-only)."""
    return build_frequency_index()


def build_frequency_index() -> dict[str, int]:
    """Return a mapping of surface form -> smallest nf band (1-48)."""
    con = sqlite3.connect(_db_path())
    try:
        rows = con.execute(_QUERY).fetchall()
    finally:
        con.close()

    index: dict[str, int] = {}
    for surface, code in rows:
        m = _NF_RE.match(code)
        if not m:
            continue
        band = int(m.group(1))
        current = index.get(surface)
        if current is None or band < current:
            index[surface] = band
    return index


def words_in_band(band: int) -> list[BandWord]:
    """Return the dictionary entries whose nf priority falls in `band` (1-48).

    Each entry is represented by its first kanji form (or kana if it has none),
    its first reading, and its first English gloss.
    """
    if not (1 <= band <= NUM_BANDS):
        return []

    code = f"nf{band:02d}"
    con = sqlite3.connect(_db_path())
    try:
        cur = con.cursor()
        cur.execute(
            """
            SELECT DISTINCT idseq FROM Kanji k JOIN KJP p ON k.ID = p.kid
                WHERE p.text = ?
            UNION
            SELECT DISTINCT idseq FROM Kana n JOIN KNP p ON n.ID = p.kid
                WHERE p.text = ?
            """,
            (code, code),
        )
        ids = [r[0] for r in cur.fetchall()]
        if not ids:
            return []

        placeholders = ",".join("?" * len(ids))
        # MIN(ID) makes SQLite return the bare column from the lowest-ID (first) row.
        kanji = dict(
            cur.execute(
                f"SELECT idseq, text FROM Kanji WHERE idseq IN ({placeholders}) "
                f"GROUP BY idseq HAVING ID = MIN(ID)",
                ids,
            ).fetchall()
        )
        kana = dict(
            cur.execute(
                f"SELECT idseq, text FROM Kana WHERE idseq IN ({placeholders}) "
                f"GROUP BY idseq HAVING ID = MIN(ID)",
                ids,
            ).fetchall()
        )
        gloss = dict(
            cur.execute(
                f"SELECT s.idseq, g.text FROM Sense s JOIN SenseGloss g ON g.sid = s.ID "
                f"WHERE s.idseq IN ({placeholders}) AND g.lang = 'eng' "
                f"GROUP BY s.idseq HAVING s.ID = MIN(s.ID)",
                ids,
            ).fetchall()
        )
    finally:
        con.close()

    words = []
    for idseq in ids:
        reading = kana.get(idseq, "")
        expression = kanji.get(idseq) or reading  # kana-only entries have no kanji
        definition = gloss.get(idseq, "")
        if expression:
            words.append(
                BandWord(expression=expression, kana=reading, definition=definition)
            )
    return words
