"""Build a {surface form -> nf frequency band} index from JMdict.

jamdict ships JMdict in a bundled SQLite database. Rather than calling
``jam.lookup()`` once per word (which materialises full entries and is slow),
we read every kanji/kana form's ``nfXX`` priority code in a single query and
collapse it to the smallest (most frequent) band per surface form.
"""

import os
import re
import sqlite3

import jamdict_data

_NF_RE = re.compile(r"^nf(\d+)$")

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
