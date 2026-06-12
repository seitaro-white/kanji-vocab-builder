"""Regenerate kanji_vocab_miner/jouyou_data.py from KanjiDic2.

KanjiDic2 (bundled with jamdict) records a `grade` for each kanji:
  1-6 = kyouiku kanji by elementary school grade (1026 total)
  8   = remaining jouyou kanji, taught in junior high ("secondary")
  9-10 = jinmeiyou (name kanji) -- NOT jouyou, excluded here

Grades {1..6, 8} sum to exactly the 2136 jouyou kanji.

Run with: uv run python scripts/gen_jouyou.py
"""

import os
import sqlite3

import jamdict_data

# KanjiDic2 grade -> our BY_GRADE key (ints for school grades, "secondary" for 8).
GRADE_MAP: dict[int, int | str] = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 8: "secondary"}

OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "kanji_vocab_miner",
    "jouyou_data.py",
)


def main() -> None:
    db = os.path.join(os.path.dirname(jamdict_data.__file__), "jamdict.db")
    con = sqlite3.connect(db)
    cur = con.cursor()

    by_grade: dict[int | str, str] = {}
    for kd_grade, key in GRADE_MAP.items():
        # Order by frequency (most common first), unranked last, then by literal.
        cur.execute(
            "SELECT literal FROM character WHERE grade=? "
            "ORDER BY freq IS NULL, freq, literal",
            (kd_grade,),
        )
        by_grade[key] = "".join(r[0] for r in cur.fetchall())
    con.close()

    header = '''"""Embedded Jouyou kanji list, generated from KanjiDic2 (bundled with jamdict).

Grades 1-6 are the kyouiku kanji (1026 total) taught in elementary school by
grade; "secondary" is KanjiDic2 grade 8 -- the remaining jouyou kanji taught in
junior high. Total == 2136. Within each grade, kanji are ordered by KanjiDic2
newspaper frequency (most common first).

Regenerate with: uv run python scripts/gen_jouyou.py
"""

'''
    lines = [header, "BY_GRADE: dict[int | str, str] = {"]
    for key in (1, 2, 3, 4, 5, 6, "secondary"):
        lines.append(f"    {key!r}: {by_grade[key]!r},")
    lines.append("}")
    lines.append("")
    lines.append("# Flat set of all 2136 jouyou kanji.")
    lines.append(
        "JOUYOU: frozenset[str] = frozenset().union("
        "*(set(v) for v in BY_GRADE.values()))"
    )
    lines.append("")

    with open(OUT_PATH, "w") as f:
        f.write("\n".join(lines))

    total = sum(len(v) for v in by_grade.values())
    print(f"Wrote {OUT_PATH} ({total} kanji)")


if __name__ == "__main__":
    main()
